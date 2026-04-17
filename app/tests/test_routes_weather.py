import os
import unittest
from pathlib import Path

_DB_PATH = Path("./protoryde_refactor_weather.db")
if _DB_PATH.exists():
    _DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


class TestWeatherRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def test_weather_current_shape(self):
        response = self.client.get("/api/weather/current/HSR Layout")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("conditions", body)
        self.assertIn("trigger_view", body)

    def test_weather_warnings_shape(self):
        response = self.client.get("/api/weather/warnings/HSR Layout")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["zone"], "HSR Layout")
        self.assertIn("warnings", body)

    def test_bank_branches_endpoint(self):
        response = self.client.get("/api/bank/branches/HSR Layout")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("total_branches", body)
        self.assertIn("closure_rate_pct", body)


if __name__ == "__main__":
    unittest.main()
