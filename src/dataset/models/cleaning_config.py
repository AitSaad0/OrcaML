import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.config.db import Base


class CleaningConfig(Base):
    __tablename__ = "cleaning_configs"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    environment_id    = Column(UUID(as_uuid=True), ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    missing_strategy  = Column(String, nullable=False, default="MEDIAN")
    remove_duplicates = Column(Boolean, nullable=False, default=True)
    encoding_method   = Column(String, nullable=False, default="ONE_HOT")
    scaling_method    = Column(String, nullable=False, default="STANDARD")
    version           = Column(String, nullable=False, default="V1")
    column_rules      = Column(JSONB, nullable=True)
    status            = Column(String, nullable=False, default="configured")

    # relationships
    environment      = relationship("Environment", back_populates="cleaning_config")
    cleaned_datasets = relationship("CleanedDataset", back_populates="cleaning_config", cascade="all, delete-orphan")