"""
RecoverIQ - Recovery Lifecycle Integrity Monitor & Operator Alerting Layer (Topic 2.2.2.22)

Authoritative, strictly read-only continuous integrity monitoring and alerting layer.
Continuously observes recovery lifecycle health, detects contradictions, stuck workflows,
and surfaces deduplicated, actionable operator alerts without mutating any subsystem.

STRICT BOUNDARIES:
- Observability and alerting layer only; NEVER mutates PaymentState or CircuitState.
- NEVER automatically executes recoveries, retries, closures, or auto-repairs.
- Acknowledging alerts only updates alert state; does not alter payment lifecycle.
- Deduplicates active alerts by deterministic fingerprint (payment + merchant + endpoint + alert_type).
- Persists alert records to logs/recovery_integrity_alerts.json.
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
INTEGRITY_ALERTS_LOG_PATH = os.path.join(LOGS_DIR, "recovery_integrity_alerts.json")

_integrity_lock = threading.Lock()
_alerts_store: Dict[str, Dict[str, Any]] = {}


class IntegrityStatus(str, Enum):
    """Authoritative integrity monitoring health statuses."""
    HEALTHY = "HEALTHY"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    RETRYING = "RETRYING"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    WAITING_FOR_MERCHANT = "WAITING_FOR_MERCHANT"
    RECOVERY_BLOCKED = "RECOVERY_BLOCKED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    INCIDENT_CLOSED = "INCIDENT_CLOSED"
    INCONSISTENT = "INCONSISTENT"
    MONITORING_UNAVAILABLE = "MONITORING_UNAVAILABLE"


class AlertSeverity(str, Enum):
    """Alert severity classification."""
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    """Alert lifecycle state."""
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertType(str, Enum):
    """Standardized integrity alert types."""
    RECOVERY_VERIFICATION_STUCK = "RECOVERY_VERIFICATION_STUCK"
    RECOVERY_INCONSISTENCY_DETECTED = "RECOVERY_INCONSISTENCY_DETECTED"
    RECOVERY_RETRY_EXHAUSTED = "RECOVERY_RETRY_EXHAUSTED"
    RECOVERY_BLOCKED_BY_CIRCUIT = "RECOVERY_BLOCKED_BY_CIRCUIT"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    HUMAN_REVIEW_EXPIRED = "HUMAN_REVIEW_EXPIRED"
    INCIDENT_CLOSURE_INCONSISTENCY = "INCIDENT_CLOSURE_INCONSISTENCY"
    RECOVERY_MONITORING_FAILURE = "RECOVERY_MONITORING_FAILURE"


def _load_persisted_alerts() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(INTEGRITY_ALERTS_LOG_PATH):
        try:
            with open(INTEGRITY_ALERTS_LOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {item.get("alert_id"): item for item in data if "alert_id" in item}
                elif isinstance(data, dict):
                    return data
        except Exception:
            return {}
    return {}


def _save_persisted_alerts(store: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(INTEGRITY_ALERTS_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(list(store.values()), f, indent=2)
    except Exception:
        pass


def _upsert_alert(
    payment_id: str,
    merchant_id: str,
    endpoint: str,
    alert_type: str,
    severity: str,
    reason: str,
    evidence_type: str,
    recommended_action: str,
    correlation_id: Optional[str] = None,
    execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Idempotently creates or updates an active alert matching the deterministic fingerprint.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    fingerprint = f"{payment_id}_{merchant_id}_{endpoint}_{alert_type}"

    with _integrity_lock:
        if not _alerts_store and os.path.exists(INTEGRITY_ALERTS_LOG_PATH):
            _alerts_store.update(_load_persisted_alerts())

        # Look for existing active or acknowledged alert with same fingerprint
        for existing in _alerts_store.values():
            if existing.get("fingerprint") == fingerprint and existing.get("status") in (AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value):
                existing["reason"] = reason
                existing["severity"] = severity
                existing["updated_at"] = now_iso
                existing["evidence_type"] = evidence_type
                existing["recommended_action"] = recommended_action
                _save_persisted_alerts(_alerts_store)
                return existing

        # Create new alert
        alert_id = f"alert_{uuid.uuid4().hex[:10]}"
        new_alert = {
            "alert_id": alert_id,
            "fingerprint": fingerprint,
            "payment_id": payment_id,
            "merchant_id": merchant_id,
            "endpoint": endpoint,
            "alert_type": alert_type,
            "severity": severity,
            "status": AlertStatus.ACTIVE.value,
            "reason": reason,
            "evidence_type": evidence_type,
            "recommended_action": recommended_action,
            "detected_at": now_iso,
            "updated_at": now_iso,
            "acknowledged_by": None,
            "acknowledged_at": None,
            "correlation_id": correlation_id,
            "execution_id": execution_id
        }
        _alerts_store[alert_id] = new_alert
        _save_persisted_alerts(_alerts_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=payment_id,
            event_type="INTEGRITY_ALERT_CREATED",
            actor_type="SYSTEM",
            source="RECOVERY_INTEGRITY_MONITOR",
            status=severity,
            reason=f"Alert {alert_type} [{severity}]: {reason}",
            merchant_id=merchant_id,
            endpoint=endpoint,
            correlation_id=alert_id
        )
    except Exception:
        pass

    return new_alert


def evaluate_recovery_integrity(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook"
) -> Dict[str, Any]:
    """
    Topic 2.2.2.22 - Read-only continuous integrity evaluation and alert correlation.
    Cross-checks all recovery subsystems, detects contradictions, and generates operator alerts.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Payment State (state_machine.py)
    payment_state = "PENDING"
    try:
        from src.state_machine import get_current_payment_state
        state_enum = get_current_payment_state(clean_payment_id)
        payment_state = state_enum.value if hasattr(state_enum, "value") else str(state_enum)
    except Exception:
        pass

    # 2. Verification Status (recovery_verification.py)
    verification_status = "VERIFICATION_PENDING"
    ver_evidence = "UNKNOWN"
    try:
        from src.recovery_verification import get_payment_recovery_verification_summary
        ver = get_payment_recovery_verification_summary(clean_payment_id, clean_merchant_id, clean_endpoint)
        verification_status = ver.get("verification_status", "VERIFICATION_PENDING")
        ver_evidence = ver.get("evidence_type", "UNKNOWN")
    except Exception:
        pass

    # 3. Consolidated Lifecycle (recovery_lifecycle.py)
    lifecycle_status = "INCIDENT_RECEIVED"
    circuit_state = "CLOSED"
    merchant_health = "HEALTHY"
    try:
        from src.recovery_lifecycle import get_consolidated_recovery_lifecycle
        lc = get_consolidated_recovery_lifecycle(clean_payment_id, clean_merchant_id, clean_endpoint)
        lifecycle_status = lc.get("lifecycle_status", "INCIDENT_RECEIVED")
        circuit_state = lc.get("circuit_state", "CLOSED")
        merchant_health = lc.get("merchant_health", "HEALTHY")
    except Exception:
        pass

    # 4. Finalization Guard (recovery_finalization.py)
    finalization_status = "RESOLUTION_PENDING"
    is_final_resolved = False
    try:
        from src.recovery_finalization import evaluate_recovery_finalization
        fin = evaluate_recovery_finalization(clean_payment_id, clean_merchant_id, clean_endpoint)
        finalization_status = fin.get("finalization_status", "RESOLUTION_PENDING")
        is_final_resolved = fin.get("incident_resolved", False)
    except Exception:
        pass

    # 5. Incident Closure (incident_closure.py)
    closure_status = "CLOSURE_PENDING"
    is_closed = False
    closure_id = None
    execution_id = None
    correlation_id = None
    try:
        from src.incident_closure import get_incident_closure_status
        cls_obj = get_incident_closure_status(clean_payment_id, clean_merchant_id, clean_endpoint)
        closure_status = cls_obj.get("closure_status", "CLOSURE_PENDING")
        is_closed = cls_obj.get("closed", False)
        closure_id = cls_obj.get("closure_id")
        execution_id = cls_obj.get("execution_id")
        correlation_id = cls_obj.get("correlation_id")
    except Exception:
        pass

    # 6. Human Review (recovery_human_review.py)
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

    # 7. Retry Status (recovery_retry_manager.py)
    retry_status = "READY"
    retry_active = False
    attempt_number = 1
    max_attempts = 3
    try:
        from src.recovery_retry_manager import get_payment_retry_status
        ret = get_payment_retry_status(clean_payment_id, clean_merchant_id, clean_endpoint)
        retry_status = ret.get("retry_status", "READY")
        attempt_number = ret.get("attempt_number", 1)
        max_attempts = ret.get("max_attempts", 3)
        if retry_status in ("SCHEDULED", "IN_PROGRESS") and not is_closed:
            retry_active = True
    except Exception:
        pass

    # Evaluate Contradictions & Integrity Rules
    conflicts = []
    generated_alerts = []

    # Rule A: Inconsistent Closure vs State / Verification
    if is_closed or closure_status in ("INCIDENT_CLOSED", "ALREADY_CLOSED"):
        if payment_state not in ("RECOVERED", "SUCCESS"):
            conflicts.append(f"Incident is marked CLOSED but PaymentState is {payment_state}.")
            generated_alerts.append(_upsert_alert(
                clean_payment_id, clean_merchant_id, clean_endpoint,
                AlertType.INCIDENT_CLOSURE_INCONSISTENCY.value, AlertSeverity.CRITICAL.value,
                f"Incident closed prematurely while payment is in state {payment_state}.",
                "STATE_MACHINE_MISMATCH", "Verify transaction status in gateway ledger.",
                correlation_id, execution_id
            ))
        if verification_status != "VERIFIED_SUCCESS":
            conflicts.append(f"Incident is marked CLOSED but verification is {verification_status}.")
            generated_alerts.append(_upsert_alert(
                clean_payment_id, clean_merchant_id, clean_endpoint,
                AlertType.INCIDENT_CLOSURE_INCONSISTENCY.value, AlertSeverity.CRITICAL.value,
                f"Incident closed without authoritative VERIFIED_SUCCESS (got {verification_status}).",
                "VERIFICATION_MISMATCH", "Re-run post-recovery verification.",
                correlation_id, execution_id
            ))
        if human_review_active:
            conflicts.append(f"Incident is marked CLOSED but active human review ({human_review_status}) exists.")
            generated_alerts.append(_upsert_alert(
                clean_payment_id, clean_merchant_id, clean_endpoint,
                AlertType.RECOVERY_INCONSISTENCY_DETECTED.value, AlertSeverity.HIGH.value,
                "Human review remained open after incident closure.",
                "ACTIVE_REVIEW_POST_CLOSURE", "Resolve or cancel lingering human review.",
                correlation_id, execution_id
            ))
        if retry_active:
            conflicts.append(f"Incident is marked CLOSED but recovery retry ({retry_status}) remains active.")
            generated_alerts.append(_upsert_alert(
                clean_payment_id, clean_merchant_id, clean_endpoint,
                AlertType.RECOVERY_INCONSISTENCY_DETECTED.value, AlertSeverity.HIGH.value,
                "Retry scheduled after incident closure.",
                "ACTIVE_RETRY_POST_CLOSURE", "Cancel lingering retry schedule.",
                correlation_id, execution_id
            ))

    # Rule B: Terminal Recovery without Verification
    if payment_state in ("RECOVERED", "SUCCESS") and verification_status not in ("VERIFIED_SUCCESS", "VERIFICATION_PENDING"):
        conflicts.append("Payment marked RECOVERED without valid ledger verification.")
        generated_alerts.append(_upsert_alert(
            clean_payment_id, clean_merchant_id, clean_endpoint,
            AlertType.RECOVERY_INCONSISTENCY_DETECTED.value, AlertSeverity.CRITICAL.value,
            f"Payment state is {payment_state} but verification is {verification_status}.",
            "UNVERIFIED_RECOVERY_TRANSITION", "Perform manual order reconciliation.",
            correlation_id, execution_id
        ))

    # Rule C: Human Review Alerting
    if human_review_active or payment_state in ("HUMAN_REVIEW", "ESCALATED"):
        if human_review_status == "EXPIRED":
            generated_alerts.append(_upsert_alert(
                clean_payment_id, clean_merchant_id, clean_endpoint,
                AlertType.HUMAN_REVIEW_EXPIRED.value, AlertSeverity.HIGH.value,
                "Human review window expired past 24-hour deadline.",
                "OPERATOR_REVIEW_DEADLINE_EXCEEDED", "Re-issue human review or escalate to lead.",
                correlation_id, execution_id
            ))
        else:
            generated_alerts.append(_upsert_alert(
                clean_payment_id, clean_merchant_id, clean_endpoint,
                AlertType.HUMAN_REVIEW_REQUIRED.value, AlertSeverity.WARNING.value,
                "Payment requires manual operator decision in Human Action Center.",
                "HUMAN_ACTION_CENTER_QUEUE", "Review transaction and submit approval/rejection.",
                correlation_id, execution_id
            ))

    # Rule D: Circuit Breaker Blocking
    if circuit_state == "OPEN":
        generated_alerts.append(_upsert_alert(
            clean_payment_id, clean_merchant_id, clean_endpoint,
            AlertType.RECOVERY_BLOCKED_BY_CIRCUIT.value, AlertSeverity.HIGH.value,
            "Outbound recovery requests blocked because merchant circuit breaker is OPEN.",
            "CIRCUIT_BREAKER_TRIPPED", "Wait for circuit cooldown or perform manual probe.",
            correlation_id, execution_id
        ))

    # Rule E: Retry Exhaustion
    if retry_status == "EXHAUSTED" and payment_state not in ("RECOVERED", "SUCCESS"):
        generated_alerts.append(_upsert_alert(
            clean_payment_id, clean_merchant_id, clean_endpoint,
            AlertType.RECOVERY_RETRY_EXHAUSTED.value, AlertSeverity.HIGH.value,
            f"Maximum recovery attempts exhausted ({attempt_number}/{max_attempts}).",
            "RETRY_CEILING_REACHED", "Escalate incident to engineering triage.",
            correlation_id, execution_id
        ))

    # Determine Overall Integrity Status
    if conflicts:
        integrity_status = IntegrityStatus.INCONSISTENT.value
        reason = "Authoritative subsystem contradiction: " + "; ".join(conflicts)
        evidence = "STATE_CONTRADICTION"
        recommended_next_step = "Closure contradiction detected — automatic repair is disabled. Operator investigation required."
    elif is_closed and payment_state in ("RECOVERED", "SUCCESS") and verification_status == "VERIFIED_SUCCESS":
        integrity_status = IntegrityStatus.INCIDENT_CLOSED.value
        reason = "Incident is authoritatively closed and all subsystem signals are fully healthy."
        evidence = "HEALTHY_CLOSED_STATE"
        recommended_next_step = "Incident closure verified. No action required."
    elif circuit_state == "OPEN":
        integrity_status = IntegrityStatus.WAITING_FOR_MERCHANT.value
        reason = "Recovery paused awaiting circuit breaker cooldown."
        evidence = "CIRCUIT_OPEN"
        recommended_next_step = "Monitor merchant endpoint health."
    elif human_review_active:
        integrity_status = IntegrityStatus.HUMAN_REVIEW_REQUIRED.value
        reason = "Incident requires operator authorization."
        evidence = "REVIEW_PENDING"
        recommended_next_step = "Operator approval required in Human Review panel."
    elif retry_status == "EXHAUSTED":
        integrity_status = IntegrityStatus.RECOVERY_FAILED.value
        reason = f"Recovery attempts exhausted ({attempt_number}/{max_attempts})."
        evidence = "RETRY_EXHAUSTED"
        recommended_next_step = "Escalate incident to engineering."
    elif retry_active:
        integrity_status = IntegrityStatus.RETRYING.value
        reason = f"Bounded recovery retry in progress (attempt {attempt_number}/{max_attempts})."
        evidence = "RETRY_SCHEDULED"
        recommended_next_step = "Await retry backoff execution."
    elif verification_status == "VERIFICATION_PENDING":
        integrity_status = IntegrityStatus.VERIFICATION_PENDING.value
        reason = "Outbound request accepted; awaiting order ledger callback."
        evidence = "VERIFICATION_IN_FLIGHT"
        recommended_next_step = "Maintain non-terminal state until ledger callback arrives."
    else:
        integrity_status = IntegrityStatus.HEALTHY.value
        reason = "Payment recovery pipeline operating within expected parameters."
        evidence = "HEALTHY_PIPELINE"
        recommended_next_step = "Proceed with recovery orchestration."

    # Fetch active alerts for this payment
    active_alerts = get_recovery_integrity_alerts(payment_id=clean_payment_id, status=AlertStatus.ACTIVE.value)
    highest_sev = "INFO"
    sev_weights = {"INFO": 0, "WARNING": 1, "HIGH": 2, "CRITICAL": 3}
    for a in active_alerts:
        if sev_weights.get(a.get("severity", "INFO"), 0) > sev_weights.get(highest_sev, 0):
            highest_sev = a.get("severity")

    return {
        "payment_id": clean_payment_id,
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "integrity_status": integrity_status,
        "payment_state": payment_state,
        "verification_status": verification_status,
        "lifecycle_status": lifecycle_status,
        "finalization_status": finalization_status,
        "closure_status": closure_status,
        "retry_status": retry_status,
        "human_review_status": human_review_status,
        "merchant_health": merchant_health,
        "circuit_state": circuit_state,
        "active_alert_count": len(active_alerts),
        "highest_severity": highest_sev if active_alerts else "INFO",
        "alerts": active_alerts,
        "reason": reason,
        "evidence": evidence,
        "recommended_next_step": recommended_next_step,
        "timestamp": now_iso
    }


