import uuid
from sqlalchemy.orm import Session
from src.environment.models.Environment import Environment
from src.environment.schemas.environment_schemas import (
    EnvironmentCreateRequest,
    EnvironmentUpdateRequest,
    EnvironmentCreateResponse,
    EnvironmentUpdateResponse,
    EnvironmentListResponse,
)


def _resolve_unique_name(base_name: str, project_id: uuid.UUID, db: Session) -> str:
    """Append (1), (2), ... if the name already exists in this project."""
    if not db.query(Environment).filter(
        Environment.project_id == project_id,
        Environment.name == base_name
    ).first():
        return base_name

    suffix = 1
    while db.query(Environment).filter(
        Environment.project_id == project_id,
        Environment.name == f"{base_name} ({suffix})"
    ).first():
        suffix += 1

    return f"{base_name} ({suffix})"


def _get_or_none(environment_id: uuid.UUID, project_id: uuid.UUID, db: Session) -> Environment | None:
    """Base fetch — scoped to project. Used internally by all operations."""
    return db.query(Environment).filter(
        Environment.id == environment_id,
        Environment.project_id == project_id,
    ).first()


def create_environment(
    body: EnvironmentCreateRequest,
    project_id: uuid.UUID,
    db: Session,
) -> EnvironmentCreateResponse:
    new_environment = Environment(
        name=_resolve_unique_name(body.name, project_id, db),
        target_column=body.target_column,
        task_type=body.task_type,
        status=body.status,
        project_id=project_id,
    )
    db.add(new_environment)
    db.commit()
    db.refresh(new_environment)
    return EnvironmentCreateResponse.model_validate(new_environment)


def get_environment(
    environment_id: uuid.UUID,
    project_id: uuid.UUID,
    db: Session,
) -> EnvironmentCreateResponse | None:
    environment = _get_or_none(environment_id, project_id, db)
    if environment is None:
        return None
    return EnvironmentCreateResponse.model_validate(environment)


def get_environment_by_name(
    name: str,
    project_id: uuid.UUID,
    db: Session,
) -> EnvironmentCreateResponse | None:
    environment = db.query(Environment).filter(
        Environment.name == name,
        Environment.project_id == project_id,
    ).first()
    if environment is None:
        return None
    return EnvironmentCreateResponse.model_validate(environment)


def list_environments(
    project_id: uuid.UUID,
    db: Session,
) -> EnvironmentListResponse:
    environments = (
        db.query(Environment)
        .filter(Environment.project_id == project_id)
        .order_by(Environment.created_at.asc())
        .all()
    )
    return EnvironmentListResponse(
        environments=[EnvironmentCreateResponse.model_validate(e) for e in environments],
        total=len(environments),
    )



def update_environment(
    environment_id: uuid.UUID,
    body: EnvironmentUpdateRequest,
    project_id: uuid.UUID,
    db: Session,
) -> EnvironmentUpdateResponse | None:
    environment = _get_or_none(environment_id, project_id, db)
    if environment is None:
        return None

    if body.name is not None:
        environment.name = _resolve_unique_name(body.name, project_id, db)
    if body.target_column is not None:
        environment.target_column = body.target_column
    if body.task_type is not None:
        environment.task_type = body.task_type
    if body.status is not None:
        environment.status = body.status

    db.commit()
    db.refresh(environment)
    return EnvironmentUpdateResponse.model_validate(environment)


def delete_environment(
    environment_id: uuid.UUID,
    project_id: uuid.UUID,
    db: Session,
) -> bool:
    """Returns True if deleted, False if not found."""
    environment = _get_or_none(environment_id, project_id, db)
    if environment is None:
        return False
    db.delete(environment)
    db.commit()
    return True



def delete_all_environments(
    project_id: uuid.UUID,
    db: Session,
) -> int:
    """Bulk delete. Returns count of deleted rows."""
    deleted = (
        db.query(Environment)
        .filter(Environment.project_id == project_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted