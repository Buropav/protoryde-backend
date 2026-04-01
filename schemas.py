from pydantic import BaseModel


class RegisterRequest(BaseModel):
    name: str
    phone: str
    delhivery_partner_id: str
    zone: str


class SimulateTriggerRequest(BaseModel):
    zone: str
    trigger_type: str
    simulated_value: float
