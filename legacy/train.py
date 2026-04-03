"""
train.py — Generates synthetic rider data, trains an XGBRegressor to predict
premium_amount, and saves the model as model.pkl.

Run once:  python train.py
"""

import numpy as np
import pandas as pd
import joblib
from xgboost import XGBRegressor


def generate_synthetic_data(n_samples: int = 500, seed: int = 42) -> pd.DataFrame:
    """Create a small synthetic DataFrame of rider risk features."""
    rng = np.random.default_rng(seed)

    zone_risk_score = rng.uniform(0.1, 1.0, n_samples)
    weather_severity = rng.integers(0, 5, n_samples).astype(float)
    claim_history = rng.integers(0, 10, n_samples).astype(float)

    # Target: a loosely linear relationship with some noise
    premium_amount = (
        50
        + 60 * zone_risk_score
        + 12 * weather_severity
        - 4 * claim_history
        + rng.normal(0, 5, n_samples)
    )

    return pd.DataFrame(
        {
            "zone_risk_score": zone_risk_score,
            "weather_severity": weather_severity,
            "claim_history": claim_history,
            "premium_amount": premium_amount,
        }
    )


def main() -> None:
    df = generate_synthetic_data()

    X = df[["zone_risk_score", "weather_severity", "claim_history"]]
    y = df["premium_amount"]

    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X, y)

    joblib.dump(model, "model.pkl")
    print("[OK] Model trained and saved to model.pkl")


if __name__ == "__main__":
    main()
