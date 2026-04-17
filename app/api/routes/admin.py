from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import now_utc, predict_premium
from app.api.schemas import PremiumPredictRequest, ResolvePredictionRequest
from app.api.constants import EXCLUSIONS, EXCLUSIONS_VERSION
from app.core.database import get_db
from app.core.models import Claim, Policy
from app.services.forecast_service import generate_zone_forecast
from app.services.fraud_model_training import train_iforest_and_save
from app.services.ml_service import premium_model_version, zone_risk_score
from app.services.model_monitoring import (
    compute_model_health,
    log_prediction,
    resolve_prediction_actual,
)
from app.services.model_registry import bootstrap_registry_if_missing
from app.services.train_model import train_and_save_model
from app.triggers.fraud_engine import iforest_model_status
from app.triggers.weather_service import ZONES

admin_router = APIRouter(prefix="/admin", tags=["admin"])
premium_router = APIRouter(prefix="/premium", tags=["admin"])
forecast_router = APIRouter(prefix="/forecast", tags=["admin"])
meta_router = APIRouter(tags=["admin"])


def _model_status(db: Session):
    from app.services.ml_service import ml_status

    bootstrap_registry_if_missing()
    status = ml_status()
    status["fraud_model"] = iforest_model_status()
    status["monitoring"] = {
        "premium_xgboost": compute_model_health(db=db, model_name="premium_xgboost"),
        "forecast_prophet": compute_model_health(db=db, model_name="forecast_prophet"),
    }
    status["zone_defaults"] = {zone: zone_risk_score(zone) for zone in ZONES.keys()}
    return status


@admin_router.get("/model-status")
def get_admin_model_status(db: Session = Depends(get_db)):
    return _model_status(db)


@premium_router.get("/model-status")
def get_premium_model_status(db: Session = Depends(get_db)):
    return _model_status(db)


@admin_router.post("/model-retrain")
def retrain_models(db: Session = Depends(get_db)):
    premium_path = train_and_save_model(db=db)
    fraud_path = train_iforest_and_save(db=db)
    forecast_snapshot = generate_zone_forecast(
        zone="HSR Layout", db=db, horizon_days=7, bump_model_version=True
    )
    return {
        "status": "ok",
        "premium_model_path": premium_path,
        "fraud_model_path": fraud_path,
        "forecast_model": {
            "model": forecast_snapshot["model"],
            "model_version": forecast_snapshot["model_version"],
            "fallback_mode": forecast_snapshot["fallback_mode"],
        },
    }


