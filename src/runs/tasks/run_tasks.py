import uuid
import mlflow
import mlflow.sklearn
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import src.auth.models.user  # noqa: F401
import src.project.models.project  # noqa: F401
import src.environment.models.Environment  # noqa: F401
# ML Imports
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier

from src.config.celery import celery
from src.config.db import SessionLocal
from src.config.config import settings
from src.runs.models.run import Run, RunStatus, Algorithm

# Configuration du logger
logger = logging.getLogger(__name__)

# MAPPING DES 6 ALGORITHMES SUPPORTÉS
MODEL_MAPPING = {
    Algorithm.LOGISTIC_REGRESSION: LogisticRegression,
    Algorithm.RANDOM_FOREST: RandomForestClassifier,
    Algorithm.SVM: SVC,
    Algorithm.DECISION_TREE: DecisionTreeClassifier,
    Algorithm.LINEAR_REGRESSION: RidgeClassifier,
    Algorithm.KNN: KNeighborsClassifier,
}

# Algorithmes qui ne supportent pas random_state
ALGORITHMS_WITHOUT_RANDOM_STATE = {
    Algorithm.KNN,
}

@celery.task(name="src.runs.tasks.run_tasks.train_iris_run", bind=True)
def train_iris_run(self, run_id: str):
    """
    Tâche Celery pour l'entraînement Iris avec tracking MLflow.

    Algorithmes supportés :
    - LOGISTIC_REGRESSION
    - RANDOM_FOREST
    - SVM
    - DECISION_TREE
    - LINEAR_REGRESSION (RidgeClassifier)
    - KNN
    """
    db: Session = SessionLocal()

    try:
        # 1. Conversion STR -> UUID
        try:
            run_uuid = uuid.UUID(run_id)
        except ValueError:
            return {"ok": False, "error": f"Format UUID invalide: {run_id}"}

        # 2. Récupération du Run et Configuration
        run = db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(Run.id == run_uuid)
        ).scalar_one_or_none()

        if not run or not run.training_config:
            return {"ok": False, "error": "Run ou TrainingConfig introuvable"}

        # 3. Passage à l'état RUNNING
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"🚀 Début du Run {run_id} [{run.algorithm.value}]")

        # 4. Préparation MLflow
        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(f"Environment_{run.environment_id}")

        # 5. Dataset Iris
        iris = load_iris()

        with mlflow.start_run(run_name=f"Run_{run.id}") as ml_run:
            run.mlflow_run_id = ml_run.info.run_id

            # 6. Instanciation du modèle
            model_class = MODEL_MAPPING.get(run.algorithm)
            if not model_class:
                raise ValueError(f"Algorithme {run.algorithm.value} non supporté.")

            hp = run.training_config.hyperparameters or {}

            # Application du random_state selon l'algorithme
            if run.algorithm not in ALGORITHMS_WITHOUT_RANDOM_STATE:
                model = model_class(**hp, random_state=run.training_config.random_state or 42)
            else:
                model = model_class(**hp)

            logger.info(f"✓ Modèle {run.algorithm.value} instancié avec succès")

            # 7. Tracking des paramètres
            mlflow.log_params(hp)
            mlflow.log_param("algorithm", run.algorithm.value)
            mlflow.log_param("cv_mode", run.training_config.cross_validation)
            mlflow.log_param("test_size", run.training_config.test_size or 0.2)
            mlflow.log_param("random_state", run.training_config.random_state or 42)
            mlflow.log_param("cv_folds", run.training_config.cv_folds or 5)

            # 8. Entraînement et Évaluation
            if run.training_config.cross_validation:
                # --- MODE CROSS-VALIDATION ---
                cv_folds = run.training_config.cv_folds or 5
                logger.info(f"Mode: Cross-validation ({cv_folds} folds)")

                scores = cross_val_score(model, iris.data, iris.target, cv=cv_folds)

                metrics = {
                    "accuracy": float(scores.mean()),
                    "precision": None,
                    "recall": None,
                    "f1_score": None
                }
                logger.info(f"CV Accuracy: {scores.mean():.4f} ± {scores.std():.4f}")

                # Entraînement sur tout le dataset pour sauvegarder le modèle
                model.fit(iris.data, iris.target)

            else:
                # --- MODE TRAIN/TEST SPLIT ---
                logger.info("Mode: Train/Test split")

                X_train, X_test, y_train, y_test = train_test_split(
                    iris.data, iris.target,
                    test_size=run.training_config.test_size or 0.2,
                    random_state=run.training_config.random_state or 42,
                    stratify=iris.target
                )
                logger.debug(f"Train: {X_train.shape[0]} samples, Test: {X_test.shape[0]} samples")

                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)

                metrics = {
                    "accuracy": float(accuracy_score(y_test, y_pred)),
                    "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
                    "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
                    "f1_score": float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
                }
                logger.info(
                    f"Résultats: Acc={metrics['accuracy']:.4f}, Pre={metrics['precision']:.4f}, "
                    f"Rec={metrics['recall']:.4f}, F1={metrics['f1_score']:.4f}"
                )

            # 9. Logging MLflow (Métriques et Modèle)
            mlflow.log_metrics({k: v for k, v in metrics.items() if v is not None})

            try:
                mlflow.sklearn.log_model(model, "model_artifact")
                logger.info("✓ Modèle sauvegardé dans MLflow")
            except Exception as e:
                logger.warning(f"Erreur lors de la sauvegarde du modèle: {e}")

            # 10. Mise à jour DB finale
            run.status = RunStatus.COMPLETED
            run.accuracy = metrics["accuracy"]
            run.precision = metrics.get("precision")
            run.recall = metrics.get("recall")
            run.f1_score = metrics.get("f1_score")
            run.finished_at = datetime.now(timezone.utc)
            run.duration_seconds = (run.finished_at - run.started_at).total_seconds()

            db.commit()
            logger.info(f"✅ Run {run_id} terminé avec succès en {run.duration_seconds:.2f}s")

        return {"ok": True, "metrics": metrics, "duration_seconds": run.duration_seconds}

    except Exception as e:
        logger.error(f"❌ Erreur Run {run_id}: {str(e)}", exc_info=True)
        db.rollback()

        # Tentative de marquage FAILED
        try:
            run_uuid = uuid.UUID(run_id)
            run_err = db.execute(select(Run).where(Run.id == run_uuid)).scalar_one_or_none()
            if run_err:
                run_err.status = RunStatus.FAILED
                run_err.finished_at = datetime.now(timezone.utc)
                db.commit()
                logger.warning(f"Run {run_id} marqué comme FAILED")
        except Exception as mark_error:
            logger.error(f"Impossible de marquer FAILED: {mark_error}")

        return {"ok": False, "error": str(e)}

    finally:
        db.close()
        logger.debug("Session DB fermée")