from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class CleanedDatasetResponse(BaseModel):
    id:                 UUID
    environment_id:     UUID
    cleaning_config_id: UUID
    file_path:          Optional[str]
    rows_before:        Optional[int]
    rows_after:         Optional[int]
    columns_dropped:    Optional[int]
    status:             str
    cleaned_at:         Optional[datetime]
    created_at:         datetime

    model_config = {"from_attributes": True}