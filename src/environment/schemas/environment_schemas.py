import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator
from src.environment.models.Environment_status import EnvironmentStatus
from src.environment.models.Task_type import TaskType

class EnvironmentBase(BaseModel):
    name: str
    target_column: str
    task_type: TaskType
    status: EnvironmentStatus

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Environment name must be at least 2 characters")
        return v.strip()

    @field_validator("target_column")
    @classmethod
    def target_column_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 1:
            raise ValueError("Target column cannot be empty")
        return v.strip()



class EnvironmentCreateRequest(EnvironmentBase):
    pass 


class EnvironmentUpdateRequest(BaseModel):
    name: str | None = None
    target_column: str | None = None
    task_type: TaskType | None = None
    status: EnvironmentStatus | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) < 2:
            raise ValueError("Environment name must be at least 2 characters")
        return v.strip() if v else v

    @field_validator("target_column")
    @classmethod
    def target_column_not_empty(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) < 1:
            raise ValueError("Target column cannot be empty")
        return v.strip() if v else v

    model_config = {"from_attributes": True}


class EnvironmentCreateResponse(EnvironmentBase):
    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class EnvironmentUpdateResponse(EnvironmentBase):
    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class EnvironmentListResponse(BaseModel):
    environments: list[EnvironmentCreateResponse]
    total: int

    model_config = {"from_attributes": True}



class EnvironmentSummary(BaseModel):
    id: uuid.UUID
    name: str
    status: EnvironmentStatus
    task_type: TaskType

    model_config = {"from_attributes": True}