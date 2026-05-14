"""
run.py — Modèles SQLAlchemy pour les runs d'entraînement.

Ce module définit :
- Les enums `RunStatus` et `Algorithm` utilisés dans toute l'application.
- `HP_BOUNDS` : les bornes de hyperparamètres pour le Random Search.
- Les modèles ORM : `Run`, `TrainingConfig`, `ModelArtifact`.
"""

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


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RunStatus(str, Enum):
    """Cycle de vie d'un run d'entraînement.

    Transitions valides :
        PENDING → RUNNING → COMPLETED
                          → FAILED
                          → CANCELLED
    """
    PENDING   = "PENDING"    # En attente dans la queue Celery
    RUNNING   = "RUNNING"    # Tâche Celery en cours d'exécution
    COMPLETED = "COMPLETED"  # Entraînement terminé avec succès
    FAILED    = "FAILED"     # Erreur pendant l'entraînement
    CANCELLED = "CANCELLED"  # Annulé manuellement via POST /cancel


class Algorithm(str, Enum):
    """Algorithmes ML supportés par OrcaML.

    Chaque valeur correspond à une clé dans HP_BOUNDS et dans les
    MODEL_MAPPING de run_tasks.py (classification et régression).
    """
    LOGISTIC_REGRESSION = "LOGISTIC_REGRESSION"
    RANDOM_FOREST       = "RANDOM_FOREST"
    SVM                 = "SVM"
    DECISION_TREE       = "DECISION_TREE"
    LINEAR_REGRESSION   = "LINEAR_REGRESSION"
    KNN                 = "KNN"
    XGBOOST             = "XGBOOST"


# ---------------------------------------------------------------------------
# Bornes des hyperparamètres pour le Random Search
# ---------------------------------------------------------------------------

# Structure par algorithme :
#   { "param_name": { "type": <type>, ...champs selon type } }
#
# Types supportés (Bergstra & Bengio, 2012) :
#   "int"       → randint(min, max)
#   "float"     → uniform(min, max)
#   "log_float" → exp(uniform(log(min), log(max)))
#                 À privilégier pour les paramètres à échelle logarithmique
#                 comme C (SVM) ou learning_rate (XGBoost).
#                 Ex : C ∈ [0.01, 100] → moyenne géométrique = 1.0 (correct)
#                                      → moyenne arithmétique = 50 (biaisée)
#   "choice"    → random.choice(values)
HP_BOUNDS = {
    Algorithm.RANDOM_FOREST: {
        "n_estimators": {"min": 10,  "max": 500, "type": "int"},
        "max_depth":    {"min": 1,   "max": 50,  "type": "int"},
    },
    Algorithm.SVM: {
        # C contrôle le compromis biais/variance → échelle log obligatoire
        "C":      {"min": 0.01, "max": 100.0, "type": "log_float"},
        "kernel": {"values": ["rbf", "linear", "poly"], "type": "choice"},
    },
    Algorithm.KNN: {
        "n_neighbors": {"min": 1, "max": 20, "type": "int"},
    },
    Algorithm.LOGISTIC_REGRESSION: {
        "C":        {"min": 0.01, "max": 100.0, "type": "log_float"},
        "max_iter": {"min": 100,  "max": 5000,  "type": "int"},
    },
    Algorithm.DECISION_TREE: {
        "max_depth": {"min": 1, "max": 50, "type": "int"},
    },
    Algorithm.LINEAR_REGRESSION: {
        # Seul hyperparamètre exposé : présence ou non de l'intercept
        "fit_intercept": {"values": [True, False], "type": "choice"},
    },
    Algorithm.XGBOOST: {
        "n_estimators":  {"min": 10,   "max": 500,  "type": "int"},
        "max_depth":     {"min": 1,    "max": 10,   "type": "int"},
        # learning_rate sur échelle log : 0.01 et 0.5 sont équidistants
        "learning_rate": {"min": 0.01, "max": 0.5,  "type": "log_float"},
        # subsample : fraction des observations utilisées par arbre
        "subsample":     {"min": 0.5,  "max": 1.0,  "type": "float"},
    },
}


# ---------------------------------------------------------------------------
# Modèle Run
# ---------------------------------------------------------------------------

