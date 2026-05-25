"""
cleaning_engine.py
~~~~~~~~~~~~~~~~~~
Pure-function cleaning logic.  No DB, no R2 — only pandas transforms.
Called by the Celery worker after the raw DataFrame is downloaded.

Returns (cleaned_df, report_dict) so the worker can persist the report.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd
from sklearn.preprocessing import (
    LabelEncoder,
    MinMaxScaler,
    RobustScaler,
    StandardScaler,
)

from src.dataset.models.cleaning_enums import (
    ColumnAction,
    EncodingMethod,
    MissingStrategy,
    OutlierMethod,
    ScalingMethod,
)
from src.dataset.schemas.cleaning_config import CleaningConfigIn, ColumnRuleIn


# ── helpers ────────────────────────────────────────────────────────────────────

def _effective_rule(
    column: str,
    config: CleaningConfigIn,
    dtype: str,
) -> ColumnRuleIn:
    """
    Return the ColumnRuleIn that applies to `column`.
    Per-column rules override the global fallback.
    """
    for rule in config.column_rules:
        if rule.column == column:
            # Fill unset fields with global defaults
            return ColumnRuleIn(
                column=rule.column,
                action=rule.action,
                missing_strategy=rule.missing_strategy or config.missing_strategy,
                fill_value=rule.fill_value,
                scaling_method=rule.scaling_method or (
                    config.scaling_method if dtype == "numeric" else ScalingMethod.none
                ),
                outlier_method=rule.outlier_method or OutlierMethod.none,
                encoding_method=rule.encoding_method or (
                    config.encoding_method if dtype == "categorical" else EncodingMethod.none
                ),
            )
    # No explicit rule → build one from globals
    return ColumnRuleIn(
        column=column,
        action=ColumnAction.clean,
        missing_strategy=config.missing_strategy,
        scaling_method=config.scaling_method if dtype == "numeric" else ScalingMethod.none,
        outlier_method=OutlierMethod.none,
        encoding_method=config.encoding_method if dtype == "categorical" else EncodingMethod.none,
    )


def _infer_dtype(series: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if series.nunique() / max(len(series), 1) < 0.5:
        return "categorical"
    return "text"


def _remove_outliers_iqr(df: pd.DataFrame, col: str) -> Tuple[pd.DataFrame, int]:
    q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
    iqr = q3 - q1
    mask = (df[col] >= q1 - 1.5 * iqr) & (df[col] <= q3 + 1.5 * iqr)
    removed = (~mask).sum()
    return df[mask].copy(), int(removed)


def _remove_outliers_zscore(df: pd.DataFrame, col: str, threshold: float = 3.0) -> Tuple[pd.DataFrame, int]:
    z = (df[col] - df[col].mean()) / df[col].std()
    mask = z.abs() <= threshold
    removed = (~mask).sum()
    return df[mask].copy(), int(removed)


def _clip_outliers_iqr(df: pd.DataFrame, col: str) -> Tuple[pd.DataFrame, int]:
    q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    df = df.copy()
    clipped = ((df[col] < lower) | (df[col] > upper)).sum()
    df[col] = df[col].clip(lower, upper)
    return df, int(clipped)


# ── main entry point ───────────────────────────────────────────────────────────

def apply_cleaning(
    df: pd.DataFrame,
    config: CleaningConfigIn,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Apply all cleaning steps according to `config`.

    Returns
    -------
    df_clean : pd.DataFrame
    report   : dict  — matches CleaningReportOut shape
    """
    df = df.copy()
    report: Dict[str, Any] = {
        "rows_before": len(df),
        "duplicates_removed": 0,
        "columns": {},
    }

    # ── Step 1: remove duplicates (global) ────────────────────────────────────
    if config.remove_duplicates:
        before = len(df)
        df = df.drop_duplicates()
        report["duplicates_removed"] = before - len(df)

    # ── Build per-column rules ─────────────────────────────────────────────────
    # Determine which columns are "target" (exempt from all transforms)
    target_cols = {
        r.column for r in config.column_rules if r.action == ColumnAction.target
    }
    drop_cols = {
        r.column for r in config.column_rules if r.action == ColumnAction.drop
    }
    # Add this set before Step 2
    one_hot_cols: set[str] = set()
    # ── Step 2: per-column imputation ─────────────────────────────────────────
    for col in df.columns:
        if col in target_cols or col in drop_cols:
            continue

        dtype = _infer_dtype(df[col])
        rule = _effective_rule(col, config, dtype)

        if rule.action in (ColumnAction.keep, ColumnAction.target):
            continue

        nulls_before = int(df[col].isna().sum())

        if dtype == "numeric":
            strategy = rule.missing_strategy or MissingStrategy.median
            if strategy == MissingStrategy.median:
                df[col] = df[col].fillna(df[col].median())
            elif strategy == MissingStrategy.mean:
                df[col] = df[col].fillna(df[col].mean())
            elif strategy == MissingStrategy.mode:
                mode_val = df[col].mode()
                df[col] = df[col].fillna(mode_val[0] if not mode_val.empty else 0)
            elif strategy == MissingStrategy.constant:
                df[col] = df[col].fillna(rule.fill_value if rule.fill_value is not None else 0)
            elif strategy == MissingStrategy.drop:
                df = df.dropna(subset=[col])
        else:
            # categorical / text: fill with mode or constant
            strategy = rule.missing_strategy or MissingStrategy.mode
            if strategy == MissingStrategy.drop:
                df = df.dropna(subset=[col])
            elif strategy == MissingStrategy.constant:
                df[col] = df[col].fillna(str(rule.fill_value) if rule.fill_value is not None else "unknown")
            else:
                mode_val = df[col].mode()
                df[col] = df[col].fillna(mode_val[0] if not mode_val.empty else "unknown")

        nulls_after = int(df[col].isna().sum())
        report["columns"][col] = {
            "action": "clean",
            "nulls_before": nulls_before,
            "nulls_after": nulls_after,
        }

    # ── Step 3: outlier handling (numeric only) ────────────────────────────────
    for col in df.columns:
        if col in target_cols or col in drop_cols:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        dtype = "numeric"
        rule = _effective_rule(col, config, dtype)
        if rule.action in (ColumnAction.keep, ColumnAction.target, ColumnAction.drop):
            continue

        outlier_method = rule.outlier_method or OutlierMethod.none
        outliers_removed = 0

        if outlier_method == OutlierMethod.iqr:
            df, outliers_removed = _remove_outliers_iqr(df, col)
        elif outlier_method == OutlierMethod.zscore:
            df, outliers_removed = _remove_outliers_zscore(df, col)
        elif outlier_method == OutlierMethod.clip:
            df, outliers_removed = _clip_outliers_iqr(df, col)

        if col not in report["columns"]:
            report["columns"][col] = {"action": "clean"}
        report["columns"][col]["outliers_removed"] = outliers_removed
