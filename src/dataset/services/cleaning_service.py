import boto3
import pandas as pd

from src.config.config import settings
from src.dataset.models.cleaning_config import CleaningConfig
from src.dataset.models.cleaning_enums import (
    MissingStrategy, EncodingMethod, ScalingMethod
)


def get_s3_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        region_name="auto"
    )


def apply_cleaning(df: pd.DataFrame, config: CleaningConfig, target_column: str) -> pd.DataFrame:
    """
    Apply V1 cleaning steps to a DataFrame.
    Each step is explained with comments.
    """

    # ── Step 1: Remove Duplicates ────────────────────────────────
    if config.remove_duplicates:
        df = df.drop_duplicates()

    # ── Step 2: Handle Missing Values ───────────────────────────
    feature_cols = [c for c in df.columns if c != target_column]

    if config.missing_strategy == MissingStrategy.drop:
        df.dropna(subset=feature_cols, inplace=True)

    elif config.missing_strategy == MissingStrategy.drop_column:
        threshold = 0.5
        for col in feature_cols:
            if df[col].isna().mean() > threshold:
                df.drop(columns=[col], inplace=True)

    elif config.missing_strategy == MissingStrategy.mean:
        num_cols = df[feature_cols].select_dtypes(include="number").columns
        for col in num_cols:
            df[col] = df[col].fillna(df[col].mean())

    elif config.missing_strategy == MissingStrategy.median:
        num_cols = df[feature_cols].select_dtypes(include="number").columns
        for col in num_cols:
            df[col] = df[col].fillna(df[col].median())

    elif config.missing_strategy == MissingStrategy.mode:
        for col in feature_cols:
            df[col] = df[col].fillna(df[col].mode()[0])

    elif config.missing_strategy == MissingStrategy.constant:
        num_cols = df[feature_cols].select_dtypes(include="number").columns
        cat_cols = df[feature_cols].select_dtypes(include="object").columns
        df[num_cols] = df[num_cols].fillna(0)
        df[cat_cols] = df[cat_cols].fillna("Unknown")

    elif config.missing_strategy == MissingStrategy.forward_fill:
        df[feature_cols] = df[feature_cols].ffill()

    # ── Step 3: Encode Categorical Columns ──────────────────────
    cat_cols = [
        c for c in df.select_dtypes(include="object").columns
        if c != target_column
    ]

    if config.encoding_method == EncodingMethod.label:
        from sklearn.preprocessing import LabelEncoder
        le = LabelEncoder()
        for col in cat_cols:
            df[col] = le.fit_transform(df[col].astype(str))

    elif config.encoding_method == EncodingMethod.one_hot:
        if cat_cols:
            df = pd.get_dummies(df, columns=cat_cols, drop_first=True)

    # ── Step 4: Scale Numerical Columns ─────────────────────────
    num_cols = [
        c for c in df.select_dtypes(include="number").columns
        if c != target_column
    ]

    if config.scaling_method == ScalingMethod.minmax:
        from sklearn.preprocessing import MinMaxScaler
        scaler = MinMaxScaler()
        df[num_cols] = scaler.fit_transform(df[num_cols])

    elif config.scaling_method == ScalingMethod.standard:
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        df[num_cols] = scaler.fit_transform(df[num_cols])

    elif config.scaling_method == ScalingMethod.robust:
        from sklearn.preprocessing import RobustScaler
        scaler = RobustScaler()
        df[num_cols] = scaler.fit_transform(df[num_cols])

    elif config.scaling_method == ScalingMethod.log:
        import numpy as np
        for col in num_cols:
            df[col] = np.log1p(df[col])

    return df