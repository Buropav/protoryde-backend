import os
import json
import hashlib
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import now_utc
from app.api.schemas import (
    NotificationSendRequest,
    PaymentCollectRequest,
    PayoutInitiateRequest,
)
from app.core.database import get_db
from app.core.models import AuditLog, Claim, Policy, Rider
from app.services.payout_service import (
    PayoutService,
    TriggerEvent as PayoutTriggerEvent,
)
from app.services.razorpay_service import (
    RazorpayAPIError,
    RazorpayConfigError,
    create_payment_link,
    create_upi_payout,
)

payments_router = APIRouter(prefix="/payments", tags=["payments"])
payouts_router = APIRouter(prefix="/payouts", tags=["payments"])
notifications_router = APIRouter(prefix="/notifications", tags=["payments"])


@payments_router.post("/collect")
def collect_premium(payload: PaymentCollectRequest, db: Session = Depends(get_db)):
    policy = (
        db.query(Policy)
        .filter(Policy.id == payload.policy_id, Policy.rider_id == payload.rider_id)
        .first()
    )
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "POLICY_NOT_FOUND",
                "message": "Policy not found for rider",
            },
        )

    if policy.status != "active":
        raise HTTPException(
            status_code=422,
            detail={"error": "POLICY_INACTIVE", "message": "Policy is not active"},
        )

    expected = float(policy.final_premium or 0.0)
    if expected > 0 and abs(float(payload.amount) - expected) > 0.01:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "AMOUNT_MISMATCH",
                "message": f"Expected premium amount is {expected}",
            },
        )

    tx_id = f"txn_col_{uuid4().hex[:10]}"
    created_at = now_utc()
    try:
        payment_link = create_payment_link(
            amount_inr=float(payload.amount),
            rider_id=payload.rider_id,
            policy_id=payload.policy_id,
            upi_id=payload.upi_id,
        )
    except RazorpayConfigError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "RAZORPAY_NOT_CONFIGURED", "message": str(exc)},
        ) from exc
    except RazorpayAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "RAZORPAY_ERROR", "message": str(exc)},
        ) from exc

    receipt_hash = hashlib.sha256(
        json.dumps(
            {
                "transaction_id": tx_id,
                "rider_id": payload.rider_id,
                "policy_id": payload.policy_id,
                "amount": float(payload.amount),
                "created_at": created_at.isoformat(),
                "razorpay_link_id": payment_link.get("id"),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    db.add(
        AuditLog(
            entity_type="Payment",
            entity_id=tx_id,
            action="PREMIUM_COLLECTION_LINK_CREATED",
            metadata_json={
                "rider_id": payload.rider_id,
                "policy_id": payload.policy_id,
                "amount": payload.amount,
                "upi_id": payload.upi_id,
                "receipt_hash": receipt_hash,
                "channel": "razorpay_payment_link",
                "razorpay_link_id": payment_link.get("id"),
                "razorpay_short_url": payment_link.get("short_url"),
                "razorpay_status": payment_link.get("status"),
            },
        )
    )
    db.commit()
    return {
        "transaction_id": tx_id,
        "status": "pending_collection",
        "collected_at": created_at.isoformat(),
        "amount": payload.amount,
        "receipt_hash": receipt_hash,
        "payment_link_id": payment_link.get("id"),
        "payment_link_url": payment_link.get("short_url"),
        "provider_status": payment_link.get("status"),
        "message": f"Payment link created for INR {payload.amount}",
    }


@payouts_router.post("/initiate")
def initiate_payout(payload: PayoutInitiateRequest, db: Session = Depends(get_db)):
    claim = (
        db.query(Claim)
        .filter(Claim.id == payload.claim_id, Claim.rider_id == payload.rider_id)
        .first()
    )
    if claim is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "CLAIM_NOT_FOUND", "message": "Claim not found for rider"},
        )

    if claim.payout_status != "PAID":
        raise HTTPException(
            status_code=422,
            detail={
                "error": "PAYOUT_NOT_APPROVED",
                "message": "Claim payout has not been approved",
            },
        )

    approved_amount = float(claim.payout_amount or 0.0)
    if abs(float(payload.amount) - approved_amount) > 0.01:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "AMOUNT_MISMATCH",
                "message": f"Approved payout amount is {approved_amount}",
            },
        )

    rider = db.query(Rider).filter(Rider.id == payload.rider_id).first()
    rider_name = rider.name if rider and rider.name else payload.rider_id

    try:
        razorpay_payout = create_upi_payout(
            amount_inr=float(payload.amount),
            rider_id=payload.rider_id,
            rider_name=rider_name,
            upi_id=payload.upi_id,
            claim_id=payload.claim_id,
        )
    except RazorpayConfigError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "RAZORPAY_NOT_CONFIGURED", "message": str(exc)},
        ) from exc
    except RazorpayAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "RAZORPAY_ERROR", "message": str(exc)},
        ) from exc

    payout_result = PayoutService.process_trigger_payout(
        rider_id=payload.rider_id,
        trigger_event=PayoutTriggerEvent(
            trigger_type=claim.trigger_type,
            value=float(claim.trigger_value or 0.0),
            threshold=float(claim.trigger_threshold or 0.0),
            breached=float(claim.trigger_value or 0.0)
            >= float(claim.trigger_threshold or 0.0),
        ),
        fraud_result={
            "claim_id": claim.id,
            "recommended_payout": approved_amount,
        },
        db=db,
    )

    tx_id = f"txn_pay_{uuid4().hex[:10]}"
    processed_at = now_utc()
    claim.payout_initiated_at = processed_at

    db.add(
        AuditLog(
            entity_type="Payout",
            entity_id=tx_id,
            action="PAYOUT_SETTLED",
            metadata_json={
                "claim_id": payload.claim_id,
                "rider_id": payload.rider_id,
                "amount": payload.amount,
                "upi_id": payload.upi_id,
                "utr_number": payout_result.utr_number,
                "smart_contract_hash": payout_result.smart_contract_hash,
                "verification_url": payout_result.verification_url,
                "razorpay_payout_id": razorpay_payout.get("id"),
                "razorpay_payout_status": razorpay_payout.get("status"),
                "razorpay_reference_id": razorpay_payout.get("reference_id"),
            },
        )
    )
    db.commit()
    return {
        "transaction_id": tx_id,
        "status": "settled",
        "processed_at": processed_at.isoformat(),
        "amount": payload.amount,
        "utr_number": payout_result.utr_number,
        "smart_contract_hash": payout_result.smart_contract_hash,
        "verification_url": payout_result.verification_url,
        "provider_payout_id": razorpay_payout.get("id"),
        "provider_status": razorpay_payout.get("status"),
        "stp_latency_ms": max(1, int(payout_result.processed_in_seconds * 1000)),
        "message": f"Payout initiated for INR {payload.amount} to {payload.upi_id}",
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
                "message": payload.message,
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


@notifications_router.get("/{rider_id}")
def get_notifications(rider_id: str, db: Session = Depends(get_db)):
    # Keep this filter backend-agnostic across SQLite/Postgres JSON behavior.
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "Notification")
        .order_by(AuditLog.created_at.desc())
        .limit(200)
        .all()
    )
    rider_logs = [
        log
        for log in logs
        if isinstance(log.metadata_json, dict)
        and log.metadata_json.get("rider_id") == rider_id
    ][:20]
    return {
        "notifications": [
            {
                "id": log.id,
                "title": log.action.replace("_", " ").title(),
                "description": log.metadata_json.get("message", "System notification"),
                "time": log.created_at.isoformat(),
                "type": log.metadata_json.get("type", "INFO"),
            }
            for log in rider_logs
        ]
    }
