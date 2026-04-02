"""
ml_service.py -- Centralised ML logic with SHAP explainability.

Loads the XGBoost model once at import time and exposes a function that
returns the predicted premium *and* a SHAP-powered breakdown of each
feature's contribution in INR.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

# ---------------------------------------------------------------------------
# Load model once at import
# ---------------------------------------------------------------------------
_MODEL_PATH = Path("model.pkl")

if not _MODEL_PATH.exists():
    raise RuntimeError(
        "model.pkl not found. Run `python train.py` first to generate it."
    )

ml_model = joblib.load(_MODEL_PATH)
print("[OK] ml_service: model.pkl loaded")

# Build the SHAP explainer once (cheap for tree models)
_explainer = shap.TreeExplainer(ml_model)

# Feature names must match the training order in train.py
_FEATURE_NAMES = ["zone_risk_score", "weather_severity", "claim_history"]

# Human-readable labels for the frontend / PDF
_FEATURE_LABELS = {
    "zone_risk_score": "Zone Flood / Risk Score",
    "weather_severity": "Upcoming Weather Forecast",
    "claim_history": "Rider Claim History",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_premium_and_breakdown(
    zone_risk: float,
    weather_severity: float,
    claim_history: int,
) -> dict:
    """
    Predict premium and explain the prediction with SHAP.

    Returns
    -------
    {
        "base_premium_inr": float,      # model's raw prediction
        "shap_base_value": float,       # SHAP expected value (mean prediction)
        "final_premium_inr": float,     # same as base_premium (no manual adj)
        "breakdown": [
            {"factor": str, "feature": str, "shap_value": float, "impact_inr": float},
            ...
        ]
    }
    """
    # Build a single-row DataFrame so SHAP keeps feature names
    X = pd.DataFrame(
        [[zone_risk, weather_severity, float(claim_history)]],
        columns=_FEATURE_NAMES,
    )

    # Prediction
    predicted = float(ml_model.predict(X)[0])

    # SHAP values for this single observation
    shap_values = _explainer.shap_values(X)
    sv = shap_values[0]  # array of shape (n_features,)
    base_value = float(_explainer.expected_value)

    # Build breakdown
    breakdown = []
    for i, feat in enumerate(_FEATURE_NAMES):
        impact = round(float(sv[i]), 2)
        breakdown.append(
            {
                "factor": _FEATURE_LABELS.get(feat, feat),
                "feature": feat,
                "shap_value": impact,
                "impact_inr": impact,
            }
        )

    return {
        "base_premium_inr": round(predicted, 2),
        "shap_base_value": round(base_value, 2),
        "final_premium_inr": round(predicted, 2),
        "breakdown": breakdown,
    }
