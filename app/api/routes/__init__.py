from fastapi import APIRouter

from app.api.routes.admin import (
    admin_router,
    forecast_router,
    meta_router,
    premium_router,
)
from app.api.routes.bank import bank_router, mock_bank_router
from app.api.routes.claims import claims_router
from app.api.routes.enrollment import (
    enrollment_router,
    policy_router as eligibility_policy_router,
)
from app.api.routes.payments import (
    notifications_router,
    payments_router,
    payouts_router,
)
from app.api.routes.policies import demo_router, policies_router, policy_router
from app.api.routes.rider import rider_router
from app.api.routes.triggers import demo_triggers_router, triggers_router
from app.api.routes.weather import mock_weather_router, weather_router

api_router = APIRouter(prefix="/api")

api_router.include_router(meta_router)
api_router.include_router(admin_router)
api_router.include_router(premium_router)
api_router.include_router(forecast_router)
api_router.include_router(weather_router)
api_router.include_router(mock_weather_router)
api_router.include_router(bank_router)
api_router.include_router(mock_bank_router)
api_router.include_router(eligibility_policy_router)
api_router.include_router(enrollment_router)
api_router.include_router(policies_router)
api_router.include_router(policy_router)
api_router.include_router(demo_router)
api_router.include_router(triggers_router)
api_router.include_router(demo_triggers_router)
api_router.include_router(claims_router)
api_router.include_router(payments_router)
api_router.include_router(payouts_router)
api_router.include_router(notifications_router)
api_router.include_router(rider_router)

__all__ = ["api_router"]
