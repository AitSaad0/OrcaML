import io
import boto3
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from src.config.celery import celery
from src.config.db import SessionLocal
from src.config.config import settings
from src.dataset.models.cleaning_config import CleaningConfig
from src.dataset.models.cleaned_dataset import CleanedDataset
from src.dataset.services.cleaning_service import apply_cleaning


def get_s3_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        region_name="auto",
    )


@celery.task(bind=True)
def run_cleaning(self, cleaned_dataset_id: str):
    """
    Celery task that:
    1. Reads raw CSV from R2
    2. Applies cleaning config
    3. Uploads clean CSV to R2
    4. Updates DB status
    """
    db: Session = SessionLocal()
    try:
        # ── Step 1: Load from DB ─────────────────────────────────
        cleaned = db.query(CleanedDataset).filter(
            CleanedDataset.id == cleaned_dataset_id
        ).first()

        config = db.query(CleaningConfig).filter(
            CleaningConfig.id == cleaned.cleaning_config_id
        ).first()

        # get the raw dataset for this environment
        from src.dataset.models.dataset import Dataset
        dataset = db.query(Dataset).filter(
            Dataset.env_id == cleaned.environment_id
        ).order_by(Dataset.uploaded_at.desc()).first()

        # update status to CLEANING
        cleaned.status = "cleaning"
        db.commit()

        # ── Step 2: Download raw file from R2 ───────────────────
        s3       = get_s3_client()
        response = s3.get_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=dataset.r2_path
        )
        file_bytes = response["Body"].read()
        df         = pd.read_csv(io.BytesIO(file_bytes))
        rows_before = len(df)

        # ── Step 3: Apply cleaning ───────────────────────────────
        # get target column from environment
        target_column = cleaned.environment.target_column
        df_clean = apply_cleaning(df.copy(), config, target_column)
        rows_after = len(df_clean)

        # ── Step 4: Upload clean file to R2 ─────────────────────
        clean_path  = f"cleaned/{cleaned.environment_id}/{cleaned.id}.csv"
        csv_buffer  = io.StringIO()
        df_clean.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")

        s3.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=clean_path,
            Body=csv_bytes,
        )

        # ── Step 5: Update DB status to READY ───────────────────
        cleaned.status          = "ready"
        cleaned.file_path       = clean_path
        cleaned.rows_before     = rows_before
        cleaned.rows_after      = rows_after
        cleaned.columns_dropped = len(df.columns) - len(df_clean.columns)
        cleaned.cleaned_at      = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        # if anything fails → mark as FAILED
        # raw file still safe in R2 → can always retry
        cleaned.status = "failed"
        db.commit()
        raise e

    finally:
        db.close()