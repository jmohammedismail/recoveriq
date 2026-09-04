"""
RecoverIQ - Bounded Automatic Recovery Retry & Verification Re-Evaluation Manager (Topic 2.2.2.15)

Coordinates bounded recovery retries when post-recovery verification returns
VERIFICATION_PENDING or VERIFICATION_FAILED.

STRICT BOUNDARIES:
- Enforces strict maximum 3 attempts (never retries infinitely).
- Re-evaluates Recovery Decision Engine before every retry attempt.
- Gated by check_circuit_request_allowed() before any outbound request.
- NEVER mutates PaymentState or CircuitState directly.
- Emits telemetry to src/recovery_audit.py and logs/recovery_retry_state.json.
"""

import os
import json
import uuid
import time
import threading
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
RETRY_STATE_LOG_PATH = os.path.join(LOGS_DIR, "recovery_retry_state.json")

DEFAULT_MAX_RECOVERY_ATTEMPTS = 3
DEFAULT_BASE_BACKOFF_SEC = 2.0
DEFAULT_MAX_BACKOFF_SEC = 30.0

_retry_lock = threading.Lock()
_payment_retry_tracker: Dict[str, Dict[str, Any]] = {}


class RetryStatus(str, Enum):
    """Authoritative retry lifecycle status."""
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_CIRCUIT = "WAITING_FOR_CIRCUIT"
    WAITING_FOR_MERCHANT = "WAITING_FOR_MERCHANT"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    COMPLETED = "COMPLETED"
    EXHAUSTED = "EXHAUSTED"
    BLOCKED = "BLOCKED"


