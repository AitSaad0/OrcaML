import os
import pickle
import logging
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config from environment ───────────────────────────────────────────────────
MODEL_PATH = os.getenv("MODEL_PATH", "/app/model.pkl")
MODEL_ID   = os.getenv("MODEL_ID", "unknown")
ALGORITHM  = os.getenv("ALGORITHM", "unknown")

# ── Load model at startup ─────────────────────────────────────────────────────
model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    logger.info(f"Loading model from {MODEL_PATH} ...")
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Model file not found at {MODEL_PATH}")
        raise RuntimeError(f"Model file not found: {MODEL_PATH}")
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    logger.info(f"Model loaded successfully — algorithm: {ALGORITHM}, id: {MODEL_ID}")
    yield
    logger.info("Shutting down model server")


app = FastAPI(
    title=f"Model Server — {ALGORITHM}",
    description=f"Inference API for model {MODEL_ID}",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Schemas ───────────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    features: list[float]  # flat list of feature values

class PredictResponse(BaseModel):
    model_id: str
    algorithm: str
    prediction: list        # list so it works for single value and multi-output
    prediction_label: str | None = None  # human readable if available


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Health check — used by your app to confirm container is ready."""
    return {
        "status": "ok",
        "model_id": MODEL_ID,
        "algorithm": ALGORITHM,
        "model_loaded": model is not None,
    }


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    """
    Run inference on the loaded model.
    Expects a flat list of feature values in the same order as training.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        features = np.array(request.features).reshape(1, -1)
        prediction = model.predict(features)
        prediction_list = prediction.tolist()

        # Try to get human-readable label if model has classes
        label = None
        if hasattr(model, "classes_"):
            label = str(model.classes_[prediction_list[0]])

        logger.info(f"Prediction made — input shape: {features.shape}, output: {prediction_list}")

        return PredictResponse(
            model_id=MODEL_ID,
            algorithm=ALGORITHM,
            prediction=prediction_list,
            prediction_label=label,
        )

    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


@app.get("/info")
def info():
    """Returns metadata about the loaded model."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    info_data = {
        "model_id": MODEL_ID,
        "algorithm": ALGORITHM,
        "model_type": type(model).__name__,
    }

    # Add available metadata if present
    if hasattr(model, "classes_"):
        info_data["classes"] = model.classes_.tolist()
    if hasattr(model, "n_features_in_"):
        info_data["n_features"] = model.n_features_in_
    if hasattr(model, "feature_names_in_"):
        info_data["feature_names"] = model.feature_names_in_.tolist()

    return info_data