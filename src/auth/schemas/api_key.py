from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyResponse(BaseModel):
    id:         UUID
    name:       str
    prefix:     str
    created_at: datetime
    last_used_at: datetime | None = None
    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Retourné une seule fois à la création — contient la clé brute."""
    raw_key: str