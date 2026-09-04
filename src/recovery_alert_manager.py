"""
RecoverIQ - Operator Alert Management & Escalation Layer (Topic 2.2.2.23)

Authoritative manager for operator-facing recovery integrity alerts.
Provides structured operator workflows (Acknowledge, Assign, Escalate, Resolve, Dismiss)
with live integrity re-evaluation, safety guards, and chronological audit history.

STRICT BOUNDARIES:
- Observational and operator workflow layer only; NEVER directly mutates PaymentState or CircuitState.
- NEVER automatically executes recoveries, retries, closures, or auto-repairs.
- Resolving an alert REQUIRES re-evaluating live integrity conditions through recovery_integrity_monitor.
- Active CRITICAL contradictions CANNOT be dismissed without underlying condition resolution.
- Thread-safe concurrency control via _alert_mgmt_lock.
- Persists management records and history to logs/recovery_alert_management.json.
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
ALERT_MGMT_LOG_PATH = os.path.join(LOGS_DIR, "recovery_alert_management.json")

_alert_mgmt_lock = threading.Lock()
_managed_alerts_store: Dict[str, Dict[str, Any]] = {}
_alert_history_store: List[Dict[str, Any]] = []


class OperatorAlertStatus(str, Enum):
    """Authoritative operator alert lifecycle states."""
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ASSIGNED = "ASSIGNED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class AlertPriority(str, Enum):
    """Authoritative alert priority levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def _load_persisted_alert_mgmt() -> Dict[str, Any]:
    if os.path.exists(ALERT_MGMT_LOG_PATH):
        try:
            with open(ALERT_MGMT_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"alerts": {}, "history": []}
    return {"alerts": {}, "history": []}


def _save_persisted_alert_mgmt(store: Dict[str, Dict[str, Any]], history: List[Dict[str, Any]]) -> None:
    try:
        with open(ALERT_MGMT_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "alerts": store,
                "history": history[-500:]  # keep last 500 history events
            }, f, indent=2)
    except Exception:
        pass


def _sync_with_integrity_monitor() -> None:
    """Syncs raw alerts from recovery_integrity_monitor into managed alerts store."""
    try:
        from src.recovery_integrity_monitor import get_recovery_integrity_alerts
        raw_alerts = get_recovery_integrity_alerts(limit=200)
        for ra in raw_alerts:
            a_id = ra.get("alert_id")
            if a_id and a_id not in _managed_alerts_store:
                _managed_alerts_store[a_id] = {
                    "alert_id": a_id,
                    "payment_id": ra.get("payment_id"),
                    "merchant_id": ra.get("merchant_id"),
                    "endpoint": ra.get("endpoint"),
                    "alert_type": ra.get("alert_type"),
                    "severity": ra.get("severity", AlertPriority.WARNING.value),
                    "status": OperatorAlertStatus.ACTIVE.value,
                    "reason": ra.get("reason"),
                    "evidence_type": ra.get("evidence_type"),
                    "recommended_action": ra.get("recommended_action"),
                    "assigned_to": None,
                    "assigned_at": None,
                    "acknowledged_by": None,
                    "acknowledged_at": None,
                    "escalated_by": None,
                    "escalated_at": None,
                    "resolved_by": None,
                    "resolved_at": None,
                    "resolution_reason": None,
                    "dismissed_by": None,
                    "dismissed_at": None,
                    "dismissal_reason": None,
                    "detected_at": ra.get("detected_at"),
                    "updated_at": ra.get("updated_at"),
                    "correlation_id": ra.get("correlation_id"),
                    "execution_id": ra.get("execution_id")
                }
    except Exception:
        pass


