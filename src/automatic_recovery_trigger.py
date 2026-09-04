"""
RecoverIQ - Automatic Recovery Event Trigger Engine (Topic 2.2.2.11)

Event-driven trigger layer that automatically reacts to incoming payment incidents.
It evaluates recovery eligibility against the authoritative Recovery Decision Engine
and invokes the Recovery Orchestrator only when automated execution is permitted.

STRICT BOUNDARIES:
- Consumes decisions from src/recovery_decision_engine.py.
- Invokes recovery workflow via src/recovery_orchestrator.py.
- NEVER bypasses human approval for REQUIRE_HUMAN_REVIEW incidents.
- NEVER bypasses circuit breaker request gating.
- NEVER directly mutates payment state.
- Persists trigger telemetry to logs/automatic_recovery_trigger_events.json.
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
TRIGGER_EVENTS_LOG_PATH = os.path.join(LOGS_DIR, "automatic_recovery_trigger_events.json")

_trigger_lock = threading.Lock()
_active_triggering_payments: set = set()
_trigger_events_log: List[Dict[str, Any]] = []


class TriggerSource(str, Enum):
    """Origin of the payment recovery event."""
    WEBHOOK_INGESTION = "WEBHOOK_INGESTION"
    BATCH_INGESTION = "BATCH_INGESTION"
    INCIDENT_MONITOR = "INCIDENT_MONITOR"
    PERIODIC_HEALTH_PROBE = "PERIODIC_HEALTH_PROBE"
    API_TRIGGER = "API_TRIGGER"


class TriggerAction(str, Enum):
    """Action taken by the trigger engine."""
    ORCHESTRATOR_INVOKED = "ORCHESTRATOR_INVOKED"
    ROUTED_TO_HUMAN_ACTION_CENTER = "ROUTED_TO_HUMAN_ACTION_CENTER"
    DEFERRED_RESILIENCE_PROTECTION = "DEFERRED_RESILIENCE_PROTECTION"
    BLOCKED_BY_CIRCUIT = "BLOCKED_BY_CIRCUIT"
    IGNORED_ALREADY_COMPLETED = "IGNORED_ALREADY_COMPLETED"
    HALTED_UNTRUSTED_WEBHOOK = "HALTED_UNTRUSTED_WEBHOOK"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


def _load_persisted_trigger_events() -> List[Dict[str, Any]]:
    if os.path.exists(TRIGGER_EVENTS_LOG_PATH):
        try:
            with open(TRIGGER_EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_persisted_trigger_events(events: List[Dict[str, Any]]) -> None:
    try:
        with open(TRIGGER_EVENTS_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
    except Exception:
        pass


def record_trigger_event(
    payment_id: str,
    merchant_id: str,
    endpoint: str,
    event_type: str,
    trigger_source: str,
    decision: str,
    action: str,
    reason: str,
    risk_level: str = "LOW",
    execution_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Records a safe automatic recovery trigger event (zero credentials or raw payloads stored).
    """
    event = {
        "event_id": f"trg_{uuid.uuid4().hex[:10]}",
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "endpoint": endpoint,
        "event_type": event_type,
        "trigger_source": trigger_source,
        "decision": decision,
        "action": action,
        "risk_level": risk_level,
        "reason": reason,
        "execution_result": execution_result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    with _trigger_lock:
        if not _trigger_events_log and os.path.exists(TRIGGER_EVENTS_LOG_PATH):
            _trigger_events_log.extend(_load_persisted_trigger_events())
        _trigger_events_log.append(event)
        if len(_trigger_events_log) > 300:
            _trigger_events_log.pop(0)
        _save_persisted_trigger_events(_trigger_events_log)

    # Correlate into Unified Recovery Audit Timeline (Topic 2.2.2.14)
    try:
        from src.recovery_audit import record_recovery_audit_event, AuditEventType
        record_recovery_audit_event(
            payment_id=payment_id,
            event_type=AuditEventType.AUTOMATIC_RECOVERY_TRIGGERED.value,
            actor_type="AI_AGENT",
            source="AUTOMATIC_RECOVERY_TRIGGER",
            status=action,
            reason=reason,
            risk_level=risk_level,
            merchant_id=merchant_id,
            endpoint=endpoint,
            correlation_id=event.get("event_id")
        )
    except Exception:
        pass

    return event


def trigger_automatic_recovery_if_eligible(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    case_data: Optional[Dict[str, Any]] = None,
    webhook_verified: Optional[bool] = None,
    trigger_source: str = "WEBHOOK_INGESTION"
) -> Dict[str, Any]:
    """
    Topic 2.2.2.11 - Automatic Event Trigger Entry Point.
    Evaluates recovery eligibility and automatically triggers recovery orchestration
    when the decision allows automated recovery, without operator manual clicking.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Deduplication / Concurrency guard
    with _trigger_lock:
        if clean_payment_id in _active_triggering_payments:
            return {
                "triggered": False,
                "action": "CONCURRENT_TRIGGER_SUPPRESSED",
                "payment_id": clean_payment_id,
                "reason": f"Automatic trigger for payment {clean_payment_id} is already in flight.",
                "timestamp": now_iso
            }
        _active_triggering_payments.add(clean_payment_id)

    try:
        # 2. Evaluate resilience recovery decision
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

        # 3. Check for Terminal / Already Completed Payment States
        if payment_state in ("RECOVERED", "SUCCESS", "REFUNDED"):
            event = record_trigger_event(
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="AUTOMATIC_RECOVERY_TRIGGER",
                trigger_source=trigger_source,
                decision=decision_val,
                action=TriggerAction.IGNORED_ALREADY_COMPLETED.value,
                reason=f"Payment is already in terminal {payment_state} state; trigger ignored.",
                risk_level=risk_level
            )
            return {
                "triggered": False,
                "eligible": False,
                "action": TriggerAction.IGNORED_ALREADY_COMPLETED.value,
                "decision": decision_val,
                "payment_state": payment_state,
                "reason": f"Payment is already in terminal {payment_state} state.",
                "trigger_event": event,
                "timestamp": now_iso
            }

        # 4. Check Webhook Authentication Failures
        if webhook_verified is False:
            event = record_trigger_event(
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="AUTOMATIC_RECOVERY_TRIGGER",
                trigger_source=trigger_source,
                decision=decision_val,
                action=TriggerAction.HALTED_UNTRUSTED_WEBHOOK.value,
                reason="Inbound webhook signature verification failed; automatic trigger halted.",
                risk_level="CRITICAL"
            )
            return {
                "triggered": False,
                "eligible": False,
                "action": TriggerAction.HALTED_UNTRUSTED_WEBHOOK.value,
                "decision": decision_val,
                "payment_state": payment_state,
                "reason": "Webhook verification failed. Automated execution strictly prohibited.",
                "trigger_event": event,
                "timestamp": now_iso
            }

        # 5. Check Human-In-The-Loop Requirement
        if requires_human or decision_val == RecoveryDecisionType.REQUIRE_HUMAN_REVIEW.value:
            # Create human review request (Topic 2.2.2.16)
            try:
                from src.recovery_human_review import create_or_get_human_review_request
                create_or_get_human_review_request(
                    payment_id=clean_payment_id,
                    merchant_id=clean_merchant_id,
                    endpoint=clean_endpoint,
                    reason=decision_reason or "Human operator approval required; routing to Human Action Center.",
                    risk_level=risk_level,
                    decision=decision_val,
                    payment_state=payment_state,
                    merchant_health=merchant_health,
                    circuit_state=circuit_state
                )
            except Exception:
                pass

            event = record_trigger_event(
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="AUTOMATIC_RECOVERY_TRIGGER",
                trigger_source=trigger_source,
                decision=decision_val,
                action=TriggerAction.ROUTED_TO_HUMAN_ACTION_CENTER.value,
                reason=decision_reason or "Human operator approval required; routing to Human Action Center.",
                risk_level=risk_level
            )
            return {
                "triggered": False,
                "eligible": False,
                "action": TriggerAction.ROUTED_TO_HUMAN_ACTION_CENTER.value,
                "decision": decision_val,
                "payment_state": payment_state,
                "reason": "Payment requires explicit operator confirmation before outbound recovery.",
                "trigger_event": event,
                "timestamp": now_iso
            }

        # 6. Check Circuit Breaker Open / Deferral
        if decision_val in (RecoveryDecisionType.WAIT_FOR_MERCHANT_RECOVERY.value, RecoveryDecisionType.DEFER_RECOVERY.value):
            action_type = TriggerAction.BLOCKED_BY_CIRCUIT.value if "OPEN" in decision_reason else TriggerAction.DEFERRED_RESILIENCE_PROTECTION.value
            event = record_trigger_event(
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="AUTOMATIC_RECOVERY_TRIGGER",
                trigger_source=trigger_source,
                decision=decision_val,
                action=action_type,
                reason=decision_reason,
                risk_level=risk_level
            )
            return {
                "triggered": False,
                "eligible": False,
                "action": action_type,
                "decision": decision_val,
                "payment_state": payment_state,
                "reason": decision_reason,
                "trigger_event": event,
                "timestamp": now_iso
            }

        # 7. Check Blocked
        if decision_val == RecoveryDecisionType.BLOCK_RECOVERY.value:
            event = record_trigger_event(
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="AUTOMATIC_RECOVERY_TRIGGER",
                trigger_source=trigger_source,
                decision=decision_val,
                action=TriggerAction.NOT_ELIGIBLE.value,
                reason=decision_reason,
                risk_level=risk_level
            )
            return {
                "triggered": False,
                "eligible": False,
                "action": TriggerAction.NOT_ELIGIBLE.value,
                "decision": decision_val,
                "payment_state": payment_state,
                "reason": decision_reason,
                "trigger_event": event,
                "timestamp": now_iso
            }

        # 8. Automated Execution Permitted -> Invoke Recovery Orchestrator
        if decision_val in (RecoveryDecisionType.ALLOW_RECOVERY.value, RecoveryDecisionType.RETRY_RECOVERY.value):
            try:
                from src.recovery_orchestrator import orchestrate_payment_recovery
            except ImportError:
                from recovery_orchestrator import orchestrate_payment_recovery

            orchestration_outcome = orchestrate_payment_recovery(
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                case_data=case_data,
                webhook_verified=webhook_verified,
                idempotency_key=f"trg_{clean_payment_id}_{clean_merchant_id}_{uuid.uuid4().hex[:8]}"
            )

            event = record_trigger_event(
                payment_id=clean_payment_id,
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint,
                event_type="AUTOMATIC_RECOVERY_TRIGGER",
                trigger_source=trigger_source,
                decision=decision_val,
                action=TriggerAction.ORCHESTRATOR_INVOKED.value,
                reason="Automatic recovery triggered and executed through orchestrator.",
                risk_level=risk_level,
                execution_result=orchestration_outcome
            )

            return {
                "triggered": True,
                "eligible": True,
                "action": TriggerAction.ORCHESTRATOR_INVOKED.value,
                "decision": decision_val,
                "payment_state": orchestration_outcome.get("payment_state", payment_state),
                "reason": "Automatic recovery executed successfully via orchestrator pipeline.",
                "execution_result": orchestration_outcome,
                "trigger_event": event,
                "timestamp": now_iso
            }

        # 9. Fallback safe denial
        event = record_trigger_event(
            payment_id=clean_payment_id,
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            event_type="AUTOMATIC_RECOVERY_TRIGGER",
            trigger_source=trigger_source,
            decision=decision_val,
            action=TriggerAction.NOT_ELIGIBLE.value,
            reason=f"Unhandled decision status {decision_val}; trigger withheld.",
            risk_level=risk_level
        )
        return {
            "triggered": False,
            "eligible": False,
            "action": TriggerAction.NOT_ELIGIBLE.value,
            "decision": decision_val,
            "reason": f"Decision {decision_val} is not eligible for automated triggering.",
            "trigger_event": event,
            "timestamp": now_iso
        }

    finally:
        with _trigger_lock:
            _active_triggering_payments.discard(clean_payment_id)


def get_automatic_recovery_telemetry(payment_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves safe trigger audit telemetry."""
    with _trigger_lock:
        if not _trigger_events_log and os.path.exists(TRIGGER_EVENTS_LOG_PATH):
            _trigger_events_log.extend(_load_persisted_trigger_events())
        if not payment_id:
            return list(_trigger_events_log)
        clean_id = str(payment_id).strip()
        return [e for e in _trigger_events_log if e.get("payment_id") == clean_id]


def reset_trigger_telemetry() -> None:
    """Helper to reset in-memory trigger telemetry and persistent file for testing."""
    with _trigger_lock:
        _active_triggering_payments.clear()
        _trigger_events_log.clear()
        if os.path.exists(TRIGGER_EVENTS_LOG_PATH):
            try:
                os.remove(TRIGGER_EVENTS_LOG_PATH)
            except Exception:
                pass
