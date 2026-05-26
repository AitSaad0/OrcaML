"""
cleaning_config_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
All DB-layer operations for the enhanced cleaning pipeline.

Covers:
  - save / update cleaning config (with column_rules)
  - pre-trigger config review
  - trigger (create CleanedDataset + enqueue Celery task)
  - status poll
  - cleaning report
  - cleaned dataset preview (from R2)
  - rollback
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.dataset.models.cleaned_dataset import CleanedDataset
from src.dataset.models.cleaning_config import CleaningConfig
from src.dataset.schemas.cleaning_config import (
    CleanedDatasetStatusOut,
    CleanedPreviewOut,
    CleaningConfigIn,
    CleaningConfigOut,
    CleaningReportOut,
    ColumnReportStats,
    ColumnReviewRow,
    ConfigReviewOut,
    RollbackOut,
    TriggerOut,
)
from src.dataset.services.r2_service import r2_download

# ── Phase 2: save config ───────────────────────────────────────────────────────

def save_cleaning_config(
    db: Session,
    environment_id: uuid.UUID,
    payload: CleaningConfigIn,
) -> CleaningConfigOut:
    """
    Upsert a CleaningConfig for the environment.
    If one already exists it is overwritten (one active config per env).
    """
    existing = (
        db.query(CleaningConfig)
        .filter(CleaningConfig.environment_id == environment_id)
        .first()
    )

    column_rules_json = [r.model_dump() for r in payload.column_rules]

    if existing:
        existing.missing_strategy  = payload.missing_strategy.value
        existing.remove_duplicates = payload.remove_duplicates
        existing.encoding_method   = payload.encoding_method.value
        existing.scaling_method    = payload.scaling_method.value
        existing.version           = payload.version
        existing.column_rules      = column_rules_json
        db.commit()
        db.refresh(existing)
        return CleaningConfigOut.model_validate(existing)

    config = CleaningConfig(
        environment_id    = environment_id,
        missing_strategy  = payload.missing_strategy.value,
        remove_duplicates = payload.remove_duplicates,
        encoding_method   = payload.encoding_method.value,
        scaling_method    = payload.scaling_method.value,
        version           = payload.version,
        column_rules      = column_rules_json,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return CleaningConfigOut.model_validate(config)


# ── Phase 3: pre-trigger config review ────────────────────────────────────────

def _rule_details(rule: Dict[str, Any], global_cfg: CleaningConfig) -> str:
    action = rule.get("action", "clean")
    if action == "drop":
        return "column will be removed from output"
    if action == "target":
        return "ML target — no transforms applied"
    if action == "keep":
        return "kept as-is — no transforms applied"

    parts: List[str] = []

    ms = rule.get("missing_strategy") or global_cfg.missing_strategy
    parts.append(f"impute({ms})")

    om = rule.get("outlier_method") or "none"
    if om != "none":
        parts.append(f"outlier({om})")

    enc = rule.get("encoding_method") or global_cfg.encoding_method
    if enc != "none":
        parts.append(f"encode({enc})")

    sm = rule.get("scaling_method") or global_cfg.scaling_method
    if sm != "none":
        parts.append(f"scale({sm})")

    return " → ".join(parts) if parts else "clean (defaults)"


def review_config(
    db: Session,
    environment_id: uuid.UUID,
) -> ConfigReviewOut:
    config = (
        db.query(CleaningConfig)
        .filter(CleaningConfig.environment_id == environment_id)
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cleaning config found for this environment. "
                   "POST /cleaning/config first.",
        )

    column_rules: List[Dict[str, Any]] = config.column_rules or []
    #rules_by_col = {r["column"]: r for r in column_rules}

    summary: List[ColumnReviewRow] = []
    for rule in column_rules:
        summary.append(
            ColumnReviewRow(
                column=rule["column"],
                action=rule.get("action", "clean"),
                details=_rule_details(rule, config),
            )
        )

    target_col = next(
        (r["column"] for r in column_rules if r.get("action") == "target"), None
    )

    return ConfigReviewOut(
        environment_id=environment_id,
        config_id=config.id,
        remove_duplicates=config.remove_duplicates,
        column_summary=summary,
        columns_to_clean=sum(
            1 for r in column_rules if r.get("action", "clean") == "clean"
        ),
        columns_to_drop=sum(
            1 for r in column_rules if r.get("action") == "drop"
        ),
        columns_to_keep=sum(
            1 for r in column_rules if r.get("action") == "keep"
        ),
        target_column=target_col,
    )


# ── Phase 4: trigger ───────────────────────────────────────────────────────────

def trigger_cleaning(
    db: Session,
    environment_id: uuid.UUID,
) -> TriggerOut:
    config = (
        db.query(CleaningConfig)
        .filter(CleaningConfig.environment_id == environment_id)
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cleaning config found. POST /cleaning/config first.",
        )

    record = CleanedDataset(
        environment_id     = environment_id,
        cleaning_config_id = config.id,
        status             = "pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Import here to avoid circular imports at module load time
    from src.dataset.tasks.cleaning_tasks import run_cleaning
    run_cleaning.delay(str(record.id))

    return TriggerOut(id=record.id, status=record.status)


# ── Phase 4: status poll ───────────────────────────────────────────────────────

def get_cleaning_status(
    db: Session,
    cleaned_dataset_id: uuid.UUID,
) -> CleanedDatasetStatusOut:
    record = db.get(CleanedDataset, cleaned_dataset_id)
    if not record:
        raise HTTPException(status_code=404, detail="Cleaned dataset not found.")
    return CleanedDatasetStatusOut.model_validate(record)


# ── Phase 5: cleaning report ───────────────────────────────────────────────────

def get_cleaning_report(
    db: Session,
    cleaned_dataset_id: uuid.UUID,
) -> CleaningReportOut:
    record = db.get(CleanedDataset, cleaned_dataset_id)
    if not record:
        raise HTTPException(status_code=404, detail="Cleaned dataset not found.")
    if record.status not in ("ready", "rolled_back"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cleaning not finished yet. Current status: {record.status}",
        )

    raw_report = record.cleaning_report or {}
    columns_stats: Optional[Dict[str, ColumnReportStats]] = None

    if "columns" in raw_report:
        columns_stats = {
            col: ColumnReportStats(**stats)
            for col, stats in raw_report["columns"].items()
        }

    return CleaningReportOut(
        cleaned_dataset_id=record.id,
        environment_id=record.environment_id,
        status=record.status,
        rows_before=record.rows_before,
        rows_after=record.rows_after,
        duplicates_removed=raw_report.get("duplicates_removed"),
        columns=columns_stats,
        cleaned_at=record.cleaned_at,
        rolled_back=record.rolled_back,
    )


# ── Phase 5: cleaned dataset preview ──────────────────────────────────────────

def get_cleaned_preview(
    db: Session,
    cleaned_dataset_id: uuid.UUID,
    rows: int = 50,
) -> CleanedPreviewOut:
    record = db.get(CleanedDataset, cleaned_dataset_id)
    if not record:
        raise HTTPException(status_code=404, detail="Cleaned dataset not found.")
    if record.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset not ready. Status: {record.status}",
        )
    if record.rolled_back:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This cleaning run has been rolled back.",
        )

    df = r2_download(record.file_path)
    preview = df.head(rows)

    return CleanedPreviewOut(
        cleaned_dataset_id=record.id,
        columns=list(preview.columns),
        rows=preview.where(pd.notnull(preview), None).to_dict(orient="records"),
        total_rows=len(df),
    )


# ── Phase 5 (reject): rollback ─────────────────────────────────────────────────

def rollback_cleaning(
    db: Session,
    cleaned_dataset_id: uuid.UUID,
) -> RollbackOut:
    """
    Mark the cleaned dataset as rolled back.

    This does NOT delete the file from R2 immediately (keeps audit trail).
    The user can re-configure and re-trigger from scratch after rollback.
    The raw dataset in R2 is untouched — it is never overwritten.
    """
    record = db.get(CleanedDataset, cleaned_dataset_id)
    if not record:
        raise HTTPException(status_code=404, detail="Cleaned dataset not found.")

    if record.rolled_back:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already rolled back.",
        )
    if record.status not in ("ready", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot roll back a job with status '{record.status}'. "
                   "Wait for it to finish first.",
        )

    record.rolled_back    = True
    record.rolled_back_at = datetime.now(timezone.utc)
    record.status         = "rolled_back"
    db.commit()
    db.refresh(record)

    return RollbackOut(
        cleaned_dataset_id=record.id,
        rolled_back=record.rolled_back,
        rolled_back_at=record.rolled_back_at,
        message=(
            "Cleaning run discarded. Your raw dataset is untouched. "
            "Update the config and POST /cleaning/trigger to start fresh."
        ),
    )