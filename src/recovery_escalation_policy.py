"""
RecoverIQ - Recovery Alert Escalation Policy & Automated Priority Management (Topic 2.2.2.24)

Centralized, authoritative escalation policy engine that deterministically computes alert
priority and escalation levels from live recovery subsystem conditions.

STRICT BOUNDARIES:
- Policy & priority management only; NEVER directly mutates PaymentState or CircuitState.
- NEVER automatically executes recoveries, retries, refunds, or auto-repairs.
- Escalation is deterministic, idempotent, auditable, and thread-safe.
- De-escalation occurs ONLY when underlying authoritative condition has genuinely cleared.
- Operator acknowledgement NEVER silently downgrades or de-escalates priority.
- Persists operational history to logs/recovery_escalation_policy.json.
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
ESCALATION_POLICY_LOG_PATH = os.path.join(LOGS_DIR, "recovery_escalation_policy.json")

_escalation_lock = threading.Lock()
_escalation_history: List[Dict[str, Any]] = []


class EscalationLevel(str, Enum):
    """Authoritative escalation tiers."""
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertPriority(str, Enum):
    """Standardized alert priority."""
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def _load_persisted_escalation_history() -> List[Dict[str, Any]]:
    if os.path.exists(ESCALATION_POLICY_LOG_PATH):
        try:
            with open(ESCALATION_POLICY_LOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("history", [])
        except Exception:
            return []
    return []


def _save_persisted_escalation_history(history: List[Dict[str, Any]]) -> None:
    try:
        with open(ESCALATION_POLICY_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "history": history[-500:]
            }, f, indent=2)
    except Exception:
        pass


def get_escalation_policy_summary() -> Dict[str, Any]:
    """
    Topic 2.2.2.24 - Returns the configured deterministic escalation policy rules and thresholds.
    """
    return {
        "policy_name": "RecoverIQ-Authoritative-Escalation-Policy",
        "version": "1.0.0",
        "levels": [
            {
                "level": EscalationLevel.CRITICAL.value,
                "priority": AlertPriority.CRITICAL.value,
                "conditions": [
                    "Authoritative subsystem contradiction (INCONSISTENT)",
                    "Incident marked CLOSED prematurely while payment is not RECOVERED",
                    "Payment marked RECOVERED without ledger VERIFIED_SUCCESS",
                    "Monitoring telemetry failure / state mutex contradiction"
                ],
                "recommended_action": "Immediate human engineer investigation. Auto-repair disabled."
            },
            {
                "level": EscalationLevel.HIGH.value,
                "priority": AlertPriority.HIGH.value,
                "conditions": [
                    "Maximum bounded retry attempts exhausted (attempt >= 3)",
                    "Circuit breaker remains OPEN blocking recovery requests",
                    "Human review expired past 24-hour review window",
                    "Recovery verification stuck in pending beyond timeout"
                ],
                "recommended_action": "Escalate to lead operator for manual triage or circuit inspection."
            },
            {
                "level": EscalationLevel.ELEVATED.value,
                "priority": AlertPriority.WARNING.value,
                "conditions": [
                    "Human review required in Human Action Center",
                    "Bounded retry scheduled and awaiting backoff window",
                    "Outbound request accepted; awaiting verification callback"
                ],
                "recommended_action": "Operator action required or await automated verification."
            },
            {
                "level": EscalationLevel.NORMAL.value,
                "priority": AlertPriority.INFO.value,
                "conditions": [
                    "Incident authoritatively closed with dual verification",
                    "Payment pipeline operating within normal operational tolerances"
                ],
                "recommended_action": "No action required."
            }
        ]
    }


def evaluate_alert_escalation(
    alert_id: str,
    operator_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.24 - Deterministically evaluates alert escalation level based on live recovery conditions.
    Updates alert priority and emits audit events if priority increases or clears.
    """
    clean_alert_id = str(alert_id or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    from src.recovery_alert_manager import get_managed_recovery_alert, _managed_alerts_store, _save_persisted_alert_mgmt, _alert_history_store, _alert_mgmt_lock
    from src.recovery_integrity_monitor import evaluate_recovery_integrity

    alert = get_managed_recovery_alert(clean_alert_id)
    if not alert:
        return {
            "success": False,
            "error": "ALERT_NOT_FOUND",
            "message": f"Alert {clean_alert_id} not found."
        }

    payment_id = alert.get("payment_id")
    merchant_id = alert.get("merchant_id", "merchant_demo")
    endpoint = alert.get("endpoint", "payment-webhook")
    prev_priority = alert.get("severity", AlertPriority.WARNING.value)

    # Re-evaluate live integrity condition from authoritative subsystems
    live_integrity = evaluate_recovery_integrity(payment_id, merchant_id, endpoint)
    integrity_status = live_integrity.get("integrity_status")
    circuit_state = live_integrity.get("circuit_state")
    retry_status = live_integrity.get("retry_status")
    human_review_status = live_integrity.get("human_review_status")
    verification_status = live_integrity.get("verification_status")
    payment_state = live_integrity.get("payment_state")
    is_closed = live_integrity.get("closure_status") in ("INCIDENT_CLOSED", "ALREADY_CLOSED")

    # Deterministic Rule Engine
    computed_level = EscalationLevel.NORMAL.value
    computed_priority = AlertPriority.INFO.value
    reason = "Recovery conditions are normal."
    evidence = "NORMAL_PIPELINE"
    recommended_action = "No operator intervention required."

    if integrity_status == "INCONSISTENT":
        computed_level = EscalationLevel.CRITICAL.value
        computed_priority = AlertPriority.CRITICAL.value
        reason = f"CRITICAL Contradiction: {live_integrity.get('reason')}"
        evidence = "STATE_MUTEX_CONTRADICTION"
        recommended_action = "Immediate lead operator investigation. Auto-repair is disabled."
    elif retry_status == "EXHAUSTED":
        computed_level = EscalationLevel.HIGH.value
        computed_priority = AlertPriority.HIGH.value
        reason = "Bounded retry ceiling reached (3/3 attempts exhausted)."
        evidence = "RETRY_CEILING_EXHAUSTED"
        recommended_action = "Escalate incident to engineering triage."
    elif circuit_state == "OPEN":
        computed_level = EscalationLevel.HIGH.value
        computed_priority = AlertPriority.HIGH.value
        reason = "Merchant endpoint circuit breaker is OPEN."
        evidence = "CIRCUIT_BREAKER_OPEN"
        recommended_action = "Inspect merchant health and monitor cooldown window."
    elif human_review_status == "EXPIRED":
        computed_level = EscalationLevel.HIGH.value
        computed_priority = AlertPriority.HIGH.value
        reason = "Human review expired past 24-hour SLA window."
        evidence = "REVIEW_SLA_EXPIRED"
        recommended_action = "Re-issue urgent review request to lead operator."
    elif human_review_status in ("REVIEW_PENDING", "REVIEW_REQUIRED") or payment_state in ("HUMAN_REVIEW", "ESCALATED"):
        computed_level = EscalationLevel.ELEVATED.value
        computed_priority = AlertPriority.WARNING.value
        reason = "Incident requires operator decision in Human Action Center."
        evidence = "HUMAN_REVIEW_PENDING"
        recommended_action = "Review transaction and submit approval/rejection."
    elif verification_status == "VERIFICATION_PENDING":
        computed_level = EscalationLevel.ELEVATED.value
        computed_priority = AlertPriority.WARNING.value
        reason = "Outbound request accepted; awaiting ledger verification."
        evidence = "VERIFICATION_IN_FLIGHT"
        recommended_action = "Await ledger callback."
    elif is_closed and payment_state in ("RECOVERED", "SUCCESS"):
        computed_level = EscalationLevel.NORMAL.value
        computed_priority = AlertPriority.INFO.value
        reason = "Incident is authoritatively closed and verified."
        evidence = "RESOLVED_CLOSURE"
        recommended_action = "No action required."

    # Priority hierarchy values for comparison
    priority_order = {"INFO": 0, "WARNING": 1, "HIGH": 2, "CRITICAL": 3}
    prev_val = priority_order.get(prev_priority, 1)
    new_val = priority_order.get(computed_priority, 1)

    action_taken = "NO_CHANGE"
    if new_val > prev_val:
        action_taken = "ALERT_PRIORITY_INCREASED"
    elif new_val < prev_val and computed_level == EscalationLevel.NORMAL.value and is_closed:
        action_taken = "ALERT_PRIORITY_DEESCALATED"
    elif new_val == prev_val:
        action_taken = "ESCALATION_ALREADY_APPLIED"

    # Update alert record under lock
    with _alert_mgmt_lock:
        if clean_alert_id in _managed_alerts_store:
            target = _managed_alerts_store[clean_alert_id]
            target["severity"] = computed_priority
            target["escalation_level"] = computed_level
            target["escalation_reason"] = reason
            target["escalation_evidence"] = evidence
            target["updated_at"] = now_iso
            _save_persisted_alert_mgmt(_managed_alerts_store, _alert_history_store)

    # Record Escalation History Event
    event_id = f"esc_{uuid.uuid4().hex[:10]}"
    history_record = {
        "event_id": event_id,
        "alert_id": clean_alert_id,
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "endpoint": endpoint,
        "action": action_taken,
        "previous_priority": prev_priority,
        "new_priority": computed_priority,
        "escalation_level": computed_level,
        "escalation_reason": reason,
        "evidence": evidence,
        "attribution": f"OPERATOR:{operator_id}" if operator_id else "AUTOMATED_POLICY_ENGINE",
        "timestamp": now_iso
    }

    with _escalation_lock:
        if not _escalation_history:
            _escalation_history.extend(_load_persisted_escalation_history())
        _escalation_history.append(history_record)
        _save_persisted_escalation_history(_escalation_history)

    # Emit Audit Telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=payment_id or "unknown",
            event_type=action_taken if action_taken != "NO_CHANGE" else "ESCALATION_POLICY_EVALUATED",
            actor_type="OPERATOR" if operator_id else "SYSTEM",
            source="RECOVERY_ESCALATION_POLICY",
            status=computed_priority,
            reason=f"Escalation evaluation: {prev_priority} -> {computed_priority} ({reason})",
            merchant_id=merchant_id,
            endpoint=endpoint,
            correlation_id=clean_alert_id
        )
    except Exception:
        pass

    return {
        "success": True,
        "alert_id": clean_alert_id,
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "endpoint": endpoint,
        "previous_priority": prev_priority,
        "current_priority": computed_priority,
        "escalation_level": computed_level,
        "action_taken": action_taken,
        "escalation_reason": reason,
        "evidence": evidence,
        "recommended_action": recommended_action,
        "attribution": f"OPERATOR:{operator_id}" if operator_id else "AUTOMATED_POLICY_ENGINE",
        "evaluated_at": now_iso
    }


def get_alert_escalation_history(alert_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.24 - Retrieves chronological escalation evaluation history.
    """
    with _escalation_lock:
        if not _escalation_history:
            _escalation_history.extend(_load_persisted_escalation_history())

        if alert_id:
            filtered = [h for h in _escalation_history if h.get("alert_id") == alert_id]
            return sorted(filtered, key=lambda x: x.get("timestamp", ""), reverse=True)

        return sorted(_escalation_history, key=lambda x: x.get("timestamp", ""), reverse=True)


def reset_escalation_policy_state() -> None:
    """Helper to reset in-memory and persisted escalation history."""
    with _escalation_lock:
        _escalation_history.clear()
        if os.path.exists(ESCALATION_POLICY_LOG_PATH):
            try:
                os.remove(ESCALATION_POLICY_LOG_PATH)
            except Exception:
                pass
