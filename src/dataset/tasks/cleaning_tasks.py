"""
cleaning_tasks.py
~~~~~~~~~~~~~~~~~
Extended Celery task.  Differences from the original:

  1. Deserialises column_rules from JSONB and passes them to the engine.
  2. Writes `cleaning_report` (per-column stats) back to the DB.
  3. Skips execution if the CleanedDataset has already been rolled back.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.config.celery import celery
from src.config.db import SessionLocal
from src.dataset.models.cleaned_dataset import CleanedDataset
from src.dataset.models.cleaning_config import CleaningConfig
from src.dataset.schemas.cleaning_config import CleaningConfigIn, ColumnRuleIn
from src.dataset.services.cleaning_engine import apply_cleaning
from src.dataset.services.r2_service import r2_download, r2_upload
from src.dataset.models.dataset import Dataset



@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def run_cleaning(self, cleaned_dataset_id: str) -> None:
    db = SessionLocal()
    try:
        record: CleanedDataset = db.get(CleanedDataset, cleaned_dataset_id)
        if not record:
            raise ValueError(f"CleanedDataset {cleaned_dataset_id} not found.")

        # Guard: user may have rolled back before the worker picked up the job
        if record.rolled_back:
            return

        config_row: CleaningConfig = db.get(CleaningConfig, record.cleaning_config_id)
        if not config_row:
            raise ValueError(f"CleaningConfig {record.cleaning_config_id} not found.")

        # ── mark in-progress ─────────────────────────────────────────────────
        record.status = "cleaning"
        db.commit()

        # ── deserialise column_rules from JSONB → Pydantic models ────────────
        raw_rules = config_row.column_rules or []
        column_rules = [ColumnRuleIn(**r) for r in raw_rules]

        config_in = CleaningConfigIn(
            missing_strategy=config_row.missing_strategy,
            remove_duplicates=config_row.remove_duplicates,
            encoding_method=config_row.encoding_method,
            scaling_method=config_row.scaling_method,
            version=config_row.version,
            column_rules=column_rules,
        )

        # ── download raw CSV from R2 ──────────────────────────────────────────
        dataset = db.query(Dataset).filter(Dataset.env_id == record.environment_id).first()
        if not dataset:
        
           raise ValueError(f"No dataset found for environment {record.environment_id}")
           
        print(f"[DEBUG] Attempting r2_download with r2_path='{dataset.r2_path}'")

        df = r2_download(dataset.r2_path)
        # ── apply cleaning ────────────────────────────────────────────────────
        df_clean, report = apply_cleaning(df, config_in)

        # ── upload cleaned CSV to R2 ──────────────────────────────────────────
        file_path = r2_upload(df_clean, str(record.environment_id), str(record.id))

        # ── persist results ───────────────────────────────────────────────────
        record.status          = "ready"
        record.file_path       = file_path
        record.rows_before     = report["rows_before"]
        record.rows_after      = report["rows_after"]
        record.cleaning_report = report
        record.cleaned_at      = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        db.rollback()
        # Mark as failed on the final retry so the user can see it
        if self.request.retries >= self.max_retries:
            try:
                record.status = "failed"
                db.commit()
            except Exception:
                db.rollback()
        raise self.retry(exc=exc)

    finally:
        db.close()