"""
RecoverIQ - Resilience-Aware Recovery Decision Engine (Topic 2.2.2.9)

Deterministic, explainable decision layer that evaluates:
  1. Authoritative payment state (src/state_machine.py)
  2. Merchant endpoint health (src/merchant_health.py)
  3. Authoritative circuit breaker request gate (src/circuit_breaker.py)
  4. Inbound webhook security status (src/webhook_security.py)
  5. Recovery context & human-in-the-loop policies

IMPORTANT:
This module solely produces recommendations and decisions.
It does NOT directly mutate payment lifecycle states, trip circuit breakers,
bypass circuit request gates, or execute human operator actions.
"""

import uuid
import threading
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone


class RecoveryDecisionType(str, Enum):
    """Authoritative decision types for recovery strategy."""
    ALLOW_RECOVERY = "ALLOW_RECOVERY"
    RETRY_RECOVERY = "RETRY_RECOVERY"
    DEFER_RECOVERY = "DEFER_RECOVERY"
    BLOCK_RECOVERY = "BLOCK_RECOVERY"
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"
    WAIT_FOR_MERCHANT_RECOVERY = "WAIT_FOR_MERCHANT_RECOVERY"


class RecoveryRiskLevel(str, Enum):
    """Derived financial and operational risk levels."""
    LOW = "LOW"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecoveryAction(str, Enum):
    """Actionable next-step directive for the recovery pipeline."""
    PROCEED_RECOVERY = "PROCEED_RECOVERY"
    RETRY_WITH_BACKOFF = "RETRY_WITH_BACKOFF"
    DEFER_AND_POLL = "DEFER_AND_POLL"
    HALT_AND_WAIT = "HALT_AND_WAIT"
    REQUEST_OPERATOR_APPROVAL = "REQUEST_OPERATOR_APPROVAL"
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"


_decision_lock = threading.Lock()
_decision_telemetry_log: List[Dict[str, Any]] = []


