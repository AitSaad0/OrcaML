"""
run_tasks.py — Tâche Celery d'entraînement ML.
"""

import uuid
import mlflow
import mlflow.sklearn
import logging
import pandas as pd
from io import BytesIO
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
import src.models  # noqa: F401

from sklearn.model_selection import train_test_split, cross_val_score, cross_validate
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    mean_squared_error, mean_absolute_error, r2_score,
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from xgboost import XGBClassifier, XGBRegressor

from src.config.celery import celery
from src.config.db import SessionLocal
from src.config.config import settings
from src.dataset.services.r2_service import get_s3_client
from src.runs.models.run import Run, RunStatus, Algorithm
from src.environment.models.Environment import Environment
from src.environment.models.Task_type import TaskType
from src.dataset.models.cleaned_dataset import CleanedDataset
from src.notifications.email_service import notify_run_completed

logger = logging.getLogger(__name__)

CLASSIFICATION_MODEL_MAPPING = {
    Algorithm.LOGISTIC_REGRESSION: LogisticRegression,
    Algorithm.RANDOM_FOREST:       RandomForestClassifier,
    Algorithm.SVM:                 SVC,
    Algorithm.DECISION_TREE:       DecisionTreeClassifier,
    Algorithm.LINEAR_REGRESSION:   RidgeClassifier,
    Algorithm.KNN:                 KNeighborsClassifier,
    Algorithm.XGBOOST:             XGBClassifier,
}

REGRESSION_MODEL_MAPPING = {
    Algorithm.XGBOOST:           XGBRegressor,
    Algorithm.RANDOM_FOREST:     __import__("sklearn.ensemble",     fromlist=["RandomForestRegressor"]).RandomForestRegressor,
    Algorithm.DECISION_TREE:     __import__("sklearn.tree",         fromlist=["DecisionTreeRegressor"]).DecisionTreeRegressor,
    Algorithm.LINEAR_REGRESSION: __import__("sklearn.linear_model", fromlist=["Ridge"]).Ridge,
    Algorithm.SVM:               __import__("sklearn.svm",          fromlist=["SVR"]).SVR,
    Algorithm.KNN:               __import__("sklearn.neighbors",    fromlist=["KNeighborsRegressor"]).KNeighborsRegressor,
}

ALGORITHMS_WITHOUT_RANDOM_STATE = {Algorithm.KNN}


