from pydantic import BaseModel
from uuid import UUID


class PreferencesResponse(BaseModel):
    email_runs:  bool
    deployments: bool
    weekly:      bool
    security:    bool
    model_config = {"from_attributes": True}


class PreferencesUpdate(BaseModel):
    email_runs:  bool | None = None
    deployments: bool | None = None
    weekly:      bool | None = None
    security:    bool | None = None