import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor


def generate_synthetic_data(n_samples: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    zone_risk_score = rng.uniform(0.1, 1.0, n_samples)
    weather_severity = rng.integers(0, 5, n_samples).astype(float)
    claim_history = rng.integers(0, 10, n_samples).astype(float)
    # Seasonal risk: month 1-12, monsoon (Jun-Sep) has higher risk
    month = rng.integers(1, 13, n_samples).astype(float)
    season_risk = np.where((month >= 6) & (month <= 9), 1.5, 0.5)
    premium_amount = (
        50
        + 60 * zone_risk_score
        + 12 * weather_severity
        - 4 * claim_history
        + 15 * season_risk  # monsoon loading adds ~₹22.5 vs ₹7.5 in dry season
        + rng.normal(0, 5, n_samples)
    )
    return pd.DataFrame(
        {
            "zone_risk_score": zone_risk_score,
            "weather_severity": weather_severity,
            "claim_history": claim_history,
            "season_risk": season_risk,
            "premium_amount": premium_amount,
        }
    )


def train_and_save_model(model_path: str = "app/models/model.pkl") -> str:
    df = generate_synthetic_data()
    X = df[["zone_risk_score", "weather_severity", "claim_history", "season_risk"]]
    y = df["premium_amount"]
    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X, y)
    joblib.dump(model, model_path)
    return model_path


if __name__ == "__main__":
    output_path = train_and_save_model()
    print(f"[OK] Model trained and saved to {output_path}")
