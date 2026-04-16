from typing import Optional

from pydantic import BaseModel


class TriggerSimulateRequest(BaseModel):
    zone: str = "HSR Layout"
    trigger_type: str = "HEAVY_RAIN"
    as_of: Optional[str] = None
    trigger_value: Optional[float] = None
    rider_id: str = "rdr_demo_hsr"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    avg_daily_earnings: float = 1050.0
    duration_hours: float = 9.0
