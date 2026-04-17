from datetime import timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.constants import EXCLUSIONS, EXCLUSIONS_VERSION
from app.api.dependencies import (
    now_utc,
)
from app.api.schemas import DemoBootstrapRequest, PolicyActivateRequest
from app.api.routes.enrollment import get_policy_eligibility
from app.core.database import get_db
from app.core.models import AuditLog, Claim, Policy, Rider
from app.services.policy_pdf import generate_ledger_pdf, generate_policy_pdf
from app.services.policy_service import activate_rider_policy, bootstrap_demo_rider
from app.triggers.weather_service import FIXTURE_VERSION

policies_router = APIRouter(prefix="/policies", tags=["policies"])
policy_router = APIRouter(prefix="/policy", tags=["policies"])
demo_router = APIRouter(prefix="/demo", tags=["policies"])


@policies_router.post("/activate")
def activate_policy(payload: PolicyActivateRequest, db: Session = Depends(get_db)):
    return activate_rider_policy(db, payload)


@demo_router.post("/bootstrap")
def bootstrap_demo_alias(payload: DemoBootstrapRequest, db: Session = Depends(get_db)):
    rider = bootstrap_demo_rider(db, payload)

    policy_response = activate_rider_policy(
        db,
        PolicyActivateRequest(
            rider_id=payload.rider_id,
            zone=payload.zone,
            exclusions_accepted=payload.exclusions_accepted,
            forecast_features=payload.forecast_features,
            rider_features=payload.rider_features,
            prefer_ml=payload.prefer_ml,
            weather_severity=payload.weather_severity,
            claim_history=payload.claim_history,
            zone_risk_score=payload.zone_risk_score,
        ),
    )

    db.refresh(rider)
    return {
        "status": "ok",
        "rider": {
            "rider_id": rider.id,
            "name": rider.name,
            "zone": rider.zone,
            "upi_id": rider.upi_id,
            "kyc_verified": rider.kyc_verified,
        },
        "policy": policy_response,
        "lockout_status": get_policy_eligibility(payload.zone),
    }


@policies_router.get("/{rider_id}/current")
def get_current_policy(rider_id: str, db: Session = Depends(get_db)):
    policy = (
        db.query(Policy)
        .filter(Policy.rider_id == rider_id, Policy.status == "active")
        .order_by(Policy.created_at.desc())
        .first()
    )
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "POLICY_NOT_FOUND", "message": "No active policy"},
        )
    return {
        "policy_id": policy.id,
        "rider_id": rider_id,
        "week_start_date": policy.week_start_date.isoformat()
        if policy.week_start_date
        else None,
        "week_end_date": policy.week_end_date.isoformat()
        if policy.week_end_date
        else None,
        "base_premium": policy.base_premium,
        "final_premium": policy.final_premium,
        "premium_breakdown": policy.premium_breakdown,
        "coverage_cap": policy.coverage_cap,
        "status": policy.status,
        "exclusions_version": EXCLUSIONS_VERSION,
        "exclusions_acknowledged_at": policy.exclusions_acknowledged_at.isoformat()
        if policy.exclusions_acknowledged_at
        else None,
    }


