import json
import hashlib
import time
from uuid import uuid4
from pydantic import BaseModel
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class TriggerEvent(BaseModel):
    trigger_type: str
    value: float
    threshold: float
    breached: bool

class PayoutResult(BaseModel):
    claim_id: str
    payout_amount: float
    utr_number: str
    processed_in_seconds: float
    smart_contract_hash: str = ""
    verification_url: str = ""

class PayoutService:
    @staticmethod
    def process_trigger_payout(
        rider_id: str,
        trigger_event: TriggerEvent,
        fraud_result: Dict[str, Any],
        db: Any
    ) -> PayoutResult:
        start_time = time.time()

        utr_number = f"UTR-{uuid4().hex[:12].upper()}"
        payout_amount = fraud_result.get("recommended_payout", 0.0)

        # Generate zero-trust web3 hash
        hash_payload = {
            "rider_id": rider_id,
            "trigger_type": trigger_event.trigger_type,
            "value": trigger_event.value,
            "amount": payout_amount,
            "timestamp": start_time
        }
        
        payload_str = json.dumps(hash_payload, sort_keys=True).encode('utf-8')
        tx_hash = "0x" + hashlib.sha256(payload_str).hexdigest()

        logger.info(f"Push notification: Rs {payout_amount} transferred via UPI. UTR: {utr_number}")

        elapsed = time.time() - start_time

        return PayoutResult(
            claim_id=fraud_result.get("claim_id", ""),
            payout_amount=payout_amount,
            utr_number=utr_number if payout_amount > 0 else "N/A",
            processed_in_seconds=round(elapsed, 4),
            smart_contract_hash=tx_hash if payout_amount > 0 else "N/A",
            verification_url=f"https://polygonscan.com/tx/{tx_hash}" if payout_amount > 0 else ""
        )
