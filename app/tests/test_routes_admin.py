import os
import unittest
from pathlib import Path

_DB_PATH = Path("./protoryde_refactor_admin.db")
if _DB_PATH.exists():
    _DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient

from app.main import app


class TestAdminRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def test_model_status_aliases(self):
        admin_resp = self.client.get("/api/admin/model-status")
        premium_resp = self.client.get("/api/premium/model-status")
        self.assertEqual(admin_resp.status_code, 200)
        self.assertEqual(premium_resp.status_code, 200)
        self.assertIn("fraud_model", admin_resp.json())
        self.assertIn("fraud_model", premium_resp.json())

    def test_admin_metrics_shape(self):
        response = self.client.get("/api/admin/metrics")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("active_policies", body)
        self.assertIn("total_premiums", body)
        self.assertIn("total_claims_paid", body)

    def test_forecast_endpoint(self):
        response = self.client.get("/api/forecast/HSR Layout")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["zone"], "HSR Layout")
        self.assertIn("forecast", body)


if __name__ == "__main__":
    unittest.main()
