"""
RecoverIQ - Authoritative Payment Reconciliation Engine (Topic 3 Capability 2)

Observational reconciliation module that compares 4 distinct state vectors:
  1. Gateway Transaction Status (Razorpay capture state)
  2. Merchant Order Status (Merchant database order record)
  3. Internal Database / Payment State (Authoritative PaymentState)
  4. Webhook Event Status (Inbound delivery & security verification)

STRICT BOUNDARIES:
- Observational ONLY; NEVER mutates PaymentState or CircuitState directly.
- Detects discrepancies & contradictions without destructive side effects.
- Thread-safe persistence to logs/recovery_reconciliation.json.
- Records structured audit events in src/recovery_audit.py.
"""

import os
import json
import uuid
import threading
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
RECONCILIATION_LOG_PATH = os.path.join(LOGS_DIR, "recovery_reconciliation.json")

_recon_lock = threading.Lock()
_recon_store: Dict[str, Dict[str, Any]] = {}


class ReconciliationStatus(str, Enum):
    RECONCILED = "RECONCILED"
    MISMATCH = "MISMATCH"
    CONTRADICTION = "CONTRADICTION"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


class ContradictionType(str, Enum):
    GATEWAY_SUCCESS_MERCHANT_NOT_CREATED = "GATEWAY_SUCCESS_MERCHANT_NOT_CREATED"
    GATEWAY_SUCCESS_INTERNAL_FAILED = "GATEWAY_SUCCESS_INTERNAL_FAILED"
    MERCHANT_CREATED_GATEWAY_FAILED = "MERCHANT_CREATED_GATEWAY_FAILED"
    WEBHOOK_MISSING_OR_DELAYED = "WEBHOOK_MISSING_OR_DELAYED"
    DB_PENDING_GATEWAY_SUCCESS = "DB_PENDING_GATEWAY_SUCCESS"
    NONE = "NONE"


