"""
RecoverIQ - Safe Read-Only Agent Tools
Provides inspection tools for the AI Agent to investigate payment incidents,
telemetry signals, merchant database state, and retry history.

SAFETY RULE:
All tools in this module are strictly READ-ONLY.
They NEVER modify data files or alter merchant state.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

# Resolve Paths relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

TELEMETRY_BATCH_PATH = DATA_DIR / "telemetry_batch.json"
MERCHANT_STATE_PATH = DATA_DIR / "merchant_state.json"
BATCH_RECOVERY_LOG_PATH = LOGS_DIR / "batch_recovery_log.json"


def _safe_load_json(file_path: Path) -> Optional[Any]:
    """Safely loads and parses a JSON file with error handling."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_payment_details(payment_id: str) -> Dict[str, Any]:
    """
    Retrieves core payment details for a specific payment ID from telemetry.
    Returns payment_id, order_id, amount, and payment_status.
    """
    if not payment_id or not isinstance(payment_id, str):
        return {"found": False, "error": "Invalid or empty payment_id"}

    batch = _safe_load_json(TELEMETRY_BATCH_PATH)
    if batch is None:
        return {"found": False, "error": f"Telemetry data file not accessible at {TELEMETRY_BATCH_PATH}"}

    for record in batch:
        if record.get("payment_id") == payment_id:
            return {
                "found": True,
                "payment_id": record.get("payment_id"),
                "order_id": record.get("order_id"),
                "amount": record.get("amount"),
                "payment_status": record.get("payment_status")
            }

    return {"found": False, "payment_id": payment_id, "error": f"Payment {payment_id} not found in telemetry batch"}


def get_telemetry(payment_id: str) -> Dict[str, Any]:
    """
    Retrieves comprehensive workflow telemetry for a payment incident.
    Returns HTTP status, webhook status, order status, inventory status, and retry count.
    """
    if not payment_id or not isinstance(payment_id, str):
        return {"found": False, "error": "Invalid or empty payment_id"}

    batch = _safe_load_json(TELEMETRY_BATCH_PATH)
    if batch is None:
        return {"found": False, "error": f"Telemetry data file not accessible at {TELEMETRY_BATCH_PATH}"}

    for record in batch:
        if record.get("payment_id") == payment_id:
            return {
                "found": True,
                "payment_id": record.get("payment_id"),
                "order_id": record.get("order_id"),
                "amount": record.get("amount"),
                "payment_status": record.get("payment_status"),
                "webhook_status": record.get("webhook_status"),
                "order_status": record.get("order_status"),
                "inventory_status": record.get("inventory_status"),
                "http_status": record.get("http_status"),
                "retry_count": record.get("retry_count")
            }

    return {"found": False, "payment_id": payment_id, "error": f"Telemetry for {payment_id} not found"}


def get_merchant_state(payment_id: str) -> Dict[str, Any]:
    """
    Retrieves current merchant database record for a payment ID.
    Returns whether the order already exists in the merchant's system.
    """
    if not payment_id or not isinstance(payment_id, str):
        return {"found": False, "error": "Invalid or empty payment_id"}

    merchant_state = _safe_load_json(MERCHANT_STATE_PATH)
    if merchant_state is None:
        return {"found": False, "error": f"Merchant state file not accessible at {MERCHANT_STATE_PATH}"}

    for state in merchant_state:
        if state.get("payment_id") == payment_id:
            return {
                "found": True,
                "payment_id": payment_id,
                "order_exists": bool(state.get("order_exists", False)),
                "raw_state": state
            }

    return {
        "found": False,
        "payment_id": payment_id,
        "order_exists": False,
        "note": "Payment record absent from merchant state table"
    }


def get_retry_history(payment_id: str) -> Dict[str, Any]:
    """
    Retrieves retry history and previous recovery audit logs for a payment ID.
    """
    if not payment_id or not isinstance(payment_id, str):
        return {"found": False, "error": "Invalid or empty payment_id"}

    # Get retry count from telemetry
    telemetry = get_telemetry(payment_id)
    retry_count = telemetry.get("retry_count", 0) if telemetry.get("found") else 0
    http_status = telemetry.get("http_status", 0) if telemetry.get("found") else None

    # Get recovery audit logs if available
    audit_logs = _safe_load_json(BATCH_RECOVERY_LOG_PATH) or []
    audit_entry = next((entry for entry in audit_logs if entry.get("payment_id") == payment_id), None)

    return {
        "found": telemetry.get("found", False),
        "payment_id": payment_id,
        "retry_count": retry_count,
        "max_allowed_retries": 2,
        "retry_buffer_available": max(0, 2 - retry_count),
        "http_status": http_status,
        "has_previous_audit_log": audit_entry is not None,
        "previous_audit_entry": audit_entry
    }


def check_order_exists(payment_id: str) -> Dict[str, Any]:
    """
    Specific boolean check tool for the AI agent to confirm if an order
    already exists in the merchant database before proposing recovery.
    """
    state = get_merchant_state(payment_id)
    if not state.get("found"):
        return {
            "payment_id": payment_id,
            "order_exists": False,
            "can_proceed_with_recovery": True,
            "reason": "Order record absent from merchant database"
        }

    order_exists = state.get("order_exists", False)
    return {
        "payment_id": payment_id,
        "order_exists": order_exists,
        "can_proceed_with_recovery": not order_exists,
        "reason": "Order already exists in merchant database (duplicate risk)" if order_exists else "Order does not exist in merchant database (safe to sync)"
    }
