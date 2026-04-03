from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.triggers.weather_service import WeatherService
from backend.triggers.fraud_engine import FraudEngine
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
                res = FraudEngine.evaluate_claim(
                    zone=zone,
                    trigger_type="HEAVY_RAIN",
                    trigger_value=rain_value,
                    rider_id=f"rdr_auto_{zone[:3].lower()}",
                    is_simulated=False,
                    latitude=None,
                    longitude=None,
                )
                logger.info(f"Auto Claim Result: {res}")
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
