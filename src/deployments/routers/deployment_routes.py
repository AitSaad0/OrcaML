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
    prefix="/deployments/environments/{environment_id}",
    tags=["Deployments"],
)


# ── Guards ────────────────────────────────────────────────────────────────────

def check_environment(environment_id: uuid.UUID, current_user: User, db: Session):
    logger.debug(f"check_environment — environment_id={environment_id}, user_id={current_user.id}")

    env = (
        db.query(Environment)
        .options(joinedload(Environment.project))
        .filter(Environment.id == environment_id)
        .first()
    )

    if not env:
        logger.warning(f"Environment {environment_id} not found in DB — returning 404")
        raise HTTPException(status_code=404, detail="Environnement introuvable.")

    logger.debug(f"Environment {environment_id} found — project_id={env.project.id}, owner_id={env.project.user_id}")

    if env.project.user_id != current_user.id:
        logger.warning(
            f"Access denied: user {current_user.id} tried to access environment "
            f"{environment_id} owned by user {env.project.user_id}"
        )
        raise HTTPException(status_code=403, detail="Accès refusé à cet environnement.")

    logger.debug(f"Environment {environment_id} ownership confirmed for user {current_user.id}")
    return env


def check_deployment(deployment_id: uuid.UUID, environment_id: uuid.UUID, db: Session):
    logger.debug(f"check_deployment — deployment_id={deployment_id}, environment_id={environment_id}")

    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()

    if not deployment:
        logger.warning(f"Deployment {deployment_id} not found in DB — returning 404")
        raise HTTPException(status_code=404, detail="Deployment introuvable.")

    logger.debug(f"Deployment {deployment_id} found — status={deployment.status}, environment_id={deployment.environment_id}")

    if deployment.environment_id != environment_id:
        logger.warning(
            f"Deployment {deployment_id} belongs to environment {deployment.environment_id}, "
            f"but was accessed under environment {environment_id} — returning 403"
        )
        raise HTTPException(
            status_code=403,
            detail="Ce deployment n'appartient pas à cet environnement.",
        )

    logger.debug(f"Deployment {deployment_id} environment check passed")
    return deployment


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=DeploymentResponse, status_code=201)
def deploy_model(
    environment_id: uuid.UUID,
    body: DeployRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"POST /deployments/environments/{environment_id} — deploy requested by user {current_user.id}, run_id={body.run_id}")
    logger.debug(f"Deploy request body: {body.dict()}")

    check_environment(environment_id, current_user, db)

    try:
        deployment = service.deploy(run_id=body.run_id, environment_id=environment_id, db=db)
    except ValueError as e:
        logger.warning(f"Deploy rejected for run {body.run_id} in environment {environment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Deploy failed for run {body.run_id} in environment {environment_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    logger.info(f"Deploy succeeded — deployment_id={deployment.id}, status={deployment.status}, endpoint={deployment.endpoint_url}")
    return deployment


@router.get("", response_model=list[DeploymentResponse])
def list_deployments(
    environment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"GET /deployments/environments/{environment_id} — list requested by user {current_user.id}")

    check_environment(environment_id, current_user, db)

    deployments = service.list_deployments(environment_id=environment_id, db=db)
    logger.info(f"Returning {len(deployments)} deployments for environment {environment_id}")
    logger.debug(f"Deployment IDs returned: {[str(d.id) for d in deployments]}")
    return deployments


@router.get("/{deployment_id}", response_model=DeploymentResponse)
def get_deployment(
    environment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"GET /deployments/environments/{environment_id}/{deployment_id} — requested by user {current_user.id}")

    check_environment(environment_id, current_user, db)
    deployment = check_deployment(deployment_id, environment_id, db)

    logger.debug(f"Returning deployment {deployment_id} — status={deployment.status}, port={deployment.port}")
    return deployment


@router.delete("/{deployment_id}", response_model=DeploymentResponse)
def undeploy_model(
    environment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"DELETE /deployments/environments/{environment_id}/{deployment_id} — undeploy requested by user {current_user.id}")

    check_environment(environment_id, current_user, db)
    check_deployment(deployment_id, environment_id, db)

    try:
        deployment = service.undeploy(deployment_id=deployment_id, db=db)
    except ValueError as e:
        logger.warning(f"Undeploy rejected for deployment {deployment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Undeploy failed for deployment {deployment_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    logger.info(f"Undeploy succeeded — deployment_id={deployment_id}, status={deployment.status}, stopped_at={deployment.stopped_at}")
    return deployment


@router.post("/{deployment_id}/predict", response_model=PredictResponse)
async def predict(
    environment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    body: PredictRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"POST /deployments/environments/{environment_id}/{deployment_id}/predict — requested by user {current_user.id}")
    logger.debug(f"Predict features: count={len(body.features)}, values={body.features}")

    check_environment(environment_id, current_user, db)
    check_deployment(deployment_id, environment_id, db)

    try:
        result = await service.predict(deployment_id=deployment_id, features=body.features, db=db)
    except ValueError as e:
        logger.warning(f"Predict rejected for deployment {deployment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Predict failed for deployment {deployment_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    logger.info(f"Predict succeeded — deployment_id={deployment_id}, algorithm={result.get('algorithm')}")
    logger.debug(f"Predict result payload: {result}")
    return result


@router.get("/{deployment_id}/logs", response_model=LogsResponse)
def get_logs(
    environment_id: uuid.UUID,
    deployment_id: uuid.UUID,
    tail: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"GET /deployments/environments/{environment_id}/{deployment_id}/logs — requested by user {current_user.id}, tail={tail}")

    if tail <= 0:
        logger.warning(f"Invalid tail value {tail} requested by user {current_user.id} — must be > 0")
        raise HTTPException(status_code=400, detail="'tail' must be a positive integer.")

    check_environment(environment_id, current_user, db)
    check_deployment(deployment_id, environment_id, db)

    try:
        logs = service.get_logs(deployment_id=deployment_id, db=db, tail=tail)
    except ValueError as e:
        logger.warning(f"get_logs rejected for deployment {deployment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"get_logs failed for deployment {deployment_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    logger.info(f"Returning {len(logs)} log lines for deployment {deployment_id} (tail={tail})")
    logger.debug(f"First log line: {logs[0] if logs else '<empty>'}")
    return LogsResponse(deployment_id=deployment_id, logs=logs)