"""
predict_service.py — Logique métier pour la prédiction sans déploiement.

Flux :
    1. Valider le Run (COMPLETED + mlflow_run_id présent)
    2. Charger l'Environment (target_column, task_type)
    3. Charger le CleanedDataset (pour les colonnes attendues après encoding)
    4. Charger la CleaningConfig (pour rejouer le même pipeline)
    5. Télécharger le dataset BRUT depuis R2  ← FIX : était le dataset nettoyé
    6. Concat brut + input → apply_cleaning → prendre la dernière ligne  ← FIX
    7. Charger le modèle depuis MLflow
    8. Prédire
"""

import logging
import pickle
from io import BytesIO
from uuid import UUID

import pandas as pd
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from src.config.config import settings
from src.dataset.models.cleaned_dataset import CleanedDataset
from src.dataset.models.cleaning_config import CleaningConfig
from src.dataset.models.dataset import Dataset                        # ← AJOUT
from src.dataset.services.cleaning_service import apply_cleaning
from src.dataset.services.r2_service import get_s3_client
from src.deployments.mlflow_clients import download_model_artifact, verify_run_has_artifact
from src.environment.models.Environment import Environment
from src.runs.models.run import Run, RunStatus

logger = logging.getLogger(__name__)


def predict_from_run(run_id: UUID, features: dict, db: Session) -> dict:
    """Effectue une prédiction depuis un run MLflow sans déploiement Docker.

    Le pipeline reproduit exactement les mêmes transformations qu'à l'entraînement :
    - même CleaningConfig (stratégie missing, encoding, scaling)
    - scaler fitté sur le dataset brut complet (pas sur 1 seule ligne)
    - colonnes alignées sur celles du CleanedDataset de référence

    Args:
        run_id:   UUID du run COMPLETED à utiliser.
        features: Dict des features brutes { nom_colonne: valeur },
                  sans la colonne target.
        db:       Session SQLAlchemy active.

    Returns:
        Dict { run_id, algorithm, prediction, prediction_label }.

    Raises:
        ValueError:    Run invalide, dataset manquant, artifact MLflow absent.
        RuntimeError:  Erreur de preprocessing ou de prédiction.
    """

    # ── 1. Valider le Run ─────────────────────────────────────────────────────
    logger.info(f"predict_from_run — run_id={run_id}")

    run = db.execute(select(Run).where(Run.id == run_id)).scalar_one_or_none()

    if not run:
        raise ValueError(f"Run {run_id} introuvable.")
    if run.status != RunStatus.COMPLETED:
        raise ValueError(f"Le run {run_id} n'est pas COMPLETED (statut : {run.status.value}).")
    if not run.mlflow_run_id:
        raise ValueError(f"Le run {run_id} n'a pas de mlflow_run_id.")

    logger.debug(f"Run validé — algorithm={run.algorithm.value}")

    # ── 2. Environment ────────────────────────────────────────────────────────
    environment = db.execute(
        select(Environment).where(Environment.id == run.environment_id)
    ).scalar_one_or_none()

    if not environment:
        raise ValueError(f"Environment {run.environment_id} introuvable.")

    target_column = environment.target_column
    task_type     = environment.task_type
    logger.debug(f"target='{target_column}', task_type={task_type.value}")

    # ── 3. CleanedDataset ─────────────────────────────────────────────────────
    # Utilisé uniquement pour récupérer les colonnes attendues après encoding
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
        raise ValueError(f"Aucun CleanedDataset 'ready' pour l'environment {run.environment_id}.")

    # ── 4. CleaningConfig ─────────────────────────────────────────────────────
    cleaning_config = db.execute(
        select(CleaningConfig)
        .where(CleaningConfig.environment_id == run.environment_id)
        .order_by(desc(CleaningConfig.created_at))
        .limit(1)
    ).scalar_one_or_none()

    if not cleaning_config:
        raise ValueError(f"Aucune CleaningConfig pour l'environment {run.environment_id}.")

    # ── 5. Télécharger le dataset BRUT et le dataset nettoyé depuis R2 ───────
    #
    # POURQUOI le dataset brut ?
    # apply_cleaning() fitte le scaler ET l'encoder sur les données qu'on lui passe.
    # Si on l'appelle sur 1 seule ligne (l'input) :
    #   - StandardScaler : mean = valeur elle-même, std = 0 → résultat = 0 pour toutes les features
    #   - get_dummies : ne voit qu'une seule catégorie → colonnes manquantes
    # Solution : concat(dataset_brut + input) → apply_cleaning → prendre la dernière ligne.
    # Le scaler se fitte sur la vraie distribution des données d'entraînement.
    #
    try:
        client = get_s3_client()

        # Dataset brut — pour fitter le scaler/encoder sur la bonne distribution
        raw_dataset = db.execute(
            select(Dataset)
            .where(Dataset.env_id == run.environment_id)
            .order_by(desc(Dataset.uploaded_at))
            .limit(1)
        ).scalar_one_or_none()

        if not raw_dataset:
            raise ValueError(f"Aucun Dataset brut pour l'environment {run.environment_id}.")

        buf_raw = BytesIO()
        client.download_fileobj(settings.R2_BUCKET_NAME, raw_dataset.r2_path, buf_raw)
        buf_raw.seek(0)
        df_raw = pd.read_csv(buf_raw)
        logger.debug(f"Dataset brut chargé — shape={df_raw.shape}")

        # Dataset nettoyé — pour récupérer les colonnes attendues après cleaning
        buf_clean = BytesIO()
        client.download_fileobj(settings.R2_BUCKET_NAME, cleaned_dataset.file_path, buf_clean)
        buf_clean.seek(0)
        df_ref        = pd.read_csv(buf_clean)
        expected_cols = [c for c in df_ref.columns if c != target_column]
        logger.debug(f"Colonnes attendues ({len(expected_cols)}) : {expected_cols}")

    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Impossible de charger les datasets depuis R2 : {e}")

    # ── 6. Cleaning des features brutes ───────────────────────────────────────
    #
    # Stratégie : concat(df_raw + df_input) → apply_cleaning → dernière ligne
    # - Le scaler/encoder se fitte sur df_raw (même distribution qu'à l'entraînement)
    # - L'input reçoit exactement la même transformation
    # - On extrait la dernière ligne après cleaning
    #
    try:
        df_input = pd.DataFrame([features])
        df_input[target_column] = 0  # Colonne target factice — exclue par apply_cleaning()

        # Concat : dataset brut en premier, input en dernier
        df_combined = pd.concat([df_raw, df_input], ignore_index=True)
        # S'assurer que la target factice ne pollue pas les lignes du dataset brut
        df_combined[target_column] = df_combined[target_column].fillna(
            df_raw[target_column] if target_column in df_raw.columns else 0
        )

        df_cleaned_all = apply_cleaning(df_combined.copy(), cleaning_config, target_column)

        # Extraire uniquement la dernière ligne = notre input transformé
        df_cleaned = df_cleaned_all.iloc[[-1]].copy()

        if target_column in df_cleaned.columns:
            df_cleaned = df_cleaned.drop(columns=[target_column])

        # Aligner avec les colonnes vues à l'entraînement
        # - colonnes manquantes (catégories absentes de l'input) → 0
        # - colonnes en trop (ne devraient pas exister) → supprimées
        df_cleaned = df_cleaned.reindex(columns=expected_cols, fill_value=0)

        X = df_cleaned.values
        logger.debug(f"Features nettoyées — shape={X.shape}, valeurs={X}")

    except Exception as e:
        raise RuntimeError(f"Échec du preprocessing des features : {e}")

    # ── 7. Charger le modèle ──────────────────────────────────────────────────
    if not verify_run_has_artifact(run.mlflow_run_id):
        raise ValueError(f"Aucun artifact MLflow pour le run {run.mlflow_run_id}.")

    try:
        model_path = download_model_artifact(run.mlflow_run_id)
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        logger.info(f"Modèle chargé — type={type(model).__name__}")
    except Exception as e:
        raise RuntimeError(f"Impossible de charger le modèle : {e}")

    # ── 8. Prédiction ─────────────────────────────────────────────────────────
    try:
        prediction = model.predict(X).tolist()
        logger.info(f"Prédiction réussie — result={prediction}")
    except Exception as e:
        raise RuntimeError(f"La prédiction a échoué : {e}")

    return {
        "run_id":           str(run_id),
        "algorithm":        run.algorithm.value,
        "prediction":       prediction,
        "prediction_label": str(prediction[0]) if prediction else None,
    }