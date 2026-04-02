"""
main.py -- ProtoRyde FastAPI server (Day 2 / database-backed).

Start:  uvicorn main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import engine, get_db
from schemas import (
    RegisterRequest,
    SimulateTriggerRequest,
    RegisterResponse,
    SimulateResponse,
)
import models

# ---------------------------------------------------------------------------
# ML model holder (populated at startup)
# ---------------------------------------------------------------------------
ml_model = None


# ---------------------------------------------------------------------------
# Lifespan -- create tables & load ML model on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global ml_model

    # Create all tables if they don't exist yet
    models.Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created / verified")

    # Load ML model
    model_path = Path("model.pkl")
    if not model_path.exists():
        raise RuntimeError(
            "model.pkl not found. Run `python train.py` first to generate it."
        )
    ml_model = joblib.load(model_path)
    print("[OK] model.pkl loaded into memory")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ProtoRyde API",
    version="0.2.0",
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
# Request helper for /predict (unchanged from Day 1)
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    zone: str
    weather_severity: float = 2.0
    claim_history: float = 1.0
    zone_risk_score: float = 0.5


# ---------------------------------------------------------------------------
# Zone-risk mapping (simple lookup for the ML model input)
# ---------------------------------------------------------------------------
ZONE_RISK = {
    "HSR":        0.8,
    "Koramangala": 0.6,
    "Whitefield":  0.5,
    "Indiranagar":  0.55,
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/predict")
def predict_premium(body: PredictRequest):
    """Run the loaded XGBoost model and return a predicted premium."""
    features = np.array(
        [[body.zone_risk_score, body.weather_severity, body.claim_history]]
    )
    prediction = float(ml_model.predict(features)[0])
    return {
        "zone": body.zone,
        "predicted_premium_inr": round(prediction, 2),
    }


@app.post("/register", response_model=RegisterResponse)
def register_rider(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a rider:
    1. Write Rider row
    2. Run ML model to compute premium
    3. Write Policy row linked to that Rider
    4. Return both records
    """
    # 1 -- Create rider
    rider = models.Rider(
        name=body.name,
        phone=body.phone,
        delhivery_partner_id=body.delhivery_partner_id,
        zone=body.zone,
    )
    db.add(rider)
    db.flush()  # generates rider.id without committing

    # 2 -- Compute premium via ML model
    zone_risk = ZONE_RISK.get(body.zone, 0.5)
    features = np.array([[zone_risk, 2.0, 1.0]])  # default weather & claim values
    predicted = float(ml_model.predict(features)[0])

    base_premium = round(predicted, 2)

    breakdown = [
        {"factor": f"{body.zone} Flood Risk", "impact_inr": round(zone_risk * 30, 2)},
        {"factor": "Upcoming Weather Forecast", "impact_inr": 12},
        {"factor": "Rider Claim History", "impact_inr": -4},
    ]
    adjustment = sum(item["impact_inr"] for item in breakdown)
    final_premium = round(base_premium + adjustment, 2)

    # 3 -- Create policy
    policy = models.Policy(
        rider_id=rider.id,
        base_premium=base_premium,
        final_premium=final_premium,
        premium_breakdown=breakdown,
        status="active",
    )
    db.add(policy)
    db.commit()
    db.refresh(rider)
    db.refresh(policy)

    # 4 -- Return
    return {
        "status": "success",
        "rider": rider,
        "policy": policy,
    }


@app.post("/triggers/simulate", response_model=SimulateResponse)
def simulate_trigger(body: SimulateTriggerRequest, db: Session = Depends(get_db)):
    """
    Simulate a parametric trigger:
    1. Write TriggerEvent row
    2. Find a rider in the given zone
    3. Create a Claim linked to that rider's active policy
    4. Log action to AuditLog
    5. Return results
    """
    # 1 -- Record the trigger event
    trigger_event = models.TriggerEvent(
        zone=body.zone,
        trigger_type=body.trigger_type,
        simulated_value=body.simulated_value,
    )
    db.add(trigger_event)
    db.flush()

    # 2 -- Find a rider in this zone
    rider = db.query(models.Rider).filter(models.Rider.zone == body.zone).first()
    if not rider:
        raise HTTPException(
            status_code=404,
            detail=f"No riders found in zone '{body.zone}'. Register a rider first.",
        )

    # Find an active policy for this rider
    policy = (
        db.query(models.Policy)
        .filter(models.Policy.rider_id == rider.id, models.Policy.status == "active")
        .first()
    )
    if not policy:
        raise HTTPException(
            status_code=404,
            detail=f"No active policy found for rider '{rider.id}'.",
        )

    # 3 -- Create a claim
    fraud_layers = {
        "gps_verification": {
            "passed": True,
            "reason": f"Rider pinged in {body.zone} within 1hr",
        },
        "delhivery_crosscheck": {
            "passed": True,
            "reason": "14/18 orders cancelled (78%)",
        },
        "account_standing": {
            "passed": True,
            "reason": "No active platform suspensions",
        },
    }

    payout = round(body.simulated_value * 10, 2)  # simple payout formula

    claim = models.Claim(
        policy_id=policy.id,
        rider_id=rider.id,
        trigger_type=body.trigger_type,
        payout_amount=payout,
        fraud_layers=fraud_layers,
        status="approved",
    )
    db.add(claim)
    db.flush()

    # 4 -- Audit log
    audit = models.AuditLog(
        entity_type="claim",
        entity_id=claim.id,
        action="claim_created",
        metadata_info={
            "trigger_event_id": trigger_event.id,
            "trigger_type": body.trigger_type,
            "zone": body.zone,
            "payout_amount": payout,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(claim)

    # 5 -- Return
    return {
        "status": "triggered",
        "trigger_event_id": trigger_event.id,
        "claims_processed": 1,
        "results": [claim],
    }
