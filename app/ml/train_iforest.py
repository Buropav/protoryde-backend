import pickle
import numpy as np
from sklearn.ensemble import IsolationForest
import os

# Mock training data: [avg_daily_earnings, duration_hours]
# Normal data points around (1050, 9)
np.random.seed(42)
normal_data = np.random.normal(loc=[1050.0, 9.0], scale=[150.0, 1.5], size=(200, 2))
# Add some outliers
outliers = np.array([
    [5000.0, 24.0],  # Insanely high earnings, working 24 hours
    [200.0, 1.0],    # Very low earnings
    [0.0, 15.0],     # No earnings, high hours
])
X_train = np.vstack([normal_data, outliers])

# Train Isolation Forest
model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
model.fit(X_train)

# Save model
model_path = '/home/anuruprkris/Project/devTrails/protoryde-backend/app/ml/isolation_forest.pkl'
with open(model_path, 'wb') as f:
    pickle.dump(model, f)

print(f"Isolation forest trained and saved to {model_path}.")
