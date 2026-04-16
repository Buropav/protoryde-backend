import json
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.models import Claim, Policy, Rider
from app.services.model_monitoring import log_prediction
from app.services.model_registry import (
    MODELS_DIR,
    bootstrap_registry_if_missing,
    get_model_entry,
    sync_model_artifact,
)
from app.triggers.weather_service import ZONES


FORECAST_CACHE_PATH = MODELS_DIR / "forecast_cache.json"
DEFAULT_COVERAGE_CAP = 2300.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_sql_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _synthetic_daily_series(zone: str, days: int = 90) -> pd.DataFrame:
    seed = sum(ord(c) for c in zone)
    rng = random.Random(seed)
    today = _utc_now().date()
    start = today - timedelta(days=days - 1)
    rows: List[Dict[str, Any]] = []
    for i in range(days):
        ds = start + timedelta(days=i)
        weekly = 0.08 if ds.weekday() in (5, 6) else 0.0
        monsoon_bias = 0.12 if ds.month in (6, 7, 8, 9) else 0.03
        jitter = rng.uniform(-0.04, 0.04)
        y = max(0.01, min(0.95, monsoon_bias + weekly + jitter))
        rows.append({"ds": pd.Timestamp(ds), "y": y})
    return pd.DataFrame(rows)


def _daily_claim_probability(zone: str, db: Session, days: int = 120) -> pd.DataFrame:
    since = _utc_now() - timedelta(days=days)

    claim_rows = (
        db.query(func.date(Claim.created_at), func.count(Claim.id))
        .filter(
            Claim.zone == zone,
            Claim.created_at >= since,
            Claim.payout_status == "PAID",
        )
        .group_by(func.date(Claim.created_at))
        .all()
    )

    policy_rows = (
        db.query(func.date(Policy.created_at), func.count(Policy.id))
        .join(Rider, Rider.id == Policy.rider_id)
        .filter(Rider.zone == zone, Policy.created_at >= since)
        .group_by(func.date(Policy.created_at))
        .all()
    )

    if not claim_rows and not policy_rows:
        return _synthetic_daily_series(zone, days=90)

    claim_by_day = {
        pd.Timestamp(_parse_sql_date(day).date()): int(count)
        for day, count in claim_rows
    }
    policy_by_day = {
        pd.Timestamp(_parse_sql_date(day).date()): int(count)
        for day, count in policy_rows
    }

    first_day = min(list(claim_by_day.keys()) + list(policy_by_day.keys()))
    last_day = pd.Timestamp(_utc_now().date())
    calendar = pd.date_range(start=first_day, end=last_day, freq="D")

    records: List[Dict[str, Any]] = []
    for day in calendar:
        claims = claim_by_day.get(day, 0)
        policies = max(policy_by_day.get(day, 0), 10)
        y = max(0.0, min(1.0, float(claims) / float(policies)))
        records.append({"ds": day, "y": y})

    frame = pd.DataFrame(records)
    if len(frame) < 30:
        return _synthetic_daily_series(zone, days=90)
    return frame


