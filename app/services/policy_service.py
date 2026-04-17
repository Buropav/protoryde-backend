from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import uuid4
from typing import Dict, Any

from app.api.constants import EXCLUSIONS_VERSION
from app.api.dependencies import check_enrollment_lockout, ensure_rider_and_policy, predict_premium, now_utc
from app.api.schemas import PolicyActivateRequest, DemoBootstrapRequest
from app.core.models import Rider, AuditLog
from app.triggers.weather_service import ZONES

def activate_rider_policy(db: Session, payload: PolicyActivateRequest) -> Dict[str, Any]:
    if payload.zone not in ZONES:
        raise HTTPException(
            status_code=422,
            detail={"error": "UNSUPPORTED_ZONE", "message": "Unsupported zone"},
        )
    if not payload.exclusions_accepted:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "EXCLUSIONS_NOT_ACKNOWLEDGED",
                "message": "Policy activation requires exclusions acceptance",
            },
        )

    active_warnings = check_enrollment_lockout(payload.zone)
    if active_warnings:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "ENROLLMENT_LOCKOUT",
                "message": "Cannot activate policy during an active weather advisory. Try again when conditions normalize.",
                "active_warnings": active_warnings,
            },
        )

    policy = ensure_rider_and_policy(
        db, rider_id=payload.rider_id, zone=payload.zone, exclusions_acknowledged=True
    )
    premium = predict_premium(
        zone=payload.zone,
        forecast_features=payload.forecast_features,
        rider_features=payload.rider_features,
        prefer_ml=payload.prefer_ml,
        explicit_zone_risk=payload.zone_risk_score,
        weather_severity=payload.weather_severity,
        claim_history=payload.claim_history,
    )

    policy.base_premium = premium["base_premium"]
    policy.final_premium = premium["final_premium"]
    policy.premium_breakdown = premium["adjustments"]
    policy.exclusions_acknowledged_at = now_utc()
    policy.status = "active"

    db.add(
        AuditLog(
            entity_type="Policy",
            entity_id=policy.id,
            action="POLICY_ACTIVATED",
            metadata_json={
                "rider_id": payload.rider_id,
                "zone": payload.zone,
                "exclusions_version": EXCLUSIONS_VERSION,
            },
        )
    )
    db.commit()
    db.refresh(policy)

    return {
        "policy_id": policy.id,
        "rider_id": payload.rider_id,
        "zone": payload.zone,
        "status": policy.status,
        "base_premium": policy.base_premium,
        "final_premium": policy.final_premium,
        "premium_breakdown": policy.premium_breakdown,
        "premium_engine": premium["engine"],
        "exclusions_version": EXCLUSIONS_VERSION,
        "exclusions_acknowledged_at": policy.exclusions_acknowledged_at.isoformat()
        if policy.exclusions_acknowledged_at
        else None,
    }

def bootstrap_demo_rider(db: Session, payload: DemoBootstrapRequest) -> Rider:
    rider = db.query(Rider).filter(Rider.id == payload.rider_id).first()
    rider_name = payload.rider_name or "ProtoRyde Rider"
    rider_upi = payload.upi_id or "rider@upi"

    if rider is None:
        rider = Rider(
            id=payload.rider_id,
            name=rider_name,
            phone=f"9{uuid4().hex[:9]}",
            delhivery_partner_id=f"DEL-{uuid4().hex[:8].upper()}",
            zone=payload.zone,
            upi_id=rider_upi,
            avg_daily_earnings=1050.0,
            claim_rate_12wk=0.6,
            fraud_flag_count=0,
            kyc_verified=True,
        )
        db.add(rider)
        db.flush()
    else:
        rider.name = rider_name
        rider.zone = payload.zone
        rider.upi_id = rider_upi
        db.flush()

    return rider
