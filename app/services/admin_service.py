from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.core.models import Policy, Claim
from app.services.forecast_service import generate_zone_forecast


def calculate_pool_health(db: Session) -> dict:
    active_policies_count = db.query(Policy).filter(Policy.status == "active").count()

    total_premiums = db.query(func.sum(Policy.final_premium)).scalar() or 0.0
    total_claims_paid = (
        db.query(func.sum(Claim.payout_amount))
        .filter(Claim.payout_status == "PAID")
        .scalar()
        or 0.0
    )
    total_balance = float(total_premiums) - float(total_claims_paid)

    forecast = generate_zone_forecast(zone="HSR Layout", db=db, horizon_days=7)
    expected_payout = float(
        sum(day.get("expected_loss", 0.0) for day in (forecast.get("forecast") or []))
    )
    post_stress_balance = total_balance - expected_payout

    bcr = (
        round(float(total_premiums) / float(total_claims_paid), 2)
        if float(total_claims_paid) > 0.0
        else None
    )
    reserve_ratio = (
        f"{round((float(total_premiums) / float(total_claims_paid)) * 100, 2)}%"
        if float(total_claims_paid) > 0.0
        else "N/A"
    )

    return {
        "active_policies": active_policies_count,
        "pool_balance": total_balance,
        "bcr": bcr,
        "status": "sustainable" if post_stress_balance >= 0 else "at_risk",
        "reserve_ratio": reserve_ratio,
        "projected_7_day_impact": {
            "zone": forecast.get("zone", "HSR Layout"),
            "expected_claims": len(forecast.get("forecast") or []),
            "expected_payout": round(expected_payout, 2),
            "post_stress_balance": post_stress_balance,
            "post_stress_status": "solvent" if post_stress_balance > 0 else "insolvent",
        },
    }
