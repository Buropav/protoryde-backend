import os
from typing import Any, Dict, Optional

import requests


class RazorpayConfigError(RuntimeError):
    pass


class RazorpayAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


BASE_URL = "https://api.razorpay.com/v1"


def _credentials() -> tuple[str, str]:
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise RazorpayConfigError("Razorpay API keys are not configured")
    return key_id, key_secret


def _request(
    method: str, path: str, payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    key_id, key_secret = _credentials()
    url = f"{BASE_URL}{path}"
    response = requests.request(
        method=method,
        url=url,
        auth=(key_id, key_secret),
        json=payload,
        timeout=12,
    )
    if response.status_code >= 400:
        try:
            body = response.json()
            message = (
                body.get("error", {}).get("description")
                or body.get("error", {}).get("reason")
                or response.text
            )
        except Exception:
            message = response.text
        raise RazorpayAPIError(f"Razorpay API error: {message}", response.status_code)
    return response.json()


def create_payment_link(
    amount_inr: float,
    rider_id: str,
    policy_id: str,
    upi_id: str,
) -> Dict[str, Any]:
    amount_paise = int(round(float(amount_inr) * 100))
    callback_url = os.getenv("RAZORPAY_CALLBACK_URL")
    payload: Dict[str, Any] = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": f"ProtoRyde premium for policy {policy_id}",
        "reference_id": f"prem_{policy_id}_{rider_id}"[:40],
        "notify": {"sms": False, "email": False},
        "reminder_enable": True,
        "notes": {
            "rider_id": rider_id,
            "policy_id": policy_id,
            "upi_id": upi_id,
        },
    }
    if callback_url:
        payload["callback_url"] = callback_url
        payload["callback_method"] = "get"
    return _request("POST", "/payment_links", payload)


def create_upi_payout(
    amount_inr: float,
    rider_id: str,
    rider_name: str,
    upi_id: str,
    claim_id: str,
) -> Dict[str, Any]:
    account_number = os.getenv("RAZORPAYX_ACCOUNT_NUMBER")
    if not account_number:
        raise RazorpayConfigError("RAZORPAYX_ACCOUNT_NUMBER is not configured")

    contact = _request(
        "POST",
        "/contacts",
        {
            "name": rider_name[:100],
            "type": "employee",
            "reference_id": f"rider_{rider_id}"[:40],
            "notes": {"rider_id": rider_id},
        },
    )

    fund_account = _request(
        "POST",
        "/fund_accounts",
        {
            "contact_id": contact["id"],
            "account_type": "vpa",
            "vpa": {"address": upi_id},
        },
    )

    amount_paise = int(round(float(amount_inr) * 100))
    payout = _request(
        "POST",
        "/payouts",
        {
            "account_number": account_number,
            "fund_account_id": fund_account["id"],
            "amount": amount_paise,
            "currency": "INR",
            "mode": "UPI",
            "purpose": "payout",
            "queue_if_low_balance": True,
            "reference_id": f"claim_{claim_id}"[:40],
            "narration": "ProtoRyde claim payout",
            "notes": {
                "claim_id": claim_id,
                "rider_id": rider_id,
            },
        },
    )
    return payout