@celery.task(name="src.runs.tasks.run_tasks.train_iris_run", bind=True)
def train_iris_run(self, run_id: str):
    db: Session = SessionLocal()

    try:
        try:
            run_uuid = uuid.UUID(run_id)
        except ValueError:
            return {"ok": False, "error": f"Format UUID invalide: {run_id}"}

        run = db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(Run.id == run_uuid)
        ).scalar_one_or_none()

        if not run or not run.training_config:
            return {"ok": False, "error": "Run ou TrainingConfig introuvable"}

        run.status     = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"🚀 Début du Run {run_id} [{run.algorithm.value}]")

        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(f"Environment_{run.environment_id}")

        environment = db.execute(
            select(Environment).where(Environment.id == run.environment_id)
        ).scalar_one_or_none()

        if not environment:
            raise ValueError(f"Environment {run.environment_id} introuvable")

        target_column = environment.target_column
        task_type     = environment.task_type
        logger.info(f"✓ Environment chargé — target: '{target_column}' | task: {task_type.value}")

        cleaned_dataset = db.execute(
            select(CleanedDataset)
            .where(
                CleanedDataset.environment_id == run.environment_id,
                CleanedDataset.status == "ready",
            )
            .order_by(desc(CleanedDataset.cleaned_at))
            .limit(1)
        ).scalar_one_or_none()

        if not cleaned_dataset:
            raise ValueError(f"Aucun CleanedDataset 'ready' pour l'environment {run.environment_id}")

        if not cleaned_dataset.file_path:
            raise ValueError(f"CleanedDataset {cleaned_dataset.id} n'a pas de file_path")

        logger.info(f"✓ CleanedDataset trouvé: {cleaned_dataset.id}")

        client = get_s3_client()
        buffer = BytesIO()
        client.download_fileobj(settings.R2_BUCKET_NAME, cleaned_dataset.file_path, buffer)
        buffer.seek(0)

        df = pd.read_csv(buffer)
        logger.info(f"✓ Dataset chargé: {df.shape[0]} lignes, {df.shape[1]} colonnes")

        if target_column not in df.columns:
            raise ValueError(f"Colonne cible '{target_column}' absente du dataset")

        X = df.drop(columns=[target_column]).values
        y = df[target_column].values
        logger.info(f"✓ X: {X.shape}, y: {y.shape}")

        with mlflow.start_run(run_name=f"Run_{run.id}") as ml_run:
            run.mlflow_run_id = ml_run.info.run_id

            if task_type == TaskType.CLASSIFICATION:
                model_class = CLASSIFICATION_MODEL_MAPPING.get(run.algorithm)
            else:
                model_class = REGRESSION_MODEL_MAPPING.get(run.algorithm)

            if not model_class:
                raise ValueError(
                    f"Algorithme {run.algorithm.value} non supporté "
                    f"pour task_type {task_type.value}."
                )

            hp = run.training_config.hyperparameters or {}

            if run.algorithm not in ALGORITHMS_WITHOUT_RANDOM_STATE:
                model = model_class(**hp, random_state=run.training_config.random_state or 42)
            else:
                model = model_class(**hp)

            logger.info(f"✓ Modèle {run.algorithm.value} instancié [{task_type.value}]")

            mlflow.log_params(hp)
            mlflow.log_param("algorithm",    run.algorithm.value)
            mlflow.log_param("task_type",    task_type.value)
            mlflow.log_param("cv_mode",      run.training_config.cross_validation)
            mlflow.log_param("test_size",    run.training_config.test_size or 0.2)
            mlflow.log_param("random_state", run.training_config.random_state or 42)
            mlflow.log_param("cv_folds",     run.training_config.cv_folds or 5)

            # ── Entraînement et Évaluation ────────────────────────────────
            if run.training_config.cross_validation:
                cv_folds = run.training_config.cv_folds or 5

                if task_type == TaskType.CLASSIFICATION:
                    logger.info(f"Mode: Cross-validation classification ({cv_folds} folds)")
                    cv_results = cross_validate(
                        model, X, y,
                        cv=cv_folds,
                        scoring={
                            "accuracy":  "accuracy",
                            "f1":        "f1_weighted",
                            "precision": "precision_weighted",
                            "recall":    "recall_weighted",
                        }
                    )
                    metrics = {
                        "accuracy":  float(cv_results["test_accuracy"].mean()),
                        "f1_score":  float(cv_results["test_f1"].mean()),
                        "precision": float(cv_results["test_precision"].mean()),
                        "recall":    float(cv_results["test_recall"].mean()),
                    }
                    logger.info(
                        f"CV Accuracy: {metrics['accuracy']:.4f}, F1: {metrics['f1_score']:.4f}"
                    )

                else:
                    logger.info(f"Mode: Cross-validation régression ({cv_folds} folds)")
                    scores = cross_val_score(model, X, y, cv=cv_folds, scoring="r2")
                    metrics = {
                        "rmse": None,
                        "mae":  None,
                        "r2":   float(scores.mean()),
                    }
                    logger.info(f"CV R2: {scores.mean():.4f} ± {scores.std():.4f}")

                model.fit(X, y)

            else:
                split_kwargs = {
                    "test_size":    run.training_config.test_size or 0.2,
                    "random_state": run.training_config.random_state or 42,
                }
                if task_type == TaskType.CLASSIFICATION:
                    split_kwargs["stratify"] = y

                X_train, X_test, y_train, y_test = train_test_split(X, y, **split_kwargs)
                logger.debug(f"Train: {X_train.shape[0]} samples, Test: {X_test.shape[0]} samples")

                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)

                if task_type == TaskType.CLASSIFICATION:
                    logger.info("Mode: Train/Test split classification")
                    metrics = {
                        "accuracy":  float(accuracy_score(y_test, y_pred)),
                        "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
                        "recall":    float(recall_score(y_test, y_pred,    average="weighted", zero_division=0)),
                        "f1_score":  float(f1_score(y_test, y_pred,        average="weighted", zero_division=0)),
                    }
                    logger.info(
                        f"Résultats: Acc={metrics['accuracy']:.4f}, F1={metrics['f1_score']:.4f}"
                    )

                else:
                    logger.info("Mode: Train/Test split régression")
                    metrics = {
                        "rmse": float(mean_squared_error(y_test, y_pred) ** 0.5),
                        "mae":  float(mean_absolute_error(y_test, y_pred)),
                        "r2":   float(r2_score(y_test, y_pred)),
                    }
                    logger.info(
                        f"Résultats: RMSE={metrics['rmse']:.4f}, "
                        f"MAE={metrics['mae']:.4f}, R2={metrics['r2']:.4f}"
                    )

            mlflow.log_metrics({k: v for k, v in metrics.items() if v is not None})

            try:
                mlflow.sklearn.log_model(model, "model_artifact")
                logger.info("✓ Modèle sauvegardé dans MLflow")
            except Exception as e:
                logger.warning(f"Erreur sauvegarde modèle: {e}")

            run.status           = RunStatus.COMPLETED
            run.finished_at      = datetime.now(timezone.utc)
            run.duration_seconds = (run.finished_at - run.started_at).total_seconds()

            if task_type == TaskType.CLASSIFICATION:
                run.accuracy  = metrics.get("accuracy")
                run.precision = metrics.get("precision")
                run.recall    = metrics.get("recall")
                run.f1_score  = metrics.get("f1_score")
            else:
                run.rmse = metrics.get("rmse")
                run.mae  = metrics.get("mae")
                run.r2   = metrics.get("r2")

            db.commit()
            logger.info(f"✅ Run {run_id} terminé en {run.duration_seconds:.2f}s")

            # ── Notification email ─────────────────────────────────────────
            notify_run_completed(db=db, run=run)

        return {"ok": True, "metrics": metrics, "duration_seconds": run.duration_seconds}

    except Exception as e:
        logger.error(f"❌ Erreur Run {run_id}: {str(e)}", exc_info=True)
        db.rollback()

        try:
            run_uuid = uuid.UUID(run_id)
            run_err  = db.execute(select(Run).where(Run.id == run_uuid)).scalar_one_or_none()
            if run_err:
                run_err.status      = RunStatus.FAILED
                run_err.finished_at = datetime.now(timezone.utc)
                db.commit()
                logger.warning(f"Run {run_id} marqué comme FAILED")
        except Exception as mark_error:
            logger.error(f"Impossible de marquer FAILED: {mark_error}")

        return {"ok": False, "error": str(e)}

    finally:
        db.close()
        logger.debug("Session DB fermée")