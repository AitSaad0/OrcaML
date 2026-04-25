from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.runs.models.run import Algorithm, RunStatus


MAX_ALGORITHMS_PER_BATCH = 6
MAX_MANUAL_ATTEMPTS_PER_ALGO = 5


class RunCreate(BaseModel):
    algorithm: Algorithm
    hyperparameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom hyperparameters (uses defaults if not provided)",
    )
    test_size: Optional[float] = Field(default=0.2, ge=0.1, le=0.5)
    random_state: Optional[int] = Field(default=42)
    cross_validation: Optional[bool] = Field(default=False)
    cv_folds: Optional[int] = Field(default=5, ge=2, le=10)

    @field_validator("cv_folds")
    @classmethod
    def validate_cv_folds(cls, v, info):
        cross_validation = info.data.get("cross_validation", False)
        if cross_validation and v < 2:
            raise ValueError("cv_folds must be >= 2 when cross_validation is True")
        return v


class BatchRunCreate(BaseModel):
    algorithms: List[Algorithm] = Field(min_length=1, max_length=MAX_ALGORITHMS_PER_BATCH)
    hyperparameters: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="HP par algo, ex: {'RANDOM_FOREST': {'n_estimators': 200}}",
    )
    test_size: Optional[float] = Field(default=0.2, ge=0.1, le=0.5)
    random_state: Optional[int] = Field(default=42)
    cross_validation: Optional[bool] = Field(default=False)
    cv_folds: Optional[int] = Field(default=5, ge=2, le=10)


class AutoRunCreate(BaseModel):
    algorithms: List[Algorithm] = Field(min_length=1, max_length=MAX_ALGORITHMS_PER_BATCH)
    test_size: Optional[float] = Field(default=0.2, ge=0.1, le=0.5)
    random_state: Optional[int] = Field(default=42)
    cross_validation: Optional[bool] = Field(default=False)
    cv_folds: Optional[int] = Field(default=5, ge=2, le=10)


class TrainingConfigResponse(BaseModel):
    id: UUID
    algorithm: Algorithm
    hyperparameters: Dict[str, Any]
    test_size: float
    random_state: int
    cross_validation: bool
    cv_folds: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RunResponse(BaseModel):
    id: UUID
    environment_id: UUID
    algorithm: Algorithm
    status: RunStatus
    duration_seconds: Optional[float] = None
    mlflow_run_id: Optional[str] = None
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    training_config: Optional[TrainingConfigResponse] = None

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    id: UUID
    environment_id: UUID
    algorithm: Algorithm
    status: RunStatus
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    duration_seconds: Optional[float] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BatchRunResponse(BaseModel):
    runs: List[RunResponse]
    total: int
    message: str


class CancelRunResponse(BaseModel):  
    id: UUID
    status: RunStatus
    message: str


class BestAutoRunResponse(BaseModel):  
    id: UUID
    algorithm: Algorithm
    f1_score: Optional[float] = None
    training_config: TrainingConfigResponse

    model_config = {"from_attributes": True}