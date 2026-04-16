import json
import logging
import math
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from app.services.bank_branch_service import get_zone_branch_metrics
from app.services.model_registry import get_model_entry
from app.triggers.weather_service import FIXTURE_VERSION, ZONES

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

TRIGGER_THRESHOLDS = {
    "HEAVY_RAIN": 30.0,
    "EXTREME_HEAT": 40.0,
    "SEVERE_AQI": 300.0,
    "BRANCH_CLOSURE": 60.0,  # percent
    "DELHIVERY_ADVISORY": 60.0,  # percent cancellation proxy
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_delhivery(zone: str) -> Dict[str, Any]:
    import pandas as pd

    try:
        df = pd.read_csv(os.path.join(DATA_DIR, "delhivery_dataset.csv"))
        zone_mask = df["source_name"].str.contains(zone, case=False, na=False) | df[
            "destination_name"
        ].str.contains(zone, case=False, na=False)
        zone_df = df[zone_mask]

        if len(zone_df) == 0:
            zone_df = df

        total_orders = len(zone_df)
        delayed = zone_df[zone_df["actual_time"] > zone_df["osrm_time"] * 1.5]
        cancelled_orders = len(delayed)
        cancellation_rate = cancelled_orders / total_orders if total_orders > 0 else 0.0

    except Exception as e:
        logger.warning(f"Failed to load real delhivery dataset: {e}")
        total_orders = 20
        cancelled_orders = 1
        cancellation_rate = 0.05

    return {
        "total_banking_orders": int(total_orders),
        "cancelled_orders": int(cancelled_orders),
        "cancellation_rate_pct": round(float(cancellation_rate) * 100, 2),
        "fixture_version": FIXTURE_VERSION,
    }


def _load_branches(zone: str) -> Dict[str, Any]:
    metrics = get_zone_branch_metrics(zone)
    return {
        "total_branches": int(metrics.get("total_branches", 0)),
        "closed_branches": int(metrics.get("closed_branches", 0)),
        "closure_rate_pct": float(metrics.get("closure_rate_pct", 0.0)),
        "source": metrics.get("source", "unknown"),
    }


def _audit(event: Dict[str, Any], db=None) -> None:
    """Write audit event to the database. Falls back to file if no session provided."""
    if db is not None:
        try:
            from app.core.models import AuditLog

            db.add(
                AuditLog(
                    entity_type=event.get("entity_type", "FraudTrace"),
                    entity_id=event.get("entity_id", ""),
                    action="FRAUD_TRACE",
                    metadata_json=event,
                )
            )
            # Don't commit here — let the caller's transaction handle it.
            return
        except Exception as exc:
            logger.warning("DB audit write failed, falling back to file: %s", exc)
    # Fallback: append to file (will be lost on Render ephemeral disk).
    audit_log_file = os.path.join(DATA_DIR, "simulation_audit.log")
    try:
        os.makedirs(os.path.dirname(audit_log_file), exist_ok=True)
        with open(audit_log_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"timestamp": _now_iso(), **event}) + "\n")
    except OSError:
        logger.warning("File audit write failed for event %s", event.get("entity_id"))


IFOREST_MODEL_PATH = os.path.join(DATA_DIR, "..", "models", "isolation_forest.pkl")
_iforest_model = None
_iforest_model_version = "v0.0.0"


def _load_iforest_model():
    global _iforest_model, _iforest_model_version
    if _iforest_model is None and os.path.exists(IFOREST_MODEL_PATH):
        try:
            import pickle

            with open(IFOREST_MODEL_PATH, "rb") as f:
                _iforest_model = pickle.load(f)
            model_entry = get_model_entry("fraud_iforest")
            _iforest_model_version = model_entry.get("version", "v0.0.0")
        except Exception as e:
            logger.error("Failed to load Isolation Forest model: %s", e)
    return _iforest_model


def iforest_model_status() -> Dict[str, Any]:
    model_entry = get_model_entry("fraud_iforest")
    model_path = Path(IFOREST_MODEL_PATH)
    return {
        "ready": _load_iforest_model() is not None,
        "model_path": str(model_path.resolve()),
        "model_version": model_entry.get("version", _iforest_model_version),
        "model_framework": model_entry.get("framework", "sklearn_isolation_forest"),
        "artifact_sha256": model_entry.get("artifact_sha256"),
    }


def reset_iforest_cache() -> None:
    global _iforest_model, _iforest_model_version
    _iforest_model = None
    _iforest_model_version = "v0.0.0"


class FraudEngine:
    @staticmethod
    def evaluate_claim(
        zone: str,
        trigger_type: str,
        trigger_value: float,
        rider_id: str,
        avg_daily_earnings: float = 1050.0,
        duration_hours: float = 9.0,
        coverage_tier: str = "STANDARD",
        is_simulated: bool = False,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        db=None,
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
        l1_passed = trigger_value >= threshold
        l1_reason = f"{trigger_value} vs {threshold} threshold"

        model = _load_iforest_model()
        if model is not None and l1_passed:
            try:
                import numpy as np

                X = np.array([[float(avg_daily_earnings), float(duration_hours)]])
                if model.predict(X)[0] == -1:
                    l1_passed = False
                    l1_reason = f"ML Anomaly (Earnings: ₹{avg_daily_earnings}, Hours: {duration_hours})"
            except Exception as e:
                logger.warning("Isolation Forest prediction failed %s", e)

        # L2: zone presence
        if latitude is not None and longitude is not None:
            zone_center = ZONES[zone]
            lat_diff = latitude - zone_center["lat"]
            lon_diff = (longitude - zone_center["lon"]) * math.cos(
                math.radians(zone_center["lat"])
            )
            dist_km = math.hypot(lat_diff, lon_diff) * 111.0
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
            {
                "layer": "L1_WEATHER_THRESHOLD",
                "passed": l1_passed,
                "reason": l1_reason,
                "evidence": {"value": trigger_value, "threshold": threshold},
            },
            {
                "layer": "L2_ZONE_PRESENCE",
                "passed": l2_passed,
                "reason": l2_reason,
                "evidence": l2_evidence,
            },
            {
                "layer": "L3_DELHIVERY_CROSS_REF",
                "passed": l3_passed,
                "reason": l3_reason,
                "evidence": delhivery,
            },
            {
                "layer": "L4_BRANCH_CLOSURE_CHECK",
                "passed": l4_passed,
                "reason": l4_reason,
                "evidence": branches,
            },
        ]

        fraud_check_passed = all(item["passed"] for item in fraud_layers)
        raw_payout = (avg_daily_earnings * (duration_hours / 9.0)) * 0.80

        coverage_cap = 2800.0 if coverage_tier == "ENHANCED" else 2300.0
        recommended_payout = (
            round(min(raw_payout, coverage_cap), 2) if fraud_check_passed else 0.0
        )

        result = {
            "claim_id": f"clm_{uuid4().hex[:10]}",
            "rider_id": rider_id,
            "zone": zone,
            "trigger_type": trigger_type,
            "trigger_event": {
                "value": trigger_value,
                "threshold": threshold,
                "breached": trigger_value >= threshold,
            },
            "fraud_check_passed": fraud_check_passed,
            "fraud_layers": fraud_layers,
            "recommended_payout": recommended_payout,
            "currency": "INR",
            "fixture_version": FIXTURE_VERSION if is_simulated else None,
        }

        _audit(
            {
                "event": "fraud_trace",
                "entity_type": "claim",
                "entity_id": result["claim_id"],
                "details": result,
            },
            db=db,
        )
        return result