def _forecast_with_prophet(history: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    from prophet import Prophet  # type: ignore

    model = Prophet(weekly_seasonality=True, daily_seasonality=False)
    model.fit(history[["ds", "y"]])
    future = model.make_future_dataframe(periods=horizon_days, freq="D")
    pred = model.predict(future).tail(horizon_days)
    out = pred[["ds", "yhat"]].copy()
    out["yhat"] = out["yhat"].clip(lower=0.0, upper=1.0)
    out.rename(columns={"yhat": "prob_payout"}, inplace=True)
    return out


def _forecast_fallback(
    history: pd.DataFrame, horizon_days: int, zone: str
) -> pd.DataFrame:
    seed = sum(ord(c) for c in zone) + len(history)
    rng = random.Random(seed)
    recent = history.tail(14)["y"]
    baseline = float(recent.mean()) if not recent.empty else 0.15
    baseline = max(0.02, min(0.85, baseline))

    start = pd.Timestamp(_utc_now().date())
    rows: List[Dict[str, Any]] = []
    for i in range(horizon_days):
        day = start + pd.Timedelta(days=i)
        weekly = 0.05 if day.weekday() in (5, 6) else 0.0
        monsoon_bias = 0.08 if day.month in (6, 7, 8, 9) else 0.02
        jitter = rng.uniform(-0.03, 0.03)
        prob = max(0.0, min(1.0, baseline + weekly + monsoon_bias + jitter))
        rows.append({"ds": day, "prob_payout": prob})
    return pd.DataFrame(rows)


def _current_forecast_version() -> str:
    bootstrap_registry_if_missing()
    model_info = get_model_entry("forecast_prophet")
    return model_info.get("version", "v0.0.0")


def generate_zone_forecast(
    zone: str,
    db: Session,
    horizon_days: int = 7,
    bump_model_version: bool = False,
) -> Dict[str, Any]:
    if zone not in ZONES:
        raise ValueError("UNSUPPORTED_ZONE")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    history = _daily_claim_probability(zone=zone, db=db)

    framework = "prophet"
    used_fallback = False
    try:
        pred = _forecast_with_prophet(history=history, horizon_days=horizon_days)
    except Exception:
        framework = "fallback_statistical"
        used_fallback = True
        pred = _forecast_fallback(history=history, horizon_days=horizon_days, zone=zone)

    forecast_rows: List[Dict[str, Any]] = []
    for _, row in pred.iterrows():
        ds_raw = str(row["ds"])
        try:
            ds_value = datetime.fromisoformat(ds_raw.replace("Z", "+00:00"))
        except ValueError:
            ds_value = datetime.strptime(ds_raw.split(" ")[0], "%Y-%m-%d")
        if ds_value.tzinfo is None:
            ds_value = ds_value.replace(tzinfo=timezone.utc)
        else:
            ds_value = ds_value.astimezone(timezone.utc)
        prob = round(float(row["prob_payout"]), 4)
        expected_loss = round(prob * DEFAULT_COVERAGE_CAP, 2)
        forecast_rows.append(
            {
                "date": ds_value.strftime("%Y-%m-%d"),
                "prob_payout": prob,
                "expected_loss": expected_loss,
                "target_date": ds_value,
            }
        )

    cache_payload = {
        "generated_at": _utc_now().isoformat(),
        "zone": zone,
        "framework": framework,
        "fallback": used_fallback,
        "forecast": [
            {
                "date": item["date"],
                "prob_payout": item["prob_payout"],
                "expected_loss": item["expected_loss"],
            }
            for item in forecast_rows
        ],
    }
    FORECAST_CACHE_PATH.write_text(
        json.dumps(cache_payload, indent=2), encoding="utf-8"
    )

    model_entry = sync_model_artifact(
        model_key="forecast_prophet",
        artifact_path=FORECAST_CACHE_PATH,
        framework=framework,
        metrics={
            "training_points": int(len(history)),
            "horizon_days": int(horizon_days),
            "fallback_mode": used_fallback,
        },
        metadata={"zone": zone},
        bump_version=bump_model_version,
    )

    model_version = model_entry.get("version", _current_forecast_version())
    final_rows: List[Dict[str, Any]] = []
    for item in forecast_rows:
        prediction_id = log_prediction(
            db,
            model_name="forecast_prophet",
            model_version=model_version,
            task_type="payout_probability",
            zone=zone,
            rider_id=None,
            target_date=item["target_date"],
            prediction_value=item["prob_payout"],
            metadata={
                "expected_loss": item["expected_loss"],
                "horizon_days": horizon_days,
            },
            commit=False,
        )
        final_rows.append(
            {
                "date": item["date"],
                "prob_payout": item["prob_payout"],
                "expected_loss": item["expected_loss"],
                "prediction_id": prediction_id,
            }
        )
    db.commit()

    return {
        "zone": zone,
        "forecast": final_rows,
        "model": model_entry["framework"],
        "model_version": model_entry["version"],
        "training_points": int(len(history)),
        "fallback_mode": used_fallback,
    }
