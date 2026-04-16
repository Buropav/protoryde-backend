from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import logging
import os

from app.core.database import SessionLocal
from app.core.models import AuditLog, Claim
from app.services.forecast_service import generate_zone_forecast
from app.services.fraud_model_training import train_iforest_and_save
from app.services.train_model import train_and_save_model
from app.triggers.fraud_engine import FraudEngine
from app.triggers.weather_service import WeatherService

logger = logging.getLogger(__name__)

ACTIVE_ZONES = ["HSR Layout", "Whitefield", "Bellandur"]


def poll_weather_and_auto_trigger():
    logger.info("Polling Weather API for active policies...")
    for zone in ACTIVE_ZONES:
        try:
            cond = WeatherService.get_current_conditions(zone, is_simulated=False)
            rain_value = cond["conditions"]["rain_24h_mm"]
            if rain_value >= 30.0:
                logger.info(f"Threshold breached in {zone}. Auto-creating claim.")
                rider_id = f"rdr_auto_{zone[:3].lower()}"
                res = FraudEngine.evaluate_claim(
                    zone=zone,
                    trigger_type="HEAVY_RAIN",
                    trigger_value=rain_value,
                    rider_id=rider_id,
                    is_simulated=False,
                    latitude=None,
                    longitude=None,
                )
                db = SessionLocal()
                try:
                    now = datetime.now(timezone.utc)
                    claim = Claim(
                        id=res["claim_id"],
                        policy_id=None,
                        rider_id=rider_id,
                        zone=zone,
                        trigger_type="HEAVY_RAIN",
                        trigger_value=rain_value,
                        trigger_threshold=float(res["trigger_event"]["threshold"]),
                        is_simulated=False,
                        fraud_check_passed=res["fraud_check_passed"],
                        fraud_layers=res["fraud_layers"],
                        payout_amount=float(res["recommended_payout"]),
                        payout_status="PAID"
                        if res["recommended_payout"] > 0
                        else "rejected",
                        payout_initiated_at=now
                        if res["recommended_payout"] > 0
                        else None,
                        delhivery_cancellation_rate=0.0,
                    )
                    db.add(claim)
                    db.add(
                        AuditLog(
                            entity_type="AutoTrigger",
                            entity_id=res["claim_id"],
                            action="AUTO_TRIGGER_CLAIM_CREATED",
                            metadata_json={"zone": zone, "trigger_value": rain_value},
                        )
                    )
                    db.commit()
                    logger.info(f"Auto Claim persisted: {res['claim_id']}")
                except Exception as db_exc:
                    db.rollback()
                    logger.error(f"Failed to persist auto claim for {zone}: {db_exc}")
                finally:
                    db.close()
            else:
                logger.debug(f"{zone} conditions normal.")
        except Exception as e:
            logger.error(f"Failed to poll {zone}: {e}")


def retrain_ml_models_job():
    db = SessionLocal()
    try:
        premium_path = train_and_save_model(db=db)
        fraud_path = train_iforest_and_save(db=db)
        zone_snapshots = []
        for zone in ACTIVE_ZONES:
            snapshot = generate_zone_forecast(
                zone=zone,
                db=db,
                horizon_days=7,
                bump_model_version=(zone == ACTIVE_ZONES[0]),
            )
            zone_snapshots.append(
                {
                    "zone": zone,
                    "model_version": snapshot.get("model_version"),
                    "fallback_mode": snapshot.get("fallback_mode"),
                }
            )

        db.add(
            AuditLog(
                entity_type="ML",
                entity_id="scheduled_retrain",
                action="ML_RETRAIN_COMPLETED",
                metadata_json={
                    "premium_model_path": premium_path,
                    "fraud_model_path": fraud_path,
                    "zones": zone_snapshots,
                },
            )
        )
        db.commit()
        logger.info("Scheduled ML retraining completed.")
    except Exception as exc:
        db.rollback()
        logger.error("Scheduled ML retraining failed: %s", exc)
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        poll_weather_and_auto_trigger,
        trigger=IntervalTrigger(minutes=5),
        id="weather_polling_job",
        name="Poll Open-Meteo every 5 minutes",
        replace_existing=True,
    )

    if os.getenv("ENABLE_ML_RETRAIN", "false").lower() == "true":
        retrain_interval_hours = int(os.getenv("ML_RETRAIN_INTERVAL_HOURS", "24"))
        scheduler.add_job(
            retrain_ml_models_job,
            trigger=IntervalTrigger(hours=retrain_interval_hours),
            id="ml_retrain_job",
            name=f"Retrain ML models every {retrain_interval_hours}h",
            replace_existing=True,
        )

    scheduler.start()
    logger.info("Background Weather Polling Scheduler Started.")
    return scheduler
