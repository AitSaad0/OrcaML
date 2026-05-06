import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.config.db import Base

class CleanedStatus(str):
    PENDING  = "pending"
    CLEANING = "cleaning"
    READY    = "ready"
    FAILED   = "failed"

class CleanedDataset(Base):
    __tablename__ = "cleaned_datasets"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    environment_id   = Column(UUID(as_uuid=True), ForeignKey("environments.id"), nullable=False)
    cleaning_config_id = Column(UUID(as_uuid=True), ForeignKey("cleaning_configs.id"), nullable=False)

    file_path        = Column(String, nullable=True)     # R2 path of clean file
    rows_before      = Column(Integer, nullable=True)    # rows before cleaning
    rows_after       = Column(Integer, nullable=True)    # rows after cleaning
    columns_dropped  = Column(Integer, nullable=True)    # how many columns removed
    status           = Column(String, default="pending", nullable=False)
    cleaned_at       = Column(DateTime(timezone=True), nullable=True)
    created_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    environment    = relationship("Environment", back_populates="cleaned_datasets")
    cleaning_config = relationship("CleaningConfig", back_populates="cleaned_datasets")

    def __repr__(self):
        return f"<CleanedDataset id={self.id} status={self.status}>"