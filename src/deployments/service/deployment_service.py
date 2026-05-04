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
MODEL_SERVER_IMAGE      = "model-server:latest"
DOCKER_NETWORK          = "orcaml_orcaml_network"
PORT_RANGE_START        = 8100
PORT_RANGE_END          = 8200
MODELS_VOLUME_HOST_PATH = "/var/lib/docker/volumes/orcaml_models_data/_data"

# ── Docker client (lazy — connects only when first used) ──────────────────────
_docker_client = None

def _get_docker_client() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        logger.debug("Docker client not initialized — connecting via docker.from_env()")
        try:
            _docker_client = docker.from_env()
            logger.info("Docker client connected successfully")
        except DockerException as e:
            logger.critical(f"Failed to connect to Docker daemon: {e}")
            raise
    else:
        logger.debug("Reusing existing Docker client instance")
    return _docker_client


# ── Port management ───────────────────────────────────────────────────────────
def _find_free_port(db: Session) -> int:
    """
    Finds a free port in range 8100-8200.
    Checks both:
      - DB:  ports already assigned to ACTIVE/DEPLOYING deployments
      - OS:  ports already bound on the host machine
    """
    logger.debug(f"Scanning for free port in range [{PORT_RANGE_START}, {PORT_RANGE_END})")

    used_ports = {
        row.port for row in db.query(Deployment.port).filter(
            Deployment.status.in_([DeploymentStatus.ACTIVE, DeploymentStatus.DEPLOYING]),
            Deployment.port.isnot(None),
        ).all()
    }

    logger.debug(f"Ports already in use by DB (ACTIVE/DEPLOYING): {sorted(used_ports)}")

    for port in range(PORT_RANGE_START, PORT_RANGE_END):
        if port in used_ports:
            logger.debug(f"Port {port} skipped — already assigned in DB")
            continue

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex(("localhost", port)) != 0:
                logger.debug(f"Port {port} is free on both DB and OS — selected")
                return port
            else:
                logger.debug(f"Port {port} skipped — already bound on host OS")

    logger.critical(
        f"Port exhaustion: no free ports in range [{PORT_RANGE_START}, {PORT_RANGE_END}). "
        f"All {PORT_RANGE_END - PORT_RANGE_START} ports are occupied."
    )
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
    """
    logger.info(f"Deploy requested — run_id={run_id}, environment_id={environment_id}")

    # ── 1. Validate run ───────────────────────────────────────────────────────
    logger.debug(f"Querying DB for run {run_id}")
    run = db.query(Run).filter(Run.id == run_id).first()

    if not run:
        logger.error(f"Run {run_id} not found in DB")
        raise ValueError(f"Run {run_id} not found")

    logger.debug(f"Run found: id={run.id}, status={run.status}, mlflow_run_id={run.mlflow_run_id}")

    if run.status != RunStatus.COMPLETED:
        logger.warning(
            f"Deploy attempted on non-COMPLETED run {run_id} "
            f"(current status: {run.status}) — rejecting"
        )
        raise ValueError(
            f"Run {run_id} is not COMPLETED (current status: {run.status}). "
            "Wait for training to finish before deploying."
        )

    if not run.mlflow_run_id:
        logger.error(f"Run {run_id} has no mlflow_run_id — artifact was not saved properly")
        raise ValueError(
            f"Run {run_id} has no mlflow_run_id — artifact was not saved properly"
        )

    logger.info(f"Run {run_id} validated — mlflow_run_id={run.mlflow_run_id}")

    # ── 2. Get or create ModelArtifact ────────────────────────────────────────
    logger.debug(f"Checking DB for existing ModelArtifact for run {run_id}")
    model_artifact = (
        db.query(ModelArtifact)
        .filter(ModelArtifact.run_id == run_id)
        .first()
    )

    if not model_artifact:
        logger.info(f"No ModelArtifact found for run {run_id} — will create one")
        logger.debug(f"Verifying MLflow artifact existence for mlflow_run_id={run.mlflow_run_id}")

        if not verify_run_has_artifact(run.mlflow_run_id):
            logger.error(
                f"MLflow has no artifact for run {run.mlflow_run_id} — "
                "training may not have saved the model correctly"
            )
            raise ValueError(
                f"No artifact found in MLflow for run {run.mlflow_run_id}. "
                "Training may not have saved the model correctly."
            )

        logger.debug(f"MLflow artifact confirmed for {run.mlflow_run_id} — starting download")
        file_path = download_model_artifact(run.mlflow_run_id)
        logger.debug(f"Artifact downloaded to: {file_path}")

        model_artifact = ModelArtifact(
            run_id=run_id,
            environment_id=environment_id,
            algorithm=run.algorithm.value,
            mlflow_run_id=run.mlflow_run_id,
            file_path=file_path,
        )
        db.add(model_artifact)
        db.flush()
        logger.info(f"ModelArtifact created: id={model_artifact.id}, algorithm={model_artifact.algorithm}, path={file_path}")
    else:
        logger.info(f"ModelArtifact already exists: id={model_artifact.id} — reusing (path={model_artifact.file_path})")

    # ── 3. Create deployment record (status: DEPLOYING) ───────────────────────
    deployment = Deployment(
        model_id=model_artifact.id,
        environment_id=environment_id,
        status=DeploymentStatus.DEPLOYING,
    )
    db.add(deployment)
    db.flush()
    logger.info(f"Deployment record created: id={deployment.id}, status=DEPLOYING")

    # ── 4. Spin up Docker container ───────────────────────────────────────────
    try:
        logger.debug("Looking for a free host port")
        port = _find_free_port(db)
        logger.info(f"Selected port {port} for deployment {deployment.id}")

        client = _get_docker_client()
        container_name = f"model-{deployment.id}"

        host_file_path = model_artifact.file_path.replace(
            "/app/models",
            MODELS_VOLUME_HOST_PATH
        )
        logger.debug(
            f"Volume mapping: {host_file_path} (host) → /app/model.pkl (container, read-only)"
        )

        logger.debug(
            f"Launching container '{container_name}' from image '{MODEL_SERVER_IMAGE}' "
            f"on network '{DOCKER_NETWORK}', port mapping 8000→{port}"
        )
        container = client.containers.run(
            image=MODEL_SERVER_IMAGE,
            name=container_name,
            detach=True,
            network=DOCKER_NETWORK,
            ports={"8000/tcp": port},
            volumes={
                host_file_path: {
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

        logger.debug(f"Container ID assigned by Docker: {container.id}")
        logger.info(f"Container started: name={container_name}, port={port}")

        # ── 5. Update deployment to ACTIVE ────────────────────────────────────
        deployment.container_id   = container.id
        deployment.container_name = container_name
        deployment.port           = port
        deployment.endpoint_url   = f"http://localhost:{port}/predict"
        deployment.status         = DeploymentStatus.ACTIVE
        deployment.deployed_at    = datetime.now(timezone.utc)

        db.commit()
        db.refresh(deployment)
        logger.info(
            f"Deployment ACTIVE: id={deployment.id}, endpoint={deployment.endpoint_url}, "
            f"container={container_name}, port={port}"
        )

    except Exception as e:
        logger.error(
            f"Container startup failed for deployment {deployment.id}: {e}",
            exc_info=True,   # ← attaches full traceback to the log
        )
        deployment.status = DeploymentStatus.FAILED
        db.commit()
        logger.warning(f"Deployment {deployment.id} marked as FAILED in DB")
        raise RuntimeError(f"Failed to start model container: {e}")

    return deployment


# ── Undeploy ──────────────────────────────────────────────────────────────────
def undeploy(deployment_id: uuid.UUID, db: Session) -> Deployment:
    """
    Stops and removes the Docker container for a deployment.
    """
    logger.info(f"Undeploy requested — deployment_id={deployment_id}")

    logger.debug(f"Querying DB for deployment {deployment_id}")
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()

    if not deployment:
        logger.error(f"Deployment {deployment_id} not found in DB")
        raise ValueError(f"Deployment {deployment_id} not found")

    logger.debug(f"Deployment found: id={deployment.id}, status={deployment.status}, container={deployment.container_name}")

    if deployment.status != DeploymentStatus.ACTIVE:
        logger.warning(
            f"Undeploy attempted on non-ACTIVE deployment {deployment_id} "
            f"(current status: {deployment.status}) — rejecting"
        )
        raise ValueError(
            f"Deployment {deployment_id} is not ACTIVE (status: {deployment.status})"
        )

    try:
        client = _get_docker_client()
        logger.debug(f"Fetching container by ID: {deployment.container_id}")
        container = client.containers.get(deployment.container_id)

        logger.debug(f"Stopping container '{deployment.container_name}' (timeout=10s)")
        container.stop(timeout=10)
        logger.debug(f"Container '{deployment.container_name}' stopped — removing")
        container.remove()
        logger.info(f"Container {deployment.container_name} stopped and removed successfully")

    except NotFound:
        logger.warning(
            f"Container {deployment.container_name} (id={deployment.container_id}) "
            "not found in Docker — it may have been removed manually. "
            "Marking deployment as STOPPED anyway."
        )
    except DockerException as e:
        logger.error(f"Docker error while stopping container {deployment.container_name}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to stop container: {e}")

    deployment.status     = DeploymentStatus.STOPPED
    deployment.stopped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(deployment)

    logger.info(f"Deployment {deployment_id} STOPPED at {deployment.stopped_at}")
    return deployment


# ── Predict ───────────────────────────────────────────────────────────────────
async def predict(
    deployment_id: uuid.UUID,
    features: list[float],
    db: Session,
) -> dict:
    """
    Forwards a prediction request to the model container over HTTP.
    """
    logger.debug(f"Predict called — deployment_id={deployment_id}, feature_count={len(features)}")

    deployment = (
        db.query(Deployment)
        .options(joinedload(Deployment.model))
        .filter(Deployment.id == deployment_id)
        .first()
    )

    if not deployment:
        logger.error(f"Deployment {deployment_id} not found in DB")
        raise ValueError(f"Deployment {deployment_id} not found")

    logger.debug(
        f"Deployment found: id={deployment.id}, status={deployment.status}, "
        f"container={deployment.container_name}, port={deployment.port}"
    )

    if deployment.status != DeploymentStatus.ACTIVE:
        logger.warning(
            f"Predict attempted on non-ACTIVE deployment {deployment_id} "
            f"(current status: {deployment.status})"
        )
        raise ValueError(
            f"Deployment {deployment_id} is not ACTIVE (status: {deployment.status})"
        )

    predict_url = f"http://{deployment.container_name}:8000/predict"
    logger.debug(f"Forwarding prediction request to {predict_url} — features={features}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(predict_url, json={"features": features})
            logger.debug(f"Model container responded with HTTP {response.status_code}")
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Raw prediction result from container: {result}")

    except httpx.TimeoutException:
        logger.error(
            f"Prediction timed out for deployment {deployment_id} "
            f"(container={deployment.container_name}, port={deployment.port})"
        )
        raise RuntimeError(f"Model container timed out — port {deployment.port}")

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Model container returned HTTP error for deployment {deployment_id}: "
            f"status={e.response.status_code}, body={e.response.text}"
        )
        raise RuntimeError(f"Model container returned an error: {e.response.text}")

    except Exception as e:
        logger.error(f"Unexpected error reaching model container for deployment {deployment_id}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to reach model container: {e}")

    # Update observability counters
    prev_calls = deployment.total_calls
    deployment.total_calls    += 1
    deployment.last_called_at  = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        f"Prediction successful — deployment_id={deployment_id}, "
        f"total_calls={prev_calls} → {deployment.total_calls}"
    )
    logger.debug(f"Prediction payload returned: {result}")

    return {
        "deployment_id": str(deployment_id),
        "model_id":      str(deployment.model_id),
        "algorithm":     deployment.model.algorithm,
        **result,
    }


# ── Logs ──────────────────────────────────────────────────────────────────────
def get_logs(
    deployment_id: uuid.UUID,
    db: Session,
    tail: int = 100,
) -> list[str]:
    """
    Fetches stdout/stderr logs directly from the Docker container.
    """
    logger.debug(f"get_logs called — deployment_id={deployment_id}, tail={tail}")

    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()

    if not deployment:
        logger.error(f"Deployment {deployment_id} not found in DB")
        raise ValueError(f"Deployment {deployment_id} not found")

    logger.debug(f"Deployment found: container_id={deployment.container_id}, name={deployment.container_name}")

    if not deployment.container_id:
        logger.warning(f"Deployment {deployment_id} has no container_id — was never started")
        raise ValueError(
            f"Deployment {deployment_id} has no container — was never started"
        )

    try:
        client = _get_docker_client()
        logger.debug(f"Fetching last {tail} log lines from container {deployment.container_name}")
        container  = client.containers.get(deployment.container_id)
        raw_logs   = container.logs(tail=tail, timestamps=True).decode("utf-8")
        lines      = [line for line in raw_logs.splitlines() if line.strip()]
        logger.info(f"Retrieved {len(lines)} log lines from container {deployment.container_name}")
        return lines

    except NotFound:
        logger.error(
            f"Container {deployment.container_name} (id={deployment.container_id}) "
            "no longer exists in Docker — may have been removed manually"
        )
        raise ValueError(
            f"Container {deployment.container_name} no longer exists — "
            "it may have been removed manually"
        )
    except DockerException as e:
        logger.error(f"Docker error fetching logs for container {deployment.container_name}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to fetch container logs: {e}")


# ── List / Get ────────────────────────────────────────────────────────────────
def get_deployment(deployment_id: uuid.UUID, db: Session) -> Deployment:
    logger.debug(f"get_deployment called — deployment_id={deployment_id}")
    deployment = (
        db.query(Deployment)
        .options(joinedload(Deployment.model))
        .filter(Deployment.id == deployment_id)
        .first()
    )
    if not deployment:
        logger.error(f"Deployment {deployment_id} not found in DB")
        raise ValueError(f"Deployment {deployment_id} not found")

    logger.debug(f"Deployment retrieved: id={deployment.id}, status={deployment.status}")
    return deployment


def list_deployments(environment_id: uuid.UUID, db: Session) -> list[Deployment]:
    logger.debug(f"list_deployments called — environment_id={environment_id}")
    deployments: list[Deployment] = (
        db.query(Deployment)
        .options(joinedload(Deployment.model))
        .filter(Deployment.environment_id == environment_id)
        .order_by(Deployment.created_at.desc())
        .all()
    )
    if not deployments:
        logger.info(f"No deployments found for environment {environment_id}")
    else:
        logger.info(f"Found {len(deployments)} deployments for environment {environment_id}")
        logger.debug(
            "Deployments summary: "
            + ", ".join(f"{d.id}({d.status})" for d in deployments)
        )
    return deployments