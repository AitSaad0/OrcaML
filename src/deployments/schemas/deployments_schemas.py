from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.deployments.models.enums import DeploymentStatus


# ── Request schemas ───────────────────────────────────────────────────────────

class DeployRequest(BaseModel):
    """Body for POST /deployments — only run_id needed, we fetch everything else."""
    run_id: UUID


class PredictRequest(BaseModel):
    """Body for POST /deployments/{id}/predict.
    
    features : dict des colonnes brutes (avant cleaning), exactement comme
               elles sortiraient d'un formulaire ou d'un CSV non nettoyé.
    
    Exemple :
        {
            "age": 25,
            "salary": 50000,
            "city": "Paris",
            "department": "Finance"
        }
    
    Le cleaning (encoding, scaling, one-hot) est appliqué automatiquement
    par le backend avant d'envoyer au container Docker.
    """
    features: dict[str, Any]  # ← raw features (pas de list[float])


# ── Response schemas ──────────────────────────────────────────────────────────

class ModelArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:             UUID
    run_id:         UUID
    environment_id: UUID
    algorithm:      str
    mlflow_run_id:  str
    file_path:      str | None
    created_at:     datetime


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:             UUID
    model_id:       UUID
    environment_id: UUID
    status:         DeploymentStatus
    endpoint_url:   str | None
    port:           int | None
    total_calls:    int
    last_called_at: datetime | None
    created_at:     datetime
    deployed_at:    datetime | None
    stopped_at:     datetime | None
    avg_latency_ms: float | None = None
    # Nested model info — useful for the frontend
    model: ModelArtifactResponse


class PredictResponse(BaseModel):
    deployment_id:    UUID
    model_id:         UUID
    algorithm:        str
    prediction:       list[Any]      # ← Any car classification (int) ou régression (float)
    prediction_label: str | None = None


class LogsResponse(BaseModel):
    deployment_id: UUID
    logs:          list[str]