def _record_history_event(
    alert_id: str,
    action: str,
    previous_status: str,
    new_status: str,
    operator_id: str,
    reason: str,
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    evt = {
        "event_id": f"alrthist_{uuid.uuid4().hex[:10]}",
        "alert_id": alert_id,
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "endpoint": endpoint,
        "action": action,
        "previous_status": previous_status,
        "new_status": new_status,
        "operator_id": operator_id,
        "reason": reason,
        "timestamp": now_iso
    }
    _alert_history_store.append(evt)
    return evt


def list_managed_recovery_alerts(
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.23 - Lists and filters operator-managed recovery integrity alerts.
    """
    with _alert_mgmt_lock:
        if not _managed_alerts_store:
            data = _load_persisted_alert_mgmt()
            _managed_alerts_store.update(data.get("alerts", {}))
            _alert_history_store.extend(data.get("history", []))

        _sync_with_integrity_monitor()
        _save_persisted_alert_mgmt(_managed_alerts_store, _alert_history_store)

        results = []
        for alert in _managed_alerts_store.values():
            if payment_id and alert.get("payment_id") != payment_id:
                continue
            if merchant_id and alert.get("merchant_id") != merchant_id:
                continue
            if severity and alert.get("severity") != severity:
                continue
            if status and alert.get("status") != status:
                continue
            if assigned_to and alert.get("assigned_to") != assigned_to:
                continue
            if alert_type and alert.get("alert_type") != alert_type:
                continue
            results.append(alert)

        results.sort(key=lambda x: x.get("updated_at") or x.get("detected_at") or "", reverse=True)
        return results[:limit]


def get_managed_recovery_alert(alert_id: str) -> Optional[Dict[str, Any]]:
    """
    Topic 2.2.2.23 - Retrieves full metadata and history for a specific alert.
    """
    clean_alert_id = str(alert_id or "").strip()
    with _alert_mgmt_lock:
        if not _managed_alerts_store:
            data = _load_persisted_alert_mgmt()
            _managed_alerts_store.update(data.get("alerts", {}))
            _alert_history_store.extend(data.get("history", []))

        _sync_with_integrity_monitor()

        alert = _managed_alerts_store.get(clean_alert_id)
        if not alert:
            return None

        history = [h for h in _alert_history_store if h.get("alert_id") == clean_alert_id]
        alert_copy = dict(alert)
        alert_copy["history"] = sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)
        return alert_copy


def acknowledge_managed_alert(
    alert_id: str,
    operator_id: str,
    reason: str
) -> Dict[str, Any]:
    """
    Topic 2.2.2.23 - Operator acknowledges an alert.
    """
    clean_alert_id = str(alert_id or "").strip()
    clean_operator_id = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_operator_id:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Acknowledgement reason is required."}

    with _alert_mgmt_lock:
        if not _managed_alerts_store:
            data = _load_persisted_alert_mgmt()
            _managed_alerts_store.update(data.get("alerts", {}))
            _alert_history_store.extend(data.get("history", []))

        _sync_with_integrity_monitor()
        alert = _managed_alerts_store.get(clean_alert_id)
        if not alert:
            return {"success": False, "error": "ALERT_NOT_FOUND", "message": f"Alert {clean_alert_id} not found."}

        prev_status = alert.get("status", OperatorAlertStatus.ACTIVE.value)
        if prev_status == OperatorAlertStatus.ACKNOWLEDGED.value:
            return {"success": True, "alert": alert, "message": "Alert was already acknowledged.", "duplicate": True}

        alert["status"] = OperatorAlertStatus.ACKNOWLEDGED.value
        alert["acknowledged_by"] = clean_operator_id
        alert["acknowledged_at"] = now_iso
        alert["updated_at"] = now_iso

        _record_history_event(
            clean_alert_id, "ACKNOWLEDGE", prev_status, OperatorAlertStatus.ACKNOWLEDGED.value,
            clean_operator_id, clean_reason, alert.get("payment_id"), alert.get("merchant_id"), alert.get("endpoint")
        )
        _save_persisted_alert_mgmt(_managed_alerts_store, _alert_history_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=alert.get("payment_id", "unknown"),
            event_type="ALERT_ACKNOWLEDGED",
            actor_type="OPERATOR",
            source="RECOVERY_ALERT_MANAGER",
            status="ACKNOWLEDGED",
            reason=f"Alert acknowledged by {clean_operator_id}: {clean_reason}",
            merchant_id=alert.get("merchant_id"),
            endpoint=alert.get("endpoint"),
            correlation_id=clean_alert_id
        )
    except Exception:
        pass

    return {"success": True, "alert": alert, "message": f"Alert {clean_alert_id} acknowledged by {clean_operator_id}."}


def assign_managed_alert(
    alert_id: str,
    operator_id: str,
    reason: str
) -> Dict[str, Any]:
    """
    Topic 2.2.2.23 - Assigns an alert to an operator.
    """
    clean_alert_id = str(alert_id or "").strip()
    clean_operator_id = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_operator_id:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Assignee operator ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Assignment reason is required."}

    with _alert_mgmt_lock:
        if not _managed_alerts_store:
            data = _load_persisted_alert_mgmt()
            _managed_alerts_store.update(data.get("alerts", {}))
            _alert_history_store.extend(data.get("history", []))

        _sync_with_integrity_monitor()
        alert = _managed_alerts_store.get(clean_alert_id)
        if not alert:
            return {"success": False, "error": "ALERT_NOT_FOUND", "message": f"Alert {clean_alert_id} not found."}

        prev_status = alert.get("status", OperatorAlertStatus.ACTIVE.value)
        if alert.get("assigned_to") == clean_operator_id and prev_status == OperatorAlertStatus.ASSIGNED.value:
            return {"success": True, "alert": alert, "message": f"Alert was already assigned to {clean_operator_id}.", "duplicate": True}

        alert["status"] = OperatorAlertStatus.ASSIGNED.value
        alert["assigned_to"] = clean_operator_id
        alert["assigned_at"] = now_iso
        alert["updated_at"] = now_iso

        _record_history_event(
            clean_alert_id, "ASSIGN", prev_status, OperatorAlertStatus.ASSIGNED.value,
            clean_operator_id, clean_reason, alert.get("payment_id"), alert.get("merchant_id"), alert.get("endpoint")
        )
        _save_persisted_alert_mgmt(_managed_alerts_store, _alert_history_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=alert.get("payment_id", "unknown"),
            event_type="ALERT_ASSIGNED",
            actor_type="OPERATOR",
            source="RECOVERY_ALERT_MANAGER",
            status="ASSIGNED",
            reason=f"Alert assigned to {clean_operator_id}: {clean_reason}",
            merchant_id=alert.get("merchant_id"),
            endpoint=alert.get("endpoint"),
            correlation_id=clean_alert_id
        )
    except Exception:
        pass

    return {"success": True, "alert": alert, "message": f"Alert {clean_alert_id} assigned to {clean_operator_id}."}


def escalate_managed_alert(
    alert_id: str,
    operator_id: str,
    reason: str,
    target_severity: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.23 - Explicitly escalates an alert to higher severity and status.
    """
    clean_alert_id = str(alert_id or "").strip()
    clean_operator_id = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_operator_id:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Escalation reason is required."}

    with _alert_mgmt_lock:
        if not _managed_alerts_store:
            data = _load_persisted_alert_mgmt()
            _managed_alerts_store.update(data.get("alerts", {}))
            _alert_history_store.extend(data.get("history", []))

        _sync_with_integrity_monitor()
        alert = _managed_alerts_store.get(clean_alert_id)
        if not alert:
            return {"success": False, "error": "ALERT_NOT_FOUND", "message": f"Alert {clean_alert_id} not found."}

        prev_status = alert.get("status", OperatorAlertStatus.ACTIVE.value)
        prev_severity = alert.get("severity", AlertPriority.WARNING.value)

        new_severity = target_severity or (
            AlertPriority.CRITICAL.value if prev_severity in (AlertPriority.HIGH.value, AlertPriority.CRITICAL.value)
            else AlertPriority.HIGH.value
        )

        alert["status"] = OperatorAlertStatus.ESCALATED.value
        alert["severity"] = new_severity
        alert["escalated_by"] = clean_operator_id
        alert["escalated_at"] = now_iso
        alert["updated_at"] = now_iso

        _record_history_event(
            clean_alert_id, "ESCALATE", prev_status, OperatorAlertStatus.ESCALATED.value,
            clean_operator_id, f"Escalated from {prev_severity} to {new_severity}: {clean_reason}",
            alert.get("payment_id"), alert.get("merchant_id"), alert.get("endpoint")
        )
        _save_persisted_alert_mgmt(_managed_alerts_store, _alert_history_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=alert.get("payment_id", "unknown"),
            event_type="ALERT_ESCALATED",
            actor_type="OPERATOR",
            source="RECOVERY_ALERT_MANAGER",
            status=new_severity,
            reason=f"Alert escalated by {clean_operator_id} to {new_severity}: {clean_reason}",
            merchant_id=alert.get("merchant_id"),
            endpoint=alert.get("endpoint"),
            correlation_id=clean_alert_id
        )
    except Exception:
        pass

    return {"success": True, "alert": alert, "message": f"Alert {clean_alert_id} escalated to {new_severity} by {clean_operator_id}."}


def resolve_managed_alert(
    alert_id: str,
    operator_id: str,
    reason: str
) -> Dict[str, Any]:
    """
    Topic 2.2.2.23 - Resolves an alert ONLY after re-evaluating live integrity conditions.
    If the underlying contradiction still exists, resolution is safely rejected.
    """
    clean_alert_id = str(alert_id or "").strip()
    clean_operator_id = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_operator_id:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Resolution reason is required."}

    with _alert_mgmt_lock:
        if not _managed_alerts_store:
            data = _load_persisted_alert_mgmt()
            _managed_alerts_store.update(data.get("alerts", {}))
            _alert_history_store.extend(data.get("history", []))

        _sync_with_integrity_monitor()
        alert = _managed_alerts_store.get(clean_alert_id)
        if not alert:
            return {"success": False, "error": "ALERT_NOT_FOUND", "message": f"Alert {clean_alert_id} not found."}

        prev_status = alert.get("status", OperatorAlertStatus.ACTIVE.value)
        if prev_status == OperatorAlertStatus.RESOLVED.value:
            return {"success": True, "alert": alert, "message": "Alert was already resolved.", "duplicate": True}

        # RE-EVALUATE LIVE INTEGRITY STATE BEFORE ALLOWING RESOLUTION
        payment_id = alert.get("payment_id")
        merchant_id = alert.get("merchant_id", "merchant_demo")
        endpoint = alert.get("endpoint", "payment-webhook")

        try:
            from src.recovery_integrity_monitor import evaluate_recovery_integrity
            live_eval = evaluate_recovery_integrity(payment_id, merchant_id, endpoint)
            live_status = live_eval.get("integrity_status")

            # Check if this alert was for an inconsistency that is still active
            if alert.get("alert_type") in ("RECOVERY_INCONSISTENCY_DETECTED", "INCIDENT_CLOSURE_INCONSISTENCY") and live_status == "INCONSISTENT":
                try:
                    from src.recovery_audit import record_recovery_audit_event
                    record_recovery_audit_event(
                        payment_id=payment_id,
                        event_type="ALERT_ACTION_REJECTED",
                        actor_type="OPERATOR",
                        source="RECOVERY_ALERT_MANAGER",
                        status="REJECTED",
                        reason=f"Resolution rejected: live integrity status is still INCONSISTENT ({live_eval.get('reason')}).",
                        merchant_id=merchant_id,
                        endpoint=endpoint,
                        correlation_id=clean_alert_id
                    )
                except Exception:
                    pass

                return {
                    "success": False,
                    "error": "CONTRADICTION_STILL_ACTIVE",
                    "message": f"Cannot resolve alert: Authoritative contradiction is still active ({live_eval.get('reason')}). Resolve underlying state first.",
                    "live_integrity_status": live_status
                }
        except Exception:
            pass

        alert["status"] = OperatorAlertStatus.RESOLVED.value
        alert["resolved_by"] = clean_operator_id
        alert["resolved_at"] = now_iso
        alert["resolution_reason"] = clean_reason
        alert["updated_at"] = now_iso

        _record_history_event(
            clean_alert_id, "RESOLVE", prev_status, OperatorAlertStatus.RESOLVED.value,
            clean_operator_id, clean_reason, payment_id, merchant_id, endpoint
        )
        _save_persisted_alert_mgmt(_managed_alerts_store, _alert_history_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=payment_id,
            event_type="ALERT_RESOLVED",
            actor_type="OPERATOR",
            source="RECOVERY_ALERT_MANAGER",
            status="RESOLVED",
            reason=f"Alert resolved by {clean_operator_id}: {clean_reason}",
            merchant_id=merchant_id,
            endpoint=endpoint,
            correlation_id=clean_alert_id
        )
    except Exception:
        pass

    return {"success": True, "alert": alert, "message": f"Alert {clean_alert_id} resolved by {clean_operator_id}."}


def dismiss_managed_alert(
    alert_id: str,
    operator_id: str,
    reason: str
) -> Dict[str, Any]:
    """
    Topic 2.2.2.23 - Dismisses non-critical alerts with mandatory reason.
    CRITICAL contradictions CANNOT be dismissed.
    """
    clean_alert_id = str(alert_id or "").strip()
    clean_operator_id = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_operator_id:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Dismissal reason is required."}

    with _alert_mgmt_lock:
        if not _managed_alerts_store:
            data = _load_persisted_alert_mgmt()
            _managed_alerts_store.update(data.get("alerts", {}))
            _alert_history_store.extend(data.get("history", []))

        _sync_with_integrity_monitor()
        alert = _managed_alerts_store.get(clean_alert_id)
        if not alert:
            return {"success": False, "error": "ALERT_NOT_FOUND", "message": f"Alert {clean_alert_id} not found."}

        # SAFETY RULE: Never dismiss active CRITICAL contradictions
        if alert.get("severity") == AlertPriority.CRITICAL.value:
            return {
                "success": False,
                "error": "CRITICAL_ALERT_DISMISSAL_PROHIBITED",
                "message": "CRITICAL integrity alerts cannot be dismissed. Resolve the underlying contradiction or escalate to lead.",
                "severity": "CRITICAL"
            }

        prev_status = alert.get("status", OperatorAlertStatus.ACTIVE.value)
        if prev_status == OperatorAlertStatus.DISMISSED.value:
            return {"success": True, "alert": alert, "message": "Alert was already dismissed.", "duplicate": True}

        alert["status"] = OperatorAlertStatus.DISMISSED.value
        alert["dismissed_by"] = clean_operator_id
        alert["dismissed_at"] = now_iso
        alert["dismissal_reason"] = clean_reason
        alert["updated_at"] = now_iso

        _record_history_event(
            clean_alert_id, "DISMISS", prev_status, OperatorAlertStatus.DISMISSED.value,
            clean_operator_id, clean_reason, alert.get("payment_id"), alert.get("merchant_id"), alert.get("endpoint")
        )
        _save_persisted_alert_mgmt(_managed_alerts_store, _alert_history_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=alert.get("payment_id", "unknown"),
            event_type="ALERT_DISMISSED",
            actor_type="OPERATOR",
            source="RECOVERY_ALERT_MANAGER",
            status="DISMISSED",
            reason=f"Alert dismissed by {clean_operator_id}: {clean_reason}",
            merchant_id=alert.get("merchant_id"),
            endpoint=alert.get("endpoint"),
            correlation_id=clean_alert_id
        )
    except Exception:
        pass

    return {"success": True, "alert": alert, "message": f"Alert {clean_alert_id} dismissed by {clean_operator_id}."}


def reset_alert_manager_state() -> None:
    """Helper to reset in-memory and persisted alert management records."""
    with _alert_mgmt_lock:
        _managed_alerts_store.clear()
        _alert_history_store.clear()
        if os.path.exists(ALERT_MGMT_LOG_PATH):
            try:
                os.remove(ALERT_MGMT_LOG_PATH)
            except Exception:
                pass