@admin_router.post("/model-monitoring/resolve")
def resolve_prediction(
    payload: ResolvePredictionRequest, db: Session = Depends(get_db)
):
    row = resolve_prediction_actual(
        db=db,
        prediction_id=payload.prediction_id,
        actual_value=payload.actual_value,
        metadata_patch=payload.metadata_patch,
    )
    return {
        "prediction_id": row.id,
        "model_name": row.model_name,
        "absolute_error": row.absolute_error,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


@admin_router.get("/model-monitoring")
def get_model_monitoring(
    model_name: Optional[str] = Query(default=None),
    zone: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    return compute_model_health(db=db, model_name=model_name, zone=zone)


@premium_router.post("/predict")
def predict_premium_endpoint(
    payload: PremiumPredictRequest, db: Session = Depends(get_db)
):
    if payload.zone not in ZONES:
        raise HTTPException(
            status_code=422,
            detail={"error": "UNSUPPORTED_ZONE", "message": "Zone is not supported"},
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

    month = now_utc().month
    next_review_date = datetime(year=now_utc().year, month=10, day=1).isoformat()
    if 6 <= month <= 9:
        season = "MONSOON"
        season_multiplier = 1.6
        rationale = "Monsoon season + high-risk zone = elevated premium"
    elif 11 <= month or month == 1:
        season = "WINTER"
        season_multiplier = 1.2
        rationale = "Winter season + elevated fog risk"
        next_review_date = datetime(
            year=now_utc().year + (1 if month >= 11 else 0), month=2, day=1
        ).isoformat()
    else:
        season = "SUMMER"
        season_multiplier = 1.0
        rationale = "Summer season standard pricing"
        next_review_date = datetime(year=now_utc().year, month=6, day=1).isoformat()

    zone_multiplier = 1.4 if "HSR" in payload.zone else 1.1

    if premium["engine"] == "ml_shap":
        log_prediction(
            db=db,
            model_name="premium_xgboost",
            model_version=premium_model_version(),
            task_type="premium_amount",
            zone=payload.zone,
            rider_id=(payload.rider_features or {}).get("rider_id"),
            target_date=None,
            prediction_value=float(premium["final_premium"]),
            metadata={
                "season": season,
                "season_multiplier": season_multiplier,
                "zone_multiplier": zone_multiplier,
                "next_review_date": next_review_date,
            },
            commit=False,
        )
        db.commit()

    return {
        "zone": payload.zone,
        "engine": premium["engine"],
        "base_premium": premium["base_premium"],
        "season_multiplier": season_multiplier,
        "zone_multiplier": zone_multiplier,
        "final_premium": premium["final_premium"],
        "season": season,
        "pricing_rationale": rationale,
        "next_review_date": next_review_date,
        "adjustments": premium["adjustments"],
        "currency": "INR",
        "model_status": premium["model_status"],
    }


@admin_router.get("/pool-health")
def get_pool_health(db: Session = Depends(get_db)):
    from app.services.admin_service import calculate_pool_health
    try:
        return calculate_pool_health(db)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail={"error": "INTERNAL_ERROR", "message": str(exc)}
        )



@forecast_router.get("/{zone}")
def get_7_day_forecast(
    zone: str,
    horizon_days: int = Query(default=7, ge=1, le=14),
    db: Session = Depends(get_db),
):
    if zone not in ZONES:
        raise HTTPException(
            status_code=422,
            detail={"error": "UNSUPPORTED_ZONE", "message": "Unsupported zone"},
        )
    try:
        return generate_zone_forecast(zone=zone, db=db, horizon_days=horizon_days)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "UNSUPPORTED_ZONE", "message": str(exc)}
        ) from exc


@admin_router.get("/metrics")
def get_admin_metrics(db: Session = Depends(get_db)):
    from sqlalchemy.sql import func

    now = now_utc()
    active_policies = (
        db.query(Policy)
        .filter(Policy.status == "active", Policy.week_end_date >= now)
        .count()
    )
    total_premiums = db.query(func.sum(Policy.final_premium)).scalar() or 0.0
    total_claims_paid = (
        db.query(func.sum(Claim.payout_amount))
        .filter(Claim.payout_status == "PAID")
        .scalar()
        or 0.0
    )

    return {
        "active_policies": active_policies,
        "total_premiums": round(total_premiums, 2),
        "total_claims_paid": round(total_claims_paid, 2),
    }


@admin_router.get("/claims_map")
def get_admin_claims_map(db: Session = Depends(get_db)):
    claims = db.query(
        Claim.id, Claim.zone, Claim.payout_amount, Claim.fraud_check_passed
    ).all()
    map_data = []

    for claim in claims:
        zone_info = ZONES.get(claim.zone, {"lat": 12.9716, "lon": 77.5946})
        map_data.append(
            {
                "id": claim.id,
                "zone": claim.zone,
                "latitude": zone_info["lat"],
                "longitude": zone_info["lon"],
                "payout_amount": claim.payout_amount,
                "fraud_check_passed": claim.fraud_check_passed,
            }
        )
    return {"claims": map_data}


@admin_router.get("/fraud_flags")
def get_admin_fraud_flags(db: Session = Depends(get_db)):
    flags = db.query(Claim).filter(Claim.fraud_check_passed == False).all()  # noqa: E712
    out = []
    for flag in flags:
        out.append(
            {
                "claim_id": flag.id,
                "rider_id": flag.rider_id,
                "zone": flag.zone,
                "trigger_type": flag.trigger_type,
                "created_at": flag.created_at.isoformat(),
                "fraud_layers": flag.fraud_layers,
            }
        )
    return {"flags": out}


@admin_router.get("/predictions")
def get_admin_predictions(db: Session = Depends(get_db)):
    return generate_zone_forecast(zone="HSR Layout", db=db, horizon_days=7)


@meta_router.get("/exclusions")
def get_exclusions():
    return {"version": EXCLUSIONS_VERSION, "items": EXCLUSIONS}
