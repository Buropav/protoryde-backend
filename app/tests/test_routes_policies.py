import os
import unittest
from pathlib import Path
from unittest.mock import patch

_DB_PATH = Path("./protoryde_refactor_policies.db")
if _DB_PATH.exists():
    _DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


class TestPolicyRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    @patch("app.services.policy_service.check_enrollment_lockout", return_value=[])
    def test_activate_policy_success(self, _mock_lockout):
        payload = {
            "rider_id": "rdr_policy_route",
            "zone": "HSR Layout",
            "exclusions_accepted": True,
            "prefer_ml": False,
        }
        response = self.client.post("/api/policies/activate", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["rider_id"], payload["rider_id"])
        self.assertIn("policy_id", body)

    def test_activate_policy_exclusions_guard(self):
        payload = {
            "rider_id": "rdr_policy_fail",
            "zone": "HSR Layout",
            "exclusions_accepted": False,
        }
        response = self.client.post("/api/policies/activate", json=payload)
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["detail"]["error"], "EXCLUSIONS_NOT_ACKNOWLEDGED")

    @patch("app.services.policy_service.check_enrollment_lockout", return_value=[])
    def test_policy_document_download(self, _mock_lockout):
        rider_id = "rdr_policy_pdf"
        activate_payload = {
            "rider_id": rider_id,
            "zone": "HSR Layout",
            "exclusions_accepted": True,
            "prefer_ml": False,
        }
        self.client.post("/api/policies/activate", json=activate_payload)

        pdf_response = self.client.get(f"/api/policies/{rider_id}/current/document")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.headers["content-type"], "application/pdf")
        self.assertIn(
            "attachment;", pdf_response.headers.get("content-disposition", "")
        )


if __name__ == "__main__":
    unittest.main()
