from typing import Optional

from pydantic import BaseModel, Field, StringConstraints, field_validator
from typing_extensions import Annotated

TriggerType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=40),
]
RiderId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"
    ),
]
ZoneName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)
]


class TriggerSimulateRequest(BaseModel):
    zone: ZoneName = "HSR Layout"
    trigger_type: TriggerType = "HEAVY_RAIN"
    as_of: Optional[str] = None
    trigger_value: Optional[float] = Field(default=None, ge=0)
    rider_id: RiderId = "rdr_demo_hsr"
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    avg_daily_earnings: float = Field(default=1050.0, gt=0)
    duration_hours: float = Field(default=9.0, gt=0, le=24)

    @field_validator("trigger_type")
    @classmethod
    def normalize_trigger_type(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {
            "HEAVY_RAIN",
            "EXTREME_HEAT",
            "SEVERE_AQI",
            "BRANCH_CLOSURE",
            "DELHIVERY_ADVISORY",
        }
        if normalized not in allowed:
            raise ValueError(
                "trigger_type must be one of HEAVY_RAIN, EXTREME_HEAT, SEVERE_AQI, BRANCH_CLOSURE, DELHIVERY_ADVISORY"
            )
        return normalized
