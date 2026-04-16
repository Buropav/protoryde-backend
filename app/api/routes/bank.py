from fastapi import APIRouter, HTTPException

from app.services.bank_branch_service import get_zone_branch_metrics
from app.triggers.weather_service import ZONES

bank_router = APIRouter(prefix="/bank", tags=["bank"])
mock_bank_router = APIRouter(prefix="/mock", tags=["bank"])


def fetch_banking_metrics(zone: str):
    if zone not in ZONES:
        raise HTTPException(
            status_code=422,
            detail={"error": "UNSUPPORTED_ZONE", "message": "Unsupported zone"},
        )

    metrics = get_zone_branch_metrics(zone)
    return {
        "zone": metrics["zone"],
        "total_branches": metrics["total_branches"],
        "closed_branches": metrics["closed_branches"],
        "closure_rate_pct": metrics["closure_rate_pct"],
        "threshold_pct": metrics["threshold_pct"],
        "trigger_breached": metrics["trigger_breached"],
        "source": metrics["source"],
        "fetched_at": metrics["fetched_at"],
    }


@bank_router.get("/branches/{zone}")
def get_banking_metrics(zone: str):
    return fetch_banking_metrics(zone)


@mock_bank_router.get("/branches/{zone}")
def get_banking_metrics_alias(zone: str):
    return fetch_banking_metrics(zone)