class Run(Base):
    """Représente une exécution d'entraînement ML dans un environnement.

    Un Run est créé via POST /runs/batch ou POST /runs/auto.
    Il est lié à un Environment (workspace projet) et contient :
    - les métriques calculées après l'entraînement,
    - les références vers MLflow (mlflow_run_id) et Celery (celery_task_id),
    - les timestamps pour mesurer la durée réelle.
    """
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Clé étrangère vers l'environnement parent (suppression en cascade)
    environment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # Indexé pour accélérer les requêtes filtrées par env
    )

    algorithm = Column(SQLEnum(Algorithm), nullable=False)
    status    = Column(SQLEnum(RunStatus), default=RunStatus.PENDING, nullable=False, index=True)

    # Identifiant MLflow pour retrouver les artefacts du modèle
    mlflow_run_id  = Column(String(255), nullable=True)
    # Identifiant Celery pour pouvoir révoquer la tâche (cancel)
    celery_task_id = Column(String(255), unique=True, nullable=True)

    # --- Métriques classification (null si régression) ---
    accuracy  = Column(Float, nullable=True)
    f1_score  = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall    = Column(Float, nullable=True)

    # --- Métriques régression (null si classification) ---
    rmse = Column(Float, nullable=True)  # Root Mean Squared Error
    mae  = Column(Float, nullable=True)  # Mean Absolute Error
    r2   = Column(Float, nullable=True)  # Coefficient de détermination R²

    duration_seconds = Column(Float, nullable=True)  # Durée totale de l'entraînement

    # True = run créé manuellement (soumis à la limite MAX_MANUAL_ATTEMPTS_PER_ALGO)
    # False = run créé via auto/random search (illimité)
    is_manual = Column(Boolean, default=True, nullable=False)

    # Timestamps pour le suivi du cycle de vie
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at  = Column(DateTime(timezone=True), nullable=True)   # Rempli au début de la tâche Celery
    finished_at = Column(DateTime(timezone=True), nullable=True)   # Rempli à la fin (succès ou échec)

    # Relations ORM
    environment    = relationship("Environment", back_populates="runs")
    training_config = relationship(
        "TrainingConfig",
        back_populates="run",
        uselist=False,          # Relation 1-to-1
        cascade="all, delete-orphan",
    )
    model_artifact = relationship(
        "ModelArtifact",
        back_populates="run",
        uselist=False,          # Relation 1-to-1
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Modèle TrainingConfig
# ---------------------------------------------------------------------------

class TrainingConfig(Base):
    """Configuration d'entraînement associée à un Run (relation 1-to-1).

    Stocke les hyperparamètres choisis (manuellement ou via random search),
    les options de split train/test, et la configuration de cross-validation.
    Créée en même temps que le Run, avant le démarrage de la tâche Celery.
    """
    __tablename__ = "training_configs"

    id     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # Garantit la relation 1-to-1 au niveau DB
    )

    algorithm        = Column(SQLEnum(Algorithm), nullable=False)
    hyperparameters  = Column(JSON, nullable=False, default=dict)  # Dict HP → valeur
    test_size        = Column(Float,   nullable=False, default=0.2)   # Ex: 0.2 = 20% test
    random_state     = Column(Integer, nullable=False, default=42)    # Reproductibilité
    cross_validation = Column(Boolean, nullable=False, default=False) # Activer la CV
    cv_folds         = Column(Integer, nullable=False, default=5)     # Nombre de folds (k)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    run = relationship("Run", back_populates="training_config")

    @staticmethod
    def get_default_hyperparameters(algorithm: Algorithm) -> dict:
        """Calcule les hyperparamètres par défaut pour un algorithme donné.

        Stratégie par type :
        - "choice"              → première valeur de la liste
        - "int"                 → valeur minimale de la plage
        - "float" / "log_float" → moyenne arithmétique arrondie à 4 décimales
                                  (approximation raisonnable ; pour log_float,
                                   la moyenne géométrique serait plus correcte
                                   mais reste acceptable pour un défaut UI)

        Args:
            algorithm: L'algorithme pour lequel générer les HP par défaut.

        Returns:
            Un dict { nom_param: valeur_défaut }.
            Retourne {} si l'algorithme n'a pas de bornes définies dans HP_BOUNDS.
        """
        bounds = HP_BOUNDS.get(algorithm, {})
        defaults = {}
        for param, meta in bounds.items():
            if meta["type"] == "choice":
                defaults[param] = meta["values"][0]
            elif meta["type"] == "int":
                defaults[param] = meta["min"]
            elif meta["type"] in ("float", "log_float"):
                defaults[param] = round((meta["min"] + meta["max"]) / 2, 4)
        return defaults

    @staticmethod
    def is_regression_algorithm(algorithm: Algorithm) -> bool:
        """Indique si un algorithme est exclusivement de régression.

        Utilisé dans run_tasks.py pour choisir les bonnes métriques à calculer :
          - True  → calculer rmse, mae, r2
          - False → calculer accuracy, f1_score, precision, recall

        Note : XGBOOST n'est pas dans REGRESSION_ONLY car il supporte les deux modes
        (classification ET régression selon task_type) — le choix se fait au niveau du Run.

        Args:
            algorithm: L'algorithme à tester.

        Returns:
            True si l'algorithme est de régression pure, False sinon.

        Exemple:
            >>> TrainingConfig.is_regression_algorithm(Algorithm.LINEAR_REGRESSION)
            True
            >>> TrainingConfig.is_regression_algorithm(Algorithm.RANDOM_FOREST)
            False
        """
        REGRESSION_ONLY = {Algorithm.LINEAR_REGRESSION}
        return algorithm in REGRESSION_ONLY