from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class UploadDatasetResponse(BaseModel):
    id:          UUID
    name:        str
    size:        int
    r2_path:     str
    env_id:      UUID
    uploaded_at: datetime
    model_config = {"from_attributes": True}

class GetDatasetResponse(BaseModel):
    id:          UUID
    name:        str
    size:        int
    r2_path:     str
    env_id:      UUID
    uploaded_at: datetime
    model_config = {"from_attributes": True}

class ListDatasetsResponse(BaseModel):
    datasets: list[GetDatasetResponse]

class DeleteDatasetResponse(BaseModel):
    message: str = "Dataset deleted successfully"