from pydantic import BaseModel


# ── Chart models ─────────────────────────────────────────────

class HistogramBucket(BaseModel):
    bin_start: float
    bin_end:   float
    count:     int

class BarEntry(BaseModel):
    label: str
    count: float


# ── Column stats ─────────────────────────────────────────────

class ColumnStats(BaseModel):
    name:            str
    dtype:           str
    missing_count:   int
    missing_percent: float

    # numerical
    mean:   float | None = None
    median: float | None = None
    std:    float | None = None
    min:    float | None = None
    max:    float | None = None
    histogram: list[HistogramBucket] | None = None  # ← NEW

    # categorical
    unique_count:  int | None = None
    top_value:     str | None = None
    top_frequency: int | None = None
    bar_chart: list[BarEntry] | None = None         # ← NEW


# ── Response ─────────────────────────────────────────────────

class DataStatsResponse(BaseModel):
    dataset_id:       str
    total_rows:       int
    total_columns:    int
    numeric_cols:     int
    categorical_cols: int
    duplicate_rows:   int
    columns:          list[ColumnStats]
    chart_missing:    list[BarEntry] = []            # ← NEW