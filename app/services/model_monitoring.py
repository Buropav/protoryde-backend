import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.models import MLPredictionLog

logger = logging.getLogger(__name__)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def log_prediction(
    db: Session,
    *,
    model_name: str,
    model_version: str,
    task_type: str,
    zone: str,
    rider_id: Optional[str],
    target_date: Optional[datetime],
    prediction_value: float,
    metadata: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> int:
    try:
        row = MLPredictionLog(
            model_name=model_name,
            model_version=model_version,
            task_type=task_type,
            zone=zone,
            rider_id=rider_id,
            target_date=target_date,
            prediction_value=float(prediction_value),
            metadata_json=metadata or {},
        )
        db.add(row)
        if commit:
            db.commit()
            db.refresh(row)
        else:
            db.flush()
        return _to_int(row.id, -1)
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to log ML prediction: %s", exc)
        return -1


def resolve_prediction_actual(
    db: Session,
    *,
    prediction_id: int,
    actual_value: float,
    metadata_patch: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> MLPredictionLog:
    row = db.query(MLPredictionLog).filter(MLPredictionLog.id == prediction_id).first()
    if row is None:
        raise ValueError("PREDICTION_LOG_NOT_FOUND")
    setattr(row, "actual_value", float(actual_value))
    predicted = _to_float(getattr(row, "prediction_value", 0.0), 0.0)
    setattr(row, "absolute_error", abs(predicted - float(actual_value)))
    setattr(row, "resolved_at", datetime.now(timezone.utc))
    if metadata_patch:
        current = getattr(row, "metadata_json", {}) or {}
        current.update(metadata_patch)
        setattr(row, "metadata_json", current)
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def compute_model_health(
    db: Session,
    *,
    model_name: Optional[str] = None,
    zone: Optional[str] = None,
    lookback_limit: int = 200,
) -> Dict[str, Any]:
    try:
        query = db.query(MLPredictionLog)
        if model_name:
            query = query.filter(MLPredictionLog.model_name == model_name)
        if zone:
            query = query.filter(MLPredictionLog.zone == zone)
        rows: List[MLPredictionLog] = (
            query.order_by(MLPredictionLog.created_at.desc())
            .limit(lookback_limit)
            .all()
        )
    except Exception as exc:
        db.rollback()
        logger.warning("Model health unavailable: %s", exc)
        return {
            "rows_considered": 0,
            "resolved_points": 0,
            "pending_actuals": 0,
            "mae": None,
            "mape": None,
            "drift_flag": False,
            "drift_reason": None,
            "error": str(exc),
        }

    resolved = [
        r
        for r in rows
        if getattr(r, "actual_value", None) is not None
        and getattr(r, "absolute_error", None) is not None
    ]
    unresolved = [r for r in rows if getattr(r, "actual_value", None) is None]
    mae = (
        round(
            sum(_to_float(getattr(r, "absolute_error", 0.0), 0.0) for r in resolved)
            / len(resolved),
            4,
        )
        if resolved
        else None
    )
    mape = (
        round(
            sum(
                abs(
                    _to_float(getattr(r, "actual_value", 0.0), 0.0)
                    - _to_float(getattr(r, "prediction_value", 0.0), 0.0)
                )
                / max(abs(_to_float(getattr(r, "actual_value", 0.0), 0.0)), 1e-6)
                for r in resolved
            )
            / len(resolved),
            4,
        )
        if resolved
        else None
    )

    drift_flag = bool(mape is not None and mape > 0.35)

    return {
        "rows_considered": len(rows),
        "resolved_points": len(resolved),
        "pending_actuals": len(unresolved),
        "mae": mae,
        "mape": mape,
        "drift_flag": drift_flag,
        "drift_reason": "MAPE above 35% threshold" if drift_flag else None,
    }
