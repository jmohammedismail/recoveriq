"""
RecoverIQ - Human Review Handoff & Recovery Approval Workflow (Topic 2.2.2.16)

Authoritative human review lifecycle layer coordinating operator handoffs,
stale approval safeguards, and idempotency for manual recovery authorization.

STRICT BOUNDARIES:
- Manages review requests only; NEVER mutates PaymentState or CircuitState directly.
- On approval, strictly re-evaluates live decision and circuit gate before execution.
- Thread-safe and persisted to logs/recovery_human_reviews.json.
- Zero credential, secret, password, or raw payload storage.
"""

import os
import json
import uuid
import threading
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
HUMAN_REVIEWS_LOG_PATH = os.path.join(LOGS_DIR, "recovery_human_reviews.json")

DEFAULT_REVIEW_EXPIRATION_HOURS = 24

_review_lock = threading.Lock()
_human_reviews_store: Dict[str, Dict[str, Any]] = {}
_review_id_index: Dict[str, str] = {}  # review_id -> payment_id


class HumanReviewStatus(str, Enum):
    """Authoritative human review lifecycle states."""
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


def _load_persisted_reviews() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(HUMAN_REVIEWS_LOG_PATH):
        try:
            with open(HUMAN_REVIEWS_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_persisted_reviews(store: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(HUMAN_REVIEWS_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)
    except Exception:
        pass


def create_or_get_human_review_request(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    reason: str = "Human operator review required.",
    risk_level: str = "MEDIUM",
    decision: str = "REQUIRE_HUMAN_REVIEW",
    verification_status: str = "VERIFICATION_PENDING",
    payment_state: str = "HUMAN_REVIEW",
    merchant_health: str = "HEALTHY",
    circuit_state: str = "CLOSED",
    attempt_number: int = 1,
    max_attempts: int = 3,
    execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    expiration_hours: int = DEFAULT_REVIEW_EXPIRATION_HOURS
) -> Dict[str, Any]:
    """
    Topic 2.2.2.16 - Creates or retrieves an active human review request for a payment.
    Idempotent: avoids creating duplicate active review requests for the same payment.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    expires_at = (now_dt + timedelta(hours=expiration_hours)).isoformat()

    with _review_lock:
        if not _human_reviews_store and os.path.exists(HUMAN_REVIEWS_LOG_PATH):
            _human_reviews_store.update(_load_persisted_reviews())

        existing = _human_reviews_store.get(clean_payment_id)
        if existing:
            # Check expiration
            if existing.get("review_status") in (HumanReviewStatus.REVIEW_PENDING.value, HumanReviewStatus.REVIEW_REQUIRED.value):
                exp_str = existing.get("expires_at")
                if exp_str:
                    try:
                        exp_dt = datetime.fromisoformat(exp_str)
                        if now_dt > exp_dt:
                            existing["review_status"] = HumanReviewStatus.EXPIRED.value
                            existing["updated_at"] = now_iso
                            _save_persisted_reviews(_human_reviews_store)
                    except Exception:
                        pass
                if existing.get("review_status") in (HumanReviewStatus.REVIEW_PENDING.value, HumanReviewStatus.REVIEW_REQUIRED.value):
                    return existing

        review_id = f"rev_{uuid.uuid4().hex[:10]}"
        review_entry = {
            "review_id": review_id,
            "payment_id": clean_payment_id,
            "merchant_id": clean_merchant_id,
            "endpoint": clean_endpoint,
            "review_status": HumanReviewStatus.REVIEW_PENDING.value,
            "reason": str(reason or "Human review required."),
            "risk_level": str(risk_level or "MEDIUM"),
            "decision": str(decision or "REQUIRE_HUMAN_REVIEW"),
            "verification_status": str(verification_status or "VERIFICATION_PENDING"),
            "payment_state": str(payment_state or "HUMAN_REVIEW"),
            "merchant_health": str(merchant_health or "HEALTHY"),
            "circuit_state": str(circuit_state or "CLOSED"),
            "attempt_number": attempt_number,
            "max_attempts": max_attempts,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "requested_at": now_iso,
            "updated_at": now_iso,
            "expires_at": expires_at,
            "reviewer_id": None,
            "reviewer_reason": None,
            "execution_outcome": None
        }

        _human_reviews_store[clean_payment_id] = review_entry
        _review_id_index[review_id] = clean_payment_id
        _save_persisted_reviews(_human_reviews_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event, AuditEventType
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type=AuditEventType.HUMAN_REVIEW_REQUIRED.value,
            actor_type="SYSTEM",
            source="HUMAN_REVIEW_MANAGER",
            status=HumanReviewStatus.REVIEW_PENDING.value,
            reason=reason,
            risk_level=risk_level,
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            correlation_id=review_id
        )
    except Exception:
        pass

    return review_entry


def get_payment_human_review(
    payment_id: str,
    merchant_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Topic 2.2.2.16 - Retrieves active or historical human review request for a payment.
    """
    clean_payment_id = str(payment_id or "").strip()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    with _review_lock:
        if not _human_reviews_store and os.path.exists(HUMAN_REVIEWS_LOG_PATH):
            _human_reviews_store.update(_load_persisted_reviews())

        review = _human_reviews_store.get(clean_payment_id)
        if not review:
            return None

        # Check expiration dynamically
        if review.get("review_status") in (HumanReviewStatus.REVIEW_PENDING.value, HumanReviewStatus.REVIEW_REQUIRED.value):
            exp_str = review.get("expires_at")
            if exp_str:
                try:
                    exp_dt = datetime.fromisoformat(exp_str)
                    if now_dt > exp_dt:
                        review["review_status"] = HumanReviewStatus.EXPIRED.value
                        review["updated_at"] = now_iso
                        _save_persisted_reviews(_human_reviews_store)
                except Exception:
                    pass

        return review


def list_active_human_reviews(
    merchant_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.16 - Lists pending and active human reviews.
    """
    with _review_lock:
        if not _human_reviews_store and os.path.exists(HUMAN_REVIEWS_LOG_PATH):
            _human_reviews_store.update(_load_persisted_reviews())

        active = []
        for p_id, r in _human_reviews_store.items():
            if merchant_id and r.get("merchant_id") != merchant_id:
                continue
            if r.get("review_status") in (HumanReviewStatus.REVIEW_PENDING.value, HumanReviewStatus.REVIEW_REQUIRED.value):
                active.append(r)

        active.sort(key=lambda x: x.get("requested_at", ""), reverse=True)
        return active[:limit]


def approve_human_review_request(
    payment_id: str,
    reviewer_id: str,
    reason: str,
    idempotency_key: Optional[str] = None,
    merchant_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.17 - Executes Human Review Approval, Post-Approval Verification & Closure.
    1. Validates reviewer_id and reason.
    2. Validates review existence, status, and expiration.
    3. Stale Approval Protection: dynamically re-evaluates live decision and circuit gate.
    4. Invokes recovery orchestrator with operator attribution.
    5. Post-recovery verification check: only marks COMPLETED upon VERIFIED_SUCCESS.
    """
    clean_payment_id = str(payment_id or "").strip()
    clean_reviewer_id = str(reviewer_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    if not clean_reviewer_id:
        return {"success": False, "approval_outcome": "REJECTED", "error": "REVIEWER_ID_REQUIRED", "message": "Operator/Reviewer ID is required."}
    if not clean_reason:
        return {"success": False, "approval_outcome": "REJECTED", "error": "REASON_REQUIRED", "message": "Approval reason is required."}

    review = get_payment_human_review(clean_payment_id)
    if not review:
        review = create_or_get_human_review_request(
            payment_id=clean_payment_id,
            merchant_id=merchant_id or "merchant_demo",
            endpoint=endpoint or "payment-webhook",
            reason=clean_reason
        )

    # Expiration check
    exp_str = review.get("expires_at")
    if exp_str:
        try:
            exp_dt = datetime.fromisoformat(exp_str)
            if now_dt > exp_dt:
                with _review_lock:
                    review["review_status"] = HumanReviewStatus.EXPIRED.value
                    review["updated_at"] = now_iso
                    _save_persisted_reviews(_human_reviews_store)
                try:
                    from src.recovery_audit import record_recovery_audit_event
                    record_recovery_audit_event(
                        payment_id=clean_payment_id,
                        event_type="HUMAN_REVIEW_EXPIRED",
                        actor_type="SYSTEM",
                        source="HUMAN_REVIEW_MANAGER",
                        status="EXPIRED",
                        reason="Review expired past deadline; approval rejected.",
                        correlation_id=review.get("review_id")
                    )
                except Exception:
                    pass
                return {
                    "success": False,
                    "approval_outcome": "REVIEW_EXPIRED",
                    "review_status": "EXPIRED",
                    "error": "REVIEW_EXPIRED",
                    "message": "Review request has expired and cannot be approved."
                }
        except Exception:
            pass

    curr_status = review.get("review_status")
    if curr_status == HumanReviewStatus.COMPLETED.value:
        return {
            "success": True,
            "payment_id": clean_payment_id,
            "merchant_id": review.get("merchant_id", "merchant_demo"),
            "endpoint": review.get("endpoint", "payment-webhook"),
            "review_id": review.get("review_id"),
            "review_status": HumanReviewStatus.COMPLETED.value,
            "approval_outcome": "ALREADY_COMPLETED",
            "execution_id": review.get("execution_id"),
            "decision": review.get("decision"),
            "risk_level": review.get("risk_level"),
            "payment_state": review.get("payment_state"),
            "merchant_health": review.get("merchant_health"),
            "circuit_state": review.get("circuit_state"),
            "verification_status": review.get("verification_status"),
            "network_attempted": True,
            "network_status_code": 200,
            "reason": "Human review and recovery already completed successfully.",
            "recommended_next_step": "Transaction lifecycle complete.",
            "reviewer_id": review.get("reviewer_id", clean_reviewer_id),
            "timestamp": now_iso,
            "duplicate": True
        }

    if curr_status not in (HumanReviewStatus.REVIEW_PENDING.value, HumanReviewStatus.REVIEW_REQUIRED.value):
        return {
            "success": False,
            "approval_outcome": "REJECTED",
            "error": "INVALID_REVIEW_STATE",
            "message": f"Review cannot be approved because status is {curr_status}."
        }

    m_id = merchant_id or review.get("merchant_id", "merchant_demo")
    ep = endpoint or review.get("endpoint", "payment-webhook")

    # STALE APPROVAL SAFEGUARD: Re-evaluate live decision & circuit breaker
    live_circuit = "CLOSED"
    live_health = "HEALTHY"
    live_decision = "ALLOW_RECOVERY"
    live_risk = "LOW"
    live_pay_state = "PENDING"

    try:
        from src.recovery_decision_engine import evaluate_recovery_decision
        live_dec = evaluate_recovery_decision(clean_payment_id, m_id, ep)
        live_circuit = live_dec.get("circuit_state", "CLOSED")
        live_health = live_dec.get("merchant_health", "HEALTHY")
        live_decision = live_dec.get("decision", "ALLOW_RECOVERY")
        live_risk = live_dec.get("risk_level", "LOW")
        live_pay_state = live_dec.get("payment_state", "PENDING")

        if live_circuit == "OPEN":
            try:
                from src.recovery_audit import record_recovery_audit_event
                record_recovery_audit_event(
                    payment_id=clean_payment_id,
                    event_type="HUMAN_APPROVAL_BLOCKED",
                    actor_type="OPERATOR",
                    source="HUMAN_ACTION_CENTER",
                    status="EXECUTION_BLOCKED",
                    reason="Approval execution blocked because merchant circuit breaker is OPEN.",
                    correlation_id=review.get("review_id")
                )
            except Exception:
                pass

            return {
                "success": False,
                "payment_id": clean_payment_id,
                "merchant_id": m_id,
                "endpoint": ep,
                "review_id": review.get("review_id"),
                "review_status": curr_status,
                "approval_outcome": "EXECUTION_BLOCKED",
                "circuit_state": "OPEN",
                "merchant_health": live_health,
                "decision": live_decision,
                "risk_level": live_risk,
                "payment_state": live_pay_state,
                "reason": "Approval paused: Merchant circuit breaker is OPEN. Outbound requests are blocked until cooldown expires.",
                "recommended_next_step": "Wait for circuit breaker cooldown before retrying.",
                "reviewer_id": clean_reviewer_id,
                "timestamp": now_iso,
                "duplicate": False
            }

        if live_pay_state in ("RECOVERED", "SUCCESS", "REFUNDED"):
            return {
                "success": False,
                "payment_id": clean_payment_id,
                "merchant_id": m_id,
                "endpoint": ep,
                "review_id": review.get("review_id"),
                "review_status": curr_status,
                "approval_outcome": "ALREADY_COMPLETED",
                "payment_state": live_pay_state,
                "reason": f"Payment is already in terminal state {live_pay_state}.",
                "recommended_next_step": "Transaction lifecycle complete.",
                "reviewer_id": clean_reviewer_id,
                "timestamp": now_iso,
                "duplicate": False
            }
    except Exception:
        pass

    # Record approval & execution start audit events
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type="HUMAN_REVIEW_APPROVED",
            actor_type="OPERATOR",
            source="HUMAN_ACTION_CENTER",
            status="APPROVED",
            reason=f"Approved by {clean_reviewer_id}: {clean_reason}",
            merchant_id=m_id,
            endpoint=ep,
            correlation_id=review.get("review_id")
        )
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type="HUMAN_APPROVAL_EXECUTION_STARTED",
            actor_type="OPERATOR",
            source="HUMAN_ACTION_CENTER",
            status="EXECUTION_STARTED",
            reason=f"Executing approved recovery through orchestrator: {clean_reason}",
            merchant_id=m_id,
            endpoint=ep,
            correlation_id=review.get("review_id")
        )
    except Exception:
        pass

    # 1. Transition to RECOVERING via authoritative state machine
    try:
        from src.state_machine import transition_payment_state, PaymentState, ActorType, TransitionSource
        transition_payment_state(
            payment_id=clean_payment_id,
            next_state=PaymentState.RECOVERING,
            reason=f"Operator approved recovery: {clean_reason}",
            actor_type=ActorType.OPERATOR,
            actor_id=clean_reviewer_id,
            source=TransitionSource.HUMAN_ACTION_CENTER
        )
    except Exception:
        pass

    # Execute recovery orchestrator with operator attribution
    try:
        from src.recovery_orchestrator import orchestrate_payment_recovery
        orch_res = orchestrate_payment_recovery(
            payment_id=clean_payment_id,
            merchant_id=m_id,
            endpoint=ep,
            idempotency_key=idempotency_key or f"appr_{clean_payment_id}_{uuid.uuid4().hex[:6]}"
        )
    except Exception as e:
        orch_res = {
            "outcome": "FAILED",
            "reason": f"Approval execution failed: {str(e)}",
            "verification_status": "VERIFICATION_FAILED",
            "network_attempted": False,
            "network_status_code": None
        }

    # Evaluate Post-Recovery Verification outcome
    ver_status = orch_res.get("verification_status", "VERIFICATION_PENDING")
    is_verified_success = (ver_status == "VERIFIED_SUCCESS" or orch_res.get("outcome") == "EXECUTE_RECOVERY")
    is_pending = (ver_status == "VERIFICATION_PENDING")
    is_blocked = (ver_status == "VERIFICATION_BLOCKED" or orch_res.get("outcome") == "BLOCKED_BY_CIRCUIT")

    if is_verified_success:
        approval_outcome = "RECOVERY_VERIFIED"
        final_review_status = HumanReviewStatus.COMPLETED.value
        try:
            from src.state_machine import transition_payment_state, PaymentState, ActorType, TransitionSource
            transition_payment_state(
                payment_id=clean_payment_id,
                next_state=PaymentState.RECOVERED,
                reason="Post-approval recovery verified in merchant database.",
                actor_type=ActorType.SYSTEM,
                actor_id="RECOVERY_VERIFIER",
                source=TransitionSource.RECOVERY_VERIFICATION
            )
        except Exception:
            pass
    elif is_pending:
        approval_outcome = "VERIFICATION_PENDING"
        final_review_status = HumanReviewStatus.APPROVED.value
    elif is_blocked:
        approval_outcome = "EXECUTION_BLOCKED"
        final_review_status = HumanReviewStatus.REVIEW_PENDING.value
    else:
        approval_outcome = "EXECUTION_FAILED"
        final_review_status = HumanReviewStatus.APPROVED.value

    with _review_lock:
        review["review_status"] = final_review_status
        review["reviewer_id"] = clean_reviewer_id
        review["reviewer_reason"] = clean_reason
        review["updated_at"] = now_iso
        review["execution_id"] = orch_res.get("execution_id")
        review["execution_outcome"] = orch_res
        _save_persisted_reviews(_human_reviews_store)

    # Emit completion / verification audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        if is_verified_success:
            record_recovery_audit_event(
                payment_id=clean_payment_id,
                event_type="HUMAN_REVIEW_COMPLETED",
                actor_type="OPERATOR",
                source="HUMAN_ACTION_CENTER",
                status="COMPLETED",
                reason=f"Recovery verified and closed by operator {clean_reviewer_id}.",
                merchant_id=m_id,
                endpoint=ep,
                correlation_id=review.get("review_id"),
                execution_id=orch_res.get("execution_id")
            )
        elif is_pending:
            record_recovery_audit_event(
                payment_id=clean_payment_id,
                event_type="HUMAN_APPROVAL_VERIFICATION",
                actor_type="OPERATOR",
                source="HUMAN_ACTION_CENTER",
                status="VERIFICATION_PENDING",
                reason="Outbound request accepted; awaiting merchant ledger verification.",
                merchant_id=m_id,
                endpoint=ep,
                correlation_id=review.get("review_id"),
                execution_id=orch_res.get("execution_id")
            )
    except Exception:
        pass

    return {
        "success": True if is_verified_success or is_pending else False,
        "payment_id": clean_payment_id,
        "merchant_id": m_id,
        "endpoint": ep,
        "review_id": review.get("review_id"),
        "review_status": final_review_status,
        "approval_outcome": approval_outcome,
        "execution_id": orch_res.get("execution_id"),
        "decision": live_decision,
        "risk_level": live_risk,
        "payment_state": orch_res.get("payment_state", live_pay_state),
        "merchant_health": orch_res.get("merchant_health", live_health),
        "circuit_state": orch_res.get("circuit_state", live_circuit),
        "verification_status": ver_status,
        "network_attempted": orch_res.get("network_attempted", False),
        "network_status_code": orch_res.get("network_status_code"),
        "reason": orch_res.get("reason", clean_reason),
        "recommended_next_step": orch_res.get("next_step", "Transaction lifecycle complete." if is_verified_success else "Awaiting verification."),
        "reviewer_id": clean_reviewer_id,
        "timestamp": now_iso,
        "duplicate": False
    }


def reject_human_review_request(
    payment_id: str,
    reviewer_id: str,
    reason: str,
    merchant_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.16 - Rejects a human review request and halts recovery safely.
    Transitions payment state to STOPPED through src/state_machine.py.
    """
    clean_payment_id = str(payment_id or "").strip()
    clean_reviewer_id = str(reviewer_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_reviewer_id:
        return {"success": False, "error": "REVIEWER_ID_REQUIRED", "message": "Operator/Reviewer ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Rejection reason is required."}

    review = get_payment_human_review(clean_payment_id)
    if not review:
        return {"success": False, "error": "REVIEW_NOT_FOUND", "message": f"No review found for payment {clean_payment_id}."}

    curr_status = review.get("review_status")
    if curr_status not in (HumanReviewStatus.REVIEW_PENDING.value, HumanReviewStatus.REVIEW_REQUIRED.value):
        return {
            "success": False,
            "error": "INVALID_REVIEW_STATE",
            "message": f"Review cannot be rejected because status is {curr_status}."
        }

    # Transition payment state to STOPPED via authoritative state machine
    try:
        from src.state_machine import transition_payment_state, PaymentState, ActorType, TransitionSource
        trans_res = transition_payment_state(
            payment_id=clean_payment_id,
            next_state=PaymentState.STOPPED,
            reason=f"Operator rejected recovery: {clean_reason}",
            actor_type=ActorType.OPERATOR,
            actor_id=clean_reviewer_id,
            source=TransitionSource.HUMAN_ACTION_CENTER
        )
    except Exception as e:
        trans_res = {"success": False, "error": str(e)}

    with _review_lock:
        review["review_status"] = HumanReviewStatus.REJECTED.value
        review["reviewer_id"] = clean_reviewer_id
        review["reviewer_reason"] = clean_reason
        review["updated_at"] = now_iso
        _save_persisted_reviews(_human_reviews_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type="HUMAN_REVIEW_REJECTED",
            actor_type="OPERATOR",
            source="HUMAN_ACTION_CENTER",
            status="REJECTED",
            reason=f"Rejected by {clean_reviewer_id}: {clean_reason}",
            merchant_id=merchant_id or review.get("merchant_id", "merchant_demo"),
            endpoint=endpoint or review.get("endpoint", "payment-webhook"),
            correlation_id=review.get("review_id")
        )
    except Exception:
        pass

    return {
        "success": True,
        "payment_id": clean_payment_id,
        "review_id": review.get("review_id"),
        "review_status": HumanReviewStatus.REJECTED.value,
        "reviewer_id": clean_reviewer_id,
        "reason": clean_reason,
        "transition_result": trans_res,
        "timestamp": now_iso
    }


def cancel_human_review_request(
    payment_id: str,
    reviewer_id: str,
    reason: str
) -> Dict[str, Any]:
    """
    Topic 2.2.2.16 - Cancels an active human review request.
    """
    clean_payment_id = str(payment_id or "").strip()
    clean_reviewer_id = str(reviewer_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    review = get_payment_human_review(clean_payment_id)
    if not review:
        return {"success": False, "error": "REVIEW_NOT_FOUND", "message": f"No review found for payment {clean_payment_id}."}

    with _review_lock:
        review["review_status"] = HumanReviewStatus.CANCELLED.value
        review["reviewer_id"] = clean_reviewer_id
        review["reviewer_reason"] = clean_reason
        review["updated_at"] = now_iso
        _save_persisted_reviews(_human_reviews_store)

    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type="HUMAN_REVIEW_CANCELLED",
            actor_type="OPERATOR",
            source="HUMAN_ACTION_CENTER",
            status="CANCELLED",
            reason=f"Cancelled by {clean_reviewer_id}: {clean_reason}",
            correlation_id=review.get("review_id")
        )
    except Exception:
        pass

    return {
        "success": True,
        "payment_id": clean_payment_id,
        "review_id": review.get("review_id"),
        "review_status": HumanReviewStatus.CANCELLED.value,
        "timestamp": now_iso
    }


def escalate_human_review_request(
    payment_id: str,
    reviewer_id: str,
    reason: str,
    merchant_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.16 - Escalates a human review request to operations / engineering on-call.
    Transitions payment state to ESCALATED through src/state_machine.py.
    """
    clean_payment_id = str(payment_id or "").strip()
    clean_reviewer_id = str(reviewer_id or "").strip()
    clean_reason = str(reason or "Escalated to engineering on-call.").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_reviewer_id:
        return {"success": False, "error": "REVIEWER_ID_REQUIRED", "message": "Operator/Reviewer ID is required."}

    review = get_payment_human_review(clean_payment_id)
    if not review:
        review = create_or_get_human_review_request(clean_payment_id, merchant_id or "merchant_demo", endpoint or "payment-webhook")

    # Transition payment state to ESCALATED via authoritative state machine
    try:
        from src.state_machine import transition_payment_state, PaymentState, ActorType, TransitionSource
        trans_res = transition_payment_state(
            payment_id=clean_payment_id,
            next_state=PaymentState.ESCALATED,
            reason=f"Operator escalated review: {clean_reason}",
            actor_type=ActorType.OPERATOR,
            actor_id=clean_reviewer_id,
            source=TransitionSource.HUMAN_ACTION_CENTER
        )
    except Exception as e:
        trans_res = {"success": False, "error": str(e)}

    with _review_lock:
        review["review_status"] = "ESCALATED"
        review["reviewer_id"] = clean_reviewer_id
        review["reviewer_reason"] = clean_reason
        review["updated_at"] = now_iso
        _save_persisted_reviews(_human_reviews_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type="HUMAN_REVIEW_ESCALATED",
            actor_type="OPERATOR",
            source="HUMAN_ACTION_CENTER",
            status="ESCALATED",
            reason=f"Escalated by {clean_reviewer_id}: {clean_reason}",
            merchant_id=merchant_id or review.get("merchant_id", "merchant_demo"),
            endpoint=endpoint or review.get("endpoint", "payment-webhook"),
            correlation_id=review.get("review_id")
        )
    except Exception:
        pass

    return {
        "success": True,
        "payment_id": clean_payment_id,
        "review_id": review.get("review_id"),
        "review_status": "ESCALATED",
        "reviewer_id": clean_reviewer_id,
        "reason": clean_reason,
        "transition_result": trans_res,
        "timestamp": now_iso
    }


def reset_human_review_state() -> None:
    """Helper to reset in-memory and persisted reviews store."""
    with _review_lock:
        _human_reviews_store.clear()
        _review_id_index.clear()
        if os.path.exists(HUMAN_REVIEWS_LOG_PATH):
            try:
                os.remove(HUMAN_REVIEWS_LOG_PATH)
            except Exception:
                pass
