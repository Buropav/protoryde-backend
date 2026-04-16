from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import numpy as np
from sqlalchemy.orm import Session

from app.core.models import Claim, Rider
from app.services.model_registry import register_model
from app.triggers.fraud_engine import reset_iforest_cache


def _build_features_from_db(db: Session, min_rows: int = 80) -> np.ndarray:
    since = datetime.now(timezone.utc) - timedelta(days=365)
    rows = (
        db.query(
            Rider.avg_daily_earnings,
            Claim.trigger_value,
            Claim.trigger_threshold,
        )
        .join(Claim, Claim.rider_id == Rider.id)
        .filter(Claim.created_at >= since)
        .all()
    )
    if len(rows) < min_rows:
        return np.empty((0, 2), dtype=float)

    features: List[List[float]] = []
    for row in rows:
        avg_earnings = float(row.avg_daily_earnings or 1050.0)
        threshold = float(row.trigger_threshold or 1.0)
        severity_ratio = float(row.trigger_value or 0.0) / max(threshold, 1.0)
        duration_hours = max(1.0, min(16.0, 4.0 + severity_ratio * 5.0))
        features.append([avg_earnings, duration_hours])
    return np.array(features, dtype=float)


def _synthetic_features(seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    normal_data = rng.normal(loc=[1050.0, 9.0], scale=[150.0, 1.5], size=(220, 2))
    outliers = np.array(
        [
            [5000.0, 24.0],
            [200.0, 1.0],
            [0.0, 15.0],
        ],
        dtype=float,
    )
    return np.vstack([normal_data, outliers])


def train_iforest_and_save(
    model_path: str = "app/models/isolation_forest.pkl", db: Session | None = None
) -> str:
    from sklearn.ensemble import IsolationForest

    out_path = Path(model_path)
    if not out_path.is_absolute():
        out_path = Path(__file__).resolve().parent.parent / "models" / out_path.name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if db is not None:
        X_train = _build_features_from_db(db)
        if len(X_train) == 0:
            X_train = _synthetic_features()
            source = "synthetic_fallback"
        else:
            source = "db_claims"
    else:
        X_train = _synthetic_features()
        source = "synthetic_fallback"

    model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    model.fit(X_train)

    import pickle

    with out_path.open("wb") as fh:
        pickle.dump(model, fh)

    register_model(
        model_key="fraud_iforest",
        artifact_path=out_path,
        framework="sklearn_isolation_forest",
        metrics={
            "training_rows": int(len(X_train)),
            "n_estimators": 100,
            "contamination": 0.05,
        },
        metadata={"source": source},
    )
    reset_iforest_cache()
    return str(out_path)
