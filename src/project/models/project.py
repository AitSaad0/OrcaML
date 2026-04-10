import uuid

from alembic.environment import Column
from sqlalchemy import UUID, DateTime, ForeignKey, String, func
from sqlalchemy.orm import relationship

from src.config.db import Base


class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="projects")



    def __repr__(self):
        return f"<Project id={self.id} name={self.name}>"