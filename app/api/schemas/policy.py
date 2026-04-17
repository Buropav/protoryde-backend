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


class PolicyActivateRequest(BaseModel):
    rider_id: RiderId
    zone: ZoneName
    exclusions_accepted: bool
    forecast_features: Dict[str, Any] = Field(default_factory=dict)
    rider_features: Dict[str, Any] = Field(default_factory=dict)
    prefer_ml: bool = True
    weather_severity: Optional[float] = None
    claim_history: Optional[float] = None
    zone_risk_score: Optional[float] = None
