import uuid
import secrets
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.config.db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name       = Column(String, nullable=False)
    key_hash   = Column(String, nullable=False, unique=True)  # stocké haché
    prefix     = Column(String(12), nullable=False)           # sk_live_abc1 — affiché à l'utilisateur
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="api_keys")

    @staticmethod
    def generate() -> tuple[str, str]:
        """Retourne (raw_key, prefix). raw_key est affiché une seule fois."""
        raw = "sk_live_" + secrets.token_urlsafe(32)
        prefix = raw[:12]
        return raw, prefix