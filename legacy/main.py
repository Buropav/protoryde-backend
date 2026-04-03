"""
main.py -- ProtoRyde FastAPI server (Day 3 / DB + PDF + SHAP).

Start:  uvicorn main:app --reload --port 8080
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
from ml_service import get_premium_and_breakdown
from pdf_service import generate_policy_pdf


# ---------------------------------------------------------------------------
# Zone-risk mapping (simple lookup for the ML model input)
# ---------------------------------------------------------------------------
ZONE_RISK = {
    "HSR":         0.8,
    "Koramangala": 0.6,
    "Whitefield":  0.5,
    "Indiranagar":  0.55,
}


# ---------------------------------------------------------------------------
# Lifespan -- create tables on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created / verified")
    # ml_service already loads the model & SHAP explainer at import time
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ProtoRyde API",
    version="0.3.0",
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
# Request helper for /predict
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
def predict_premium(body: PredictRequest):
    """Run the ML model with SHAP explainability and return the breakdown."""
    result = get_premium_and_breakdown(
        zone_risk=body.zone_risk_score,
        weather_severity=body.weather_severity,
        claim_history=int(body.claim_history),
    )
    return {
        "zone": body.zone,
        "predicted_premium_inr": result["base_premium_inr"],
        "shap_breakdown": result["breakdown"],
    }


@app.post("/register", response_model=RegisterResponse)
def register_rider(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a rider:
    1. Write Rider row
    2. Compute premium via ML + SHAP breakdown
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
    db.flush()

    # 2 -- Get real ML premium + SHAP breakdown
    zone_risk = ZONE_RISK.get(body.zone, 0.5)
    ml_result = get_premium_and_breakdown(
        zone_risk=zone_risk,
        weather_severity=2.0,
        claim_history=1,
    )

    base_premium = ml_result["base_premium_inr"]
    breakdown = ml_result["breakdown"]
    final_premium = ml_result["final_premium_inr"]

    # 3 -- Create policy with SHAP-driven breakdown
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


@app.get("/policy/{policy_id}/pdf")
def download_policy_pdf(policy_id: str, db: Session = Depends(get_db)):
    """
    Generate and stream a PDF for the given policy.
    """
    policy = db.query(models.Policy).filter(models.Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found.")

    rider = db.query(models.Rider).filter(models.Rider.id == policy.rider_id).first()
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found for this policy.")

    # Build dicts for the PDF service
    policy_data = {
        "id": policy.id,
        "base_premium": policy.base_premium,
        "final_premium": policy.final_premium,
        "premium_breakdown": policy.premium_breakdown,
        "status": policy.status,
        "created_at": policy.created_at,
    }
    rider_data = {
        "name": rider.name,
        "phone": rider.phone,
        "delhivery_partner_id": rider.delhivery_partner_id,
        "zone": rider.zone,
    }

    buf = generate_policy_pdf(policy_data, rider_data)

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="protoryde_policy.pdf"'
        },
    )


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

    payout = round(body.simulated_value * 10, 2)

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
