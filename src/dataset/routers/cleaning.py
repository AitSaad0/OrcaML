"""
cleaning.py  (router)
~~~~~~~~~~~~~~~~~~~~~
All cleaning-related HTTP endpoints.

New endpoints added:
  GET  /environments/{env_id}/datasets/schema       → Phase 2 column schema
  POST /environments/{env_id}/cleaning/config       → Phase 2 save config
  GET  /environments/{env_id}/cleaning/review       → Phase 3 review
  POST /environments/{env_id}/cleaning/trigger      → Phase 4 trigger job
  GET  /environments/{env_id}/cleaning/{id}/status  → Phase 4 poll status
  GET  /environments/{env_id}/cleaning/{id}/report  → Phase 5 report
  GET  /environments/{env_id}/cleaning/{id}/preview → Phase 5 preview
  POST /environments/{env_id}/cleaning/{id}/rollback→ Phase 5 rollback
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.auth.dependencies.auth import get_current_user
from src.config.db import get_db
from src.dataset.schemas.cleaning_config import (
    CleanedDatasetStatusOut,
    CleanedPreviewOut,
    CleaningConfigIn,
    CleaningConfigOut,
    CleaningReportOut,
    ConfigReviewOut,
    DatasetSchemaOut,
    RollbackOut,
    TriggerOut,
)
from src.dataset.services.cleaning_config_service import (
    get_cleaned_preview,
    get_cleaning_report,
    get_cleaning_status,
    review_config,
    rollback_cleaning,
    save_cleaning_config,
    trigger_cleaning,
)
from src.dataset.services.schema_service import get_dataset_schema

router = APIRouter(
    prefix="/environments/{env_id}",
    tags=["cleaning"],
)


# ── Phase 2a: dataset schema (for building per-column config UI) ───────────────
@router.get(
    "/datasets/schema",
    response_model=DatasetSchemaOut,
    summary="Infer column types and null stats from the raw dataset",
)
def dataset_schema(
    env_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> DatasetSchemaOut:
    return get_dataset_schema(env_id, db)


# ── Phase 2b: save cleaning config ────────────────────────────────────────────
@router.post(
    "/cleaning/config",
    response_model=CleaningConfigOut,
    status_code=201,
    summary="Save (or replace) the cleaning config with per-column rules",
)
def create_cleaning_config(
    env_id: uuid.UUID,
    payload: CleaningConfigIn,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> CleaningConfigOut:
    return save_cleaning_config(db, env_id, payload)


# ── Phase 3: config review ────────────────────────────────────────────────────
@router.get(
    "/cleaning/review",
    response_model=ConfigReviewOut,
    summary="Preview what the current config will do, before triggering",
)
def config_review(
    env_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> ConfigReviewOut:
    return review_config(db, env_id)


# ── Phase 4a: trigger ─────────────────────────────────────────────────────────
@router.post(
    "/cleaning/trigger",
    response_model=TriggerOut,
    status_code=202,
    summary="Enqueue the async cleaning job",
)
def trigger(
    env_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> TriggerOut:
    return trigger_cleaning(db, env_id)


# ── Phase 4b: status poll ─────────────────────────────────────────────────────
@router.get(
    "/cleaning/{cleaned_id}/status",
    response_model=CleanedDatasetStatusOut,
    summary="Poll the status of a cleaning job",
)
def cleaning_status(
    env_id: uuid.UUID,
    cleaned_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> CleanedDatasetStatusOut:
    return get_cleaning_status(db, cleaned_id)


# ── Phase 5a: cleaning report ─────────────────────────────────────────────────
@router.get(
    "/cleaning/{cleaned_id}/report",
    response_model=CleaningReportOut,
    summary="Get the per-column cleaning report after the job finishes",
)
def cleaning_report(
    env_id: uuid.UUID,
    cleaned_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> CleaningReportOut:
    return get_cleaning_report(db, cleaned_id)


# ── Phase 5b: cleaned dataset preview ────────────────────────────────────────
@router.get(
    "/cleaning/{cleaned_id}/preview",
    response_model=CleanedPreviewOut,
    summary="Preview the first N rows of the cleaned dataset",
)
def cleaned_preview(
    env_id: uuid.UUID,
    cleaned_id: uuid.UUID,
    rows: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> CleanedPreviewOut:
    return get_cleaned_preview(db, cleaned_id, rows)


# ── Phase 5c: rollback ────────────────────────────────────────────────────────
@router.post(
    "/cleaning/{cleaned_id}/rollback",
    response_model=RollbackOut,
    summary="Reject the cleaning result and mark for re-run",
)
def rollback(
    env_id: uuid.UUID,
    cleaned_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> RollbackOut:
    return rollback_cleaning(db, cleaned_id)