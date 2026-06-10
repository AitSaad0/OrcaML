import logging
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO

import docker
import httpx
import pandas as pd
from docker.errors import DockerException, NotFound
from sqlalchemy import select, desc
from sqlalchemy.orm import Session, joinedload

from src.config.config import settings
from src.dataset.models.cleaned_dataset import CleanedDataset
from src.dataset.models.cleaning_config import CleaningConfig
from src.dataset.models.dataset import Dataset
from src.dataset.services.cleaning_service import apply_cleaning
from src.dataset.services.r2_service import get_s3_client
from src.deployments.mlflow_clients import download_model_artifact, verify_run_has_artifact
from src.deployments.models.deployment import Deployment
from src.deployments.models.enums import DeploymentStatus
from src.deployments.models.model_artifact import ModelArtifact
from src.environment.models.Environment import Environment
from src.runs.models.run import Run, RunStatus
from src.notifications.email_service import notify_deployment
from src.deployments.cache_manager import touch_model

logger = logging.getLogger(__name__)

MODEL_SERVER_IMAGE = "moubakhta/orcaml-model-server:latest"
DOCKER_NETWORK          = "orcaml_orcaml_network"
MODELS_VOLUME_HOST_PATH = "/var/lib/docker/volumes/orcaml_models_data/_data"
BASE_HOST = "16.170.57.181.nip.io"
_docker_client = None


def _get_docker_client() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        try:
            _docker_client = docker.from_env()
            logger.info("Docker client connected successfully")
        except DockerException as e:
            logger.critical(f"Failed to connect to Docker daemon: {e}")
            raise
    return _docker_client


def build_labels(deployment_id: uuid.UUID) -> dict:
    """
    Labels read by Traefik automatically when the container starts.
    No config file, no reload needed.
    """
    name = f"model-{deployment_id}"
    return {
        # Tell Traefik to manage this container
        "traefik.enable": "true",

        # Router: match incoming requests by hostname
        f"traefik.http.routers.{name}.rule": f"Host(`{name}.{BASE_HOST}`)",

        # Use the web entrypoint (port 80)
        f"traefik.http.routers.{name}.entrypoints": "web",

        # Tell Traefik which port the container listens on internally
        f"traefik.http.services.{name}.loadbalancer.server.port": "8000",

        "traefik.docker.network": "orcaml_orcaml_network",
        # Custom labels for filtering our containers
        "orcaml.managed": "true",
        "orcaml.deployment_id": str(deployment_id),
    }

def list_downloadable_runs(environment_id: uuid.UUID, db: Session) -> list[Run]:
    return (
        db.query(Run)
        .filter(
            Run.environment_id == environment_id,
            Run.status == RunStatus.COMPLETED,
            Run.mlflow_run_id.isnot(None),
        )
        .order_by(Run.finished_at.desc())
        .all()
    )


def download_model_by_run(run_id: uuid.UUID, environment_id: uuid.UUID, db: Session) -> str:
    run = db.query(Run).filter(
        Run.id == run_id,
        Run.environment_id == environment_id, 
    ).first()

    if not run:
        raise ValueError(f"Run {run_id} not found in environment {environment_id}")
    if run.status != RunStatus.COMPLETED:
        raise ValueError(f"Run {run_id} is not COMPLETED")
    if not run.mlflow_run_id:
        raise ValueError(f"Run {run_id} has no mlflow_run_id")

    try:
        return download_model_artifact(run.mlflow_run_id)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Artifact not found in MLflow for run {run.mlflow_run_id}: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to download artifact: {e}")

