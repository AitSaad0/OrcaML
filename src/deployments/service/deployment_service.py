import logging
import socket
import uuid
from datetime import datetime, timezone

import docker
import httpx
from docker.errors import DockerException, NotFound
from sqlalchemy.orm import Session, joinedload

from src.deployments.mlflow_clients import download_model_artifact, verify_run_has_artifact
from src.deployments.models.deployment import Deployment
from src.deployments.models.enums import DeploymentStatus
from src.deployments.models.model_artifact import ModelArtifact
from src.runs.models.run import Run, RunStatus

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_SERVER_IMAGE = "model-server:latest"
DOCKER_NETWORK = "orcaml_orcaml_network"
PORT_RANGE_START   = 8100
PORT_RANGE_END     = 8200
MODELS_VOLUME_HOST_PATH = "/var/lib/docker/volumes/orcaml_models_data/_data" 

# ── Docker client (lazy — connects only when first used) ──────────────────────
_docker_client = None

def _get_docker_client() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


# ── Port management ───────────────────────────────────────────────────────────
def _find_free_port(db: Session) -> int:
    """
    Finds a free port in range 8100-8200.
    Checks both:
      - DB:  ports already assigned to ACTIVE/DEPLOYING deployments
      - OS:  ports already bound on the host machine
    """
    used_ports = {
        row.port for row in db.query(Deployment.port).filter(
            Deployment.status.in_([DeploymentStatus.ACTIVE, DeploymentStatus.DEPLOYING]),
            Deployment.port.isnot(None),
        ).all()
    }

    for port in range(PORT_RANGE_START, PORT_RANGE_END):
        if port in used_ports:
            continue
        # Double-check the port is actually free on the OS
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex(("localhost", port)) != 0:
                return port

    raise RuntimeError(
        f"No free ports available in range {PORT_RANGE_START}-{PORT_RANGE_END}"
    )


# ── Deploy ────────────────────────────────────────────────────────────────────
def deploy(run_id: uuid.UUID, environment_id: uuid.UUID, db: Session) -> Deployment:
    """
    Full deploy flow:
      1. Validate run exists and is COMPLETED
      2. Get or create ModelArtifact (download .pkl from MLflow)
      3. Find a free port
      4. Spin up Docker container with the model mounted
      5. Save Deployment record to DB and return it

    Args:
        run_id:         UUID of the run to deploy
        environment_id: UUID of the environment (for scoping)
        db:             SQLAlchemy session

    Returns:
        Deployment DB object with status ACTIVE or FAILED
    """

    # ── 1. Validate run ───────────────────────────────────────────────────────
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ValueError(f"Run {run_id} not found")
    if run.status != RunStatus.COMPLETED:
        raise ValueError(
            f"Run {run_id} is not COMPLETED (current status: {run.status}). "
            "Wait for training to finish before deploying."
        )
    if not run.mlflow_run_id:
        raise ValueError(
            f"Run {run_id} has no mlflow_run_id — artifact was not saved properly"
        )

    # ── 2. Get or create ModelArtifact ────────────────────────────────────────
    model_artifact = (
        db.query(ModelArtifact)
        .filter(ModelArtifact.run_id == run_id)
        .first()
    )

    if not model_artifact:
        # Safety check — verify MLflow actually has the artifact
        if not verify_run_has_artifact(run.mlflow_run_id):
            raise ValueError(
                f"No artifact found in MLflow for run {run.mlflow_run_id}. "
                "Training may not have saved the model correctly."
            )

        # Download .pkl from MLflow to /app/models/{mlflow_run_id}/
        file_path = download_model_artifact(run.mlflow_run_id)

        model_artifact = ModelArtifact(
            run_id=run_id,
            environment_id=environment_id,
            algorithm=run.algorithm.value,
            mlflow_run_id=run.mlflow_run_id,
            file_path=file_path,
        )
        db.add(model_artifact)
        db.flush()  # get model_artifact.id without committing yet
        logger.info(f"ModelArtifact created: {model_artifact.id}")
    else:
        logger.info(f"ModelArtifact already exists: {model_artifact.id}, reusing")

    # ── 3. Create deployment record (status: DEPLOYING) ───────────────────────
    deployment = Deployment(
        model_id=model_artifact.id,
        environment_id=environment_id,
        status=DeploymentStatus.DEPLOYING,
    )
    db.add(deployment)
    db.flush()  # get deployment.id before starting container
    logger.info(f"Deployment record created: {deployment.id}")

    # ── 4. Spin up Docker container ───────────────────────────────────────────
    try:
        port = _find_free_port(db)
        client = _get_docker_client()
        container_name = f"model-{deployment.id}"
        host_file_path = model_artifact.file_path.replace(
            "/app/models", 
            MODELS_VOLUME_HOST_PATH
        )

        container = client.containers.run(
            image=MODEL_SERVER_IMAGE,
            name=container_name,
            detach=True,                           # run in background
            network=DOCKER_NETWORK,                # join the app network
            ports={"8000/tcp": port},              # map container 8000 → host port
            volumes={
                host_file_path: {          # ← host path, not container path
                    "bind": "/app/model.pkl",
                    "mode": "ro",
                }
            },
            environment={
                "MODEL_ID":   str(model_artifact.id),
                "ALGORITHM":  model_artifact.algorithm,
                "MODEL_PATH": "/app/model.pkl",
            },
            restart_policy={"Name": "unless-stopped"},
        )

        logger.info(f"Mounting model file: {model_artifact.file_path}")
        logger.info(f"Container started: {container_name} on port {port}")

        # ── 5. Update deployment to ACTIVE ────────────────────────────────────
        deployment.container_id   = container.id
        deployment.container_name = container_name
        deployment.port           = port
        deployment.endpoint_url   = f"http://localhost:{port}/predict"
        deployment.status         = DeploymentStatus.ACTIVE
        deployment.deployed_at    = datetime.now(timezone.utc)

        db.commit()
        db.refresh(deployment)
        logger.info(f"Deployment ACTIVE: {deployment.id} → {deployment.endpoint_url}")

    except Exception as e:
        logger.error(f"Container startup failed for deployment {deployment.id}: {e}")
        deployment.status = DeploymentStatus.FAILED
        db.commit()
        raise RuntimeError(f"Failed to start model container: {e}")

    return deployment


