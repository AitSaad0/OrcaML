from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException
from starlette import status

from src.dataset.models.cleaning_config import CleaningConfig
from src.dataset.models.cleaned_dataset import CleanedDataset
from src.dataset.schemas.cleaning_config import CleaningConfigCreate
from src.dataset.tasks.cleaning_tasks import run_cleaning


def create_cleaning_config(env_id: UUID, body: CleaningConfigCreate, db: Session) -> CleaningConfig:
    # one config per environment — update if exists
    existing = db.query(CleaningConfig).filter(
        CleaningConfig.environment_id == env_id
    ).first()

    if existing:
        for key, value in body.model_dump().items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing

    config = CleaningConfig(environment_id=env_id, **body.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def trigger_cleaning(env_id: UUID, db: Session) -> CleanedDataset:
    # check config exists
    config = db.query(CleaningConfig).filter(
        CleaningConfig.environment_id == env_id
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cleaning config found. Create one first."
        )

    # create CleanedDataset record with status=pending
    cleaned = CleanedDataset(
        environment_id     = env_id,
        cleaning_config_id = config.id,
        status             = "pending",
    )
    db.add(cleaned)
    db.commit()
    db.refresh(cleaned)

    # send to Celery queue
    run_cleaning.delay(str(cleaned.id))

    return cleaned


def get_cleaned_dataset(cleaned_id: UUID, db: Session) -> CleanedDataset:
    cleaned = db.query(CleanedDataset).filter(
        CleanedDataset.id == cleaned_id
    ).first()
    if not cleaned:
        raise HTTPException(status_code=404, detail="Cleaned dataset not found")
    return cleaned