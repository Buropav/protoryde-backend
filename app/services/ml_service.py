import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "model.pkl"
FEATURE_NAMES = ["zone_risk_score", "weather_severity", "claim_history"]
FEATURE_LABELS = {
    "zone_risk_score": "Zone Flood / Risk Score",
    "weather_severity": "Upcoming Weather Forecast",
    "claim_history": "Rider Claim History",
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


def _lazy_load_model() -> None:
    """Load the ML model and SHAP explainer on first use, not at import time."""
    global _MODEL, _EXPLAINER, _ML_ERROR, _ML_LOADED
    if _ML_LOADED:
        return
    _ML_LOADED = True
    try:
        import joblib
        import shap

        if MODEL_PATH.exists():
            _MODEL = joblib.load(MODEL_PATH)
            _EXPLAINER = shap.TreeExplainer(_MODEL)
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
    return {
        "ready": _MODEL is not None and _EXPLAINER is not None,
        "model_path": str(MODEL_PATH),
        "error": _ML_ERROR,
    }


def zone_risk_score(zone: str) -> float:
    return float(ZONE_RISK.get(zone, 0.50))


def predict_with_shap(
    zone: str,
    weather_severity: float = 2.0,
    claim_history: float = 1.0,
    explicit_zone_risk: Optional[float] = None,
) -> Dict[str, Any]:
    _lazy_load_model()
    if not (_MODEL is not None and _EXPLAINER is not None):
        raise RuntimeError(_ML_ERROR or "ML model unavailable")

    import pandas as pd

    zr = explicit_zone_risk if explicit_zone_risk is not None else zone_risk_score(zone)
    X = pd.DataFrame([[zr, float(weather_severity), float(claim_history)]], columns=FEATURE_NAMES)
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

    return {
        "engine": "ml_shap",
        "zone": zone,
        "zone_risk_score": zr,
        "base_premium": round(predicted, 2),
        "final_premium": round(predicted, 2),
        "adjustments": breakdown,
        "adjustment_total": adjustment_total,
        "model_status": ml_status(),
    }

