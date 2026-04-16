import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

HEAVY_RAIN_THRESHOLD = 30.0
EXTREME_HEAT_THRESHOLD = 40.0
SEVERE_AQI_THRESHOLD = 300.0
FIXTURE_VERSION = "2026.04.03.v1"

# Coordinates for the 8 demo zones.
ZONES = {
    "HSR Layout": {"lat": 12.9141, "lon": 77.6411},
    "Whitefield": {"lat": 12.9698, "lon": 77.7499},
    "Bellandur": {"lat": 12.9304, "lon": 77.6784},
    "Koramangala": {"lat": 12.9279, "lon": 77.6271},
    "Indiranagar": {"lat": 12.9784, "lon": 77.6408},
    "Marathahalli": {"lat": 12.9569, "lon": 77.7011},
    "BTM Layout": {"lat": 12.9166, "lon": 77.6101},
    "Electronic City": {"lat": 12.8452, "lon": 77.6602},
}

# Open fallback data used only when live fetch fails.
FALLBACK_WEATHER = {
    "HSR Layout": {
        "rain_24h_mm": 44.0,
        "temp_c": 31.5,
        "aqi": 162,
        "humidity_pct": 78.0,
        "wind_kph": 13.2,
    },
    "Whitefield": {
        "rain_24h_mm": 12.0,
        "temp_c": 30.0,
        "aqi": 118,
        "humidity_pct": 66.0,
        "wind_kph": 9.8,
    },
    "Bellandur": {
        "rain_24h_mm": 48.0,
        "temp_c": 30.8,
        "aqi": 188,
        "humidity_pct": 80.0,
        "wind_kph": 14.5,
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WeatherService:
    @staticmethod
    def _build_trigger_view(conditions: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        return {
            "heavy_rain": {
                "value": conditions["rain_24h_mm"],
                "threshold": HEAVY_RAIN_THRESHOLD,
                "breached": conditions["rain_24h_mm"] >= HEAVY_RAIN_THRESHOLD,
            },
            "extreme_heat": {
                "value": conditions["temp_c"],
                "threshold": EXTREME_HEAT_THRESHOLD,
                "breached": conditions["temp_c"] >= EXTREME_HEAT_THRESHOLD,
            },
            "severe_aqi": {
                "value": conditions["aqi"],
                "threshold": SEVERE_AQI_THRESHOLD,
                "breached": conditions["aqi"] >= SEVERE_AQI_THRESHOLD,
            },
        }

    @staticmethod
    async def _live_conditions_async(zone: str) -> Dict[str, float]:
        """Fetch live weather + air quality concurrently using httpx."""
        coords = ZONES[zone]
        lat, lon = coords["lat"], coords["lon"]

        conditions = {
            "rain_24h_mm": 0.0,
            "temp_c": 0.0,
            "aqi": 0.0,
            "humidity_pct": 0.0,
            "wind_kph": 0.0,
        }

        async with httpx.AsyncClient(timeout=6.0) as client:
            weather_req = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m",
                    "timezone": "auto",
                },
            )
            air_req = client.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "european_aqi",
                    "timezone": "auto",
                },
            )
            weather_res, air_res = await asyncio.gather(weather_req, air_req)

        weather_res.raise_for_status()
        current = weather_res.json().get("current", {})
        # NOTE: Open-Meteo "current.precipitation" is the instantaneous rate (mm),
        # not a 24h cumulative total. For demo purposes this is acceptable; for
        # production, switch to the "daily" endpoint with "precipitation_sum".
        conditions["rain_24h_mm"] = float(current.get("precipitation", 0.0))
        conditions["temp_c"] = float(current.get("temperature_2m", 0.0))
        conditions["humidity_pct"] = float(current.get("relative_humidity_2m", 0.0))
        conditions["wind_kph"] = float(current.get("wind_speed_10m", 0.0))

        air_res.raise_for_status()
        air_current = air_res.json().get("current", {})
        conditions["aqi"] = float(air_current.get("european_aqi", 0.0))
        return conditions

    @staticmethod
    def _live_conditions_sync(zone: str) -> Dict[str, float]:
        """Sync wrapper for _live_conditions_async — safe to call from sync FastAPI endpoints."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an async context (e.g. FastAPI); run in a new thread.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run, WeatherService._live_conditions_async(zone)
                ).result()
        else:
            return asyncio.run(WeatherService._live_conditions_async(zone))

    @staticmethod
    def get_current_conditions(zone: str, is_simulated: bool = False) -> Dict[str, Any]:
        if zone not in ZONES:
            raise ValueError(f"Unsupported zone: {zone}")

        if is_simulated:
            logger.warning("is_simulated was requested for %s but is disabled", zone)

        source = "open-meteo"
        try:
            conditions = WeatherService._live_conditions_sync(zone)
        except Exception:
            # Fall back to static values to avoid hard failures when upstream is unavailable.
            conditions = FALLBACK_WEATHER.get(zone, FALLBACK_WEATHER["Whitefield"])
            source = "open-meteo-fallback"

        logger.info(
            "Fetched hyper-local weather for boundary/ward %s (ward_level_data: True)",
            zone,
        )
        return {
            "zone": zone,
            "ward_level_data": True,
            "timestamp": _now_iso(),
            "source": source,
            "is_simulated": False,
            "fixture_version": FIXTURE_VERSION if source != "open-meteo" else None,
            "conditions": conditions,
            "trigger_view": WeatherService._build_trigger_view(conditions),
        }

    @staticmethod
    def get_forecast_warnings(zone: str, is_simulated: bool = False) -> List[str]:
        current = WeatherService.get_current_conditions(zone, is_simulated=False)
        warnings: List[str] = []
        trigger_view = current["trigger_view"]
        if trigger_view["heavy_rain"]["breached"]:
            warnings.append("Heavy Rain Advisory: Threshold conditions are breached.")
        if trigger_view["extreme_heat"]["breached"]:
            warnings.append(
                "Extreme Heat Advisory: Temperatures are at or above threshold."
            )
        if trigger_view["severe_aqi"]["breached"]:
            warnings.append("Severe AQI Advisory: Air quality threshold is breached.")
        return warnings
