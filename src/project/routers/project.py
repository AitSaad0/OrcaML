from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from uuid import UUID

from src.config.db import get_db
from src.auth.dependencies.auth import get_current_user
from src.auth.models.user import User
from src.project import project_service as service
from src.project.schemas.projects import (
    CreateProjectRequest,
    CreateProjectResponse,
    GetProjectResponse,
    ListProjectsResponse,
    UpdateProjectRequest,
    UpdateProjectResponse,
    DeleteProjectResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=CreateProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_project(body, user_id=current_user.id, db=db)


@router.get("/", response_model=ListProjectsResponse)
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = service.list_projects(user_id=current_user.id, db=db)
    return ListProjectsResponse(projects=projects)


@router.get("/{project_id}", response_model=GetProjectResponse)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_project(project_id, user_id=current_user.id, db=db)


@router.put("/{project_id}", response_model=UpdateProjectResponse)
def update_project(
    project_id: UUID,
    body: UpdateProjectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.update_project(project_id, body, user_id=current_user.id, db=db)


@router.delete("/{project_id}", response_model=DeleteProjectResponse)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_project(project_id, user_id=current_user.id, db=db)
    return DeleteProjectResponse(message="Project deleted successfully")