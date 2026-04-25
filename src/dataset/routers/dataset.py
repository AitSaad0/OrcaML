from fastapi import APIRouter, Depends, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from uuid import UUID
from src.config.db import get_db
from src.auth.dependencies.auth import get_current_user
from src.auth.models.user import User
from src.dataset import dataset_service as service
from src.dataset.schemas.dataset import (
    UploadDatasetResponse,
    GetDatasetResponse,
    ListDatasetsResponse,
    DeleteDatasetResponse,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])

@router.post("/upload", response_model=UploadDatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file:   UploadFile = File(...),
    env_id: UUID       = Form(...),
    db:     Session    = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.upload_dataset(file=file, env_id=env_id, db=db)

@router.get("/", response_model=ListDatasetsResponse)
def list_datasets(
    env_id: UUID,
    db:     Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasets = service.list_datasets(env_id=env_id, db=db)
    return ListDatasetsResponse(datasets=datasets)

@router.get("/{dataset_id}", response_model=GetDatasetResponse)
def get_dataset(
    dataset_id: UUID,
    db:         Session = Depends(get_db),
    current_user: User  = Depends(get_current_user),
):
    return service.get_dataset(dataset_id=dataset_id, db=db)

@router.delete("/{dataset_id}", response_model=DeleteDatasetResponse)
def delete_dataset(
    dataset_id: UUID,
    db:         Session = Depends(get_db),
    current_user: User  = Depends(get_current_user),
):
    service.delete_dataset(dataset_id=dataset_id, db=db)
    return DeleteDatasetResponse()