from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.dataset.models.cleaning_enums import (
    ColumnAction,
    EncodingMethod,
    MissingStrategy,
    OutlierMethod,
    ScalingMethod,
)


# ── per-column rule ────────────────────────────────────────────────────────────

class ColumnRuleIn(BaseModel):
    """One rule for one column. Only `column` and `action` are required."""
    column:           str
    action:           ColumnAction = ColumnAction.clean

    # numeric transforms (ignored for categoricals / drop / target / keep)
    missing_strategy: Optional[MissingStrategy] = None
    fill_value:       Optional[float | str]     = None   # used when strategy == constant
    scaling_method:   Optional[ScalingMethod]   = None
    outlier_method:   Optional[OutlierMethod]   = None

    # categorical transforms
    encoding_method:  Optional[EncodingMethod]  = None


class ColumnRuleOut(ColumnRuleIn):
    pass


# ── cleaning config ────────────────────────────────────────────────────────────

class CleaningConfigIn(BaseModel):
    missing_strategy:  MissingStrategy = MissingStrategy.median    # "MEDIAN"
    remove_duplicates: bool            = True
    encoding_method:   EncodingMethod  = EncodingMethod.one_hot    # "ONE_HOT"
    scaling_method:    ScalingMethod   = ScalingMethod.standard    # "STANDARD"
    version:           str             = "V1"
    column_rules:      List[ColumnRuleIn] = Field(default_factory=list)


class CleaningConfigOut(BaseModel):
    id:                uuid.UUID
    environment_id:    uuid.UUID
    missing_strategy:  str
    remove_duplicates: bool
    encoding_method:   str
    scaling_method:    str
    version:           str
    column_rules:      Optional[List[Dict[str, Any]]] = None
    status:            str

    class Config:
        from_attributes = True


# ── dataset schema endpoint ────────────────────────────────────────────────────

class ColumnSchema(BaseModel):
    """Describes one column inferred from the raw dataset."""
    name:         str
    dtype:        str                    # "numeric" | "categorical" | "datetime" | "text"
    null_count:   int
    null_pct:     float
    unique_count: int
    sample_values: List[Any]            # up to 5 representative values
    suggested_action: ColumnAction      # our best guess for the user


class DatasetSchemaOut(BaseModel):
    environment_id: uuid.UUID
    total_rows:     int
    total_columns:  int
    columns:        List[ColumnSchema]


# ── config review (pre-trigger dry-run) ───────────────────────────────────────

class ColumnReviewRow(BaseModel):
    column:  str
    action:  str
    details: str   # human-readable summary, e.g. "impute median → standard scale → IQR outlier removal"


class ConfigReviewOut(BaseModel):
    environment_id:      uuid.UUID
    config_id:           uuid.UUID
    remove_duplicates:   bool
    column_summary:      List[ColumnReviewRow]
    columns_to_clean:    int
    columns_to_drop:     int
    columns_to_keep:     int
    target_column:       Optional[str]


# ── trigger response ───────────────────────────────────────────────────────────

class TriggerOut(BaseModel):
    id:     uuid.UUID
    status: str


# ── cleaning report ────────────────────────────────────────────────────────────

class ColumnReportStats(BaseModel):
    action:            str
    nulls_before:      Optional[int]   = None
    nulls_after:       Optional[int]   = None
    outliers_removed:  Optional[int]   = None
    scaling:           Optional[str]   = None
    encoding:          Optional[str]   = None
    new_columns:       Optional[List[str]] = None


class CleaningReportOut(BaseModel):
    cleaned_dataset_id:  uuid.UUID
    environment_id:      uuid.UUID
    status:              str
    rows_before:         Optional[int]
    rows_after:          Optional[int]
    duplicates_removed:  Optional[int]
    columns:             Optional[Dict[str, ColumnReportStats]]
    cleaned_at:          Optional[datetime]
    rolled_back:         bool

    class Config:
        from_attributes = True


# ── cleaned dataset preview ────────────────────────────────────────────────────

class CleanedPreviewOut(BaseModel):
    cleaned_dataset_id: uuid.UUID
    columns:            List[str]
    rows:               List[Dict[str, Any]]
    total_rows:         int


# ── rollback ───────────────────────────────────────────────────────────────────

class RollbackOut(BaseModel):
    cleaned_dataset_id: uuid.UUID
    rolled_back:        bool
    rolled_back_at:     Optional[datetime]
    message:            str


# ── status poll ────────────────────────────────────────────────────────────────

class CleanedDatasetStatusOut(BaseModel):
    id:            uuid.UUID
    status:        str
    rows_before:   Optional[int]
    rows_after:    Optional[int]
    file_path:     Optional[str]
    cleaned_at:    Optional[datetime]
    rolled_back:   bool

    class Config:
        from_attributes = True