@policies_router.get("/{rider_id}/history")
def get_policy_history(rider_id: str, db: Session = Depends(get_db)):
    policies = (
        db.query(Policy)
        .filter(Policy.rider_id == rider_id)
        .order_by(Policy.created_at.desc())
        .all()
    )
    return {
        "rider_id": rider_id,
        "count": len(policies),
        "policies": [
            {
                "policy_id": row.id,
                "status": row.status,
                "week_start_date": row.week_start_date.isoformat()
                if row.week_start_date
                else None,
                "week_end_date": row.week_end_date.isoformat()
                if row.week_end_date
                else None,
                "base_premium": row.base_premium,
                "final_premium": row.final_premium,
                "coverage_cap": row.coverage_cap,
                "exclusions_acknowledged_at": row.exclusions_acknowledged_at.isoformat()
                if row.exclusions_acknowledged_at
                else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in policies
        ],
    }


@policies_router.get("/{rider_id}/current/document")
def download_current_policy_document(rider_id: str, db: Session = Depends(get_db)):
    rider = db.query(Rider).filter(Rider.id == rider_id).first()
    if rider is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "RIDER_NOT_FOUND", "message": "Rider not found"},
        )

    policy = (
        db.query(Policy)
        .filter(Policy.rider_id == rider_id, Policy.status == "active")
        .order_by(Policy.created_at.desc())
        .first()
    )
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "POLICY_NOT_FOUND", "message": "No active policy"},
        )

    from app.triggers.fraud_engine import TRIGGER_THRESHOLDS

    pdf_bytes = generate_policy_pdf(
        policy_data={
            "id": policy.id,
            "status": policy.status,
            "base_premium": policy.base_premium,
            "final_premium": policy.final_premium,
            "premium_breakdown": policy.premium_breakdown,
            "created_at": policy.created_at,
        },
        rider_data={
            "name": rider.name,
            "phone": rider.phone,
            "delhivery_partner_id": rider.delhivery_partner_id,
            "zone": rider.zone,
        },
        exclusions=EXCLUSIONS,
        exclusions_version=EXCLUSIONS_VERSION,
        thresholds={
            "HEAVY_RAIN_MM": TRIGGER_THRESHOLDS["HEAVY_RAIN"],
            "EXTREME_HEAT_C": TRIGGER_THRESHOLDS["EXTREME_HEAT"],
            "SEVERE_AQI": TRIGGER_THRESHOLDS["SEVERE_AQI"],
            "BRANCH_CLOSURE_PERCENT": TRIGGER_THRESHOLDS["BRANCH_CLOSURE"],
            "DELHIVERY_ADVISORY_PERCENT": TRIGGER_THRESHOLDS["DELHIVERY_ADVISORY"],
        },
        fixture_version=FIXTURE_VERSION,
    )
    filename = f"protoryde-policy-{policy.id}.pdf"
    db.add(
        AuditLog(
            entity_type="Policy",
            entity_id=policy.id,
            action="POLICY_DOCUMENT_DOWNLOADED",
            metadata_json={"rider_id": rider_id, "filename": filename},
        )
    )
    db.commit()

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@policies_router.get("/{rider_id}/ledger/document")
def download_annual_ledger_document(rider_id: str, db: Session = Depends(get_db)):
    rider = db.query(Rider).filter(Rider.id == rider_id).first()
    if rider is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "RIDER_NOT_FOUND", "message": "Rider not found"},
        )

    now = now_utc()
    one_year_ago = now - timedelta(days=365)

    policies = (
        db.query(Policy)
        .filter(Policy.rider_id == rider_id, Policy.created_at >= one_year_ago)
        .order_by(Policy.created_at.desc())
        .all()
    )

    claims = (
        db.query(Claim)
        .filter(Claim.rider_id == rider_id, Claim.created_at >= one_year_ago)
        .order_by(Claim.created_at.desc())
        .all()
    )

    total_base_premium = sum(p.base_premium or 0.0 for p in policies)
    total_claims_paid = sum(
        c.payout_amount or 0.0 for c in claims if c.payout_status == "PAID"
    )
    net_balance = total_claims_paid - total_base_premium
    claims_count = len(claims)

    summary_metrics = {
        "total_base_premium": total_base_premium,
        "total_claims_paid": total_claims_paid,
        "net_balance": net_balance,
        "claims_count": claims_count,
    }

    policy_dicts = [
        {
            "id": p.id,
            "week_start_date": p.week_start_date,
            "status": p.status,
            "base_premium": p.base_premium,
        }
        for p in policies
    ]

    claim_dicts = [
        {
            "id": c.id,
            "trigger_type": c.trigger_type,
            "payout_status": c.payout_status,
            "payout_amount": c.payout_amount,
        }
        for c in claims
    ]

    pdf_bytes = generate_ledger_pdf(
        rider_data={
            "name": rider.name,
            "phone": rider.phone,
            "delhivery_partner_id": rider.delhivery_partner_id,
            "zone": rider.zone,
        },
        policies=policy_dicts,
        claims=claim_dicts,
        summary_metrics=summary_metrics,
    )

    filename = f"protoryde_annual_ledger_{rider_id}.pdf"

    db.add(
        AuditLog(
            entity_type="Rider",
            entity_id=rider_id,
            action="ANNUAL_LEDGER_DOWNLOADED",
            metadata_json={
                "filename": filename,
                "policies_count": len(policies),
                "claims_count": claims_count,
            },
        )
    )
    db.commit()

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@policy_router.post("/{id}/upgrade")
def upgrade_policy(id: str, db: Session = Depends(get_db)):
    policy = db.query(Policy).filter(Policy.id == id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if getattr(policy, "coverage_tier", "STANDARD") == "ENHANCED":
        raise HTTPException(
            status_code=400, detail="Policy is already upgraded to ENHANCED tier"
        )

    policy.coverage_tier = "ENHANCED"
    policy.final_premium += 25.0
    policy.coverage_cap = 2800.0

    db.commit()
    db.refresh(policy)

    return {
        "status": "upgraded",
        "policy_id": policy.id,
        "coverage_tier": policy.coverage_tier,
        "final_premium": policy.final_premium,
        "coverage_cap": policy.coverage_cap,
    }
