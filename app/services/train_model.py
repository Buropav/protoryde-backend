import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor


def load_delhivery_data(seed: int = 42) -> pd.DataFrame:
    try:
        # Load the real Kaggle Delhivery dataset
        df = pd.read_csv("app/data/delhivery_dataset.csv")
    except FileNotFoundError:
        # Fallback for CI/CD or tests
        return generate_synthetic_data(seed=seed)

    # Calculate a real-world proxy for zone risk based on logistics delays
    # (actual delivery time vs expected OSRM routing time)
    safe_osrm = df['osrm_time'].replace(0, 1)  # avoid division by zero
    delay_ratio = (df['actual_time'] / safe_osrm).fillna(1.0)
    
    # Normalize delay ratio into a zone risk score (0.1 to 1.0)
    normalized_risk = delay_ratio / 3.0
    zone_risk_score = np.clip(normalized_risk, 0.1, 1.0)
    
    n_samples = len(df)
    rng = np.random.default_rng(seed)
    
    # While routing delay calculates real world 'Zone Risk', we simulate the other 
    # external contextual factors (weather severity, rider claim history) 
    # since they don't natively exist in a logistics routing database.
    weather_severity = rng.integers(0, 5, n_samples).astype(float)
    claim_history = rng.integers(0, 10, n_samples).astype(float)
    
    # Try parsing month from trip_creation_time, fallback to synthetic if invalid
    try:
        month = pd.to_datetime(df['trip_creation_time']).dt.month
        season_risk = np.where((month >= 6) & (month <= 9), 1.5, 0.5)
    except:
        month = rng.integers(1, 13, n_samples).astype(float)
        season_risk = np.where((month >= 6) & (month <= 9), 1.5, 0.5)
    
    # Construct historical Premium target variable for model to learn from
    premium_amount = (
        50
        + 60 * zone_risk_score
        + 12 * weather_severity
        - 4 * claim_history
        + 15 * season_risk 
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
    # Use real dataset loader here
    df = load_delhivery_data()
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
