import os
import logging
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODELS_BASE_DIR     = os.getenv("MODELS_BASE_DIR", "/app/models")

logger.debug(f"MLflow config — tracking_uri={MLFLOW_TRACKING_URI}, models_base_dir={MODELS_BASE_DIR}")


# ── Client ────────────────────────────────────────────────────────────────────
def _get_client() -> MlflowClient:
    logger.debug(f"Initializing MlflowClient with tracking_uri={MLFLOW_TRACKING_URI}")
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    logger.debug("MlflowClient created successfully")
    return client


# ── Main functions ────────────────────────────────────────────────────────────
def download_model_artifact(mlflow_run_id: str) -> str:
    """
    Downloads the trained model artifact from MLflow and saves it locally.

    Flow:
      1. Connect to MLflow tracking server
      2. Download the artifact folder 'model_artifact' for the given run
      3. Find the .pkl file inside the downloaded folder
      4. Return the absolute path to the .pkl file

    Args:
        mlflow_run_id: The MLflow run ID stored in the Run table

    Returns:
        Absolute path to the downloaded model.pkl file
        e.g. /app/models/{mlflow_run_id}/model.pkl

    Raises:
        FileNotFoundError: if no .pkl file is found after download
        Exception: if MLflow download fails
    """
    logger.info(f"download_model_artifact called — mlflow_run_id={mlflow_run_id}")

    dst_dir = Path(MODELS_BASE_DIR) / mlflow_run_id
    logger.debug(f"Target directory for artifact: {dst_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Directory ensured (created or already existed): {dst_dir}")

    # Check if already downloaded — avoid re-downloading on redeploy
    logger.debug(f"Checking for existing .pkl in {dst_dir}")
    existing_pkl = _find_pkl(dst_dir)
    if existing_pkl:
        logger.info(f"Artifact already cached at {existing_pkl} — skipping download")
        return str(existing_pkl)

    logger.debug(f"No cached artifact found — proceeding with MLflow download")

    try:
        client = _get_client()
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

        logger.debug(
            f"Calling client.download_artifacts — "
            f"run_id={mlflow_run_id}, path='model_artifact', dst_path={dst_dir}"
        )
        local_path = client.download_artifacts(
            run_id=mlflow_run_id,
            path="model_artifact",
            dst_path=str(dst_dir),
        )
        logger.info(f"MLflow artifact downloaded successfully to: {local_path}")
        logger.debug(f"Downloaded directory contents: {list(Path(local_path).rglob('*'))}")

    except Exception as e:
        logger.error(
            f"Failed to download artifact from MLflow for run {mlflow_run_id}: {e}",
            exc_info=True,
        )
        raise

    # Find the .pkl inside the downloaded folder
    logger.debug(f"Scanning for .pkl file inside {local_path}")
    pkl_path = _find_pkl(Path(local_path))

    if not pkl_path:
        contents = list(Path(local_path).rglob("*"))
        logger.error(
            f"No .pkl file found after download for run {mlflow_run_id}. "
            f"local_path={local_path}, contents={contents}"
        )
        raise FileNotFoundError(
            f"No .pkl file found in downloaded artifact at {local_path}. "
            f"Contents: {contents}"
        )

    logger.info(f"Model .pkl located at: {pkl_path}")
    logger.debug(f"pkl file size: {pkl_path.stat().st_size} bytes")
    return str(pkl_path)


def verify_run_has_artifact(mlflow_run_id: str) -> bool:
    """
    Checks if a run has a model artifact saved in MLflow.
    Use this before attempting a download.

    Args:
        mlflow_run_id: The MLflow run ID to check

    Returns:
        True if artifact exists, False otherwise
    """
    logger.debug(f"verify_run_has_artifact called — mlflow_run_id={mlflow_run_id}")

    try:
        client = _get_client()
        artifacts = client.list_artifacts(mlflow_run_id, path="model_artifact")
        logger.debug(f"MLflow artifacts listed for run {mlflow_run_id}: {artifacts}")

        if not artifacts:
            logger.warning(f"No artifacts found under 'model_artifact' for run {mlflow_run_id}")
            return False

        logger.info(f"Artifact verified — run {mlflow_run_id} has {len(artifacts)} artifact(s) under 'model_artifact'")
        return True

    except Exception as e:
        logger.error(
            f"Failed to verify artifacts for MLflow run {mlflow_run_id}: {e}",
            exc_info=True,
        )
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────
def _find_pkl(directory: Path) -> Path | None:
    """Recursively finds the first .pkl file in a directory."""
    logger.debug(f"_find_pkl scanning: {directory}")

    for pkl_file in directory.rglob("*.pkl"):
        logger.debug(f"Found .pkl: {pkl_file}")
        return pkl_file

    logger.debug(f"No .pkl found in {directory}")
    return None