"""
RecoverIQ - Recovery Post-Closure Consistency Guard (Topic 2.2.2.21 / Consistency Validation)

Authoritative, strictly read-only post-closure consistency validation layer.
Continuously verifies that recorded incident closure remains in exact agreement
with the authoritative state machine, verification engine, and finalization guard.

STRICT BOUNDARIES:
- Strictly read-only; NEVER directly mutates PaymentState or CircuitState.
- NEVER automatically reopens incidents, triggers retries, or dispatches network requests.
- When an inconsistency is detected: reports, audits, and exposes it without auto-repair.
- Persists operational validation telemetry to logs/recovery_consistency_events.json.
- Zero credential, secret, password, or raw payload storage.
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
CONSISTENCY_EVENTS_LOG_PATH = os.path.join(LOGS_DIR, "recovery_consistency_events.json")

_consistency_lock = threading.Lock()
_consistency_events_log: List[Dict[str, Any]] = []


class ConsistencyStatus(str, Enum):
    """Authoritative consistency validation statuses."""
    CONSISTENT = "CONSISTENT"
    VALIDATION_PENDING = "VALIDATION_PENDING"
    INCONSISTENT = "INCONSISTENT"
    VALIDATION_BLOCKED = "VALIDATION_BLOCKED"
    ALREADY_CONSISTENT = "ALREADY_CONSISTENT"


def _load_persisted_consistency_events() -> List[Dict[str, Any]]:
    if os.path.exists(CONSISTENCY_EVENTS_LOG_PATH):
        try:
            with open(CONSISTENCY_EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_persisted_consistency_events(events: List[Dict[str, Any]]) -> None:
    try:
        with open(CONSISTENCY_EVENTS_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
    except Exception:
        pass


def validate_recovery_consistency(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    closure_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic: Post-Closure Consistency Guard - Validates consistency across all authoritative signals.
    Compares: PaymentState, Verification, Finalization, IncidentClosure, HumanReview, Retry, Circuit.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Authoritative Payment State (src/state_machine.py)
    payment_state = "PENDING"
    try:
        from src.state_machine import get_current_payment_state
        state_enum = get_current_payment_state(clean_payment_id)
        payment_state = state_enum.value if hasattr(state_enum, "value") else str(state_enum)
    except Exception:
        pass

    # 2. Post-Recovery Verification Status (src/recovery_verification.py)
    verification_status = "VERIFICATION_PENDING"
    try:
        from src.recovery_verification import get_payment_recovery_verification_summary
        ver = get_payment_recovery_verification_summary(clean_payment_id, clean_merchant_id, clean_endpoint)
        verification_status = ver.get("verification_status", "VERIFICATION_PENDING")
    except Exception:
        pass

    # 3. Finalization Status (src/recovery_finalization.py)
    finalization_status = "RESOLUTION_PENDING"
    try:
        from src.recovery_finalization import evaluate_recovery_finalization
        fin = evaluate_recovery_finalization(clean_payment_id, clean_merchant_id, clean_endpoint)
        finalization_status = fin.get("finalization_status", "RESOLUTION_PENDING")
    except Exception:
        pass

    # 4. Incident Closure Action State (src/incident_closure.py)
    closure_status = "CLOSURE_PENDING"
    is_closed = False
    rec_closure_id = None
    execution_id = None
    correlation_id = None
    try:
        from src.incident_closure import get_incident_closure_status
        cls_obj = get_incident_closure_status(clean_payment_id, clean_merchant_id, clean_endpoint)
        closure_status = cls_obj.get("closure_status", "CLOSURE_PENDING")
        is_closed = cls_obj.get("closed", False)
        rec_closure_id = cls_obj.get("closure_id")
        execution_id = cls_obj.get("execution_id")
        correlation_id = cls_obj.get("correlation_id")
    except Exception:
        pass

    # 5. Human Review Status (src/recovery_human_review.py)
    human_review_status = None
    human_review_active = False
    try:
        from src.recovery_human_review import get_payment_human_review
        hr = get_payment_human_review(clean_payment_id, clean_merchant_id, clean_endpoint)
        if hr:
            human_review_status = hr.get("review_status")
            if human_review_status in ("REVIEW_PENDING", "REVIEW_REQUIRED"):
                human_review_active = True
    except Exception:
        pass

    # 6. Retry Status (src/recovery_retry_manager.py)
    retry_status = "READY"
    retry_active = False
    try:
        from src.recovery_retry_manager import get_payment_retry_status
        ret = get_payment_retry_status(clean_payment_id, clean_merchant_id, clean_endpoint)
        retry_status = ret.get("retry_status", "READY")
        if retry_status in ("SCHEDULED", "IN_PROGRESS") and not is_closed:
            retry_active = True
    except Exception:
        pass

    # 7. Circuit & Merchant Health (src/circuit_breaker.py & src/merchant_health.py)
    circuit_state = "CLOSED"
    merchant_health = "HEALTHY"
    try:
        from src.recovery_lifecycle import get_consolidated_recovery_lifecycle
        lc = get_consolidated_recovery_lifecycle(clean_payment_id, clean_merchant_id, clean_endpoint)
        circuit_state = lc.get("circuit_state", "CLOSED")
        merchant_health = lc.get("merchant_health", "HEALTHY")
    except Exception:
        pass

    # 8. Check Inconsistencies
    conflicts = []
    if is_closed or closure_status in ("INCIDENT_CLOSED", "ALREADY_CLOSED"):
        if payment_state not in ("RECOVERED", "SUCCESS"):
            conflicts.append(f"Closure is {closure_status} but PaymentState is {payment_state} (expected RECOVERED).")
        if verification_status != "VERIFIED_SUCCESS":
            conflicts.append(f"Closure is {closure_status} but Verification is {verification_status} (expected VERIFIED_SUCCESS).")
        if finalization_status not in ("INCIDENT_RESOLVED", "ALREADY_RESOLVED"):
            conflicts.append(f"Closure is {closure_status} but Finalization is {finalization_status} (expected INCIDENT_RESOLVED).")
        if human_review_active:
            conflicts.append(f"Closure is {closure_status} but an active Human Review ({human_review_status}) is still pending.")
        if retry_active:
            conflicts.append(f"Closure is {closure_status} but an active Recovery Retry ({retry_status}) is still scheduled.")

    if conflicts:
        consistency_status = ConsistencyStatus.INCONSISTENT.value
        reason = "Closure inconsistency detected: " + "; ".join(conflicts)
        evidence = "STATE_MUTEX_CONTRADICTION"
        recommended_next_step = "Closure inconsistency detected — automatic repair is disabled. Operator review required."
    elif is_closed and payment_state in ("RECOVERED", "SUCCESS") and verification_status == "VERIFIED_SUCCESS" and finalization_status in ("INCIDENT_RESOLVED", "ALREADY_RESOLVED") and not human_review_active and not retry_active:
        consistency_status = ConsistencyStatus.CONSISTENT.value
        reason = "All authoritative recovery, verification, and closure signals are consistent."
        evidence = "STATE_MACHINE_VERIFIED_CLOSURE"
        recommended_next_step = "No action required. Incident closure is consistent."
    elif circuit_state == "OPEN" or verification_status == "VERIFICATION_BLOCKED":
        consistency_status = ConsistencyStatus.VALIDATION_BLOCKED.value
        reason = "Consistency validation blocked: Circuit breaker is OPEN or verification was blocked."
        evidence = "CIRCUIT_SAFETY_GUARD"
        recommended_next_step = "Wait for circuit breaker cooldown before re-evaluating."
    else:
        consistency_status = ConsistencyStatus.VALIDATION_PENDING.value
        reason = "Incident recovery pipeline is in progress; authoritative closure has not yet converged."
        evidence = "ASYNC_PIPELINE_IN_FLIGHT"
        recommended_next_step = "Await authoritative verification and closure execution."

    final_closure_id = rec_closure_id or closure_id

    entry = {
        "payment_id": clean_payment_id,
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "consistency_status": consistency_status,
        "payment_state": payment_state,
        "verification_status": verification_status,
        "finalization_status": finalization_status,
        "closure_status": closure_status,
        "human_review_active": human_review_active,
        "retry_active": retry_active,
        "circuit_state": circuit_state,
        "merchant_health": merchant_health,
        "closure_id": final_closure_id,
        "execution_id": execution_id,
        "correlation_id": correlation_id,
        "reason": reason,
        "evidence": evidence,
        "recommended_next_step": recommended_next_step,
        "validation_timestamp": now_iso
    }

    # Persist validation telemetry
    try:
        with _consistency_lock:
            if not _consistency_events_log and os.path.exists(CONSISTENCY_EVENTS_LOG_PATH):
                _consistency_events_log.extend(_load_persisted_consistency_events())

            event_record = {
                "event_id": f"const_{uuid.uuid4().hex[:10]}",
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "closure_id": final_closure_id,
                "execution_id": execution_id,
                "correlation_id": correlation_id,
                "consistency_status": consistency_status,
                "reason": reason,
                "evidence_type": evidence,
                "timestamp": now_iso
            }
            _consistency_events_log.append(event_record)
            if len(_consistency_events_log) > 300:
                _consistency_events_log.pop(0)
            _save_persisted_consistency_events(_consistency_events_log)
    except Exception:
        pass

    # Correlate to recovery audit timeline
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type=f"CONSISTENCY_{consistency_status}",
            actor_type="SYSTEM",
            source="RECOVERY_CONSISTENCY_GUARD",
            status=consistency_status,
            reason=reason,
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            correlation_id=final_closure_id
        )
    except Exception:
        pass

    return entry


def reset_consistency_state() -> None:
    """Helper to reset in-memory and persisted consistency logs."""
    with _consistency_lock:
        _consistency_events_log.clear()
        if os.path.exists(CONSISTENCY_EVENTS_LOG_PATH):
            try:
                os.remove(CONSISTENCY_EVENTS_LOG_PATH)
            except Exception:
                pass