def _prepare_features(features: dict, environment_id: uuid.UUID, db: Session) -> list[float]:
    environment = db.execute(
        select(Environment).where(Environment.id == environment_id)
    ).scalar_one_or_none()
    if not environment:
        raise ValueError(f"Environment {environment_id} introuvable.")
    target_column = environment.target_column

    cleaned_dataset = db.execute(
        select(CleanedDataset)
        .where(CleanedDataset.environment_id == environment_id, CleanedDataset.status == "ready")
        .order_by(desc(CleanedDataset.cleaned_at))
        .limit(1)
    ).scalar_one_or_none()
    if not cleaned_dataset:
        raise ValueError(f"Aucun CleanedDataset 'ready' pour l'environment {environment_id}.")

    cleaning_config = db.execute(
        select(CleaningConfig)
        .where(CleaningConfig.environment_id == environment_id)
        .order_by(desc(CleaningConfig.created_at))
        .limit(1)
    ).scalar_one_or_none()
    if not cleaning_config:
        raise ValueError(f"Aucune CleaningConfig pour l'environment {environment_id}.")

    raw_dataset = db.execute(
        select(Dataset)
        .where(Dataset.env_id == environment_id)
        .order_by(desc(Dataset.uploaded_at))
        .limit(1)
    ).scalar_one_or_none()
    if not raw_dataset:
        raise ValueError(f"Aucun Dataset brut pour l'environment {environment_id}.")

    try:
        client_s3 = get_s3_client()

        buffer_raw = BytesIO()
        client_s3.download_fileobj(settings.R2_BUCKET_NAME, raw_dataset.r2_path, buffer_raw)
        buffer_raw.seek(0)
        df_raw = pd.read_csv(buffer_raw)
        logger.debug(f"Dataset brut chargé — {df_raw.shape[0]} lignes")

        buffer_clean = BytesIO()
        client_s3.download_fileobj(settings.R2_BUCKET_NAME, cleaned_dataset.file_path, buffer_clean)
        buffer_clean.seek(0)
        df_reference  = pd.read_csv(buffer_clean)
        expected_cols = [c for c in df_reference.columns if c != target_column]
        logger.debug(f"Colonnes attendues ({len(expected_cols)}) : {expected_cols}")

    except Exception as e:
        raise RuntimeError(f"Impossible de charger les datasets depuis R2 : {e}")

    try:
        df_input = pd.DataFrame([features])
        df_input[target_column] = 0

        df_combined = pd.concat([df_raw, df_input], ignore_index=True)
        df_cleaned  = apply_cleaning(df_combined.copy(), cleaning_config, target_column)
        df_cleaned  = df_cleaned.iloc[[-1]]

        if target_column in df_cleaned.columns:
            df_cleaned = df_cleaned.drop(columns=[target_column])

        df_cleaned    = df_cleaned.reindex(columns=expected_cols, fill_value=0)
        features_list = df_cleaned.values[0].tolist()
        logger.debug(f"Features nettoyées — {len(features_list)} valeurs")
        return features_list

    except Exception as e:
        raise RuntimeError(f"Échec du preprocessing : {e}")


def deploy(run_id: uuid.UUID, environment_id: uuid.UUID, db: Session) -> Deployment:
    logger.info(f"Deploy requested — run_id={run_id}, environment_id={environment_id}")

    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ValueError(f"Run {run_id} not found")
    if run.status != RunStatus.COMPLETED:
        raise ValueError(f"Run {run_id} is not COMPLETED (current status: {run.status}).")
    if not run.mlflow_run_id:
        raise ValueError(f"Run {run_id} has no mlflow_run_id.")

    model_artifact = db.query(ModelArtifact).filter(ModelArtifact.run_id == run_id).first()

    if not model_artifact:
        if not verify_run_has_artifact(run.mlflow_run_id):
            raise ValueError(f"No artifact found in MLflow for run {run.mlflow_run_id}.")
        file_path = download_model_artifact(run.mlflow_run_id)
        touch_model(run.mlflow_run_id)
        model_artifact = ModelArtifact(
            run_id=run_id,
            environment_id=environment_id,
            algorithm=run.algorithm.value,
            mlflow_run_id=run.mlflow_run_id,
            file_path=file_path,
        )
        db.add(model_artifact)
        db.flush()
        logger.info(f"ModelArtifact created: id={model_artifact.id}")
    else:
        logger.info(f"ModelArtifact already exists: id={model_artifact.id} — reusing")

    deployment = Deployment(
        model_id=model_artifact.id,
        environment_id=environment_id,
        status=DeploymentStatus.DEPLOYING,
    )
    db.add(deployment)
    db.flush()  # generates deployment.id without committing

    try:
        client         = _get_docker_client()
        subdomain      = f"model-{deployment.id}"
        container_name = f"model-{deployment.id}"
        host_file_path = model_artifact.file_path.replace("/app/models", MODELS_VOLUME_HOST_PATH)

        container = client.containers.run(
            image=MODEL_SERVER_IMAGE,
            name=container_name,
            labels=build_labels(deployment.id),
            detach=True,
            network=DOCKER_NETWORK,
            # no ports mapping — Traefik handles routing internally
            volumes={host_file_path: {"bind": "/app/model.pkl", "mode": "ro"}},
            environment={
                "MODEL_ID":   str(model_artifact.id),
                "ALGORITHM":  model_artifact.algorithm,
                "MODEL_PATH": "/app/model.pkl",
            },
            restart_policy={"Name": "unless-stopped"},
        )

        deployment.container_id   = container.id
        deployment.container_name = container_name
        deployment.subdomain      = subdomain
        deployment.endpoint_url   = f"http://{subdomain}.{BASE_HOST}/predict"
        deployment.status         = DeploymentStatus.ACTIVE
        deployment.deployed_at    = datetime.now(timezone.utc)

        db.commit()
        db.refresh(deployment)
        logger.info(f"Deployment ACTIVE: id={deployment.id}, url={deployment.endpoint_url}")

        notify_deployment(db=db, deployment=deployment, success=True)

    except Exception as e:
        logger.error(f"Container startup failed: {e}", exc_info=True)
        deployment.status = DeploymentStatus.FAILED
        db.commit()
        notify_deployment(db=db, deployment=deployment, success=False)
        raise RuntimeError(f"Failed to start model container: {e}")

    return deployment


