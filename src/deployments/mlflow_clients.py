import os
import logging
import mlflow
from mlflow.tracking import MlflowClient
from pathlib import Path
from src.deployments.cache_manager import touch_model, _find_pkl

logger = logging.getLogger(__name__)
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODELS_BASE_DIR     = os.getenv("MODELS_BASE_DIR", "/app/models")

def _get_client() -> MlflowClient:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    return MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)

def download_model_artifact(mlflow_run_id: str) -> str:
    dst_dir = Path(MODELS_BASE_DIR) / mlflow_run_id
    dst_dir.mkdir(parents=True, exist_ok=True)
    
    existing_pkl = _find_pkl(dst_dir)
    if existing_pkl:
        touch_model(mlflow_run_id) # Update LRU
        return str(existing_pkl)

    client = _get_client()
    local_path = client.download_artifacts(run_id=mlflow_run_id, path="model_artifact", dst_path=str(dst_dir))
    
    pkl_path = _find_pkl(Path(local_path))
    if not pkl_path:
        raise FileNotFoundError(f"No .pkl found for run {mlflow_run_id}")
    
    touch_model(mlflow_run_id)
    return str(pkl_path)

def verify_run_has_artifact(mlflow_run_id: str) -> bool:
    try:
        client = _get_client()
        return len(client.list_artifacts(mlflow_run_id, path="model_artifact")) > 0
    except Exception:
        return False