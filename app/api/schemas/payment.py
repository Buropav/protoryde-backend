from pydantic import BaseModel


class PaymentCollectRequest(BaseModel):
    rider_id: str
    policy_id: str
    amount: float
    upi_id: str


class PayoutInitiateRequest(BaseModel):
    claim_id: str
    rider_id: str
    amount: float
    upi_id: str


class NotificationSendRequest(BaseModel):
    rider_id: str
    phone: str
    message: str
    type: str = "sms"
