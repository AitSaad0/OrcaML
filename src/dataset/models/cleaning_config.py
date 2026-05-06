import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from src.config.db import Base
from src.dataset.models.cleaning_enums import (
    MissingStrategy, EncodingMethod, ScalingMethod, CleaningVersion
)

class CleaningConfig(Base):
    __tablename__ = "cleaning_configs"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    environment_id = Column(UUID(as_uuid=True), ForeignKey("environments.id"), nullable=False)

    # V1 — must have
    missing_strategy  = Column(SAEnum(MissingStrategy), default=MissingStrategy.MEDIAN, nullable=False)
    remove_duplicates = Column(Boolean, default=True, nullable=False)
    encoding_method   = Column(SAEnum(EncodingMethod), default=EncodingMethod.ONE_HOT, nullable=False)
    scaling_method    = Column(SAEnum(ScalingMethod),  default=ScalingMethod.STANDARD, nullable=False)

    # version
    version    = Column(SAEnum(CleaningVersion), default=CleaningVersion.V1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    environment   = relationship("Environment", back_populates="cleaning_config")
    cleaned_datasets = relationship("CleanedDataset", back_populates="cleaning_config")

    def __repr__(self):
        return f"<CleaningConfig id={self.id} version={self.version}>"