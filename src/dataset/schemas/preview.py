from pydantic import BaseModel
from typing import Any

class ColumnInfo(BaseModel):
    name: str                  # column name e.g "age"
    dtype: str                 # data type e.g "int64", "object"
    missing_count: int         # how many NaN values
    missing_percent: float     # percentage of missing values

class DataPreviewResponse(BaseModel):
    dataset_id: str
    total_rows: int            # total number of rows
    total_columns: int         # total number of columns
    columns: list[ColumnInfo]  # info about each column
    head: list[dict[str, Any]] # first 5 rows as list of dicts