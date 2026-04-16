from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import ensure_rider_and_policy, now_utc
from app.api.routes.bank import fetch_banking_metrics
from app.api.routes.weather import fetch_delhivery_metrics
from app.api.schemas import TriggerSimulateRequest
from app.core.database import get_db
from app.core.models import AuditLog, Claim
from app.services.payout_service import (
    PayoutService,
    TriggerEvent as PayoutTriggerEvent,
)
from app.triggers.fraud_engine import FraudEngine, TRIGGER_THRESHOLDS
from app.triggers.weather_service import WeatherService, ZONES

triggers_router = APIRouter(prefix="/triggers", tags=["triggers"])
demo_triggers_router = APIRouter(prefix="/demo", tags=["triggers"])


@triggers_router.post("/simulate")
def simulate_trigger(payload: TriggerSimulateRequest, db: Session = Depends(get_db)):
    trigger_type = payload.trigger_type.upper()
    if trigger_type not in TRIGGER_THRESHOLDS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "UNSUPPORTED_TRIGGER",
                "message": "trigger_type must be one of HEAVY_RAIN, EXTREME_HEAT, SEVERE_AQI, BRANCH_CLOSURE, DELHIVERY_ADVISORY",
            },
        )

    if payload.zone not in ZONES:
        raise HTTPException(
            status_code=422,
            detail={"error": "UNSUPPORTED_ZONE", "message": "Unsupported zone"},
        )

    weather = WeatherService.get_current_conditions(payload.zone, is_simulated=False)
    trigger_view = weather["trigger_view"]

    derived_value = payload.trigger_value
    if derived_value is None:
        if trigger_type == "HEAVY_RAIN":
            derived_value = float(trigger_view["heavy_rain"]["value"])
        elif trigger_type == "EXTREME_HEAT":
            derived_value = float(trigger_view["extreme_heat"]["value"])
        elif trigger_type == "SEVERE_AQI":
            derived_value = float(trigger_view["severe_aqi"]["value"])
        elif trigger_type == "BRANCH_CLOSURE":
            branch = fetch_banking_metrics(payload.zone)
            derived_value = float(branch["closure_rate_pct"])
        else:
            delhivery = fetch_delhivery_metrics(
                payload.zone, now_utc().date().isoformat()
            )
            derived_value = float(delhivery["cancellation_rate_pct"])

    policy = ensure_rider_and_policy(db, rider_id=payload.rider_id, zone=payload.zone)

    result = FraudEngine.evaluate_claim(
        zone=payload.zone,
        trigger_type=trigger_type,
        trigger_value=float(derived_value),
        rider_id=payload.rider_id,
        avg_daily_earnings=payload.avg_daily_earnings,
        duration_hours=payload.duration_hours,
        coverage_tier=policy.coverage_tier,
        is_simulated=False,
        latitude=payload.latitude,
        longitude=payload.longitude,
        db=db,
    )

    claim = Claim(
        id=result["claim_id"],
        policy_id=policy.id,
        rider_id=payload.rider_id,
        zone=payload.zone,
        trigger_type=trigger_type,
        trigger_value=float(derived_value),
        trigger_threshold=float(result["trigger_event"]["threshold"]),
        is_simulated=False,
        fraud_check_passed=result["fraud_check_passed"],
        fraud_layers=result["fraud_layers"],
        payout_amount=float(result["recommended_payout"]),
        payout_status="PAID" if result["recommended_payout"] > 0 else "rejected",
        payout_initiated_at=now_utc() if result["recommended_payout"] > 0 else None,
        delhivery_cancellation_rate=next(
            (
                layer["evidence"].get("cancellation_rate_pct", 0.0)
                for layer in result["fraud_layers"]
                if layer["layer"] == "L3_DELHIVERY_CROSS_REF"
            ),
            0.0,
        ),
    )
    db.add(claim)
    db.add(
        AuditLog(
            entity_type="Simulation",
            entity_id=result["claim_id"],
            action="TRIGGER_SIMULATION_EXECUTED",
            metadata_json={
                "zone": payload.zone,
                "trigger_type": trigger_type,
                "is_simulated": False,
            },
        )
    )
    db.commit()

    return {
        "simulation_id": f"sim_{uuid4().hex[:8]}",
        "zone": payload.zone,
        "trigger_type": trigger_type,
        "trigger_event": result["trigger_event"],
        "riders_evaluated": 1,
        "claims_preview": [
            {
                "rider_id": payload.rider_id,
                "fraud_check_passed": result["fraud_check_passed"],
                "fraud_layers": result["fraud_layers"],
                "recommended_payout": result["recommended_payout"],
                "currency": result["currency"],
                "claim_id": result["claim_id"],
            }
        ],
        "fixture_version": None,
    }


@demo_triggers_router.post("/simulate-trigger")
def simulate_trigger_demo_alias(
    payload: TriggerSimulateRequest, db: Session = Depends(get_db)
):
    result = simulate_trigger(payload, db)
    claim_preview = (result.get("claims_preview") or [{}])[0]
    trigger_event = result.get("trigger_event") or {}
    payout_result = PayoutService.process_trigger_payout(
        rider_id=payload.rider_id,
        trigger_event=PayoutTriggerEvent(
            trigger_type=result.get("trigger_type", payload.trigger_type),
            value=float(trigger_event.get("value", 0.0)),
            threshold=float(trigger_event.get("threshold", 0.0)),
            breached=bool(trigger_event.get("breached", False)),
        ),
        fraud_result={
            "claim_id": claim_preview.get("claim_id", ""),
            "recommended_payout": float(claim_preview.get("recommended_payout", 0.0)),
        },
        db=db,
    )
    return {
        "claim_id": payout_result.claim_id,
        "payout_amount": payout_result.payout_amount,
        "utr_number": payout_result.utr_number,
        "processed_in_seconds": payout_result.processed_in_seconds,
        "smart_contract_hash": getattr(payout_result, "smart_contract_hash", "N/A"),
        "verification_url": getattr(payout_result, "verification_url", ""),
        "simulation": result,
    }
