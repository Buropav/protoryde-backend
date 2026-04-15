from fastapi.testclient import TestClient
from app.main import app
import sys

client = TestClient(app)
response = client.post("/api/triggers/simulate", json={
    "rider_id": "rdr_demo_hsr",
    "zone": "HSR Layout",
    "trigger_type": "HEAVY_RAIN",
    "is_simulated": True,
    "avg_daily_earnings": 1050.0,
    "duration_hours": 9.0
})
print(response.status_code)
print(response.json())
if response.status_code != 200:
    sys.exit(1)
