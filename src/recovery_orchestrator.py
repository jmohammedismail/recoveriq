"""
RecoverIQ - Automatic Recovery Orchestration Engine (Topic 2.2.2.10)

Coordinates recovery execution by integrating:
  1. Authoritative payment state (src/state_machine.py)
  2. Inbound webhook authentication (src/webhook_security.py)
  3. Merchant endpoint health telemetry (src/merchant_health.py)
  4. Outbound circuit breaker request gate (src/circuit_breaker.py)
  5. Resilience recovery decision engine (src/recovery_decision_engine.py)

IMPORTANT SAFETY BOUNDARIES:
- The orchestrator consumes decisions from src/recovery_decision_engine.py.
- The orchestrator NEVER bypasses human approval for REQUIRE_HUMAN_REVIEW cases.
- Outbound network requests MUST pass check_circuit_request_allowed() immediately before execution.
- Payment state transitions MUST use transition_payment_state() with full attribution (actor_type="AI_AGENT", source="RECOVERY_ORCHESTRATOR").
- Execution results are persisted to logs/recovery_orchestration_events.json.
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
ORCHESTRATION_LOG_PATH = os.path.join(LOGS_DIR, "recovery_orchestration_events.json")

DEFAULT_MAX_RECOVERY_ATTEMPTS = 3
DEFAULT_BASE_BACKOFF_SEC = 2.0

_orchestrator_lock = threading.Lock()
_active_in_flight_payments: set = set()
_orchestration_events_log: List[Dict[str, Any]] = []
_payment_attempt_counters: Dict[str, int] = {}


class RecoveryWorkflowOutcome(str, Enum):
    """Authoritative workflow outcome classifications."""
    EXECUTE_RECOVERY = "EXECUTE_RECOVERY"
    WAIT = "WAIT"
    BLOCKED = "BLOCKED"
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    FAILED = "FAILED"


def _load_persisted_orchestration_events() -> List[Dict[str, Any]]:
    if os.path.exists(ORCHESTRATION_LOG_PATH):
        try:
            with open(ORCHESTRATION_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_persisted_orchestration_events(events: List[Dict[str, Any]]) -> None:
    try:
        with open(ORCHESTRATION_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
    except Exception:
        pass


def record_orchestration_event(
    execution_id: str,
    payment_id: str,
    merchant_id: str,
    endpoint: str,
    event_type: str,
    outcome: str,
    decision: str,
    reason: str,
    attempt_number: int = 1,
    circuit_state: str = "CLOSED",
    merchant_health: str = "HEALTHY",
    failure_category: Optional[str] = None,
    actor_type: str = "AI_AGENT",
    source: str = "RECOVERY_ORCHESTRATOR"
) -> Dict[str, Any]:
    """
    Records a safe orchestration event to memory and disk (zero credentials or raw payloads stored).
    """
    event = {
        "event_id": f"orch_evt_{uuid.uuid4().hex[:10]}",
        "execution_id": execution_id,
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "endpoint": endpoint,
        "attempt_number": attempt_number,
        "event_type": event_type,
        "outcome": outcome,
        "decision": decision,
        "circuit_state": circuit_state,
        "merchant_health": merchant_health,
        "failure_category": failure_category,
        "reason": reason,
        "actor_type": actor_type,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    with _orchestrator_lock:
        if not _orchestration_events_log and os.path.exists(ORCHESTRATION_LOG_PATH):
            _orchestration_events_log.extend(_load_persisted_orchestration_events())
        _orchestration_events_log.append(event)
        if len(_orchestration_events_log) > 300:
            _orchestration_events_log.pop(0)
        _save_persisted_orchestration_events(_orchestration_events_log)

    # Correlate into Unified Recovery Audit Timeline (Topic 2.2.2.14)
    try:
        from src.recovery_audit import record_recovery_audit_event, AuditEventType
        record_recovery_audit_event(
            payment_id=payment_id,
            event_type=event_type,
            actor_type=actor_type,
            source=source,
            status=outcome,
            reason=reason,
            merchant_id=merchant_id,
            endpoint=endpoint,
            correlation_id=event.get("event_id"),
            execution_id=execution_id
        )
    except Exception:
        pass

    return event


def orchestrate_payment_recovery(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    max_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS,
    idempotency_key: Optional[str] = None,
    case_data: Optional[Dict[str, Any]] = None,
    webhook_verified: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.10 - Core Automatic Recovery Orchestration Workflow.
    Coordinates decision evaluation, human review safety, circuit request gating,
    network execution, health telemetry logging, and authoritative payment state transitions.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    exec_id = f"exec_{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Concurrency Guard: prevent simultaneous double execution for the same payment
    with _orchestrator_lock:
        if clean_payment_id in _active_in_flight_payments:
            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.WAIT.value,
                "decision": "CONCURRENT_EXECUTION_IN_FLIGHT",
                "risk_level": "ELEVATED",
                "network_attempted": False,
                "requires_human_review": False,
                "reason": f"Payment {clean_payment_id} is already undergoing recovery in another thread/process.",
                "next_step": "Wait for active recovery workflow to complete.",
                "timestamp": now_iso
            }
        _active_in_flight_payments.add(clean_payment_id)
        current_attempt = _payment_attempt_counters.get(clean_payment_id, 0) + 1
        _payment_attempt_counters[clean_payment_id] = current_attempt

    try:
        # 2. Evaluate Resilience Recovery Decision
        try:
            from src.recovery_decision_engine import evaluate_recovery_decision, RecoveryDecisionType
        except ImportError:
            from recovery_decision_engine import evaluate_recovery_decision, RecoveryDecisionType

        decision_obj = evaluate_recovery_decision(
            payment_id=clean_payment_id,
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            case_data=case_data,
            webhook_verified=webhook_verified
        )

        decision_val = decision_obj.get("decision", "REQUIRE_HUMAN_REVIEW")
        risk_level = decision_obj.get("risk_level", "LOW")
        decision_reason = decision_obj.get("reason", "")
        requires_human = decision_obj.get("requires_human_review", False)
        payment_state = decision_obj.get("payment_state", "PENDING")
        merchant_health = decision_obj.get("merchant_health", "NO_DATA")
        circuit_state = decision_obj.get("circuit_state", "CLOSED")

        record_orchestration_event(
            execution_id=exec_id,
            payment_id=clean_payment_id,
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            event_type="RECOVERY_DECISION_EVALUATED",
            outcome="EVALUATED",
            decision=decision_val,
            reason=decision_reason,
            attempt_number=current_attempt,
            circuit_state=circuit_state,
            merchant_health=merchant_health
        )

        # 3. Check for Terminal / Already Completed Payment States
        if payment_state in ("RECOVERED", "SUCCESS", "REFUNDED"):
            record_orchestration_event(
                execution_id=exec_id,
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="RECOVERY_ALREADY_COMPLETED",
                outcome=RecoveryWorkflowOutcome.ALREADY_COMPLETED.value,
                decision=decision_val,
                reason=f"Payment is in terminal state ({payment_state}); no outbound recovery needed.",
                attempt_number=current_attempt,
                circuit_state=circuit_state,
                merchant_health=merchant_health
            )
            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.ALREADY_COMPLETED.value,
                "decision": decision_val,
                "risk_level": risk_level,
                "payment_state": payment_state,
                "circuit_state": circuit_state,
                "merchant_health": merchant_health,
                "attempt_number": current_attempt,
                "max_attempts": max_attempts,
                "network_attempted": False,
                "requires_human_review": False,
                "reason": f"Payment is already in terminal {payment_state} state.",
                "next_step": "Transaction lifecycle complete. No action required.",
                "timestamp": now_iso
            }

        # 4. Enforce Human-In-The-Loop Safety Gate
        if requires_human or decision_val == RecoveryDecisionType.REQUIRE_HUMAN_REVIEW.value:
            record_orchestration_event(
                execution_id=exec_id,
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="RECOVERY_REQUIRES_HUMAN",
                outcome=RecoveryWorkflowOutcome.REQUIRE_HUMAN_REVIEW.value,
                decision=decision_val,
                reason=decision_reason or "Human operator approval required.",
                attempt_number=current_attempt,
                circuit_state=circuit_state,
                merchant_health=merchant_health
            )
            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.REQUIRE_HUMAN_REVIEW.value,
                "decision": decision_val,
                "risk_level": risk_level,
                "payment_state": payment_state,
                "circuit_state": circuit_state,
                "merchant_health": merchant_health,
                "attempt_number": current_attempt,
                "max_attempts": max_attempts,
                "network_attempted": False,
                "requires_human_review": True,
                "reason": decision_reason or "Human operator approval is required before execution.",
                "next_step": "Route to Human Action Center for operator confirmation.",
                "timestamp": now_iso
            }

        # 5. Check Retry Limit
        if current_attempt > max_attempts:
            record_orchestration_event(
                execution_id=exec_id,
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="RECOVERY_ATTEMPT_LIMIT_EXCEEDED",
                outcome=RecoveryWorkflowOutcome.FAILED.value,
                decision=decision_val,
                reason=f"Recovery attempt limit exceeded ({current_attempt}/{max_attempts}).",
                attempt_number=current_attempt,
                circuit_state=circuit_state,
                merchant_health=merchant_health
            )
            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.FAILED.value,
                "decision": decision_val,
                "risk_level": "HIGH",
                "payment_state": payment_state,
                "circuit_state": circuit_state,
                "merchant_health": merchant_health,
                "attempt_number": current_attempt,
                "max_attempts": max_attempts,
                "network_attempted": False,
                "requires_human_review": True,
                "reason": f"Maximum recovery attempts reached ({max_attempts}). Escalating for review.",
                "next_step": "Operator review required in Human Action Center.",
                "timestamp": now_iso
            }

        # 6. Check Decision Workflow Outcomes: Defer / Wait
        if decision_val == RecoveryDecisionType.WAIT_FOR_MERCHANT_RECOVERY.value:
            record_orchestration_event(
                execution_id=exec_id,
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="RECOVERY_WAITING_FOR_CIRCUIT",
                outcome=RecoveryWorkflowOutcome.WAIT.value,
                decision=decision_val,
                reason=decision_reason,
                attempt_number=current_attempt,
                circuit_state=circuit_state,
                merchant_health=merchant_health
            )
            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.WAIT.value,
                "decision": decision_val,
                "risk_level": risk_level,
                "payment_state": payment_state,
                "circuit_state": circuit_state,
                "merchant_health": merchant_health,
                "attempt_number": current_attempt,
                "max_attempts": max_attempts,
                "network_attempted": False,
                "requires_human_review": False,
                "reason": decision_reason,
                "next_step": "Wait for circuit breaker cooldown or probe resolution.",
                "timestamp": now_iso
            }

        if decision_val == RecoveryDecisionType.DEFER_RECOVERY.value:
            record_orchestration_event(
                execution_id=exec_id,
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="RECOVERY_WAITING_FOR_MERCHANT",
                outcome=RecoveryWorkflowOutcome.WAIT.value,
                decision=decision_val,
                reason=decision_reason,
                attempt_number=current_attempt,
                circuit_state=circuit_state,
                merchant_health=merchant_health
            )
            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.WAIT.value,
                "decision": decision_val,
                "risk_level": risk_level,
                "payment_state": payment_state,
                "circuit_state": circuit_state,
                "merchant_health": merchant_health,
                "attempt_number": current_attempt,
                "max_attempts": max_attempts,
                "network_attempted": False,
                "requires_human_review": False,
                "reason": decision_reason,
                "next_step": "Defer dispatch until merchant health metrics improve.",
                "timestamp": now_iso
            }

        # 7. Authoritative Circuit Request Gate Check (immediately before network execution)
        try:
            from src.circuit_breaker import check_circuit_request_allowed
        except ImportError:
            from circuit_breaker import check_circuit_request_allowed

        gate_check = check_circuit_request_allowed(
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            payment_id=clean_payment_id
        )

        if not gate_check.get("allowed"):
            err_reason = gate_check.get("error", "CIRCUIT_BLOCKED")
            record_orchestration_event(
                execution_id=exec_id,
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="RECOVERY_REQUEST_BLOCKED",
                outcome=RecoveryWorkflowOutcome.BLOCKED.value,
                decision=decision_val,
                reason=f"Circuit request gate blocked interaction: {err_reason}",
                attempt_number=current_attempt,
                circuit_state=gate_check.get("circuit_state", "OPEN"),
                merchant_health=merchant_health
            )
            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.BLOCKED.value,
                "decision": decision_val,
                "risk_level": "CRITICAL" if gate_check.get("circuit_state") == "OPEN" else "HIGH",
                "payment_state": payment_state,
                "circuit_state": gate_check.get("circuit_state", "OPEN"),
                "merchant_health": merchant_health,
                "attempt_number": current_attempt,
                "max_attempts": max_attempts,
                "network_attempted": False,
                "requires_human_review": False,
                "reason": f"Circuit breaker gate prevented outbound request ({err_reason}).",
                "next_step": "Wait for circuit breaker cooldown before retrying.",
                "timestamp": now_iso
            }

        is_probe = gate_check.get("is_probe", False)
        gen = gate_check.get("circuit_generation", 0)

        # 8. Outbound Network Execution & Measurement
        start_time = time.monotonic()
        try:
            # Simulate real recovery order-sync interaction
            status_code = 200
            network_success = True
            failure_cat = "SUCCESS"
        except Exception as net_err:
            status_code = 500
            network_success = False
            failure_cat = "SERVER_ERROR"

        latency_ms = round((time.monotonic() - start_time) * 1000, 2)

        # 9. Invoke Authoritative Post-Recovery Verification Layer (Topic 2.2.2.13)
        try:
            from src.recovery_verification import verify_recovery_outcome, VerificationOutcome
        except ImportError:
            from recovery_verification import verify_recovery_outcome, VerificationOutcome

        merchant_resp_sim = {
            "order_synced": network_success,
            "order_id": case_data.get("order_id") if case_data else f"ord_{clean_payment_id}"
        }

        verification = verify_recovery_outcome(
            payment_id=clean_payment_id,
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            network_status_code=status_code,
            merchant_response=merchant_resp_sim,
            case_data=case_data,
            webhook_verified=webhook_verified,
            circuit_state=gate_check.get("circuit_state", "CLOSED"),
            merchant_health=merchant_health
        )
        v_status = verification.get("verification_status", VerificationOutcome.VERIFICATION_FAILED.value)

        # 10. Record Endpoint Health Observation (Topic 2.2.1 & 2.2.2.8)
        # Only true verified success reports SUCCESS to health telemetry
        try:
            from src.merchant_health import record_endpoint_observation
        except ImportError:
            from merchant_health import record_endpoint_observation

        record_endpoint_observation(
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            status_code=status_code if v_status == VerificationOutcome.VERIFIED_SUCCESS.value else (500 if not network_success else 200),
            latency_ms=latency_ms,
            timed_out=(status_code == 504),
            retry_attempt=current_attempt,
            payment_id=clean_payment_id
        )

        # If this was a probe in HALF_OPEN, record probe outcome
        if is_probe:
            try:
                from src.circuit_breaker import record_half_open_probe_result
            except ImportError:
                from circuit_breaker import record_half_open_probe_result
            record_half_open_probe_result(
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                success=(v_status == VerificationOutcome.VERIFIED_SUCCESS.value),
                failure_category=failure_cat if v_status == VerificationOutcome.VERIFIED_SUCCESS.value else "VERIFICATION_FAILURE",
                payment_id=clean_payment_id,
                circuit_generation=gen
            )

        # 11. Authoritative State Machine Transitions Based on Verified Outcome
        if v_status == VerificationOutcome.VERIFIED_SUCCESS.value:
            try:
                from src.state_machine import transition_payment_state, PaymentState
            except ImportError:
                from state_machine import transition_payment_state, PaymentState

            trans_res = transition_payment_state(
                payment_id=clean_payment_id,
                next_state=PaymentState.RECOVERED,
                reason="Post-recovery verification confirmed order sync in merchant database.",
                actor_type="AI_AGENT",
                actor_id="recovery_orchestrator",
                source="RECOVERY_ORCHESTRATOR",
                case_data=case_data
            )
            final_payment_state = trans_res.get("current_state", "RECOVERED") if trans_res.get("success") else payment_state

            record_orchestration_event(
                execution_id=exec_id,
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="RECOVERY_COMPLETED",
                outcome=RecoveryWorkflowOutcome.EXECUTE_RECOVERY.value,
                decision=decision_val,
                reason=f"Recovery executed and verified successfully (HTTP {status_code} in {latency_ms}ms).",
                attempt_number=current_attempt,
                circuit_state=gate_check.get("circuit_state", "CLOSED"),
                merchant_health=merchant_health,
                failure_category="SUCCESS"
            )

            # Topic 2.2.2.20 - Automatic Incident Closure Trigger
            try:
                from src.incident_closure import close_incident_if_qualified
                close_incident_if_qualified(
                    payment_id=clean_payment_id,
                    merchant_id=clean_merchant_id,
                    endpoint=clean_endpoint,
                    closure_reason="Automatic incident closure triggered following verified recovery completion."
                )
            except Exception:
                pass

            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.EXECUTE_RECOVERY.value,
                "decision": decision_val,
                "risk_level": risk_level,
                "payment_state": final_payment_state,
                "circuit_state": gate_check.get("circuit_state", "CLOSED"),
                "merchant_health": merchant_health,
                "verification_status": v_status,
                "attempt_number": current_attempt,
                "max_attempts": max_attempts,
                "network_attempted": True,
                "network_status_code": status_code,
                "latency_ms": latency_ms,
                "requires_human_review": False,
                "reason": f"Automatic recovery executed and verified successfully (HTTP {status_code}).",
                "next_step": "Recovery verified. Transaction marked RECOVERED.",
                "timestamp": now_iso
            }
        elif v_status == VerificationOutcome.VERIFICATION_PENDING.value:
            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.WAIT.value,
                "decision": decision_val,
                "risk_level": risk_level,
                "payment_state": "RECOVERING",
                "circuit_state": gate_check.get("circuit_state", "CLOSED"),
                "merchant_health": merchant_health,
                "verification_status": v_status,
                "attempt_number": current_attempt,
                "max_attempts": max_attempts,
                "network_attempted": True,
                "network_status_code": status_code,
                "latency_ms": latency_ms,
                "requires_human_review": False,
                "reason": verification.get("verification_reason", "Awaiting merchant verification confirmation."),
                "next_step": verification.get("recommended_next_step", "Await verification callback."),
                "timestamp": now_iso
            }
        else:
            record_orchestration_event(
                execution_id=exec_id,
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="RECOVERY_ATTEMPT_FAILED",
                outcome=RecoveryWorkflowOutcome.FAILED.value,
                decision=decision_val,
                reason=verification.get("verification_reason", f"Recovery network call failed (HTTP {status_code})."),
                attempt_number=current_attempt,
                circuit_state=gate_check.get("circuit_state", "CLOSED"),
                merchant_health=merchant_health,
                failure_category=failure_cat
            )
            return {
                "execution_id": exec_id,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "outcome": RecoveryWorkflowOutcome.FAILED.value,
                "decision": decision_val,
                "risk_level": "HIGH",
                "payment_state": payment_state,
                "circuit_state": gate_check.get("circuit_state", "CLOSED"),
                "merchant_health": merchant_health,
                "verification_status": v_status,
                "attempt_number": current_attempt,
                "max_attempts": max_attempts,
                "network_attempted": True,
                "network_status_code": status_code,
                "latency_ms": latency_ms,
                "requires_human_review": False,
                "reason": verification.get("verification_reason", f"Recovery failed with HTTP {status_code}."),
                "next_step": "Evaluate retry with backoff or route to operator review.",
                "timestamp": now_iso
            }

    finally:
        with _orchestrator_lock:
            _active_in_flight_payments.discard(clean_payment_id)


def get_orchestration_telemetry(payment_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves safe orchestration telemetry logs."""
    with _orchestrator_lock:
        if not _orchestration_events_log and os.path.exists(ORCHESTRATION_LOG_PATH):
            _orchestration_events_log.extend(_load_persisted_orchestration_events())
        if not payment_id:
            return list(_orchestration_events_log)
        clean_id = str(payment_id).strip()
        return [e for e in _orchestration_events_log if e.get("payment_id") == clean_id]


def reset_orchestrator_state() -> None:
    """Helper to reset in-memory orchestration state and telemetry file for testing."""
    with _orchestrator_lock:
        _active_in_flight_payments.clear()
        _orchestration_events_log.clear()
        _payment_attempt_counters.clear()
        if os.path.exists(ORCHESTRATION_LOG_PATH):
            try:
                os.remove(ORCHESTRATION_LOG_PATH)
            except Exception:
                pass
