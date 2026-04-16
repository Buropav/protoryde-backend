import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import httpx

from app.triggers.weather_service import ZONES

logger = logging.getLogger(__name__)

OVERPASS_URL = os.getenv(
    "BANK_BRANCH_OVERPASS_URL", "https://overpass-api.de/api/interpreter"
)
SEARCH_RADIUS_METERS = int(os.getenv("BANK_SEARCH_RADIUS_METERS", "5000"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("BANK_BRANCH_TIMEOUT_SECONDS", "12"))
CACHE_TTL_SECONDS = int(os.getenv("BANK_DATA_CACHE_TTL_SECONDS", "21600"))

_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_overpass_query(lat: float, lon: float, radius: int) -> str:
    return (
        "[out:json][timeout:25];"
        "("
        f'node["amenity"="bank"](around:{radius},{lat},{lon});'
        f'way["amenity"="bank"](around:{radius},{lat},{lon});'
        f'relation["amenity"="bank"](around:{radius},{lat},{lon});'
        ");"
        "out tags center;"
    )


def _is_likely_closed(tags: Dict[str, Any]) -> bool:
    opening_hours = str(tags.get("opening_hours", "")).strip().lower()
    if opening_hours in {"closed", "off", "no"}:
        return True

    if str(tags.get("disused", "")).strip().lower() == "yes":
        return True
    if str(tags.get("abandoned", "")).strip().lower() == "yes":
        return True

    disused_amenity = str(tags.get("disused:amenity", "")).strip().lower()
    abandoned_amenity = str(tags.get("abandoned:amenity", "")).strip().lower()
    was_amenity = str(tags.get("was:amenity", "")).strip().lower()

    if disused_amenity == "bank" or abandoned_amenity == "bank":
        return True
    if was_amenity == "bank" and str(tags.get("amenity", "")).strip().lower() != "bank":
        return True

    return False


def _fetch_live_metrics(zone: str) -> Dict[str, Any]:
    coords = ZONES[zone]
    query = _build_overpass_query(
        lat=float(coords["lat"]),
        lon=float(coords["lon"]),
        radius=SEARCH_RADIUS_METERS,
    )

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.get(OVERPASS_URL, params={"data": query})
        response.raise_for_status()
        payload = response.json()

    elements = payload.get("elements") or []
    seen = set()
    total_branches = 0
    closed_branches = 0

    for element in elements:
        ident = f"{element.get('type', 'x')}:{element.get('id', '0')}"
        if ident in seen:
            continue
        seen.add(ident)

        tags = element.get("tags") or {}
        amenity = str(tags.get("amenity", "")).strip().lower()
        if amenity != "bank":
            continue

        total_branches += 1
        if _is_likely_closed(tags):
            closed_branches += 1

    closure_rate_pct = (
        round((float(closed_branches) / float(total_branches)) * 100.0, 2)
        if total_branches > 0
        else 0.0
    )

    return {
        "zone": zone,
        "total_branches": int(total_branches),
        "closed_branches": int(closed_branches),
        "closure_rate_pct": closure_rate_pct,
        "threshold_pct": 60.0,
        "trigger_breached": closure_rate_pct >= 60.0,
        "source": "openstreetmap_overpass",
        "fetched_at": _now_iso(),
    }


def get_zone_branch_metrics(zone: str) -> Dict[str, Any]:
    if zone not in ZONES:
        raise ValueError(f"Unsupported zone: {zone}")

    now = time.time()
    cached = _CACHE.get(zone)
    if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    try:
        metrics = _fetch_live_metrics(zone)
        _CACHE[zone] = (now, metrics)
        return metrics
    except Exception as exc:
        logger.warning("Branch metrics fetch failed for %s: %s", zone, exc)
        if cached:
            stale = dict(cached[1])
            stale["source"] = "cache_stale"
            return stale
        return {
            "zone": zone,
            "total_branches": 0,
            "closed_branches": 0,
            "closure_rate_pct": 0.0,
            "threshold_pct": 60.0,
            "trigger_breached": False,
            "source": "unavailable",
            "fetched_at": _now_iso(),
        }