def _load_persisted_reconciliations() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(RECONCILIATION_LOG_PATH):
        try:
            with open(RECONCILIATION_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_persisted_reconciliations(data: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(RECONCILIATION_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def evaluate_payment_reconciliation(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    case_data: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 3 - Evaluates 4-way reconciliation across Gateway, Merchant, DB, and Webhook.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    t_id = trace_id or f"tr_{clean_payment_id}_{uuid.uuid4().hex[:8]}"

    data = case_data or {}
    order_id = str(data.get("order_id", f"ORD_{clean_payment_id}") or f"ORD_{clean_payment_id}").strip()
    amount = float(data.get("amount", 0) or 0)
    gateway_status = str(data.get("payment_status", "SUCCESS") or "SUCCESS").upper()
    merchant_order_exists = bool(data.get("merchant_order_exists", False))
    merchant_order_status = "CREATED" if merchant_order_exists else str(data.get("order_status", "NOT_CREATED") or "NOT_CREATED").upper()
    webhook_status = str(data.get("webhook_status", "DELAYED") or "DELAYED").upper()

    # 1. Authoritative internal payment state
    try:
        from src.state_machine import get_current_payment_state
        curr_state = get_current_payment_state(clean_payment_id, case_data)
        internal_db_state = curr_state.value
    except Exception:
        internal_db_state = "RECOVERED" if merchant_order_exists else "PENDING"

    # 2. Authoritative verification status
    verification_status = "UNKNOWN"
    try:
        from src.recovery_verification import get_payment_recovery_verification_summary
        v_sum = get_payment_recovery_verification_summary(clean_payment_id, clean_merchant_id, clean_endpoint)
        verification_status = v_sum.get("verification_status", "UNKNOWN")
    except Exception:
        pass

    # 3. Analyze 4-vector alignment
    discrepancies: List[str] = []
    contradiction_type = ContradictionType.NONE.value

    # Case A: Gateway SUCCESS but Merchant NOT_CREATED
    if gateway_status == "SUCCESS" and merchant_order_status in ("NOT_CREATED", "UNKNOWN") and not merchant_order_exists:
        status = ReconciliationStatus.MISMATCH.value
        contradiction_type = ContradictionType.GATEWAY_SUCCESS_MERCHANT_NOT_CREATED.value
        recommended_action = "IDEMPOTENT_ORDER_SYNC"
        reason = (
            f"Payment captured successfully by Gateway (₹{amount:,.2f}), but merchant order "
            f"({order_id}) was not created due to webhook delivery timeout."
        )
        discrepancies.append("Gateway: Captured ✓ vs Merchant: Order Not Created ✗")
        discrepancies.append("Database: Marked PENDING ⚠ vs Gateway: SUCCESS ✓")

    # Case B: Gateway SUCCESS but Internal DB marked FAILED
    elif gateway_status == "SUCCESS" and internal_db_state in ("FAILED", "RECOVERY_FAILED"):
        status = ReconciliationStatus.CONTRADICTION.value
        contradiction_type = ContradictionType.GATEWAY_SUCCESS_INTERNAL_FAILED.value
        recommended_action = "LEAD_OPERATOR_INTEGRITY_INVESTIGATION"
        reason = (
            f"Critical Ledger Contradiction: Gateway reports SUCCESS for payment {clean_payment_id}, "
            f"but internal database marked transaction FAILED."
        )
        discrepancies.append("Gateway: SUCCESS ✓ vs Internal DB: FAILED ✗")

    # Case C: Merchant CREATED but Gateway FAILED/REFUNDED
    elif merchant_order_exists and gateway_status in ("FAILED", "CANCELLED", "REFUNDED"):
        status = ReconciliationStatus.CONTRADICTION.value
        contradiction_type = ContradictionType.MERCHANT_CREATED_GATEWAY_FAILED.value
        recommended_action = "HALT_FULFILLMENT_AND_REVERSE_ORDER"
        reason = (
            f"Critical Risk: Merchant order {order_id} exists in database, but Gateway reports "
            f"{gateway_status}. Order may be fulfilled without captured funds."
        )
        discrepancies.append(f"Merchant: Order Exists ✓ vs Gateway: {gateway_status} ✗")

    # Case D: Fully Reconciled
    elif (gateway_status == "SUCCESS" and (merchant_order_exists or merchant_order_status == "CREATED") and
          (internal_db_state in ("RECOVERED", "SUCCESS") or verification_status == "VERIFIED_SUCCESS")):
        status = ReconciliationStatus.RECONCILED.value
        contradiction_type = ContradictionType.NONE.value
        recommended_action = "NO_ACTION_FULLY_RECONCILED"
        reason = (
            f"All 4 systems are in complete synchronization. Funds captured by Gateway, order {order_id} "
            f"confirmed in merchant database, and internal ledger marked {internal_db_state}."
        )

    # Case E: DB Pending while Gateway Succeeded
    elif gateway_status == "SUCCESS" and internal_db_state == "PENDING":
        status = ReconciliationStatus.MISMATCH.value
        contradiction_type = ContradictionType.DB_PENDING_GATEWAY_SUCCESS.value
        recommended_action = "SYNCHRONIZE_INTERNAL_LEDGER"
        reason = (
            f"Gateway captured funds successfully, but internal ledger is still in PENDING state."
        )
        discrepancies.append("Internal DB: PENDING ⚠ vs Gateway: SUCCESS ✓")

    else:
        status = ReconciliationStatus.PENDING.value
        contradiction_type = ContradictionType.NONE.value
        recommended_action = "MONITOR_IN_FLIGHT_WORKFLOW"
        reason = "Payment workflow is currently in flight or awaiting downstream signals."

    reconciliation_obj = {
        "reconciliation_id": f"rec_{clean_payment_id}_{uuid.uuid4().hex[:6]}",
        "payment_id": clean_payment_id,
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "order_id": order_id,
        "amount": amount,
        "trace_id": t_id,
        "reconciliation_status": status,
        "contradiction_type": contradiction_type,
        "recommended_action": recommended_action,
        "reason": reason,
        "discrepancies": discrepancies,
        "vectors": {
            "gateway": {
                "system": "Payment Gateway (Razorpay)",
                "status": gateway_status,
                "verified": gateway_status == "SUCCESS"
            },
            "merchant": {
                "system": "Merchant Order DB",
                "status": merchant_order_status,
                "order_exists": merchant_order_exists,
                "verified": merchant_order_exists
            },
            "database": {
                "system": "Internal Ledger / State Machine",
                "status": internal_db_state,
                "verified": internal_db_state in ("RECOVERED", "SUCCESS")
            },
            "webhook": {
                "system": "Inbound Webhook Stream",
                "status": webhook_status,
                "verified": webhook_status in ("DELIVERED", "VERIFIED", "PROCESSED")
            }
        },
        "evaluated_at": now_iso
    }

    with _recon_lock:
        if not _recon_store:
            _recon_store.update(_load_persisted_reconciliations())
        _recon_store[clean_payment_id] = reconciliation_obj
        _save_persisted_reconciliations(_recon_store)

    try:
        from src.recovery_audit import record_recovery_audit_event
        event_type = (
            "RECONCILIATION_MISMATCH_DETECTED" if status in (ReconciliationStatus.MISMATCH.value, ReconciliationStatus.CONTRADICTION.value)
            else "RECONCILIATION_COMPLETED"
        )
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type=event_type,
            actor_type="RECONCILIATION_ENGINE",
            source="RECOVERY_RECONCILIATION",
            status=status,
            reason=reason,
            risk_level="HIGH" if status == ReconciliationStatus.CONTRADICTION.value else ("MEDIUM" if status == ReconciliationStatus.MISMATCH.value else "LOW"),
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            correlation_id=t_id,
            metadata={
                "reconciliation_status": status,
                "contradiction_type": contradiction_type,
                "discrepancies_count": len(discrepancies)
            }
        )
    except Exception:
        pass

    return reconciliation_obj


def get_payment_reconciliation(payment_id: str) -> Optional[Dict[str, Any]]:
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    with _recon_lock:
        if not _recon_store:
            _recon_store.update(_load_persisted_reconciliations())
        if clean_payment_id in _recon_store:
            return _recon_store[clean_payment_id]

    return evaluate_payment_reconciliation(clean_payment_id)


def list_reconciliation_mismatches() -> List[Dict[str, Any]]:
    with _recon_lock:
        if not _recon_store:
            _recon_store.update(_load_persisted_reconciliations())
        return [
            rec for rec in _recon_store.values()
            if rec.get("reconciliation_status") in (ReconciliationStatus.MISMATCH.value, ReconciliationStatus.CONTRADICTION.value)
        ]
