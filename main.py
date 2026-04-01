"""
main.py — ProtoRyde FastAPI server (Day 1 / stateless).

Start:  uvicorn main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from schemas import RegisterRequest, SimulateTriggerRequest

# ---------------------------------------------------------------------------
# Model holder (populated at startup)
# ---------------------------------------------------------------------------
model = None


# ---------------------------------------------------------------------------
# Lifespan — load model.pkl once on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    model_path = Path("model.pkl")
    if not model_path.exists():
        raise RuntimeError(
            "model.pkl not found. Run `python train.py` first to generate it."
        )
    model = joblib.load(model_path)
    print("[OK] model.pkl loaded into memory")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ProtoRyde API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response helpers
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    zone: str
    weather_severity: float = 2.0
    claim_history: float = 1.0
    zone_risk_score: float = 0.5


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/predict")
async def predict_premium(body: PredictRequest):
    """Run the loaded XGBoost model and return a predicted premium."""
    features = np.array(
        [[body.zone_risk_score, body.weather_severity, body.claim_history]]
    )
    prediction = float(model.predict(features)[0])
    return {
        "zone": body.zone,
        "predicted_premium_inr": round(prediction, 2),
    }


@app.post("/register")
async def register_rider(body: RegisterRequest):
    """Register a rider — returns hardcoded response to unblock frontend."""
    return {
        "status": "success",
        "rider_id": "rdr_12345",
        "policy_id": "pol_99887",
        "premium": {
            "base_premium_inr": 82,
            "final_premium_inr": 115,
            "breakdown": [
                {"factor": "HSR Layout Flood Risk", "impact_inr": 25},
                {"factor": "Upcoming Weather Forecast", "impact_inr": 12},
                {"factor": "Rider Claim History", "impact_inr": -4},
            ],
        },
    }


@app.post("/triggers/simulate")
async def simulate_trigger(body: SimulateTriggerRequest):
    """Simulate a parametric trigger — returns hardcoded response."""
    return {
        "status": "triggered",
        "claims_processed": 1,
        "results": [
            {
                "rider_id": "rdr_12345",
                "payout_amount_inr": 840,
                "fraud_layers": {
                    "gps_verification": {
                        "passed": True,
                        "reason": "Rider pinged in HSR within 1hr",
                    },
                    "delhivery_crosscheck": {
                        "passed": True,
                        "reason": "14/18 orders cancelled (78%)",
                    },
                    "account_standing": {
                        "passed": True,
                        "reason": "No active platform suspensions",
                    },
                },
            }
        ],
    }
