from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Claim

claims_router = APIRouter(prefix="/claims", tags=["claims"])


@claims_router.get("/{rider_id}")
def get_claims_for_rider(rider_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(Claim)
        .filter(Claim.rider_id == rider_id)
        .order_by(Claim.created_at.desc())
        .all()
    )
    return {
        "rider_id": rider_id,
        "count": len(rows),
        "claims": [
            {
                "claim_id": row.id,
                "trigger_type": row.trigger_type,
                "trigger_value": row.trigger_value,
                "trigger_threshold": row.trigger_threshold,
                "fraud_check_passed": row.fraud_check_passed,
                "fraud_layers": row.fraud_layers,
                "payout_amount": row.payout_amount,
                "payout_status": row.payout_status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "is_simulated": row.is_simulated,
            }
            for row in rows
        ],
    }


@claims_router.get("")
def get_claims_admin(
    zone: Optional[str] = Query(default=None),
    trigger_type: Optional[str] = Query(default=None),
    is_simulated: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(Claim)
    if zone:
        query = query.filter(Claim.zone == zone)
    if trigger_type:
        query = query.filter(Claim.trigger_type == trigger_type.upper())
    if is_simulated is not None:
        query = query.filter(Claim.is_simulated == is_simulated)

    rows = query.order_by(Claim.created_at.desc()).limit(limit).all()
    return {
        "count": len(rows),
        "claims": [
            {
                "claim_id": row.id,
                "rider_id": row.rider_id,
                "zone": row.zone,
                "trigger_type": row.trigger_type,
                "payout_amount": row.payout_amount,
                "payout_status": row.payout_status,
                "fraud_check_passed": row.fraud_check_passed,
                "is_simulated": row.is_simulated,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }
