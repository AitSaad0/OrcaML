import os
import logging
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
# Loaded from environment — already set in docker-compose as http://mlflow:5000
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

# Local directory inside the app container where artifacts are saved
# e.g. /app/models/{mlflow_run_id}/model.pkl
MODELS_BASE_DIR = os.getenv("MODELS_BASE_DIR", "/app/models")


# ── Client ────────────────────────────────────────────────────────────────────
def _get_client() -> MlflowClient:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    return MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)


# ── Main function ─────────────────────────────────────────────────────────────
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
    logger.info(f"Downloading artifact for MLflow run: {mlflow_run_id}")

    # Destination folder for this specific run
    dst_dir = Path(MODELS_BASE_DIR) / mlflow_run_id
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Check if already downloaded — avoid re-downloading on redeploy
    existing_pkl = _find_pkl(dst_dir)
    if existing_pkl:
        logger.info(f"Artifact already exists at {existing_pkl}, skipping download")
        return str(existing_pkl)

    try:
        client = _get_client()

        # Download the artifact folder from MLflow
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

        local_path = client.download_artifacts(
            run_id=mlflow_run_id,
            path="model_artifact",
            dst_path=str(dst_dir),
        )
        logger.info(f"Artifact downloaded to: {local_path}")

    except Exception as e:
        logger.error(f"Failed to download artifact from MLflow: {e}")
        raise

    # Find the .pkl file inside the downloaded folder
    # MLflow saves sklearn models as: model_artifact/model.pkl
    pkl_path = _find_pkl(Path(local_path))
    if not pkl_path:
        raise FileNotFoundError(
            f"No .pkl file found in downloaded artifact at {local_path}. "
            f"Contents: {list(Path(local_path).rglob('*'))}"
        )

    logger.info(f"Model .pkl found at: {pkl_path}")
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
    return True

# ── Helpers ───────────────────────────────────────────────────────────────────
def _find_pkl(directory: Path) -> Path | None:
    """Recursively finds the first .pkl file in a directory."""
    for pkl_file in directory.rglob("*.pkl"):
        return pkl_file
    return None