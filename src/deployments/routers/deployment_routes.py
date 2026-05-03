import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from src.config.db import get_db
from src.auth.dependencies.auth import get_current_user
from src.auth.models.user import User
from src.environment.models.Environment import Environment
from src.deployments.models.deployment import Deployment
from src.deployments.service import deployment_service as service
from src.deployments.schemas.deployments_schemas import (
    DeployRequest,
    DeploymentResponse,
    PredictRequest,
    PredictResponse,
    LogsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/environments/{environment_id}/deployments",
    tags=["Deployments"],
)

# ─────────────────────────────────────────────────────────────
# 🔐 CHECKS
# ─────────────────────────────────────────────────────────────

def check_environment(environment_id: uuid.UUID, current_user: User, db: Session):
    env = (
        db.query(Environment)
        .options(joinedload(Environment.project))
        .filter(Environment.id == environment_id)
        .first()
    )

    if not env:
        raise HTTPException(status_code=404, detail="Environnement introuvable.")

    if env.project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accès refusé à cet environnement.")

    return env


def check_deployment(deployment_id: uuid.UUID, environment_id: uuid.UUID, db: Session):
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()

    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment introuvable.")

    if deployment.environment_id != environment_id:
        raise HTTPException(
            status_code=403,
            detail="Ce deployment n'appartient pas à cet environnement.",
        )

    return deployment


# ─────────────────────────────────────────────────────────────
# 🚀 ROUTES
# ─────────────────────────────────────────────────────────────

@router.post("", response_model=DeploymentResponse, status_code=201)
def deploy_model(
    environment_id: uuid.UUID,
    body: DeployRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_environment(environment_id, current_user, db)

    return service.deploy(
        run_id=body.run_id,
        environment_id=environment_id,
        db=db,
    )


@router.get("", response_model=list[DeploymentResponse])
def list_deployments(
    environment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_environment(environment_id, current_user, db)

    return service.list_deployments(environment_id=environment_id, db=db)


@router.get("/{deployment_id}", response_model=DeploymentResponse)
def get_deployment(
    environment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_environment(environment_id, current_user, db)
    return check_deployment(deployment_id, environment_id, db)


@router.delete("/{deployment_id}", response_model=DeploymentResponse)
def undeploy_model(
    environment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_environment(environment_id, current_user, db)
    check_deployment(deployment_id, environment_id, db)

    return service.undeploy(deployment_id=deployment_id, db=db)


@router.post("/{deployment_id}/predict", response_model=PredictResponse)
async def predict(
    environment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    body: PredictRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_environment(environment_id, current_user, db)
    check_deployment(deployment_id, environment_id, db)

    return await service.predict(
        deployment_id=deployment_id,
        features=body.features,
        db=db,
    )


@router.get("/{deployment_id}/logs", response_model=LogsResponse)
def get_logs(
    environment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    tail: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_environment(environment_id, current_user, db)
    check_deployment(deployment_id, environment_id, db)

    logs = service.get_logs(
        deployment_id=deployment_id,
        db=db,
        tail=tail,
    )

    return LogsResponse(deployment_id=deployment_id, logs=logs)