def undeploy(deployment_id: uuid.UUID, db: Session) -> Deployment:
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise ValueError(f"Deployment {deployment_id} not found")
    if deployment.status != DeploymentStatus.ACTIVE:
        raise ValueError(f"Deployment {deployment_id} is not ACTIVE (status: {deployment.status})")

    try:
        client    = _get_docker_client()
        container = client.containers.get(deployment.container_id)
        container.stop(timeout=10)
        container.remove()
        # Traefik automatically removes the route when container stops
        logger.info(f"Container {deployment.container_name} stopped and removed")
    except NotFound:
        logger.warning(f"Container {deployment.container_name} not found — marking STOPPED anyway")
    except DockerException as e:
        raise RuntimeError(f"Failed to stop container: {e}")

    deployment.status     = DeploymentStatus.STOPPED
    deployment.stopped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(deployment)
    return deployment


async def predict(deployment_id: uuid.UUID, features: dict, db: Session) -> dict:
    deployment = (
        db.query(Deployment)
        .options(joinedload(Deployment.model))
        .filter(Deployment.id == deployment_id)
        .first()
    )
    if not deployment:
        raise ValueError(f"Deployment {deployment_id} not found")
    if deployment.status != DeploymentStatus.ACTIVE:
        raise ValueError(f"Deployment {deployment_id} is not ACTIVE (status: {deployment.status})")

    try:
        features_list = _prepare_features(
            features=features,
            environment_id=deployment.environment_id,
            db=db,
        )
    except (ValueError, RuntimeError):
        raise
    except Exception as e:
        raise RuntimeError(f"Échec du preprocessing : {e}")

    # Internal Docker network call — use container_name directly, not the Traefik URL
    predict_url = f"http://{deployment.container_name}:8000/predict"
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(predict_url, json={"features": features_list})
            response.raise_for_status()
            result = response.json()
        latency_ms = (time.monotonic() - start) * 1000
        logger.debug(f"Predict latency: {latency_ms:.1f}ms")

    except httpx.TimeoutException:
        raise RuntimeError(f"Model container timed out — container {deployment.container_name}")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Model container returned an error: {e.response.text}")
    except Exception as e:
        raise RuntimeError(f"Failed to reach model container: {e}")

    # Update running average latency
    if deployment.avg_latency_ms is None:
        deployment.avg_latency_ms = latency_ms
    else:
        deployment.avg_latency_ms = (
            (deployment.avg_latency_ms * deployment.total_calls + latency_ms)
            / (deployment.total_calls + 1)
        )

    deployment.total_calls    += 1
    deployment.last_called_at  = datetime.now(timezone.utc)

    from src.deployments.models.prediction import Prediction
    prediction_record = Prediction(
        deployment_id    = deployment_id,
        input_features   = features,
        prediction       = result.get("prediction", []),
        prediction_label = result.get("prediction_label"),
        confidence       = result.get("confidence"),
    )
    db.add(prediction_record)
    db.commit()

    return {
        "deployment_id": str(deployment_id),
        "model_id":      str(deployment.model_id),
        "algorithm":     deployment.model.algorithm,
        **result,
    }


def get_logs(deployment_id: uuid.UUID, db: Session, tail: int = 100) -> list[str]:
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise ValueError(f"Deployment {deployment_id} not found")
    if not deployment.container_id:
        raise ValueError(f"Deployment {deployment_id} has no container.")

    try:
        client    = _get_docker_client()
        container = client.containers.get(deployment.container_id)
        raw_logs  = container.logs(tail=tail, timestamps=True).decode("utf-8")
        return [line for line in raw_logs.splitlines() if line.strip()]
    except NotFound:
        raise ValueError(f"Container {deployment.container_name} no longer exists")
    except DockerException as e:
        raise RuntimeError(f"Failed to fetch container logs: {e}")


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