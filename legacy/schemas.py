from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str
    phone: str
    delhivery_partner_id: str
    zone: str


class SimulateTriggerRequest(BaseModel):
    zone: str
    trigger_type: str
    simulated_value: float


# ---------------------------------------------------------------------------
# Response schemas (ORM-mode enabled)
# ---------------------------------------------------------------------------

class RiderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    phone: str
    delhivery_partner_id: str
    zone: str
    created_at: datetime


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rider_id: str
    base_premium: float
    final_premium: float
    premium_breakdown: list | dict
    status: str
    created_at: datetime


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: str
    rider_id: str
    trigger_type: str
    payout_amount: float
    fraud_layers: dict
    status: str
    created_at: datetime


class RegisterResponse(BaseModel):
    status: str
    rider: RiderResponse
    policy: PolicyResponse


class SimulateResponse(BaseModel):
    status: str
    trigger_event_id: str
    claims_processed: int
    results: list[ClaimResponse]
