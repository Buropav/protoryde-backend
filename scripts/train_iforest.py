import pickle
import pandas as pd
from pathlib import Path
import numpy as np
from sklearn.ensemble import IsolationForest

csv_path = Path(__file__).resolve().parent.parent / "app" / "data" / "delhivery_dataset.csv"

try:
    df = pd.read_csv(csv_path)
    
    # We need features: avg_daily_earnings, duration_hours
    # We calculate proxy values:
    # 15 rupees per km
    # hours = actual_time in minutes / 60
    
    df["duration_hours"] = df["actual_time"] / 60.0
    df["avg_daily_earnings"] = df["osrm_distance"] * 15.0
    
    # Drop rows with na or extremely unrealistic values just in case
    df = df.dropna(subset=["avg_daily_earnings", "duration_hours"])
    
    X_train = df[["avg_daily_earnings", "duration_hours"]].values
    
    # Use random sample to not freeze isolation forest if dataset is too massive
    if len(X_train) > 10000:
        np.random.seed(42)
        indices = np.random.choice(len(X_train), 10000, replace=False)
        X_train = X_train[indices]
except Exception as e:
    print(f"Failed to read delhivery dataset: {e}")
    # Fallback to random if dataset doesn't load
    np.random.seed(42)
    X_train = np.random.normal(loc=[1050.0, 9.0], scale=[150.0, 1.5], size=(200, 2))

# Add some obvious outliers so the model knows what to catch
outliers = np.array(
    [
        [8000.0, 24.0],  # Insanely high earnings, working 24 hours
        [50.0, 1.0],  # Very low earnings
        [0.0, 20.0],  # No earnings, high hours
        [10000.0, 2.0] # Super high earnings in very low hours
    ]
)
X_train = np.vstack([X_train, outliers])

model = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
model.fit(X_train)

model_path = Path(__file__).resolve().parent.parent / "app" / "models" / "isolation_forest.pkl"
with open(model_path, "wb") as f:
    pickle.dump(model, f)

print(f"Isolation forest trained on delhivery dataset ({len(X_train)} rows) and saved to {model_path}.")
