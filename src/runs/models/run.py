import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.config.db import Base


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Algorithm(str, Enum):
    LOGISTIC_REGRESSION = "LOGISTIC_REGRESSION"
    RANDOM_FOREST = "RANDOM_FOREST"
    SVM = "SVM"
    DECISION_TREE = "DECISION_TREE"
    LINEAR_REGRESSION = "LINEAR_REGRESSION"
    KNN = "KNN"


#  Intervalles autorisés pour chaque hyperparamètre
HP_BOUNDS = {
    Algorithm.RANDOM_FOREST: {
        "n_estimators": {"min": 10,   "max": 500,  "default": 100, "type": "int"},
        "max_depth":    {"min": 1,    "max": 50,   "default": 10,  "type": "int"},
    },
    Algorithm.SVM: {
        "C":            {"min": 0.01, "max": 100.0, "default": 1.0, "type": "float"},
        "kernel": {"values": ["rbf", "linear", "poly"], "default": "rbf", "type": "str"},
    },
    Algorithm.KNN: {
        "n_neighbors":  {"min": 1,    "max": 20,   "default": 5,   "type": "int"},
    },
    Algorithm.LOGISTIC_REGRESSION: {
        "C":            {"min": 0.01, "max": 100.0, "default": 1.0,  "type": "float"},
        "max_iter":     {"min": 100,  "max": 5000,  "default": 1000, "type": "int"},
    },
    Algorithm.DECISION_TREE: {
        "max_depth":    {"min": 1,    "max": 50,   "default": 10,  "type": "int"},
    },
    Algorithm.LINEAR_REGRESSION: {
        "fit_intercept": {"values": [True, False], "default": True, "type": "bool"},
    },
}


class Run(Base):
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    environment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    algorithm = Column(SQLEnum(Algorithm), nullable=False)
    status = Column(SQLEnum(RunStatus), default=RunStatus.PENDING, nullable=False, index=True)

    mlflow_run_id = Column(String(255), nullable=True)
    celery_task_id = Column(String(255), unique=True, nullable=True)

    accuracy = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    is_manual = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    environment = relationship("Environment", back_populates="runs")

    training_config = relationship(
        "TrainingConfig",
        back_populates="run",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TrainingConfig(Base):
    __tablename__ = "training_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, unique=True)

    algorithm = Column(SQLEnum(Algorithm), nullable=False)
    hyperparameters = Column(JSON, nullable=False, default=dict)
    test_size = Column(Float, nullable=False, default=0.2)
    random_state = Column(Integer, nullable=False, default=42)
    cross_validation = Column(Boolean, nullable=False, default=False)
    cv_folds = Column(Integer, nullable=False, default=5)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    run = relationship("Run", back_populates="training_config")
   # Recupère les hyperparamètres par défaut pour un algorithme donné
    @staticmethod
    def get_default_hyperparameters(algorithm: Algorithm) -> dict:
      bounds = HP_BOUNDS.get(algorithm, {})
      return {
        param: meta["default"]
        for param, meta in bounds.items()
        if "default" in meta
      }
     # sert à faire une recherche automatique des meilleures combinaisons.
    @staticmethod
    def get_hyperparameter_grid(algorithm: Algorithm) -> dict:
        grids = {
            Algorithm.RANDOM_FOREST: {
                "n_estimators": [100, 200, 500],
                "max_depth": [5, 10, 15],
            },
            Algorithm.SVM: {
                "kernel": ["rbf", "linear" , "poly"],
                "C": [0.1, 1.0, 10.0],
            },
            Algorithm.KNN: {
                "n_neighbors": [3, 5, 10],
            },
            Algorithm.LOGISTIC_REGRESSION: {
                "C": [0.1, 1.0, 10.0],
                "max_iter": [100, 500, 1000],
            },
            Algorithm.DECISION_TREE: {
                "max_depth": [5, 10, 15],
            },
            Algorithm.LINEAR_REGRESSION: {
                "fit_intercept": [True, False],
            },
        }
        return grids.get(algorithm, {})