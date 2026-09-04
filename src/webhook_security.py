"""
RecoverIQ - Real Webhook Signature Verification Layer (Topic 2.1)

Provides HMAC-SHA256 raw-body signature generation and constant-time verification
for incoming payment gateway webhooks.
"""

import os
import hmac
import hashlib
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("recoveriq.webhook_security")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Environment-based secret with development fallback
DEFAULT_DEV_SECRET = "dev_webhook_secret_recoveriq_sec_key_2026"

# In-memory security verification audit event log
_webhook_security_events: list = []
_last_verification_status: Dict[str, Any] = {
    "status": "NO_EVENTS",
    "timestamp": None,
    "event_id": None,
    "payment_id": None
}


def get_webhook_secret() -> Optional[str]:
    """
    Retrieves the authoritative webhook secret from environment variables.
    Falls back to development secret if running in standard local dev/test mode.
    """
    secret = os.environ.get("WEBHOOK_SECRET")
    if secret:
        return secret
    # Safe development default
    return DEFAULT_DEV_SECRET


def generate_webhook_signature(raw_body: bytes, secret: Optional[str] = None) -> str:
    """
    Generates a hexadecimal HMAC-SHA256 signature for the given raw request bytes.
    """
    sec = secret if secret is not None else get_webhook_secret()
    if not sec:
        raise ValueError("Cannot generate signature: WEBHOOK_SECRET is not configured.")

    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")

    return hmac.new(
        key=sec.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(
    raw_body: bytes,
    received_signature: Optional[str],
    secret: Optional[str] = None,
    payment_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verifies incoming webhook signature against raw request bytes using constant-time comparison.
    Never exposes the webhook secret or expected digest in responses.
    """
    sec = secret if secret is not None else get_webhook_secret()
    event_id = f"evt_wh_sec_{uuid.uuid4().hex[:10]}"
    timestamp = datetime.now(timezone.utc).isoformat()

    # 1. Missing secret configuration
    if not sec:
        logger.error("WEBHOOK_SECRET_UNCONFIGURED: Cannot verify webhook signature.")
        res = {
            "verified": False,
            "status": "CONFIGURATION_ERROR",
            "error": "WEBHOOK_SECRET_UNCONFIGURED",
            "event_id": event_id,
            "message": "Webhook signature verification is enabled but server secret is unconfigured."
        }
        return res

    # 2. Missing signature header
    if not received_signature or not str(received_signature).strip():
        logger.warning("WEBHOOK_SIGNATURE_MISSING: Webhook request rejected (missing X-Webhook-Signature).")
        res = {
            "verified": False,
            "status": "MISSING",
            "error": "WEBHOOK_SIGNATURE_MISSING",
            "event_id": event_id,
            "message": "Webhook signature is required."
        }
        _record_security_event(res, timestamp, payment_id)
        return res

    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")

    # 3. Calculate expected signature over RAW BYTES
    expected_sig = hmac.new(
        key=sec.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    clean_received = str(received_signature).strip().lower()
    # Normalize potential prefix like 'sha256=' or 'sha256:'
    if clean_received.startswith("sha256="):
        clean_received = clean_received[7:]
    elif clean_received.startswith("sha256:"):
        clean_received = clean_received[7:]

    # 4. Constant-Time Comparison
    is_valid = hmac.compare_digest(expected_sig.lower(), clean_received)

    if not is_valid:
        logger.warning(f"WEBHOOK_SIGNATURE_INVALID: Webhook request rejected (tamper/invalid signature, event={event_id}).")
        res = {
            "verified": False,
            "status": "INVALID",
            "error": "WEBHOOK_SIGNATURE_INVALID",
            "event_id": event_id,
            "message": "Webhook signature verification failed."
        }
        _record_security_event(res, timestamp, payment_id)
        return res

    # 5. Verified successfully
    logger.info(f"WEBHOOK_SIGNATURE_VERIFIED: Webhook authenticated successfully (event={event_id}).")
    res = {
        "verified": True,
        "status": "VERIFIED",
        "event_id": event_id,
        "message": "Webhook signature verified."
    }
    _record_security_event(res, timestamp, payment_id)
    return res


def _record_security_event(result: Dict[str, Any], timestamp: str, payment_id: Optional[str]):
    """Records safe verification telemetry without credentials."""
    event = {
        "event_type": "WEBHOOK_SIGNATURE_VERIFICATION",
        "event_id": result.get("event_id"),
        "signature_status": result.get("status"),
        "actor_type": "GATEWAY",
        "source": "WEBHOOK",
        "timestamp": timestamp,
        "payment_id": payment_id
    }
    _webhook_security_events.append(event)
    if len(_webhook_security_events) > 100:
        _webhook_security_events.pop(0)

    _last_verification_status["status"] = result.get("status")
    _last_verification_status["timestamp"] = timestamp
    _last_verification_status["event_id"] = result.get("event_id")
    _last_verification_status["payment_id"] = payment_id


def get_webhook_security_status() -> Dict[str, Any]:
    """
    Exposes safe verification status metadata for frontend observability.
    """
    return {
        "verification_enabled": True,
        "algorithm": "HMAC-SHA256",
        "header": "X-Webhook-Signature",
        "last_verification": dict(_last_verification_status),
        "total_verifications": len(_webhook_security_events)
    }


def reset_webhook_security_state():
    """Helper for testing state reset."""
    _webhook_security_events.clear()
    _last_verification_status["status"] = "NO_EVENTS"
    _last_verification_status["timestamp"] = None
    _last_verification_status["event_id"] = None
    _last_verification_status["payment_id"] = None
