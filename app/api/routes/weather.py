import os

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.api.constants import DATA_DIR
from app.triggers.weather_service import FIXTURE_VERSION, WeatherService

weather_router = APIRouter(prefix="/weather", tags=["weather"])
mock_weather_router = APIRouter(prefix="/mock", tags=["weather"])


def fetch_delhivery_metrics(zone: str, date: str):
    try:
        df = pd.read_csv(os.path.join(DATA_DIR, "delhivery_dataset.csv"))
        zone_mask = df["source_name"].str.contains(zone, case=False, na=False) | df[
            "destination_name"
        ].str.contains(zone, case=False, na=False)
        zone_df = df[zone_mask]
        if len(zone_df) == 0:
            zone_df = df

        total_orders = len(zone_df)
        delayed = zone_df[zone_df["actual_time"] > zone_df["osrm_time"] * 1.5]
        cancelled_orders = len(delayed)
        cancellation_rate_pct = (
            round((cancelled_orders / total_orders) * 100, 2)
            if total_orders > 0
            else 0.0
        )

        return {
            "zone": zone,
            "date": date,
            "total_banking_orders": int(total_orders),
            "cancelled_orders": int(cancelled_orders),
            "cancellation_rate_pct": cancellation_rate_pct,
            "note": "Live data from logistics dataset",
            "fixture_version": FIXTURE_VERSION,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "DATASET_ERROR",
                "message": f"Failed to load real logistics dataset: {str(exc)}",
            },
        ) from exc


@weather_router.get("/current/{zone}")
def get_current_weather(zone: str):
    try:
        return WeatherService.get_current_conditions(zone, is_simulated=False)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "UNSUPPORTED_ZONE", "message": str(exc)}
        ) from exc


@weather_router.get("/warnings/{zone}")
def get_weather_warnings(zone: str):
    try:
        warnings = WeatherService.get_forecast_warnings(zone, is_simulated=False)
        return {"zone": zone, "warnings": warnings}
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "UNSUPPORTED_ZONE", "message": str(exc)}
        ) from exc


@mock_weather_router.get("/delhivery/{zone}/{date}")
def get_delhivery_metrics(zone: str, date: str):
    return fetch_delhivery_metrics(zone, date)
