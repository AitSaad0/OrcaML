import uuid

from sqlalchemy import UUID, Column, DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from src.environment.models.Task_type import TaskType
from src.environment.models.Environment_status import EnvironmentStatus
from src.config.db import Base


class Environment(Base):
    __tablename__ = "environments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    target_column = Column(String, nullable=False)
    task_type = Column(SAEnum(TaskType,  name="tasktype", create_type=True), nullable=False)
    status = Column(SAEnum(EnvironmentStatus, name="environmentstatus", create_type=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

    project = relationship("Project", back_populates="environments")

    def __repr__(self):
        return f"<Environment id={self.id} name={self.name}>"