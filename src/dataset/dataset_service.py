from uuid import UUID
from fastapi import HTTPException, UploadFile
from starlette import status
from sqlalchemy.orm import Session
from src.dataset.models.dataset import Dataset
from src.dataset import r2_service

def upload_dataset(file: UploadFile, env_id: UUID, db: Session) -> Dataset:
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed"
        )
    new_dataset = Dataset(name=file.filename, size=0, r2_path="", env_id=env_id)
    db.add(new_dataset)
    db.flush()
    r2_path = r2_service.upload_to_r2(
        file=file.file,
        filename=file.filename,
        dataset_id=str(new_dataset.id)
    )
    new_dataset.r2_path = r2_path
    new_dataset.size    = file.size or 0
    db.commit()
    db.refresh(new_dataset)
    return new_dataset

def get_dataset(dataset_id: UUID, db: Session) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset

def list_datasets(env_id: UUID, db: Session) -> list[Dataset]:
    return db.query(Dataset).filter(Dataset.env_id == env_id).all()

def delete_dataset(dataset_id: UUID, db: Session) -> None:
    dataset = get_dataset(dataset_id, db)
    r2_service.delete_from_r2(dataset.r2_path)
    db.delete(dataset)
    db.commit()