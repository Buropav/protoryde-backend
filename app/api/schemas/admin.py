from typing import Any, Dict

from pydantic import BaseModel, Field


class ResolvePredictionRequest(BaseModel):
    prediction_id: int
    actual_value: float
    metadata_patch: Dict[str, Any] = Field(default_factory=dict)
