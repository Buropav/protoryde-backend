from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session
import logging

from app.core.models import Policy, Rider
from app.services.ml_service import is_ml_ready, ml_status, predict_with_shap
from app.services.pricing_service import PricingService
from app.triggers.weather_service import WeatherService

logger = logging.getLogger(__name__)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def check_enrollment_lockout(zone: str) -> List[str]:
    try:
        return WeatherService.get_forecast_warnings(zone, is_simulated=False)
    except Exception:
        return []


def predict_premium(
    zone: str,
    forecast_features: Optional[Dict[str, Any]] = None,
    rider_features: Optional[Dict[str, Any]] = None,
    prefer_ml: bool = True,
    explicit_zone_risk: Optional[float] = None,
    weather_severity: Optional[float] = None,
    claim_history: Optional[float] = None,
) -> Dict[str, Any]:
    if prefer_ml and is_ml_ready():
        try:
            ml_payload = predict_with_shap(
                zone=zone,
                weather_severity=float(
                    weather_severity
                    if weather_severity is not None
                    else (forecast_features or {}).get("weather_severity", 2.0)
                ),
                claim_history=float(
                    claim_history
                    if claim_history is not None
                    else (rider_features or {}).get("claim_history", 1.0)
                ),
                explicit_zone_risk=explicit_zone_risk,
            )
            return {
                "engine": "ml_shap",
                "zone": zone,
                "base_premium": ml_payload["base_premium"],
                "final_premium": ml_payload["final_premium"],
                "adjustments": ml_payload["adjustments"],
                "model_status": ml_payload["model_status"],
            }
        except Exception as exc:
            logger.warning(
                "ML premium prediction failed; using rule engine fallback: %s", exc
            )

    rule_payload = PricingService.predict(
        {
            "zone": zone,
            "forecast_features": forecast_features or {},
            "rider_features": rider_features or {},
            "is_simulated": False,
        }
    )
    return {
        "engine": "rule_engine",
        "zone": zone,
        "base_premium": rule_payload["base_premium"],
        "final_premium": rule_payload["final_premium"],
        "adjustments": rule_payload["adjustments"],
        "model_status": ml_status(),
    }


def ensure_rider_and_policy(
    db: Session, rider_id: str, zone: str, exclusions_acknowledged: bool = True
) -> Policy:
    rider = db.query(Rider).filter(Rider.id == rider_id).first()
    if rider is None:
        rider = Rider(
            id=rider_id,
            name="ProtoRyde Rider",
            phone=f"9{uuid4().hex[:9]}",
            delhivery_partner_id=f"DEL-{uuid4().hex[:8].upper()}",
            zone=zone,
            upi_id="rider@upi",
            avg_daily_earnings=1050.0,
            claim_rate_12wk=0.6,
            fraud_flag_count=0,
            kyc_verified=True,
        )
        db.add(rider)
        db.flush()

    now = now_utc()
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=now.weekday()
    )
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    policy = (
        db.query(Policy)
        .filter(
            Policy.rider_id == rider_id,
            Policy.week_start_date >= week_start,
            Policy.status == "active",
        )
        .first()
    )
    if policy is None:
        premium = predict_premium(
            zone=zone, forecast_features={}, rider_features={}, prefer_ml=True
        )
        policy = Policy(
            id=f"pol_{uuid4().hex[:10]}",
            rider_id=rider_id,
            week_start_date=week_start,
            week_end_date=week_end,
            base_premium=premium["base_premium"],
            final_premium=premium["final_premium"],
            premium_breakdown=premium["adjustments"],
            coverage_tier="STANDARD",
            coverage_cap=2300.0,
            status="active",
            exclusions_acknowledged_at=now if exclusions_acknowledged else None,
        )
        db.add(policy)
    return policy