# ── Step 4: encoding (categorical only) ───────────────────────────────────
    one_hot_cols: set[str] = set()
    cols_snapshot = list(df.columns)
    for col in cols_snapshot:
        if col in target_cols or col in drop_cols:
            continue

        dtype = _infer_dtype(df[col])
        if dtype not in ("categorical", "text"):
            continue

        rule = _effective_rule(col, config, dtype)
        if rule.action in (ColumnAction.keep, ColumnAction.target, ColumnAction.drop):
            continue

        enc = rule.encoding_method or EncodingMethod.none
        new_cols: List[str] = []

        if enc == EncodingMethod.one_hot:
            dummies = pd.get_dummies(df[[col]], columns=[col], drop_first=True)
            new_cols = list(dummies.columns)
            one_hot_cols.update(new_cols)   # ← track them
            df = pd.concat([df.drop(columns=[col]), dummies], axis=1)
        elif enc == EncodingMethod.label:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
        elif enc == EncodingMethod.ordinal:
            categories = sorted(df[col].dropna().unique().tolist())
            mapping = {cat: i for i, cat in enumerate(categories)}
            df[col] = df[col].map(mapping)

        if col not in report["columns"]:
            report["columns"][col] = {"action": "clean"}
        report["columns"][col]["encoding"] = enc.value if enc else "none"
        if new_cols:
            report["columns"][col]["new_columns"] = new_cols

    # ── Step 5: scaling (numeric only) ────────────────────────────────────────
    for col in list(df.columns):
        if col in target_cols or col in drop_cols or col in one_hot_cols:
            continue                        # ← one_hot_cols skipped here
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        dtype = "numeric"
        rule = _effective_rule(col, config, dtype)
        if rule.action in (ColumnAction.keep, ColumnAction.target, ColumnAction.drop):
            continue

        sm = rule.scaling_method or ScalingMethod.none
        scaler_map = {
            ScalingMethod.standard: StandardScaler(),
            ScalingMethod.minmax:   MinMaxScaler(),
            ScalingMethod.robust:   RobustScaler(),
        }

        if sm in scaler_map:
            vals = df[[col]].values
            df[col] = scaler_map[sm].fit_transform(vals).flatten()

        if col not in report["columns"]:
            report["columns"][col] = {"action": "clean"}
        report["columns"][col]["scaling"] = sm.value if sm else "none"

    # ── Step 6: drop columns ──────────────────────────────────────────────────
    existing_drop = [c for c in drop_cols if c in df.columns]
    for col in existing_drop:
        report["columns"][col] = {"action": "drop"}
    df = df.drop(columns=existing_drop, errors="ignore")

    # ── Step 7: record target columns ─────────────────────────────────────────
    for col in target_cols:
        if col in df.columns:
            report["columns"][col] = {"action": "target"}

    report["rows_after"] = len(df)
    return df.reset_index(drop=True), report