import os
import unittest
from pathlib import Path

# Ensure database path is local to this repository for test runs.
os.environ.setdefault("DATABASE_URL", "sqlite:///./protoryde.db")

from fastapi.testclient import TestClient

from app.main import app


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def test_policy_activate_success(self):
        payload = {
            "rider_id": "rdr_api_bootstrap",
            "zone": "HSR Layout",
            "exclusions_accepted": True,
        }
        response = self.client.post("/api/policies/activate", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["rider_id"], payload["rider_id"])
        self.assertIn("policy_id", body)

    def test_policy_activate_exclusions_guard(self):
        payload = {
            "rider_id": "rdr_api_bootstrap_fail",
            "zone": "HSR Layout",
            "exclusions_accepted": False,
        }
        response = self.client.post("/api/policies/activate", json=payload)
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["detail"]["error"], "EXCLUSIONS_NOT_ACKNOWLEDGED")

    def test_simulate_returns_contract_shape(self):
        rider_id = "rdr_api_simulate"
        activate = {
            "rider_id": rider_id,
            "zone": "HSR Layout",
            "exclusions_accepted": True,
        }
        self.client.post("/api/policies/activate", json=activate)

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

    def test_policy_pdf_download_headers(self):
        rider_id = "rdr_api_pdf"
        activate = {
            "rider_id": rider_id,
            "zone": "HSR Layout",
            "exclusions_accepted": True,
        }
        response = self.client.post("/api/policies/activate", json=activate)
        self.assertEqual(response.status_code, 200)

        pdf_response = self.client.get(f"/api/policies/{rider_id}/current/document")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.headers["content-type"], "application/pdf")
        self.assertIn(
            "attachment;", pdf_response.headers.get("content-disposition", "")
        )
        self.assertTrue(len(pdf_response.content) > 100)


if __name__ == "__main__":
    unittest.main()
