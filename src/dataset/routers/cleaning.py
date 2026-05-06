from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from uuid import UUID

from src.config.db import get_db
from src.auth.dependencies.auth import get_current_user
from src.auth.models.user import User
from src.dataset.services import cleaning_config_service as service
from src.dataset.schemas.cleaning_config import CleaningConfigCreate, CleaningConfigResponse
from src.dataset.schemas.cleaned_dataset import CleanedDatasetResponse

router = APIRouter(prefix="/environments/{env_id}/cleaning", tags=["cleaning"])


@router.post("/config", response_model=CleaningConfigResponse, status_code=status.HTTP_201_CREATED)
def create_cleaning_config(
    env_id: UUID,
    body:   CleaningConfigCreate,
    db:     Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save or update cleaning configuration for an environment."""
    return service.create_cleaning_config(env_id=env_id, body=body, db=db)


@router.post("/trigger", response_model=CleanedDatasetResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_cleaning(
    env_id: UUID,
    db:     Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger the cleaning process — runs in background via Celery."""
    return service.trigger_cleaning(env_id=env_id, db=db)


@router.get("/status/{cleaned_id}", response_model=CleanedDatasetResponse)
def get_cleaning_status(
    env_id:     UUID,
    cleaned_id: UUID,
    db:         Session = Depends(get_db),
    current_user: User  = Depends(get_current_user),
):
    """Check the status of a cleaning job."""
    return service.get_cleaned_dataset(cleaned_id=cleaned_id, db=db)