from pydantic import BaseModel

class ColumnStats(BaseModel):
    name: str
    dtype: str
    missing_count: int
    missing_percent: float
    # numerical stats — None for non-numerical columns
    mean:   float | None = None
    median: float | None = None
    std:    float | None = None
    min:    float | None = None
    max:    float | None = None
    # categorical stats — None for numerical columns
    unique_count:  int         | None = None
    top_value:     str         | None = None   # most frequent value
    top_frequency: int         | None = None   # how many times it appears

class DataStatsResponse(BaseModel):
    dataset_id:    str
    total_rows:    int
    total_columns: int
    numeric_cols:  int    # how many numerical columns
    categorical_cols: int # how many categorical columns
    duplicate_rows: int   # how many duplicate rows
    columns: list[ColumnStats]