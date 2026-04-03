import unittest

from backend.triggers.fraud_engine import FraudEngine
from backend.triggers.premium_service import PremiumService
from backend.triggers.weather_service import WeatherService


class TestPhase2Contracts(unittest.TestCase):
    def test_weather_simulation_shape(self):
        payload = WeatherService.get_current_conditions("HSR Layout", is_simulated=True)
        self.assertIn("conditions", payload)
        self.assertIn("trigger_view", payload)
        self.assertTrue(payload["is_simulated"])
        self.assertIn("rain_24h_mm", payload["conditions"])
        self.assertIn("heavy_rain", payload["trigger_view"])

    def test_fraud_layer_order_and_names(self):
        result = FraudEngine.evaluate_claim(
            zone="HSR Layout",
            trigger_type="HEAVY_RAIN",
            trigger_value=44.0,
            rider_id="rdr_test_001",
            is_simulated=True,
        )
        layer_names = [layer["layer"] for layer in result["fraud_layers"]]
        self.assertEqual(
            layer_names,
            [
                "L1_WEATHER_THRESHOLD",
                "L2_ZONE_PRESENCE",
                "L3_DELHIVERY_CROSS_REF",
                "L4_BRANCH_CLOSURE_CHECK",
            ],
        )
        self.assertTrue(result["fraud_check_passed"])
        self.assertEqual(result["recommended_payout"], 840.0)

    def test_zone_premium_differs(self):
        hsr = PremiumService.predict({"zone": "HSR Layout", "forecast_features": {}, "rider_features": {}})
        whitefield = PremiumService.predict({"zone": "Whitefield", "forecast_features": {}, "rider_features": {}})
        self.assertNotEqual(hsr["final_premium"], whitefield["final_premium"])
        self.assertGreater(hsr["final_premium"], whitefield["final_premium"])


if __name__ == "__main__":
    unittest.main()
