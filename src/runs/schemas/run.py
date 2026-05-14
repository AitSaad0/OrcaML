"""
run_schemas.py — Schémas Pydantic pour les runs d'entraînement.

Séparation des responsabilités :
  - Schémas d'entrée  (Create) : valident les données reçues par l'API.
  - Schémas de sortie (Response) : sérialisent les objets ORM vers JSON.

Constantes métier exposées ici pour être partagées entre le router et le service :
  MAX_ALGORITHMS_PER_BATCH     = 6
  MAX_MANUAL_ATTEMPTS_PER_ALGO = 5
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.runs.models.run import Algorithm, RunStatus


# ---------------------------------------------------------------------------
# Constantes métier
# ---------------------------------------------------------------------------

# Nombre maximum d'algorithmes acceptés dans un seul appel batch ou auto
MAX_ALGORITHMS_PER_BATCH     = 6
# Nombre maximum de runs manuels autorisés par algorithme et par environnement
# (ne s'applique pas aux runs auto / random search)
MAX_MANUAL_ATTEMPTS_PER_ALGO = 5


# ---------------------------------------------------------------------------
# Schémas d'entrée — Création de runs
# ---------------------------------------------------------------------------

class RunCreate(BaseModel):
    """Schéma de base pour créer un run unique.

    Utilisé comme fondation par BatchRunCreate et directement dans les tests.
    Les hyperparamètres sont optionnels : si absents, TrainingConfig.get_default_hyperparameters()
    sera appelé dans le service pour fournir des valeurs par défaut.
    """

    algorithm: Algorithm
    hyperparameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="HP personnalisés — utilise les valeurs par défaut si absent.",
    )
    test_size:        Optional[float] = Field(default=0.2, ge=0.1, le=0.5)   # Proportion du jeu de test [10%-50%]
    random_state:     Optional[int]   = Field(default=42)                      # Graine pour la reproductibilité
    cross_validation: Optional[bool]  = Field(default=False)                  # Activer la validation croisée
    cv_folds:         Optional[int]   = Field(default=5, ge=2, le=10)         # Nombre de folds k (si CV activée)

    @field_validator("cv_folds")
    @classmethod
    def validate_cv_folds(cls, v, info):
        """Vérifie que cv_folds >= 2 lorsque cross_validation est activée.

        Pydantic valide les champs dans l'ordre de déclaration, donc
        cross_validation est déjà résolu dans info.data quand ce validateur s'exécute.
        """
        if info.data.get("cross_validation", False) and v < 2:
            raise ValueError("cv_folds must be >= 2 when cross_validation is True")
        return v


class BatchRunCreate(BaseModel):
    """Corps de requête pour POST /runs/batch.

    Crée un run manuel par algorithme listé.
    Les hyperparamètres sont indexés par nom d'algorithme pour permettre
    une configuration fine par algo dans le même appel.

    Exemple :
        {
            "algorithms": ["RANDOM_FOREST", "XGBOOST"],
            "hyperparameters": {
                "RANDOM_FOREST": {"n_estimators": 200},
                "XGBOOST":       {"learning_rate": 0.05}
            }
        }
    """

    algorithms: List[Algorithm] = Field(
        min_length=1,
        max_length=MAX_ALGORITHMS_PER_BATCH,
        description=f"Entre 1 et {MAX_ALGORITHMS_PER_BATCH} algorithmes.",
    )
    hyperparameters: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="HP par algo, ex: {'RANDOM_FOREST': {'n_estimators': 200}}",
    )
    test_size:        Optional[float] = Field(default=0.2, ge=0.1, le=0.5)
    random_state:     Optional[int]   = Field(default=42)
    cross_validation: Optional[bool]  = Field(default=False)
    cv_folds:         Optional[int]   = Field(default=5, ge=2, le=10)


class AutoRunCreate(BaseModel):
    """Corps de requête pour POST /runs/auto (Random Search).

    Génère n_iter combinaisons d'hyperparamètres par algorithme, échantillonnées
    aléatoirement selon les distributions définies dans HP_BOUNDS (run.py).
    Les runs créés ont is_manual=False et ne sont pas soumis à MAX_MANUAL_ATTEMPTS_PER_ALGO.
    """

    algorithms: List[Algorithm] = Field(
        min_length=1,
        max_length=MAX_ALGORITHMS_PER_BATCH,
    )
    n_iter: int = Field(
        default=10,
        ge=5,
        le=50,
        description="Nombre de combinaisons HP à tester par algorithme.",
    )
    test_size:        Optional[float] = Field(default=0.2, ge=0.1, le=0.5)
    random_state:     Optional[int]   = Field(default=42)
    cross_validation: Optional[bool]  = Field(default=False)
    cv_folds:         Optional[int]   = Field(default=5, ge=2, le=10)


# ---------------------------------------------------------------------------
# Schémas de sortie — Réponses API
# ---------------------------------------------------------------------------

class TrainingConfigResponse(BaseModel):
    """Représentation sérialisée d'une TrainingConfig liée à un Run.

    Inclus dans RunResponse pour donner le détail complet de la configuration
    utilisée lors de l'entraînement.
    """

    id:               UUID
    algorithm:        Algorithm
    hyperparameters:  Dict[str, Any]   # HP effectivement utilisés (après résolution des défauts)
    test_size:        float
    random_state:     int
    cross_validation: bool
    cv_folds:         int
    created_at:       datetime

    model_config = {"from_attributes": True}  # Permet la conversion depuis un objet ORM SQLAlchemy


class RunResponse(BaseModel):
    """Réponse complète pour un run unique (GET /{run_id}, POST /batch, POST /auto).

    Les métriques sont mutuellement exclusives selon task_type :
    - Classification → accuracy, f1_score, precision, recall (rmse/mae/r2 = null)
    - Régression     → rmse, mae, r2 (accuracy/f1/precision/recall = null)
    """

    id:             UUID
    environment_id: UUID
    algorithm:      Algorithm
    status:         RunStatus

    duration_seconds: Optional[float] = None  # Null tant que le run n'est pas terminé
    mlflow_run_id:    Optional[str]   = None  # Null tant que le run n'a pas démarré

    # Métriques classification (null si tâche de régression)
    accuracy:  Optional[float] = None
    f1_score:  Optional[float] = None
    precision: Optional[float] = None
    recall:    Optional[float] = None

    # Métriques régression (null si tâche de classification)
    rmse: Optional[float] = None  # Root Mean Squared Error
    mae:  Optional[float] = None  # Mean Absolute Error
    r2:   Optional[float] = None  # Coefficient de détermination R²

    created_at:  datetime
    started_at:  Optional[datetime] = None   # Rempli au démarrage de la tâche Celery
    finished_at: Optional[datetime] = None   # Rempli à la fin (succès ou échec)

    training_config: Optional[TrainingConfigResponse] = None

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    """Réponse allégée pour GET / (liste de runs).

    Exclut training_config et les métriques détaillées (precision, recall)
    pour réduire la taille des réponses sur les listes potentiellement longues.
    """

    id:             UUID
    environment_id: UUID
    algorithm:      Algorithm
    status:         RunStatus

    # Métriques résumées — classification
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None

    # Métriques résumées — régression
    rmse: Optional[float] = None
    mae:  Optional[float] = None
    r2:   Optional[float] = None

    duration_seconds: Optional[float] = None
    created_at:       datetime
    finished_at:      Optional[datetime] = None

    model_config = {"from_attributes": True}


class BatchRunResponse(BaseModel):
    """Réponse pour POST /batch et POST /auto.

    `total` peut être inférieur au nombre d'algorithmes demandés si certains
    runs ont été rejetés (limite MAX_MANUAL_ATTEMPTS_PER_ALGO atteinte, etc.).
    Le champ `message` fournit un résumé lisible du résultat.
    """

    runs:    List[RunResponse]
    total:   int
    message: str


class CancelRunResponse(BaseModel):
    """Réponse pour POST /{run_id}/cancel."""

    id:      UUID
    status:  RunStatus  # Toujours CANCELLED si la requête a réussi
    message: str


class BestAutoRunResponse(BaseModel):
    """Réponse pour GET /best-auto et GET /best-manual.

    Retourne uniquement les métriques clés et la config d'entraînement
    pour identifier rapidement le meilleur run sans surcharger la réponse.

    ⚠️  Pour la régression, f1_score est null — le tri par r2 ou rmse
    n'est pas encore implémenté (voir Phase 4 — open questions).
    """

    id:        UUID
    algorithm: Algorithm

    # Métrique principale classification
    f1_score: Optional[float] = None

    # Métriques régression
    rmse: Optional[float] = None
    mae:  Optional[float] = None
    r2:   Optional[float] = None

    training_config: TrainingConfigResponse  # Toujours présent (non optionnel)

    model_config = {"from_attributes": True}



class RunPredictRequest(BaseModel):
    """Corps de requête pour POST /{run_id}/predict.

    Les features doivent être fournies sous forme de dict avec les noms
    de colonnes BRUTES (non nettoyées), exactement comme dans le CSV original
    avant cleaning. Le service applique automatiquement le même pipeline de
    cleaning qu'à l'entraînement (encoding, scaling, alignement des colonnes).

    Exemple pour un dataset avec colonnes [age, city, salary] et target=salary :
        {
            "features": {
                "age":  32,
                "city": "Paris"
            }
        }
    Ne pas inclure la colonne target — elle est exclue automatiquement.
    """

    features: Dict[str, Any] = Field(
        description="Features brutes avec noms de colonnes (hors target_column)."
    )


class RunPredictResponse(BaseModel):
    """Réponse pour POST /{run_id}/predict.

    `prediction` est une liste car model.predict() retourne toujours un array.
    `prediction_label` est la représentation string du premier élément,
    utile pour l'affichage côté client sans parsing supplémentaire.

    Note : run_id est retourné en str par le service (str(uuid)) — Pydantic
    le coerce automatiquement vers UUID à la sérialisation.
    """

    run_id:           str            # str(UUID) retourné par predict_service
    algorithm:        str
    prediction:       List[Any]      # [1] classification, [245000.5] régression
    prediction_label: Optional[str] = None  # str(prediction[0]), null si vide