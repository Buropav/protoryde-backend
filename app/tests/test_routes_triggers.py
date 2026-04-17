import os
import unittest
from pathlib import Path
from unittest.mock import patch

_DB_PATH = Path("./protoryde_refactor_triggers.db")
if _DB_PATH.exists():
    _DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


class TestTriggerRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    @patch("app.services.policy_service.check_enrollment_lockout", return_value=[])
    def test_simulate_trigger_contract_shape(self, _mock_lockout):
        rider_id = "rdr_triggers_route"
        activate_payload = {
            "rider_id": rider_id,
            "zone": "HSR Layout",
            "exclusions_accepted": True,
            "prefer_ml": False,
        }
        self.client.post("/api/policies/activate", json=activate_payload)

        payload = {
            "zone": "HSR Layout",
            "trigger_type": "HEAVY_RAIN",
            "rider_id": rider_id,
        }
        response = self.client.post("/api/triggers/simulate", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("simulation_id", body)
        self.assertIn("trigger_event", body)
        self.assertGreaterEqual(len(body["claims_preview"]), 1)
        layers = body["claims_preview"][0]["fraud_layers"]
        self.assertEqual(
            [item["layer"] for item in layers],
            [
                "L1_WEATHER_THRESHOLD",
                "L2_ZONE_PRESENCE",
                "L3_DELHIVERY_CROSS_REF",
                "L4_BRANCH_CLOSURE_CHECK",
            ],
        )


if __name__ == "__main__":
    unittest.main()
