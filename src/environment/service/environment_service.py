import uuid
from sqlalchemy.orm import Session, joinedload
from src.environment.models.Environment import Environment
from src.environment.schemas.environment_schemas import (
    EnvironmentCreateRequest,
    EnvironmentUpdateRequest,
    EnvironmentCreateResponse,
    EnvironmentUpdateResponse,
    EnvironmentListResponse,
)
from src.dataset.services.r2_service import delete_from_r2


def _resolve_unique_name(base_name: str, project_id: uuid.UUID, db: Session) -> str:
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
        .options(
            joinedload(Environment.runs),
            joinedload(Environment.deployments),
        )
        .filter(Environment.project_id == project_id)
        .order_by(Environment.created_at.asc())
        .all()
    )

    results = []
    for env in environments:
        data = EnvironmentCreateResponse.model_validate(env)
        data.total_runs = len(env.runs)
        data.total_deployments = len(env.deployments)
        results.append(data)

    return EnvironmentListResponse(environments=results, total=len(results))

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
    environment = _get_or_none(environment_id, project_id, db)
    if environment is None:
        return False

    # 1. Nettoyer les fichiers bruts sur R2
    for dataset in environment.datasets:
        if dataset.r2_path:
            delete_from_r2(dataset.r2_path)

    # 2. Nettoyer les fichiers nettoyés sur R2
    for cleaned in environment.cleaned_datasets:
        if cleaned.file_path:
            delete_from_r2(cleaned.file_path)

    # 3. Supprimer en DB
    db.delete(environment)
    db.commit()
    return True


def delete_all_environments(
    project_id: uuid.UUID,
    db: Session,
) -> int:
    environments = (
        db.query(Environment)
        .filter(Environment.project_id == project_id)
        .all()
    )

    count = 0
    for environment in environments:
        for dataset in environment.datasets:
            if dataset.r2_path:
                delete_from_r2(dataset.r2_path)
        for cleaned in environment.cleaned_datasets:
            if cleaned.file_path:
                delete_from_r2(cleaned.file_path)
        db.delete(environment)
        count += 1

    db.commit()
    return count