import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.config.db import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    deployment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    input_features   = Column(JSON,   nullable=False)  # features brutes envoyées
    prediction       = Column(JSON,   nullable=False)  # ex: [1] ou [0]
    prediction_label = Column(String, nullable=True)   # str(prediction[0])
    confidence       = Column(Float,  nullable=True)   # proba max si dispo

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    deployment = relationship("Deployment", back_populates="predictions")

    def __repr__(self):
        return f"<Prediction id={self.id} deployment_id={self.deployment_id}>"