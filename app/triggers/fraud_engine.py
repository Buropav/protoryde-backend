import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from app.triggers.weather_service import FIXTURE_VERSION, ZONES

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
AUDIT_LOG_FILE = os.path.join(DATA_DIR, "simulation_audit.log")

TRIGGER_THRESHOLDS = {
    "HEAVY_RAIN": 30.0,
    "EXTREME_HEAT": 40.0,
    "SEVERE_AQI": 300.0,
    "BRANCH_CLOSURE": 60.0,  # percent
    "DELHIVERY_ADVISORY": 60.0,  # percent cancellation proxy
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_delhivery(zone: str) -> Dict[str, Any]:
    data = _read_json(os.path.join(DATA_DIR, "delhivery_cancellations.json"))
    entry = data.get(zone, {"total_orders": 20, "cancelled_orders": 1, "cancellation_rate": 0.05})
    return {
        "total_banking_orders": int(entry.get("total_orders", 0)),
        "cancelled_orders": int(entry.get("cancelled_orders", 0)),
        "cancellation_rate_pct": round(float(entry.get("cancellation_rate", 0.0)) * 100, 2),
        "fixture_version": FIXTURE_VERSION,
    }


def _load_branches(zone: str) -> Dict[str, Any]:
    data = _read_json(os.path.join(DATA_DIR, "bank_branches.json"))
    entry = data.get(zone, {"total_branches": 10, "closed_branches": 0, "closure_rate": 0.0})
    return {
        "total_branches": int(entry.get("total_branches", 0)),
        "closed_branches": int(entry.get("closed_branches", 0)),
        "closure_rate_pct": round(float(entry.get("closure_rate", 0.0)) * 100, 2),
        "fixture_version": FIXTURE_VERSION,
    }


def _audit(event: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(AUDIT_LOG_FILE), exist_ok=True)
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"timestamp": _now_iso(), **event}) + "\n")


class FraudEngine:
    @staticmethod
    def evaluate_claim(
        zone: str,
        trigger_type: str,
        trigger_value: float,
        rider_id: str,
        avg_daily_earnings: float = 1050.0,
        duration_hours: float = 9.0,
        is_simulated: bool = False,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Dict[str, Any]:
        trigger_type = trigger_type.upper()
        if trigger_type not in TRIGGER_THRESHOLDS:
            raise ValueError("UNSUPPORTED_TRIGGER")
        if zone not in ZONES:
            raise ValueError("UNSUPPORTED_ZONE")

        threshold = TRIGGER_THRESHOLDS[trigger_type]
        delhivery = _load_delhivery(zone)
        branches = _load_branches(zone)

        # L1: weather/environment threshold
        l1_passed = trigger_value >= threshold if trigger_type in {"HEAVY_RAIN", "EXTREME_HEAT", "SEVERE_AQI"} else True
        l1_reason = f"{trigger_value} vs {threshold} threshold"

        # L2: zone presence
        if is_simulated and latitude is None and longitude is None:
            l2_passed = True
            l2_reason = "Simulated mode: rider zone presence accepted"
            l2_evidence = {"mode": "simulated"}
        elif latitude is not None and longitude is not None:
            zone_center = ZONES[zone]
            dist_km = math.hypot(latitude - zone_center["lat"], longitude - zone_center["lon"]) * 111.0
            l2_passed = dist_km <= 5.0
            l2_reason = f"GPS distance from zone center: {dist_km:.2f}km"
            l2_evidence = {"distance_km": round(dist_km, 2), "max_km": 5.0}
        else:
            l2_passed = False
            l2_reason = "Missing GPS coordinates"
            l2_evidence = {"latitude": latitude, "longitude": longitude}

        # L3: Delhivery cross-reference
        l3_passed = delhivery["cancellation_rate_pct"] >= 60.0
        l3_reason = (
            f"{delhivery['cancelled_orders']}/{delhivery['total_banking_orders']} orders cancelled "
            f"({delhivery['cancellation_rate_pct']}%)"
        )

        # L4: Branch closure
        l4_passed = branches["closure_rate_pct"] >= 60.0
        l4_reason = (
            f"{branches['closed_branches']}/{branches['total_branches']} branches closed "
            f"({branches['closure_rate_pct']}%)"
        )

        fraud_layers = [
            {"layer": "L1_WEATHER_THRESHOLD", "passed": l1_passed, "reason": l1_reason, "evidence": {"value": trigger_value, "threshold": threshold}},
            {"layer": "L2_ZONE_PRESENCE", "passed": l2_passed, "reason": l2_reason, "evidence": l2_evidence},
            {"layer": "L3_DELHIVERY_CROSS_REF", "passed": l3_passed, "reason": l3_reason, "evidence": delhivery},
            {"layer": "L4_BRANCH_CLOSURE_CHECK", "passed": l4_passed, "reason": l4_reason, "evidence": branches},
        ]

        fraud_check_passed = all(item["passed"] for item in fraud_layers)
        raw_payout = (avg_daily_earnings * (duration_hours / 9.0)) * 0.80
        recommended_payout = round(min(raw_payout, 2300.0), 2) if fraud_check_passed else 0.0

        result = {
            "claim_id": f"clm_{uuid4().hex[:10]}",
            "rider_id": rider_id,
            "zone": zone,
            "trigger_type": trigger_type,
            "trigger_event": {"value": trigger_value, "threshold": threshold, "breached": trigger_value >= threshold},
            "fraud_check_passed": fraud_check_passed,
            "fraud_layers": fraud_layers,
            "recommended_payout": recommended_payout,
            "currency": "INR",
            "fixture_version": FIXTURE_VERSION if is_simulated else None,
        }

        _audit({"event": "fraud_trace", "entity_type": "claim", "entity_id": result["claim_id"], "details": result})
        return result
