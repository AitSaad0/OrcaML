from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from src.dataset.models.cleaning_enums import (
    MissingStrategy, EncodingMethod, ScalingMethod, CleaningVersion
)

class CleaningConfigCreate(BaseModel):
    missing_strategy:  MissingStrategy  = MissingStrategy.MEDIAN
    remove_duplicates: bool             = True
    encoding_method:   EncodingMethod   = EncodingMethod.ONE_HOT
    scaling_method:    ScalingMethod    = ScalingMethod.STANDARD
    version:           CleaningVersion  = CleaningVersion.V1

class CleaningConfigResponse(BaseModel):
    id:               UUID
    environment_id:   UUID
    missing_strategy: MissingStrategy
    remove_duplicates: bool
    encoding_method:  EncodingMethod
    scaling_method:   ScalingMethod
    version:          CleaningVersion
    created_at:       datetime

    model_config = {"from_attributes": True}