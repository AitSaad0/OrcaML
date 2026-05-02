import io
import pandas as pd
import boto3
from src.config.config import settings
from src.dataset.schemas.stats import DataStatsResponse, ColumnStats


def get_s3_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        region_name="auto",
    )


def generate_stats(r2_path: str, dataset_id: str) -> DataStatsResponse:
    """
    Read full CSV from R2 and compute statistics per column.

    Pandas concepts used:
    - df.describe()         → summary stats for numerical columns
    - df.select_dtypes()    → filter columns by type
    - df.duplicated().sum() → count duplicate rows
    - df[col].value_counts()→ frequency of each value
    """

    # ── Step 1: Download from R2 ─────────────────────────────────
    s3 = get_s3_client()
    response   = s3.get_object(Bucket=settings.R2_BUCKET_NAME, Key=r2_path)
    file_bytes = response["Body"].read()
    df         = pd.read_csv(io.BytesIO(file_bytes))

    # ── Step 2: Identify column types ───────────────────────────
    # select_dtypes(include="number") → only int64, float64 columns
    # select_dtypes(include="object") → only string/text columns
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include="object").columns.tolist()

    # ── Step 3: Count duplicates ─────────────────────────────────
    # df.duplicated() → True/False per row (True = duplicate)
    # .sum()          → count of True = count of duplicates
    duplicate_rows = int(df.duplicated().sum())

    # ── Step 4: Compute stats per column ────────────────────────
    columns = []
    for col in df.columns:

        missing_count   = int(df[col].isna().sum())
        missing_percent = round(float(df[col].isna().mean() * 100), 2)

        if col in num_cols:
            # ── Numerical column ──────────────────────────────
            # df[col].mean()   → average value
            # df[col].median() → middle value (50th percentile)
            # df[col].std()    → standard deviation (spread)
            # df[col].min()    → smallest value
            # df[col].max()    → largest value
            columns.append(ColumnStats(
                name            = col,
                dtype           = str(df[col].dtype),
                missing_count   = missing_count,
                missing_percent = missing_percent,
                mean            = round(float(df[col].mean()),   4) if not df[col].isna().all() else None,
                median          = round(float(df[col].median()), 4) if not df[col].isna().all() else None,
                std             = round(float(df[col].std()),    4) if not df[col].isna().all() else None,
                min             = round(float(df[col].min()),    4) if not df[col].isna().all() else None,
                max             = round(float(df[col].max()),    4) if not df[col].isna().all() else None,
            ))

        else:
            # ── Categorical column ────────────────────────────
            # value_counts() → counts how many times each value appears
            # Example: {"Paris": 10, "London": 5, "Berlin": 3}
            # .index[0]      → most frequent value ("Paris")
            # .iloc[0]       → its count (10)
            value_counts  = df[col].value_counts()
            top_value     = str(value_counts.index[0])   if len(value_counts) > 0 else None
            top_frequency = int(value_counts.iloc[0])    if len(value_counts) > 0 else None

            columns.append(ColumnStats(
                name            = col,
                dtype           = str(df[col].dtype),
                missing_count   = missing_count,
                missing_percent = missing_percent,
                unique_count    = int(df[col].nunique()),  # nunique() = number of unique values
                top_value       = top_value,
                top_frequency   = top_frequency,
            ))

    # ── Step 5: Return ───────────────────────────────────────────
    return DataStatsResponse(
        dataset_id       = str(dataset_id),
        total_rows       = len(df),
        total_columns    = len(df.columns),
        numeric_cols     = len(num_cols),
        categorical_cols = len(cat_cols),
        duplicate_rows   = duplicate_rows,
        columns          = columns,
    )