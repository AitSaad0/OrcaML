from uuid import UUID
from starlette import status
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.project.models.project import Project
from src.project.schemas.projects import CreateProjectRequest, UpdateProjectRequest


def _resolve_unique_name(base_name: str, user_id: UUID, db: Session) -> str:
    existing_names = {
        p.name for p in db.query(Project)
                            .filter(Project.user_id == user_id)
                            .all()
    }

    if base_name not in existing_names:
        return base_name
        
    suffix = 1
    while f"{base_name} ({suffix})" in existing_names:
        suffix += 1
    return f"{base_name} ({suffix})"


def create_project(body: CreateProjectRequest, user_id: UUID, db: Session) -> Project:
    unique_name = _resolve_unique_name(body.name, user_id, db)
    new_project = Project(
        name=unique_name,
        description=body.description,
        user_id=user_id
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


def get_project(project_id: UUID, user_id: UUID, db: Session) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user_id)  
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


def list_projects(user_id: UUID, db: Session) -> list[Project]:
    return db.query(Project).filter(Project.user_id == user_id).all() 
        

def update_project(project_id: UUID, body: UpdateProjectRequest, user_id: UUID, db: Session) -> Project:
    project = get_project(project_id, user_id, db)

    if body.name is not None:
        # also resolve unique name on rename
        project.name = _resolve_unique_name(body.name, user_id, db)
    if body.description is not None:
        project.description = body.description

    db.commit()
    db.refresh(project)
    return project

def delete_project(project_id: UUID, user_id: UUID, db: Session) -> None:
    project = get_project(project_id, user_id, db)
    db.delete(project)
    db.commit()