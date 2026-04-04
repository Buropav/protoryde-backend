from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.triggers.weather_service import WeatherService
from app.triggers.fraud_engine import FraudEngine
from app.core.database import SessionLocal
from app.core.models import AuditLog, Claim
from datetime import datetime, timezone
import logging

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
                        payout_status="credited" if res["recommended_payout"] > 0 else "rejected",
                        payout_initiated_at=now if res["recommended_payout"] > 0 else None,
                        delhivery_cancellation_rate=0.0,
                    )
                    db.add(claim)
                    db.add(AuditLog(
                        entity_type="AutoTrigger",
                        entity_id=res["claim_id"],
                        action="AUTO_TRIGGER_CLAIM_CREATED",
                        metadata_json={"zone": zone, "trigger_value": rain_value},
                    ))
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

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        poll_weather_and_auto_trigger,
        trigger=IntervalTrigger(minutes=5),
        id='weather_polling_job',
        name='Poll Open-Meteo every 5 minutes',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Background Weather Polling Scheduler Started.")
    return scheduler