def evaluate_recovery_decision(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    case_data: Optional[Dict[str, Any]] = None,
    webhook_verified: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Evaluates the safest recovery strategy for a payment by combining:
      - Payment State
      - Merchant Endpoint Health
      - Circuit Breaker State & Cooldown
      - Webhook Authentication Status
      - Human Action Requirements

    Returns a structured RecoveryDecision object without mutating any underlying state.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Resolve authoritative Payment State
    try:
        try:
            from src.state_machine import get_current_payment_state, PaymentState
        except ImportError:
            from state_machine import get_current_payment_state, PaymentState
        current_payment_state = get_current_payment_state(clean_payment_id, case_data)
        payment_state_str = current_payment_state.value
    except Exception:
        payment_state_str = str(case_data.get("payment_status") if case_data else "UNKNOWN").upper()

    # 2. Resolve authoritative Merchant Health
    try:
        try:
            from src.merchant_health import get_endpoint_health_summary
        except ImportError:
            from merchant_health import get_endpoint_health_summary
        health_summary = get_endpoint_health_summary(clean_merchant_id, clean_endpoint)
        merchant_health_str = health_summary.get("health", "NO_DATA")
    except Exception:
        merchant_health_str = "NO_DATA"
        health_summary = {}

    # 3. Resolve authoritative Circuit Breaker Status
    try:
        try:
            from src.circuit_breaker import get_circuit_breaker_status, CircuitState
        except ImportError:
            from circuit_breaker import get_circuit_breaker_status, CircuitState
        circuit_status = get_circuit_breaker_status(clean_merchant_id, clean_endpoint)
        circuit_state_str = circuit_status.get("state", "CLOSED")
        cooldown_remaining = circuit_status.get("cooldown_remaining_sec", 0.0)
        probe_count = circuit_status.get("half_open_probe_count", 0)
        probe_limit = circuit_status.get("half_open_probe_limit", 3)
    except Exception:
        circuit_state_str = "CLOSED"
        cooldown_remaining = 0.0
        probe_count = 0
        probe_limit = 3
        circuit_status = {}

    # Determine base request allowance from circuit state
    requests_allowed = (circuit_state_str == "CLOSED") or (
        circuit_state_str == "HALF_OPEN" and probe_count < probe_limit
    )

    # 4. Evaluate Webhook Security Check
    if webhook_verified is False:
        decision = RecoveryDecisionType.REQUIRE_HUMAN_REVIEW.value
        action = RecoveryAction.REQUEST_OPERATOR_APPROVAL.value
        risk_level = RecoveryRiskLevel.CRITICAL.value
        confidence = 99
        requires_human_review = True
        reason = "Inbound webhook signature verification failed; untrusted payload requires operator review before any recovery."
        next_step = "Operator must verify webhook authenticity in Human Action Center."
    
    # 5. Evaluate Terminal / Completed Payment States
    elif payment_state_str in ("RECOVERED", "SUCCESS"):
        decision = RecoveryDecisionType.BLOCK_RECOVERY.value
        action = RecoveryAction.NO_ACTION_REQUIRED.value
        risk_level = RecoveryRiskLevel.LOW.value
        confidence = 100
        requires_human_review = False
        reason = f"Payment is already in terminal {payment_state_str} state; no further recovery action is needed."
        next_step = "No action required. Transaction lifecycle complete."

    elif payment_state_str == "REFUNDED":
        decision = RecoveryDecisionType.BLOCK_RECOVERY.value
        action = RecoveryAction.NO_ACTION_REQUIRED.value
        risk_level = RecoveryRiskLevel.LOW.value
        confidence = 100
        requires_human_review = False
        reason = "Payment has already been REFUNDED; recovery action is not applicable."
        next_step = "Maintain terminal refund record."

    elif payment_state_str == "STOPPED":
        decision = RecoveryDecisionType.REQUIRE_HUMAN_REVIEW.value
        action = RecoveryAction.REQUEST_OPERATOR_APPROVAL.value
        risk_level = RecoveryRiskLevel.HIGH.value
        confidence = 95
        requires_human_review = True
        reason = "Payment recovery was explicitly STOPPED; human operator intervention is required to resume."
        next_step = "Review incident reason and approve restart in Human Action Center."

    # 6. Evaluate Human-In-The-Loop Requirement
    elif payment_state_str in ("HUMAN_REVIEW", "ESCALATED") or (case_data and case_data.get("requires_human_review")):
        decision = RecoveryDecisionType.REQUIRE_HUMAN_REVIEW.value
        action = RecoveryAction.REQUEST_OPERATOR_APPROVAL.value
        risk_level = RecoveryRiskLevel.HIGH.value if merchant_health_str == "UNHEALTHY" else RecoveryRiskLevel.ELEVATED.value
        confidence = 90
        requires_human_review = True
        reason = f"Payment state is {payment_state_str}; requires operator approval before dispatch."
        next_step = "Operator must review and approve recovery action in Human Action Center."

    # 7. Evaluate Circuit Breaker OPEN
    elif circuit_state_str == "OPEN":
        decision = RecoveryDecisionType.WAIT_FOR_MERCHANT_RECOVERY.value
        action = RecoveryAction.HALT_AND_WAIT.value
        risk_level = RecoveryRiskLevel.CRITICAL.value if payment_state_str in ("RECOVERING", "FAILED") else RecoveryRiskLevel.HIGH.value
        confidence = 98
        requires_human_review = False
        reason = f"Recovery blocked because merchant endpoint circuit breaker is OPEN with {cooldown_remaining}s cooldown remaining."
        next_step = "Wait for circuit breaker cooldown to expire before attempting recovery probe."

    # 8. Evaluate Circuit Breaker HALF_OPEN
    elif circuit_state_str == "HALF_OPEN":
        if probe_count < probe_limit:
            decision = RecoveryDecisionType.ALLOW_RECOVERY.value
            action = RecoveryAction.PROCEED_RECOVERY.value
            risk_level = RecoveryRiskLevel.HIGH.value
            confidence = 75
            requires_human_review = False
            reason = f"Admitting cautious probe recovery request ({probe_count + 1} of {probe_limit}) under HALF_OPEN circuit state."
            next_step = "Execute single recovery request through circuit gate as a probe."
        else:
            decision = RecoveryDecisionType.WAIT_FOR_MERCHANT_RECOVERY.value
            action = RecoveryAction.HALT_AND_WAIT.value
            risk_level = RecoveryRiskLevel.HIGH.value
            confidence = 90
            requires_human_review = False
            reason = f"Circuit breaker is HALF_OPEN and probe limit ({probe_limit}) is reached. Waiting for probe results."
            next_step = "Wait for existing recovery probes to confirm merchant endpoint health."

    # 9. Evaluate CLOSED Circuit with Merchant Health Matrix
    elif circuit_state_str == "CLOSED":
        if merchant_health_str == "HEALTHY":
            decision = RecoveryDecisionType.ALLOW_RECOVERY.value
            action = RecoveryAction.PROCEED_RECOVERY.value
            risk_level = RecoveryRiskLevel.LOW.value
            confidence = 95
            requires_human_review = False
            reason = "Recovery allowed because merchant endpoint is HEALTHY and circuit breaker is CLOSED."
            next_step = "Recovery request may proceed through the circuit gate."

        elif merchant_health_str == "DEGRADED":
            decision = RecoveryDecisionType.RETRY_RECOVERY.value
            action = RecoveryAction.RETRY_WITH_BACKOFF.value
            risk_level = RecoveryRiskLevel.ELEVATED.value
            confidence = 82
            requires_human_review = False
            reason = "Recovery permitted with elevated risk because merchant endpoint is DEGRADED."
            next_step = "Dispatch recovery request with cautious exponential backoff."

        elif merchant_health_str == "UNHEALTHY":
            decision = RecoveryDecisionType.DEFER_RECOVERY.value
            action = RecoveryAction.DEFER_AND_POLL.value
            risk_level = RecoveryRiskLevel.HIGH.value
            confidence = 88
            requires_human_review = False
            reason = "Recovery deferred because merchant endpoint is UNHEALTHY despite circuit being CLOSED."
            next_step = "Defer dispatch until merchant health improves or circuit trips."

        else: # NO_DATA
            decision = RecoveryDecisionType.ALLOW_RECOVERY.value
            action = RecoveryAction.PROCEED_RECOVERY.value
            risk_level = RecoveryRiskLevel.ELEVATED.value
            confidence = 70
            requires_human_review = False
            reason = "Recovery decision is conservative because merchant endpoint health data is NO_DATA."
            next_step = "Proceed with initial recovery attempt through circuit gate."

    # 10. Fallback safe handling
    else:
        decision = RecoveryDecisionType.REQUIRE_HUMAN_REVIEW.value
        action = RecoveryAction.REQUEST_OPERATOR_APPROVAL.value
        risk_level = RecoveryRiskLevel.HIGH.value
        confidence = 50
        requires_human_review = True
        reason = f"Ambiguous operational context (Circuit: {circuit_state_str}, Health: {merchant_health_str}); defaulting to human review."
        next_step = "Operator inspection required."

    decision_payload = {
        "decision": decision,
        "action": action,
        "confidence": confidence,
        "risk_level": risk_level,
        "reason": reason,
        "payment_id": clean_payment_id,
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "payment_state": payment_state_str,
        "merchant_health": merchant_health_str,
        "circuit_state": circuit_state_str,
        "requests_allowed": requests_allowed,
        "requires_human_review": requires_human_review,
        "recommended_next_step": next_step,
        "timestamp": now_iso
    }

    # Record safe decision telemetry (zero credentials or sensitive payloads)
    event_id = f"dec_{uuid.uuid4().hex[:10]}"
    telemetry_entry = {
        "event_id": event_id,
        **decision_payload
    }
    with _decision_lock:
        _decision_telemetry_log.append(telemetry_entry)
        if len(_decision_telemetry_log) > 200:
            _decision_telemetry_log.pop(0)

    return decision_payload


def get_decision_telemetry(payment_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves safe decision telemetry audit log."""
    with _decision_lock:
        if not payment_id:
            return list(_decision_telemetry_log)
        clean_id = str(payment_id).strip()
        return [e for e in _decision_telemetry_log if e.get("payment_id") == clean_id]


def clear_decision_telemetry() -> None:
    """Helper to reset in-memory decision telemetry for tests."""
    with _decision_lock:
        _decision_telemetry_log.clear()
