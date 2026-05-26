from __future__ import annotations

import uuid
from typing import Any, List

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.dataset.models.cleaning_enums import ColumnAction
from src.dataset.models.dataset import Dataset
from src.dataset.schemas.cleaning_config import ColumnSchema, DatasetSchemaOut
from src.dataset.services.r2_service import r2_download


def _infer_dtype(series: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if series.nunique() / max(len(series), 1) < 0.5:
        return "categorical"
    return "text"


def _suggest_action(series: pd.Series, dtype: str) -> ColumnAction:
    name = series.name.lower()
    if any(kw in name for kw in ("_id", "id_", "uuid", "key")):
        return ColumnAction.keep
    if name in ("target", "label", "y", "output", "class"):
        return ColumnAction.target
    if dtype == "text" and series.nunique() > 100:
        return ColumnAction.drop
    return ColumnAction.clean


def get_dataset_schema(environment_id: uuid.UUID, db: Session) -> DatasetSchemaOut:
    dataset = db.query(Dataset).filter(Dataset.env_id == environment_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="No dataset found for this environment")

    df = r2_download(dataset.r2_path)
    df_sample = df.head(5000)

    columns: List[ColumnSchema] = []
    for col in df_sample.columns:
        series = df_sample[col]
        dtype = _infer_dtype(series)
        null_count = int(series.isna().sum())
        total = max(len(series), 1)
        sample: List[Any] = series.dropna().unique()[:5].tolist()

        columns.append(
            ColumnSchema(
                name=col,
                dtype=dtype,
                null_count=null_count,
                null_pct=round(null_count / total * 100, 2),
                unique_count=int(series.nunique()),
                sample_values=sample,
                suggested_action=_suggest_action(series, dtype),
            )
        )

    return DatasetSchemaOut(
        environment_id=environment_id,
        total_rows=len(df),
        total_columns=len(df.columns),
        columns=columns,
    )