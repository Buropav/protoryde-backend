import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.model_registry import (
    MODELS_DIR,
    bootstrap_registry_if_missing,
    get_model_entry,
    sync_model_artifact,
)

logger = logging.getLogger(__name__)

MODEL_KEY = "premium_xgboost"
MODEL_PATH = MODELS_DIR / "model.pkl"
FEATURE_NAMES = ["zone_risk_score", "weather_severity", "claim_history", "season_risk"]
FEATURE_LABELS = {
    "zone_risk_score": "Zone Flood / Risk Score",
    "weather_severity": "Upcoming Weather Forecast",
    "claim_history": "Rider Claim History",
    "season_risk": "Seasonal Risk (Monsoon Loading)",
}
ZONE_RISK = {
    "HSR Layout": 0.80,
    "Bellandur": 0.82,
    "Koramangala": 0.64,
    "Indiranagar": 0.55,
    "Whitefield": 0.45,
    "Marathahalli": 0.58,
    "BTM Layout": 0.60,
    "Electronic City": 0.50,
}

_MODEL = None
_EXPLAINER = None
_ML_ERROR = None
_ML_LOADED = False
_MODEL_VERSION = "v0.0.0"


def _lazy_load_model() -> None:
    """Load the ML model and SHAP explainer on first use, not at import time."""
    global _MODEL, _EXPLAINER, _ML_ERROR, _ML_LOADED, _MODEL_VERSION
    if _ML_LOADED:
        return
    _ML_LOADED = True
    bootstrap_registry_if_missing()
    try:
        import joblib
        import shap

        if MODEL_PATH.exists():
            _MODEL = joblib.load(MODEL_PATH)
            _EXPLAINER = shap.TreeExplainer(_MODEL)
            sync_model_artifact(
                model_key=MODEL_KEY,
                artifact_path=MODEL_PATH,
                framework="xgboost",
                metadata={"service": "ml_service", "lazy_loaded": True},
                bump_version=False,
            )
            _MODEL_VERSION = get_model_entry(MODEL_KEY).get("version", "v0.0.0")
            logger.info("ML model loaded from %s", MODEL_PATH)
        else:
            _ML_ERROR = f"model.pkl not found at {MODEL_PATH}"
            logger.warning(_ML_ERROR)
    except Exception as exc:  # pragma: no cover - env dependent
        _ML_ERROR = str(exc)
        logger.warning("ML model load failed: %s", _ML_ERROR)


def is_ml_ready() -> bool:
    _lazy_load_model()
    return _MODEL is not None and _EXPLAINER is not None


def ml_status() -> Dict[str, Any]:
    _lazy_load_model()
    model_entry = get_model_entry(MODEL_KEY)
    return {
        "ready": _MODEL is not None and _EXPLAINER is not None,
        "model_path": str(MODEL_PATH),
        "model_version": _MODEL_VERSION,
        "model_framework": model_entry.get("framework", "xgboost"),
        "artifact_sha256": model_entry.get("artifact_sha256"),
        "error": _ML_ERROR,
    }


def premium_model_version() -> str:
    _lazy_load_model()
    return _MODEL_VERSION


def invalidate_model_cache() -> None:
    global _MODEL, _EXPLAINER, _ML_ERROR, _ML_LOADED, _MODEL_VERSION
    _MODEL = None
    _EXPLAINER = None
    _ML_ERROR = None
    _ML_LOADED = False
    _MODEL_VERSION = "v0.0.0"


def zone_risk_score(zone: str) -> float:
    return float(ZONE_RISK.get(zone, 0.50))


def _current_season_risk() -> float:
    """Return seasonal risk factor: 1.5 during monsoon (Jun-Sep), 0.5 otherwise."""
    month = datetime.now(timezone.utc).month
    return 1.5 if 6 <= month <= 9 else 0.5


def predict_with_shap(
    zone: str,
    weather_severity: float = 2.0,
    claim_history: float = 1.0,
    explicit_zone_risk: Optional[float] = None,
    season_risk: Optional[float] = None,
) -> Dict[str, Any]:
    _lazy_load_model()
    if not (_MODEL is not None and _EXPLAINER is not None):
        raise RuntimeError(_ML_ERROR or "ML model unavailable")

    import pandas as pd

    zr = explicit_zone_risk if explicit_zone_risk is not None else zone_risk_score(zone)
    sr = season_risk if season_risk is not None else _current_season_risk()
    X = pd.DataFrame(
        {
            "zone_risk_score": [float(zr)],
            "weather_severity": [float(weather_severity)],
            "claim_history": [float(claim_history)],
            "season_risk": [float(sr)],
        }
    )
    predicted = float(_MODEL.predict(X)[0])

    shap_values = _EXPLAINER.shap_values(X)
    values = shap_values[0]

    breakdown: List[Dict[str, Any]] = []
    for idx, feat in enumerate(FEATURE_NAMES):
        impact = round(float(values[idx]), 2)
        breakdown.append(
            {
                "factor": FEATURE_LABELS.get(feat, feat),
                "feature": feat,
                "shap_value": impact,
                "impact_inr": impact,
                # Keep compatibility with current policy payload shape.
                "amount": impact,
                "reason": "SHAP contribution",
            }
        )

    adjustment_total = round(sum(item["shap_value"] for item in breakdown), 2)

    # SHAP base value = expected model output (average prediction).
    # base_premium = SHAP expected value, final_premium = actual prediction with ₹40 floor.
    base_value = round(float(_EXPLAINER.expected_value), 2)
    final = max(40.0, round(predicted, 2))  # enforce ₹40 minimum (same as rule engine)

    return {
        "engine": "ml_shap",
        "zone": zone,
        "zone_risk_score": zr,
        "season_risk": sr,
        "base_premium": base_value,
        "final_premium": final,
        "adjustments": breakdown,
        "adjustment_total": adjustment_total,
        "model_status": ml_status(),
    }