def get_recovery_integrity_alerts(
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.22 - Lists and filters active / historical integrity alerts.
    """
    with _integrity_lock:
        if not _alerts_store and os.path.exists(INTEGRITY_ALERTS_LOG_PATH):
            _alerts_store.update(_load_persisted_alerts())

        results = []
        for alert in _alerts_store.values():
            if payment_id and alert.get("payment_id") != payment_id:
                continue
            if merchant_id and alert.get("merchant_id") != merchant_id:
                continue
            if severity and alert.get("severity") != severity:
                continue
            if status and alert.get("status") != status:
                continue
            if alert_type and alert.get("alert_type") != alert_type:
                continue
            results.append(alert)

        results.sort(key=lambda x: x.get("detected_at", ""), reverse=True)
        return results[:limit]


def acknowledge_recovery_integrity_alert(
    alert_id: str,
    operator_id: str,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.22 - Operator acknowledges an integrity alert without mutating payment or circuit state.
    """
    clean_alert_id = str(alert_id or "").strip()
    clean_operator_id = str(operator_id or "").strip()
    clean_reason = str(reason or "Acknowledged by operator").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_operator_id:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}

    with _integrity_lock:
        if not _alerts_store and os.path.exists(INTEGRITY_ALERTS_LOG_PATH):
            _alerts_store.update(_load_persisted_alerts())

        alert = _alerts_store.get(clean_alert_id)
        if not alert:
            return {"success": False, "error": "ALERT_NOT_FOUND", "message": f"Alert {clean_alert_id} not found."}

        alert["status"] = AlertStatus.ACKNOWLEDGED.value
        alert["acknowledged_by"] = clean_operator_id
        alert["acknowledged_at"] = now_iso
        alert["acknowledgement_reason"] = clean_reason
        _save_persisted_alerts(_alerts_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=alert.get("payment_id", "unknown"),
            event_type="INTEGRITY_ALERT_ACKNOWLEDGED",
            actor_type="OPERATOR",
            source="RECOVERY_INTEGRITY_MONITOR",
            status="ACKNOWLEDGED",
            reason=f"Alert {alert.get('alert_type')} acknowledged by {clean_operator_id}: {clean_reason}",
            merchant_id=alert.get("merchant_id"),
            endpoint=alert.get("endpoint"),
            correlation_id=clean_alert_id
        )
    except Exception:
        pass

    return {
        "success": True,
        "alert": alert,
        "message": f"Alert {clean_alert_id} acknowledged."
    }


def reset_integrity_monitor_state() -> None:
    """Helper to reset in-memory and persisted integrity alerts."""
    with _integrity_lock:
        _alerts_store.clear()
        if os.path.exists(INTEGRITY_ALERTS_LOG_PATH):
            try:
                os.remove(INTEGRITY_ALERTS_LOG_PATH)
            except Exception:
                pass
