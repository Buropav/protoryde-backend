from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import now_utc
from app.core.database import get_db
from app.core.models import Claim, Rider

rider_router = APIRouter(prefix="/rider", tags=["rider"])


@rider_router.get("/{id}/calendar")
def get_rider_calendar(id: str, db: Session = Depends(get_db)):
    now = now_utc()
    calendar = []

    rider = db.query(Rider).filter(Rider.id == id).first()
    if rider is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "RIDER_NOT_FOUND", "message": "Rider not found"},
        )

    seven_days_ago = now - timedelta(days=7)
    claims = (
        db.query(Claim)
        .filter(
            Claim.rider_id == id,
            Claim.created_at >= seven_days_ago,
            Claim.payout_status == "PAID",
        )
        .all()
    )

    claims_by_date = {}
    for claim in claims:
        date_key = claim.created_at.date().isoformat()
        claims_by_date[date_key] = (
            claims_by_date.get(date_key, 0.0) + claim.payout_amount
        )

    base_daily_earnings = float(rider.avg_daily_earnings or 0.0)

    for i in range(7):
        target_date = (now - timedelta(days=i)).date()
        date_str = target_date.isoformat()

        delhivery_earnings = round(base_daily_earnings, 2)
        claim_payout = claims_by_date.get(date_str, 0.0)

        calendar.append(
            {
                "date": date_str,
                "delhivery_earnings": delhivery_earnings,
                "claim_payout": claim_payout,
                "total_earnings": round(delhivery_earnings + claim_payout, 2),
                "protected": claim_payout > 0.0,
            }
        )

    return {"rider_id": id, "calendar": calendar}
