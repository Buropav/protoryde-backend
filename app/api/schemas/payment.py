from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

RiderId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"
    ),
]
RecordId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$"
    ),
]
UpiId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=5, max_length=80, pattern=r"^[A-Za-z0-9._-]{2,}@[A-Za-z]{2,}$"
    ),
]
Phone = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=10, max_length=16, pattern=r"^\+?[0-9]{10,15}$"
    ),
]


class PaymentCollectRequest(BaseModel):
    rider_id: RiderId
    policy_id: RecordId
    amount: float = Field(gt=0)
    upi_id: UpiId


class PayoutInitiateRequest(BaseModel):
    claim_id: RecordId
    rider_id: RiderId
    amount: float = Field(gt=0)
    upi_id: UpiId


class NotificationSendRequest(BaseModel):
    rider_id: RiderId
    phone: Phone
    message: str = Field(min_length=2, max_length=500)
    type: str = "sms"
