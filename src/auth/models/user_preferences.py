import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.config.db import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    email_runs   = Column(Boolean, default=True,  nullable=False)
    deployments  = Column(Boolean, default=True,  nullable=False)
    weekly       = Column(Boolean, default=False, nullable=False)
    security     = Column(Boolean, default=False, nullable=False)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="preferences")