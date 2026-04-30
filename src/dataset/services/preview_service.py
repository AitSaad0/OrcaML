import io
import pandas as pd
import boto3
from src.config.config import settings
from src.dataset.schemas.preview import DataPreviewResponse, ColumnInfo

def get_s3_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        region_name="auto",
    )

def generate_preview(r2_path: str, dataset_id: str) -> DataPreviewResponse:
    """
    1. Download CSV from R2 into RAM (as bytes)
    2. Read with pandas — never saved to disk
    3. Extract stats and return
    """

    # ── Step 1: Download file from R2 into RAM ──────────────────
    # get_object returns the file as a stream
    # we read it into bytes → wrap in BytesIO → pandas reads it
    # BytesIO is like a "fake file" in memory
    s3 = get_s3_client()
    response = s3.get_object(Bucket=settings.R2_BUCKET_NAME, Key=r2_path)
    file_bytes = response["Body"].read()          # raw bytes in RAM
    file_like  = io.BytesIO(file_bytes)           # wrap as file-like object

    # ── Step 2: Read with pandas ────────────────────────────────
    # pd.read_csv reads the file and creates a DataFrame
    # A DataFrame is like an Excel table in Python
    # Example:
    #    age  name    salary
    # 0   25  Alice   50000
    # 1   30  Bob     60000
    df = pd.read_csv(file_like)

    # ── Step 3: Extract column information ──────────────────────
    columns = []
    for col in df.columns:
        # df[col].dtype    → the data type of the column (int64, float64, object)
        # df[col].isna()   → True/False for each row (True = missing)
        # .sum()           → count of True values = count of missing
        # .mean() * 100    → percentage of missing values
        missing_count   = int(df[col].isna().sum())
        missing_percent = round(float(df[col].isna().mean() * 100), 2)

        columns.append(ColumnInfo(
            name            = col,
            dtype           = str(df[col].dtype),
            missing_count   = missing_count,
            missing_percent = missing_percent,
        ))

    # ── Step 4: Get first 5 rows ─────────────────────────────────
    # df.head(5)          → first 5 rows as DataFrame
    # .to_dict("records") → convert to list of dicts
    # Example: [{"age": 25, "name": "Alice"}, {"age": 30, "name": "Bob"}]
    # fillna("") → replace NaN with empty string so JSON doesn't break
    head = df.head(5).fillna("").to_dict("records")

    # ── Step 5: Return the preview ───────────────────────────────
    return DataPreviewResponse(
        dataset_id     = str(dataset_id),
        total_rows     = len(df),        # len(df) = number of rows
        total_columns  = len(df.columns),# len(df.columns) = number of columns
        columns        = columns,
        head           = head,
    )