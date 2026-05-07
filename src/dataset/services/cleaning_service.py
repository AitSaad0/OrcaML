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
    # df.drop_duplicates() removes rows that are 100% identical
    # inplace=True → modifies df directly instead of returning a copy
    if config.remove_duplicates:
        df.drop_duplicates(inplace=True)

    # ── Step 2: Handle Missing Values ───────────────────────────
    # We separate target column from features
    # Never fill/drop the target column — it's what we're predicting
    feature_cols = [c for c in df.columns if c != target_column]

    if config.missing_strategy == MissingStrategy.DROP_ROWS:
        # remove any row that has at least one missing value
        df.dropna(subset=feature_cols, inplace=True)

    elif config.missing_strategy == MissingStrategy.DROP_COLUMN:
        # remove columns where more than 50% of values are missing
        threshold = 0.5
        for col in feature_cols:
            if df[col].isna().mean() > threshold:
                df.drop(columns=[col], inplace=True)

    elif config.missing_strategy == MissingStrategy.MEAN:
        # fill missing with column average — only for numerical columns
        num_cols = df[feature_cols].select_dtypes(include="number").columns
        for col in num_cols:
            df[col].fillna(df[col].mean(), inplace=True)

    elif config.missing_strategy == MissingStrategy.MEDIAN:
        # fill missing with column median — better than mean for outliers
        num_cols = df[feature_cols].select_dtypes(include="number").columns
        for col in num_cols:
            df[col].fillna(df[col].median(), inplace=True)

    elif config.missing_strategy == MissingStrategy.MODE:
        # fill missing with most frequent value — good for categorical
        for col in feature_cols:
            df[col].fillna(df[col].mode()[0], inplace=True)

    elif config.missing_strategy == MissingStrategy.CONSTANT:
        # fill missing with fixed values
        num_cols = df[feature_cols].select_dtypes(include="number").columns
        cat_cols = df[feature_cols].select_dtypes(include="object").columns
        df[num_cols] = df[num_cols].fillna(0)
        df[cat_cols] = df[cat_cols].fillna("Unknown")

    elif config.missing_strategy == MissingStrategy.FORWARD_FILL:
        # fill missing with value from previous row — good for time series
        df[feature_cols] = df[feature_cols].fillna(method="ffill")

    # ── Step 3: Encode Categorical Columns ──────────────────────
    # ML models need numbers — text columns must be converted
    cat_cols = [
        c for c in df.select_dtypes(include="object").columns
        if c != target_column
    ]

    if config.encoding_method == EncodingMethod.LABEL:
        # assign integer to each unique value
        # Example: ["cat", "dog", "cat"] → [0, 1, 0]
        from sklearn.preprocessing import LabelEncoder
        le = LabelEncoder()
        for col in cat_cols:
            df[col] = le.fit_transform(df[col].astype(str))

    elif config.encoding_method == EncodingMethod.ONE_HOT:
        # create one binary column per unique value
        # Example: color=[red,blue] → color_red=[1,0], color_blue=[0,1]
        # drop_first=True avoids multicollinearity
        if cat_cols:
            df = pd.get_dummies(df, columns=cat_cols, drop_first=True)

    # ── Step 4: Scale Numerical Columns ─────────────────────────
    # Never scale the target column
    num_cols = [
        c for c in df.select_dtypes(include="number").columns
        if c != target_column
    ]

    if config.scaling_method == ScalingMethod.MIN_MAX:
        # scale to [0, 1]: (x - min) / (max - min)
        from sklearn.preprocessing import MinMaxScaler
        scaler = MinMaxScaler()
        df[num_cols] = scaler.fit_transform(df[num_cols])

    elif config.scaling_method == ScalingMethod.STANDARD:
        # standardize: (x - mean) / std → mean=0, std=1
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        df[num_cols] = scaler.fit_transform(df[num_cols])

    elif config.scaling_method == ScalingMethod.ROBUST:
        # robust to outliers: (x - median) / IQR
        from sklearn.preprocessing import RobustScaler
        scaler = RobustScaler()
        df[num_cols] = scaler.fit_transform(df[num_cols])

    elif config.scaling_method == ScalingMethod.LOG:
        # log transform for skewed distributions
        import numpy as np
        for col in num_cols:
            df[col] = np.log1p(df[col])  # log(x+1) handles 0 values

    return df