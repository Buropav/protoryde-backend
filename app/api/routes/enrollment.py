from datetime import timedelta

from fastapi import APIRouter, HTTPException

from app.api.dependencies import check_enrollment_lockout, now_utc
from app.triggers.weather_service import WeatherService, ZONES

policy_router = APIRouter(prefix="/policy", tags=["enrollment"])
enrollment_router = APIRouter(prefix="/enrollment", tags=["enrollment"])


@policy_router.get("/eligibility")
@enrollment_router.get("/eligibility")
def get_policy_eligibility(zone: str):
    if zone not in ZONES:
        raise HTTPException(
            status_code=422,
            detail={"error": "UNSUPPORTED_ZONE", "message": "Unsupported zone"},
        )

    weather = WeatherService.get_current_conditions(zone, is_simulated=False)
    lockout_active = False
    reason = None

    if weather["conditions"]["aqi"] > 500:
        lockout_active = True
        reason = "Severe AQI weather advisory active. Enrollment paused for 48 hours to prevent adverse selection."
    elif weather["conditions"]["rain_24h_mm"] > 20:
        lockout_active = True
        reason = "Severe rainfall active. Enrollment paused for 48 hours to prevent adverse selection."

    return {
        "zone": zone,
        "lockout_active": lockout_active,
        "reason": reason,
        "expires_at": (now_utc() + timedelta(hours=48)).isoformat()
        if lockout_active
        else None,
    }


@enrollment_router.get("/lockout-status/{zone}")
def get_enrollment_lockout_status(zone: str):
    if zone not in ZONES:
        raise HTTPException(
            status_code=422,
            detail={"error": "UNSUPPORTED_ZONE", "message": "Unsupported zone"},
        )

    warnings = check_enrollment_lockout(zone)
    return {
        "zone": zone,
        "lockout_active": len(warnings) > 0,
        "active_warnings": warnings,
        "message": "Enrollment blocked — active weather advisory"
        if warnings
        else "Enrollment open",
    }
