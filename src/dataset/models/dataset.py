from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from src.config.db import Base
from datetime import datetime
import uuid

class Dataset(Base):
    __tablename__ = "datasets"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String, nullable=False)
    size        = Column(Integer, nullable=False)
    r2_path     = Column(String, nullable=False)
    env_id      = Column(UUID(as_uuid=True), ForeignKey("environments.id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Dataset id={self.id} name={self.name}>"