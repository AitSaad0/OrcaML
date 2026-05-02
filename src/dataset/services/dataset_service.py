from uuid import UUID
import io
import pandas as pd
from fastapi import HTTPException, UploadFile
from starlette import status
from sqlalchemy.orm import Session
from src.dataset.models.dataset import Dataset
from src.dataset.services import r2_service


def upload_dataset(file: UploadFile, env_id: UUID, db: Session) -> Dataset:
    # ── Step 1: Check file extension ────────────────────────────
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    # ── Step 2: Read first bytes ─────────────────────────────────
    header = file.file.read(5)
    file.file.seek(0)

    # ── Step 3: Check if it's a PDF ──────────────────────────────
    if header.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is a PDF not a CSV")

    # ── Step 4: Check if content is valid CSV ────────────────────
    try:
        sample = file.file.read(1024)
        file.file.seek(0)

        # check valid UTF-8 text
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Not valid text")

        # check for null bytes — binary files contain them, CSVs never do
        if b"\x00" in sample:
            raise ValueError("File contains null bytes — not a valid CSV")

        # check pandas can read it with at least 1 column
        result = pd.read_csv(io.BytesIO(sample))
        if len(result.columns) == 0:
            raise ValueError("No columns found")

    except HTTPException:
        raise   # re-raise HTTP exceptions — don't swallow them
    except Exception:
        raise HTTPException(status_code=400, detail="File is not a valid CSV")

    # ── Step 5: Save to DB and upload to R2 ──────────────────────
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    return dataset


def list_datasets(env_id: UUID, db: Session) -> list[Dataset]:
    return db.query(Dataset).filter(Dataset.env_id == env_id).all()


def delete_dataset(dataset_id: UUID, db: Session) -> None:
    dataset = get_dataset(dataset_id, db)
    r2_service.delete_from_r2(dataset.r2_path)
    db.delete(dataset)
    db.commit()