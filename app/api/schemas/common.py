from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PremiumPredictRequest(BaseModel):
    zone: str = "HSR Layout"
    forecast_features: Dict[str, Any] = Field(default_factory=dict)
    rider_features: Dict[str, Any] = Field(default_factory=dict)
    is_simulated: bool = False
    prefer_ml: bool = True
    weather_severity: Optional[float] = None
    claim_history: Optional[float] = None
    zone_risk_score: Optional[float] = None


class DemoBootstrapRequest(BaseModel):
    rider_id: str
    rider_name: Optional[str] = Field(default=None, alias="name")
    zone: str = "HSR Layout"
    upi_id: Optional[str] = None
    exclusions_accepted: bool = True
    forecast_features: Dict[str, Any] = Field(default_factory=dict)
    rider_features: Dict[str, Any] = Field(default_factory=dict)
    prefer_ml: bool = True
    weather_severity: Optional[float] = None
    claim_history: Optional[float] = None
    zone_risk_score: Optional[float] = None

    model_config = {"populate_by_name": True}
