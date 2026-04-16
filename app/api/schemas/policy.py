from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PolicyActivateRequest(BaseModel):
    rider_id: str
    zone: str
    exclusions_accepted: bool
    forecast_features: Dict[str, Any] = Field(default_factory=dict)
    rider_features: Dict[str, Any] = Field(default_factory=dict)
    prefer_ml: bool = True
    weather_severity: Optional[float] = None
    claim_history: Optional[float] = None
    zone_risk_score: Optional[float] = None
