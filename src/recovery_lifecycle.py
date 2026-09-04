"""
RecoverIQ - Recovery Lifecycle Completion, Final Incident Resolution & End-to-End Status Consolidation (Topic 2.2.2.18)

Read-only aggregation and lifecycle consolidation layer that unifies all authoritative
signals into a single, cohesive, end-to-end incident resolution view.

STRICT BOUNDARIES:
- Purely read/aggregation layer; NEVER mutates PaymentState or CircuitState directly.
- Derives consolidated lifecycle status dynamically from authoritative subsystems.
- Failure-safe: if any subsystem has missing data, falls back gracefully without crashing.
- Zero credential, secret, password, or raw payload storage.
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class RecoveryLifecycleStatus(str, Enum):
    """Authoritative consolidated lifecycle states."""
    INCIDENT_RECEIVED = "INCIDENT_RECEIVED"
    RECOVERY_ELIGIBLE = "RECOVERY_ELIGIBLE"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    RETRYING = "RETRYING"
    WAITING_FOR_MERCHANT = "WAITING_FOR_MERCHANT"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    HUMAN_REVIEW_PENDING = "HUMAN_REVIEW_PENDING"
    RECOVERY_VERIFIED = "RECOVERY_VERIFIED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    RECOVERY_BLOCKED = "RECOVERY_BLOCKED"
    RECOVERY_REJECTED = "RECOVERY_REJECTED"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"


def get_consolidated_recovery_lifecycle(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook"
) -> Dict[str, Any]:
    """
    Topic 2.2.2.18 - Aggregates and consolidates the authoritative end-to-end recovery lifecycle.
    Queries state_machine, recovery_decision_engine, circuit_breaker, merchant_health,
    recovery_verification, recovery_retry_manager, recovery_human_review, and recovery_audit.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Authoritative Payment State
    payment_state = "PENDING"
    try:
        from src.state_machine import get_current_payment_state
        state_enum = get_current_payment_state(clean_payment_id)
        payment_state = state_enum.value if hasattr(state_enum, "value") else str(state_enum)
    except Exception:
        pass

    # 2. Recovery Decision Engine
    decision_val = "ALLOW_RECOVERY"
    risk_level = "LOW"
    decision_reason = ""
    circuit_state = "CLOSED"
    merchant_health = "HEALTHY"
    requires_human_review = False
    try:
        from src.recovery_decision_engine import evaluate_recovery_decision
        dec = evaluate_recovery_decision(clean_payment_id, clean_merchant_id, clean_endpoint)
        decision_val = dec.get("decision", "ALLOW_RECOVERY")
        risk_level = dec.get("risk_level", "LOW")
        decision_reason = dec.get("reason", "")
        circuit_state = dec.get("circuit_state", "CLOSED")
        merchant_health = dec.get("merchant_health", "HEALTHY")
        requires_human_review = dec.get("requires_human_review", False)
    except Exception:
        pass

    # 3. Post-Recovery Verification
    verification_status = "VERIFICATION_PENDING"
    verification_reason = ""
    try:
        from src.recovery_verification import get_payment_recovery_verification_summary
        ver = get_payment_recovery_verification_summary(clean_payment_id, clean_merchant_id, clean_endpoint)
        verification_status = ver.get("verification_status", "VERIFICATION_PENDING")
        verification_reason = ver.get("verification_reason", "")
    except Exception:
        pass

    # 4. Retry Manager
    retry_status = "READY"
    attempt_number = 1
    max_attempts = 3
    try:
        from src.recovery_retry_manager import get_payment_retry_status
        ret = get_payment_retry_status(clean_payment_id, clean_merchant_id, clean_endpoint)
        retry_status = ret.get("retry_status", "READY")
        attempt_number = ret.get("attempt_number", 1)
        max_attempts = ret.get("max_attempts", 3)
    except Exception:
        pass

    # 5. Human Review
    human_review_status = None
    review_id = None
    try:
        from src.recovery_human_review import get_payment_human_review
        hr = get_payment_human_review(clean_payment_id, clean_merchant_id, clean_endpoint)
        if hr:
            human_review_status = hr.get("review_status")
            review_id = hr.get("review_id")
    except Exception:
        pass

    # 6. Audit Timeline (Last event)
    last_event_type = "INCIDENT_RECEIVED"
    last_event_timestamp = now_iso
    correlation_id = None
    execution_id = None
    try:
        from src.recovery_audit import get_payment_recovery_timeline
        timeline = get_payment_recovery_timeline(clean_payment_id, clean_merchant_id, clean_endpoint)
        if timeline and len(timeline) > 0:
            last_evt = timeline[-1]
            last_event_type = last_evt.get("event_type", "EVENT_RECORDED")
            last_event_timestamp = last_evt.get("timestamp", now_iso)
            correlation_id = last_evt.get("correlation_id") or last_evt.get("event_id")
            execution_id = last_evt.get("execution_id")
    except Exception:
        pass

    # 7. Derive Consolidated Lifecycle Status and Final Outcome
    recovery_completed = False
    recovery_blocked = False

    if payment_state in ("RECOVERED", "SUCCESS") and verification_status == "VERIFIED_SUCCESS":
        lifecycle_status = RecoveryLifecycleStatus.RECOVERY_COMPLETED.value
        final_outcome = "RECOVERY_COMPLETED"
        recovery_completed = True
        reason = "Payment recovery successfully executed, verified against ledger, and marked RECOVERED."
        recommended_next_step = "Transaction lifecycle complete. No further action required."
    elif payment_state in ("RECOVERED", "SUCCESS"):
        lifecycle_status = RecoveryLifecycleStatus.ALREADY_COMPLETED.value
        final_outcome = "ALREADY_COMPLETED"
        recovery_completed = True
        reason = f"Payment is in authoritative completed state {payment_state}."
        recommended_next_step = "Transaction lifecycle complete."
    elif human_review_status == "REJECTED" or payment_state == "STOPPED":
        lifecycle_status = RecoveryLifecycleStatus.RECOVERY_REJECTED.value
        final_outcome = "RECOVERY_REJECTED"
        reason = "Recovery was rejected by operator and payment transitioned to STOPPED."
        recommended_next_step = "Payment recovery permanently halted."
    elif human_review_status in ("REVIEW_PENDING", "REVIEW_REQUIRED"):
        lifecycle_status = RecoveryLifecycleStatus.HUMAN_REVIEW_PENDING.value
        final_outcome = "HUMAN_REVIEW_PENDING"
        requires_human_review = True
        reason = "Payment awaiting manual operator authorization in Human Action Center."
        recommended_next_step = "Operator review required in Human Action Center."
    elif requires_human_review or decision_val == "REQUIRE_HUMAN_REVIEW" or payment_state in ("HUMAN_REVIEW", "ESCALATED"):
        lifecycle_status = RecoveryLifecycleStatus.HUMAN_REVIEW_REQUIRED.value
        final_outcome = "HUMAN_REVIEW_REQUIRED"
        requires_human_review = True
        reason = decision_reason or "Automated recovery prohibited; operator confirmation required."
        recommended_next_step = "Submit review approval in Human Review panel."
    elif circuit_state == "OPEN":
        lifecycle_status = RecoveryLifecycleStatus.WAITING_FOR_MERCHANT.value
        final_outcome = "WAITING_FOR_MERCHANT"
        recovery_blocked = True
        reason = "Outbound recovery paused because merchant circuit breaker is OPEN."
        recommended_next_step = "Wait for circuit breaker cooldown before probing or retrying."
    elif verification_status == "VERIFICATION_BLOCKED":
        lifecycle_status = RecoveryLifecycleStatus.RECOVERY_BLOCKED.value
        final_outcome = "RECOVERY_BLOCKED"
        recovery_blocked = True
        reason = verification_reason or "Recovery verification blocked due to circuit or security constraints."
        recommended_next_step = "Inspect circuit and merchant endpoint health."
    elif retry_status == "EXHAUSTED":
        lifecycle_status = RecoveryLifecycleStatus.RECOVERY_FAILED.value
        final_outcome = "RECOVERY_FAILED"
        reason = f"Maximum recovery attempts exhausted ({attempt_number}/{max_attempts})."
        recommended_next_step = "Escalate incident to operator in Human Action Center."
    elif retry_status in ("SCHEDULED", "IN_PROGRESS"):
        lifecycle_status = RecoveryLifecycleStatus.RETRYING.value
        final_outcome = "RETRYING"
        reason = f"Payment eligible for retry attempt {attempt_number + 1} of {max_attempts}."
        recommended_next_step = "Execute bounded recovery through circuit gate."
    elif verification_status == "VERIFICATION_PENDING":
        lifecycle_status = RecoveryLifecycleStatus.VERIFICATION_PENDING.value
        final_outcome = "VERIFICATION_PENDING"
        reason = verification_reason or "Outbound recovery dispatched; awaiting asynchronous order confirmation."
        recommended_next_step = "Maintain RECOVERING state and await merchant ledger verification callback."
    else:
        lifecycle_status = RecoveryLifecycleStatus.RECOVERY_ELIGIBLE.value
        final_outcome = "RECOVERY_ELIGIBLE"
        reason = decision_reason or "Payment is healthy and eligible for automated recovery."
        recommended_next_step = "Proceed with automated recovery orchestration."

    return {
        "payment_id": clean_payment_id,
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "lifecycle_status": lifecycle_status,
        "final_outcome": final_outcome,
        "payment_state": payment_state,
        "verification_status": verification_status,
        "retry_status": retry_status,
        "human_review_status": human_review_status,
        "review_id": review_id,
        "merchant_health": merchant_health,
        "circuit_state": circuit_state,
        "risk_level": risk_level,
        "decision": decision_val,
        "recovery_completed": recovery_completed,
        "recovery_blocked": recovery_blocked,
        "requires_human_review": requires_human_review,
        "reason": reason,
        "recommended_next_step": recommended_next_step,
        "last_event": last_event_type,
        "last_event_timestamp": last_event_timestamp,
        "correlation_id": correlation_id,
        "execution_id": execution_id,
        "timestamp": now_iso
    }
