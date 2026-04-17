from typing import Any, Dict

from pydantic import BaseModel, Field


class ResolvePredictionRequest(BaseModel):
    prediction_id: int
    actual_value: float = Field(ge=0)
    metadata_patch: Dict[str, Any] = Field(default_factory=dict)
