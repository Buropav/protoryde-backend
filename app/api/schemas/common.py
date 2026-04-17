from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

RiderId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"
    ),
]
ZoneName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
UpiId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=5, max_length=80, pattern=r"^[A-Za-z0-9._-]{2,}@[A-Za-z]{2,}$"
    ),
]
RiderName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]


class PremiumPredictRequest(BaseModel):
    zone: ZoneName = "HSR Layout"
    forecast_features: Dict[str, Any] = Field(default_factory=dict)
    rider_features: Dict[str, Any] = Field(default_factory=dict)
    is_simulated: bool = False
    prefer_ml: bool = True
    weather_severity: Optional[float] = None
    claim_history: Optional[float] = None
    zone_risk_score: Optional[float] = None


class DemoBootstrapRequest(BaseModel):
    rider_id: RiderId
    rider_name: Optional[RiderName] = Field(default=None, alias="name")
    zone: ZoneName = "HSR Layout"
    upi_id: Optional[UpiId] = None
    exclusions_accepted: bool = True
    forecast_features: Dict[str, Any] = Field(default_factory=dict)
    rider_features: Dict[str, Any] = Field(default_factory=dict)
    prefer_ml: bool = True
    weather_severity: Optional[float] = None
    claim_history: Optional[float] = None
    zone_risk_score: Optional[float] = None

    model_config = {"populate_by_name": True}
