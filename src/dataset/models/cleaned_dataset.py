import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.config.db import Base


class CleanedDataset(Base):
    __tablename__ = "cleaned_datasets"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    environment_id      = Column(UUID(as_uuid=True), ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    cleaning_config_id  = Column(UUID(as_uuid=True), ForeignKey("cleaning_configs.id", ondelete="CASCADE"), nullable=False)
    status              = Column(String, nullable=False, default="pending")
    file_path           = Column(String, nullable=True)
    rows_before         = Column(Integer, nullable=True)
    rows_after          = Column(Integer, nullable=True)
    cleaned_at          = Column(DateTime, nullable=True)
    cleaning_report     = Column(JSONB, nullable=True)
    rolled_back         = Column(Boolean, nullable=False, default=False)
    rolled_back_at      = Column(DateTime, nullable=True)

    # relationships
    environment     = relationship("Environment", back_populates="cleaned_datasets")
    cleaning_config = relationship("CleaningConfig", back_populates="cleaned_datasets")