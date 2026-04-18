import uuid
from sqlalchemy.orm import Session

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
from fastapi import APIRouter, Depends, HTTPException, Query, status

router = APIRouter(prefix="/environments/{project_id}", tags=["environments"])


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


@router.get("/{environment_id}", response_model=EnvironmentCreateResponse)
def get_environment(
    environment_id: uuid.UUID,
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
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


@router.delete("/", status_code=status.HTTP_200_OK)
def delete_all_environments(
    project: Project = Depends(get_project_or_403),
    db: Session = Depends(get_db),
):
    deleted_count = delete_all_environments_service(project_id=project.id, db=db)
    return {"deleted": deleted_count}