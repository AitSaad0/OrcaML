import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.config.db import Base


class ModelArtifact(Base):
    __tablename__ = "models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    environment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    algorithm     = Column(String(100), nullable=False)
    mlflow_run_id = Column(String(255), nullable=False)

    file_path = Column(String(500), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    run = relationship("Run", back_populates="model_artifact")
    environment = relationship("Environment", back_populates="models")
    deployments = relationship(
        "Deployment",
        back_populates="model",
        cascade="all, delete-orphan",
    )