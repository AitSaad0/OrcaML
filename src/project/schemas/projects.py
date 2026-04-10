from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Project name must be at least 2 characters")
        return v.strip()


class CreateProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    user_id: UUID          # ← so client knows which user owns it
    created_at: datetime
    model_config = {"from_attributes": True}


class GetProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    user_id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class ListProjectsResponse(BaseModel):
    projects: list[GetProjectResponse]


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class UpdateProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class DeleteProjectResponse(BaseModel):
    message: str = "Project deleted successfully"