# ── Undeploy ──────────────────────────────────────────────────────────────────
def undeploy(deployment_id: uuid.UUID, db: Session) -> Deployment:
    """
    Stops and removes the Docker container for a deployment.

    Args:
        deployment_id: UUID of the deployment to stop
        db:            SQLAlchemy session

    Returns:
        Updated Deployment with status STOPPED
    """
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise ValueError(f"Deployment {deployment_id} not found")
    if deployment.status != DeploymentStatus.ACTIVE:
        raise ValueError(
            f"Deployment {deployment_id} is not ACTIVE (status: {deployment.status})"
        )

    try:
        client = _get_docker_client()
        container = client.containers.get(deployment.container_id)
        container.stop(timeout=10)
        container.remove()
        logger.info(f"Container {deployment.container_name} stopped and removed")

    except NotFound:
        # Container already gone — still mark as stopped cleanly
        logger.warning(
            f"Container {deployment.container_name} not found in Docker, "
            "marking as STOPPED anyway"
        )
    except DockerException as e:
        logger.error(f"Error stopping container: {e}")
        raise RuntimeError(f"Failed to stop container: {e}")

    deployment.status     = DeploymentStatus.STOPPED
    deployment.stopped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(deployment)

    logger.info(f"Deployment {deployment_id} STOPPED")
    return deployment


# ── Predict ───────────────────────────────────────────────────────────────────
async def predict(
    deployment_id: uuid.UUID,
    features: list[float],
    db: Session,
) -> dict:
    """
    Forwards a prediction request to the model container over HTTP.
    Increments total_calls and updates last_called_at on every call.

    Args:
        deployment_id: UUID of the deployment to call
        features:      Flat list of feature values (same order as training)
        db:            SQLAlchemy session

    Returns:
        Dict with prediction results from the model container
    """
    deployment = (
        db.query(Deployment)
        .options(joinedload(Deployment.model))
        .filter(Deployment.id == deployment_id)
        .first()
    )
    if not deployment:
        raise ValueError(f"Deployment {deployment_id} not found")
    if deployment.status != DeploymentStatus.ACTIVE:
        raise ValueError(
            f"Deployment {deployment_id} is not ACTIVE (status: {deployment.status})"
        )

    # Forward to model container
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"http://{deployment.container_name}:8000/predict",
                json={"features": features},
            )
            response.raise_for_status()
            result = response.json()

    except httpx.TimeoutException:
        raise RuntimeError(
            f"Model container timed out — port {deployment.port}"
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Model container returned an error: {e.response.text}"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to reach model container: {e}")

    # Update observability counters
    deployment.total_calls    += 1
    deployment.last_called_at  = datetime.now(timezone.utc)
    db.commit()

    return {
        "deployment_id": str(deployment_id),
        "model_id":      str(deployment.model_id),
        "algorithm":     deployment.model.algorithm,
        **result,  # prediction, prediction_label from serve.py
    }


# ── Logs ──────────────────────────────────────────────────────────────────────
def get_logs(
    deployment_id: uuid.UUID,
    db: Session,
    tail: int = 100,
) -> list[str]:
    """
    Fetches stdout/stderr logs directly from the Docker container.

    Args:
        deployment_id: UUID of the deployment
        db:            SQLAlchemy session
        tail:          Number of log lines to return (default 100)

    Returns:
        List of log line strings with timestamps
    """
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise ValueError(f"Deployment {deployment_id} not found")
    if not deployment.container_id:
        raise ValueError(
            f"Deployment {deployment_id} has no container — was never started"
        )

    try:
        client = _get_docker_client()
        container = client.containers.get(deployment.container_id)
        raw_logs  = container.logs(tail=tail, timestamps=True).decode("utf-8")
        return [line for line in raw_logs.splitlines() if line.strip()]

    except NotFound:
        raise ValueError(
            f"Container {deployment.container_name} no longer exists — "
            "it may have been removed manually"
        )
    except DockerException as e:
        raise RuntimeError(f"Failed to fetch container logs: {e}")


# ── List / Get ────────────────────────────────────────────────────────────────
def get_deployment(deployment_id: uuid.UUID, db: Session) -> Deployment:
    deployment = (
        db.query(Deployment)
        .options(joinedload(Deployment.model))
        .filter(Deployment.id == deployment_id)
        .first()
    )
    if not deployment:
        raise ValueError(f"Deployment {deployment_id} not found")
    return deployment


def list_deployments(environment_id: uuid.UUID, db: Session) -> list[Deployment]:
    return (
        db.query(Deployment)
        .options(joinedload(Deployment.model))
        .filter(Deployment.environment_id == environment_id)
        .order_by(Deployment.created_at.desc())
        .all()
    )