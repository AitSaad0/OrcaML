import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Float,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.config.db import Base
from src.deployments.models.enums import DeploymentStatus

class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    environment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Docker info
    container_id   = Column(String(255), nullable=True)
    container_name = Column(String(255), nullable=True)
    subdomain     = Column(String(255), nullable=True)
    endpoint_url   = Column(String(500), nullable=True)

    # Status
    status = Column(
        SQLEnum(DeploymentStatus),
        default=DeploymentStatus.DEPLOYING,
        nullable=False,
        index=True,
    )

    # Observability
    total_calls    = Column(Integer, default=0, nullable=False)
    last_called_at = Column(DateTime(timezone=True), nullable=True)
    avg_latency_ms = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    stopped_at  = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    model       = relationship("ModelArtifact", back_populates="deployments")
    environment = relationship("Environment", back_populates="deployments")
    predictions = relationship("Prediction", back_populates="deployment", cascade="all, delete-orphan")