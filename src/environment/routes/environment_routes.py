import uuid
from io import BytesIO

import pandas as pd
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
import logging
from src.project.models.project import Project
from src.auth.dependencies.auth import get_project_or_403
from src.environment.service.environment_service import (
    create_environment as create_environment_service,
    get_environment as get_environment_service,
    get_environment_by_name as get_environment_by_name_service,
    list_environments as list_environments_service,
    update_environment as update_environment_service,
    delete_environment as delete_environment_service,
    delete_all_environments as delete_all_environments_service,
)
from src.config.db import get_db
from src.environment.schemas.environment_schemas import (
    EnvironmentCreateRequest,
    EnvironmentCreateResponse,
    EnvironmentUpdateRequest,
    EnvironmentUpdateResponse,
    EnvironmentListResponse,
)
from src.dataset.models.cleaned_dataset import CleanedDataset
from src.dataset.models.dataset import Dataset
from src.dataset.services.r2_service import get_s3_client
from src.config.config import settings
from fastapi import APIRouter, Depends, HTTPException, Query, status

router = APIRouter(prefix="/environments/{project_id}", tags=["environments"])

logger = logging.getLogger(__name__)


@router.post("/", response_model=EnvironmentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_environment(
    body: EnvironmentCreateRequest,
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
    return create_environment_service(body, project_id=project.id, db=db)


@router.get("/", response_model=EnvironmentListResponse)
def list_environments(
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
    return list_environments_service(project_id=project.id, db=db)


@router.get("/by-name", response_model=EnvironmentCreateResponse)
def get_environment_by_name(
    name: str = Query(..., min_length=1),
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
    environment = get_environment_by_name_service(name=name, project_id=project.id, db=db)
    if environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment with name '{name}' not found.",
        )
    return environment


@router.get("/{environment_id}/columns")
def get_environment_columns(
    environment_id: uuid.UUID,
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
    environment = get_environment_service(environment_id=environment_id, project_id=project.id, db=db)
    if environment is None:
        raise HTTPException(status_code=404, detail="Environment not found")

    # ── Lire le dataset BRUT (pas le nettoyé) pour avoir les vrais types ──────
    raw_dataset = db.query(Dataset).filter(Dataset.env_id == environment_id).first()
    if not raw_dataset:
        raise HTTPException(status_code=404, detail="No dataset found for this environment")

    client = get_s3_client()
    buf = BytesIO()
    client.download_fileobj(settings.R2_BUCKET_NAME, raw_dataset.r2_path, buf)
    buf.seek(0)
    df = pd.read_csv(buf)

    # Exclure la colonne cible et retourner nom + type pour chaque colonne
    schema = []
    for col in df.columns:
        if col == environment.target_column:
            continue
        col_type = "number" if pd.api.types.is_numeric_dtype(df[col]) else "text"
        sample_values = df[col].dropna().astype(str).unique()[:3].tolist()
        schema.append({
            "name": col,
            "type": col_type,
            "sample_values": sample_values,
        })

    # Compatibilité avec l'ancien format { columns: [...] }
    columns = [c["name"] for c in schema]
    return {"columns": columns, "schema": schema}


@router.get("/{environment_id}", response_model=EnvironmentCreateResponse)
def get_environment(
    environment_id: uuid.UUID,
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
    logger.info(f">>> GET ENVIRONMENT ROUTE HIT: {environment_id}, user: {project.user_id}")
    environment = get_environment_service(environment_id=environment_id, project_id=project.id, db=db)
    if environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment '{environment_id}' not found.",
        )
    return environment


@router.patch("/{environment_id}", response_model=EnvironmentUpdateResponse)
def update_environment(
    environment_id: uuid.UUID,
    body: EnvironmentUpdateRequest,
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
    environment = update_environment_service(
        environment_id=environment_id,
        body=body,
        project_id=project.id,
        db=db,
    )
    if environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment '{environment_id}' not found.",
        )
    return environment


@router.delete("/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_environment(
    environment_id: uuid.UUID,
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
    deleted = delete_environment_service(environment_id=environment_id, project_id=project.id, db=db)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment '{environment_id}' not found.",
        )
    return {"message": "Environment deleted successfully"}


@router.delete("/", status_code=status.HTTP_200_OK)
def delete_all_environments(
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
    deleted_count = delete_all_environments_service(project_id=project.id, db=db)
    return {"deleted": deleted_count}