def _load_persisted_retry_state() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(RETRY_STATE_LOG_PATH):
        try:
            with open(RETRY_STATE_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_persisted_retry_state(state_dict: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(RETRY_STATE_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, indent=2)
    except Exception:
        pass


def calculate_backoff_delay(attempt: int, base_sec: float = DEFAULT_BASE_BACKOFF_SEC, max_sec: float = DEFAULT_MAX_BACKOFF_SEC) -> float:
    """
    Computes bounded exponential backoff delay:
    attempt 1 -> 0s
    attempt 2 -> base_sec (e.g. 2.0s)
    attempt 3 -> base_sec * 2 (e.g. 4.0s)
    """
    if attempt <= 1:
        return 0.0
    delay = base_sec * (2 ** (attempt - 2))
    return min(delay, max_sec)


def get_payment_retry_status(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook"
) -> Dict[str, Any]:
    """
    Topic 2.2.2.15 - Retrieves the authoritative recovery retry status for a payment.
    Re-evaluates current decision, verification status, and circuit health dynamically.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    with _retry_lock:
        if not _payment_retry_tracker and os.path.exists(RETRY_STATE_LOG_PATH):
            _payment_retry_tracker.update(_load_persisted_retry_state())
        entry = _payment_retry_tracker.get(clean_payment_id, {})
        attempt_number = entry.get("attempt_number", 1)
        max_attempts = entry.get("max_attempts", DEFAULT_MAX_RECOVERY_ATTEMPTS)

    # Re-evaluate live decision
    try:
        from src.recovery_decision_engine import evaluate_recovery_decision
        dec = evaluate_recovery_decision(clean_payment_id, clean_merchant_id, clean_endpoint)
        decision_val = dec.get("decision", "REQUIRE_HUMAN_REVIEW")
        risk_level = dec.get("risk_level", "LOW")
        decision_reason = dec.get("reason", "")
        payment_state = dec.get("payment_state", "PENDING")
        circuit_state = dec.get("circuit_state", "CLOSED")
        merchant_health = dec.get("merchant_health", "HEALTHY")
        requires_human = dec.get("requires_human_review", False)
    except Exception:
        decision_val = "REQUIRE_HUMAN_REVIEW"
        risk_level = "ELEVATED"
        decision_reason = "Decision engine unavailable."
        payment_state = "PENDING"
        circuit_state = "CLOSED"
        merchant_health = "HEALTHY"
        requires_human = False

    # Re-evaluate live verification summary
    try:
        from src.recovery_verification import get_payment_recovery_verification_summary, VerificationOutcome
        ver = get_payment_recovery_verification_summary(clean_payment_id, clean_merchant_id, clean_endpoint)
        verification_status = ver.get("verification_status", VerificationOutcome.VERIFICATION_PENDING.value)
    except Exception:
        verification_status = "VERIFICATION_PENDING"

    # Determine retry availability and status
    if payment_state in ("RECOVERED", "SUCCESS", "REFUNDED") or verification_status == "VERIFIED_SUCCESS":
        retry_available = False
        retry_status = RetryStatus.COMPLETED.value
        reason = "Recovery completed and verified. No further retries required."
        next_step = "Transaction lifecycle complete."
    elif requires_human or decision_val == "REQUIRE_HUMAN_REVIEW" or payment_state in ("HUMAN_REVIEW", "ESCALATED", "STOPPED"):
        retry_available = False
        retry_status = RetryStatus.HUMAN_REVIEW_REQUIRED.value
        reason = decision_reason or "Human operator confirmation required before execution."
        next_step = "Route to Human Action Center for review."
    elif circuit_state == "OPEN":
        retry_available = False
        retry_status = RetryStatus.WAITING_FOR_CIRCUIT.value
        reason = "Outbound recovery paused because circuit breaker is OPEN."
        next_step = "Wait for circuit breaker cooldown before probing or retrying."
    elif attempt_number >= max_attempts:
        retry_available = False
        retry_status = RetryStatus.EXHAUSTED.value
        reason = f"Maximum recovery attempts exhausted ({attempt_number}/{max_attempts})."
        next_step = "Escalate incident to operator in Human Action Center."
    else:
        retry_available = True
        retry_status = RetryStatus.READY.value if attempt_number == 1 else RetryStatus.SCHEDULED.value
        reason = f"Payment eligible for retry attempt {attempt_number + 1} of {max_attempts}."
        next_step = "Execute bounded recovery through circuit gate."

    backoff_sec = calculate_backoff_delay(attempt_number + 1)

    return {
        "payment_id": clean_payment_id,
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "attempt_number": attempt_number,
        "max_attempts": max_attempts,
        "retry_available": retry_available,
        "retry_status": retry_status,
        "verification_status": verification_status,
        "decision": decision_val,
        "risk_level": risk_level,
        "merchant_health": merchant_health,
        "circuit_state": circuit_state,
        "payment_state": payment_state,
        "backoff_seconds": backoff_sec,
        "reason": reason,
        "recommended_next_step": next_step,
        "timestamp": now_iso
    }


def execute_bounded_recovery_retry(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    case_data: Optional[Dict[str, Any]] = None,
    webhook_verified: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.15 - Orchestrates a bounded retry with fresh decision re-evaluation
    and post-recovery verification.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    status_obj = get_payment_retry_status(clean_payment_id, clean_merchant_id, clean_endpoint)
    attempt_num = status_obj["attempt_number"]
    max_att = status_obj["max_attempts"]

    if not status_obj["retry_available"]:
        # Record blocked/exhausted telemetry
        try:
            from src.recovery_audit import record_recovery_audit_event, AuditEventType
            record_recovery_audit_event(
                payment_id=clean_payment_id,
                event_type=AuditEventType.RECOVERY_RETRY_BLOCKED.value if status_obj["retry_status"] != RetryStatus.EXHAUSTED.value else AuditEventType.RECOVERY_RETRY_EXHAUSTED.value,
                actor_type="AI_AGENT",
                source="RECOVERY_RETRY_MANAGER",
                status=status_obj["retry_status"],
                reason=status_obj["reason"],
                risk_level=status_obj["risk_level"],
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint
            )
        except Exception:
            pass

        return {
            "success": False,
            "payment_id": clean_payment_id,
            "retry_status": status_obj["retry_status"],
            "attempt_number": attempt_num,
            "max_attempts": max_att,
            "reason": status_obj["reason"],
            "recommended_next_step": status_obj["recommended_next_step"],
            "timestamp": now_iso
        }

    # Record retry started
    try:
        from src.recovery_audit import record_recovery_audit_event, AuditEventType
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type=AuditEventType.RECOVERY_RETRY_STARTED.value,
            actor_type="AI_AGENT",
            source="RECOVERY_RETRY_MANAGER",
            status="IN_PROGRESS",
            reason=f"Starting bounded recovery retry attempt {attempt_num + 1}/{max_att}.",
            risk_level=status_obj["risk_level"],
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint
        )
    except Exception:
        pass

    # Invoke orchestrator
    try:
        from src.recovery_orchestrator import orchestrate_payment_recovery
        orch_res = orchestrate_payment_recovery(
            payment_id=clean_payment_id,
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            case_data=case_data,
            webhook_verified=webhook_verified,
            max_attempts=max_att
        )
    except Exception as e:
        orch_res = {
            "outcome": "FAILED",
            "reason": f"Retry orchestration encountered exception: {str(e)}",
            "payment_state": status_obj["payment_state"],
            "verification_status": "VERIFICATION_FAILED"
        }

    # Update attempt counter in persistent tracker
    with _retry_lock:
        new_attempt = attempt_num + 1
        _payment_retry_tracker[clean_payment_id] = {
            "payment_id": clean_payment_id,
            "merchant_id": clean_merchant_id,
            "endpoint": clean_endpoint,
            "attempt_number": new_attempt,
            "max_attempts": max_att,
            "last_outcome": orch_res.get("outcome", "FAILED"),
            "verification_status": orch_res.get("verification_status", "VERIFICATION_FAILED"),
            "last_retry_at": now_iso
        }
        _save_persisted_retry_state(_payment_retry_tracker)

    # Record completion/exhaustion audit event
    is_success = (orch_res.get("verification_status") == "VERIFIED_SUCCESS" or orch_res.get("outcome") == "EXECUTE_RECOVERY")
    event_type_to_record = "RECOVERY_RETRY_COMPLETED" if is_success else ("RECOVERY_RETRY_EXHAUSTED" if new_attempt >= max_att else "RECOVERY_RETRY_FAILED")

    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type=event_type_to_record,
            actor_type="AI_AGENT",
            source="RECOVERY_RETRY_MANAGER",
            status="SUCCESS" if is_success else "FAILED",
            reason=orch_res.get("reason", f"Retry attempt {new_attempt}/{max_att} outcome: {orch_res.get('outcome')}"),
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            execution_id=orch_res.get("execution_id")
        )
    except Exception:
        pass

    return {
        "success": is_success,
        "payment_id": clean_payment_id,
        "attempt_number": new_attempt,
        "max_attempts": max_att,
        "orchestration": orch_res,
        "retry_status": RetryStatus.COMPLETED.value if is_success else (RetryStatus.EXHAUSTED.value if new_attempt >= max_att else RetryStatus.SCHEDULED.value),
        "timestamp": now_iso
    }


def reset_retry_manager_state() -> None:
    """Helper to reset in-memory and persisted retry tracker."""
    with _retry_lock:
        _payment_retry_tracker.clear()
        if os.path.exists(RETRY_STATE_LOG_PATH):
            try:
                os.remove(RETRY_STATE_LOG_PATH)
            except Exception:
                pass
