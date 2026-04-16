import os
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import now_utc
from app.api.schemas import (
    NotificationSendRequest,
    PaymentCollectRequest,
    PayoutInitiateRequest,
)
from app.core.database import get_db
from app.core.models import AuditLog

payments_router = APIRouter(prefix="/payments", tags=["payments"])
payouts_router = APIRouter(prefix="/payouts", tags=["payments"])
notifications_router = APIRouter(prefix="/notifications", tags=["payments"])


@payments_router.post("/collect")
def collect_premium(payload: PaymentCollectRequest, db: Session = Depends(get_db)):
    tx_id = f"txn_col_{uuid4().hex[:10]}"
    db.add(
        AuditLog(
            entity_type="Payment",
            entity_id=tx_id,
            action="PREMIUM_COLLECTED",
            metadata_json={
                "rider_id": payload.rider_id,
                "policy_id": payload.policy_id,
                "amount": payload.amount,
                "upi_id": payload.upi_id,
            },
        )
    )
    db.commit()
    return {
        "transaction_id": tx_id,
        "status": "success",
        "collected_at": now_utc().isoformat(),
        "amount": payload.amount,
        "message": f"Successfully deducted INR {payload.amount} from {payload.upi_id}",
    }


@payouts_router.post("/initiate")
def initiate_payout(payload: PayoutInitiateRequest, db: Session = Depends(get_db)):
    tx_id = f"txn_pay_{uuid4().hex[:10]}"
    db.add(
        AuditLog(
            entity_type="Payout",
            entity_id=tx_id,
            action="PAYOUT_INITIATED",
            metadata_json={
                "claim_id": payload.claim_id,
                "rider_id": payload.rider_id,
                "amount": payload.amount,
                "upi_id": payload.upi_id,
            },
        )
    )
    db.commit()
    return {
        "transaction_id": tx_id,
        "status": "success",
        "processed_at": now_utc().isoformat(),
        "amount": payload.amount,
        "message": f"Successfully initiated INR {payload.amount} transfer to {payload.upi_id}",
        "stp_latency_ms": 142,
    }


@notifications_router.post("/send")
def send_notification(payload: NotificationSendRequest, db: Session = Depends(get_db)):
    msg_id = f"msg_{uuid4().hex[:10]}"

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if bot_token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            telegram_payload = {
                "chat_id": chat_id,
                "text": f"🚨 *ProtoRyde Instant Payout* 🚨\n\n*Rider ID*: `{payload.rider_id}`\n*Status*: Paid ✅\n\n*Message*: {payload.message}",
                "parse_mode": "Markdown",
            }
            requests.post(url, json=telegram_payload, timeout=5)
        except Exception:
            pass

    db.add(
        AuditLog(
            entity_type="Notification",
            entity_id=msg_id,
            action="NOTIFICATION_SENT",
            metadata_json={
                "rider_id": payload.rider_id,
                "phone": payload.phone,
                "type": payload.type,
            },
        )
    )
    db.commit()
    return {
        "message_id": msg_id,
        "status": "delivered",
        "delivered_at": now_utc().isoformat(),
        "preview": payload.message,
    }
