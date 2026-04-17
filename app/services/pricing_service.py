from datetime import datetime, timezone
from typing import Any, Dict, List

from app.triggers.weather_service import FIXTURE_VERSION

ZONE_BASE_PREMIUM = {
    "Whitefield": 55.0,
    "Indiranagar": 82.0,
    "HSR Layout": 115.0,
    "Bellandur": 120.0,
    "Koramangala": 90.0,
    "Marathahalli": 88.0,
    "BTM Layout": 84.0,
    "Electronic City": 76.0,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PricingService:
    @staticmethod
    def predict(payload: Dict[str, Any]) -> Dict[str, Any]:
        zone = payload.get("zone", "HSR Layout")
        base = ZONE_BASE_PREMIUM.get(zone, 82.0)

        weather = payload.get("forecast_features", {}) or {}
        rider = payload.get("rider_features", {}) or {}

        rain_prob = float(weather.get("rain_probability_pct", 0.0))
        aqi_forecast_days = float(weather.get("aqi_days_above_200", 0.0))
        claim_rate = float(rider.get("claim_rate_12wk", 0.0))
        fraud_flags = int(rider.get("fraud_flag_count", 0))
        first_month = bool(rider.get("first_4_weeks", False))

        adjustments: List[Dict[str, Any]] = []

        if rain_prob >= 60:
            adjustments.append(
                {
                    "factor": "rain_risk",
                    "amount": 18.0,
                    "reason": "7-day rain probability >= 60%",
                }
            )
        if aqi_forecast_days >= 3:
            adjustments.append(
                {
                    "factor": "aqi_risk",
                    "amount": 12.0,
                    "reason": "AQI forecast elevated for 3+ days",
                }
            )
        if claim_rate < 1.0:
            adjustments.append(
                {
                    "factor": "low_claim_rate",
                    "amount": -10.0,
                    "reason": "Claim rate below 1/month",
                }
            )
        if fraud_flags == 0:
            adjustments.append(
                {
                    "factor": "clean_fraud_record",
                    "amount": -8.0,
                    "reason": "No fraud flags",
                }
            )
        if first_month:
            adjustments.append(
                {
                    "factor": "new_rider_loading",
                    "amount": 5.0,
                    "reason": "Insufficient rider history",
                }
            )

        adjustment_total = round(sum(item["amount"] for item in adjustments), 2)
        final_premium = max(40.0, round(base + adjustment_total, 2))

        return {
            "zone": zone,
            "timestamp": _now_iso(),
            "model_version": "protoryde-weighted-v1",
            "fixture_version": FIXTURE_VERSION,
            "base_premium": base,
            "adjustments": adjustments,
            "adjustment_total": adjustment_total,
            "final_premium": final_premium,
            "currency": "INR",
        }
