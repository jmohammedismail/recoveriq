"""
RecoverIQ - Recovery Alert Escalation Execution & Operator Handoff (Topic 2.2.2.25)

Authoritative execution and handoff manager converting escalation-policy decisions
into structured, actionable operator escalation handoffs.

STRICT BOUNDARIES:
- Observational and operator workflow handoff layer only; NEVER directly mutates PaymentState or CircuitState.
- NEVER automatically executes recoveries, retries, refunds, or auto-repairs.
- Completing a handoff ONLY signifies operator workflow completion, NEVER payment recovery or incident resolution.
- Thread-safe concurrency control via _executor_lock.
- Persists handoff records and history to logs/recovery_escalation_execution.json.
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
ESCALATION_EXECUTION_LOG_PATH = os.path.join(LOGS_DIR, "recovery_escalation_execution.json")

_executor_lock = threading.Lock()
_handoffs_store: Dict[str, Dict[str, Any]] = {}
_handoff_history_store: List[Dict[str, Any]] = []


class EscalationAction(str, Enum):
    """Deterministic escalation handoff actions."""
    NO_ACTION = "NO_ACTION"
    OPERATOR_QUEUE = "OPERATOR_QUEUE"
    LEAD_OPERATOR_REQUIRED = "LEAD_OPERATOR_REQUIRED"
    ENGINEERING_REVIEW_REQUIRED = "ENGINEERING_REVIEW_REQUIRED"
    CRITICAL_INCIDENT_HANDOFF = "CRITICAL_INCIDENT_HANDOFF"


class HandoffStatus(str, Enum):
    """Lifecycle status of an operator escalation handoff."""
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ASSIGNED = "ASSIGNED"
    ESCALATED = "ESCALATED"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


def _load_persisted_executions() -> Dict[str, Any]:
    if os.path.exists(ESCALATION_EXECUTION_LOG_PATH):
        try:
            with open(ESCALATION_EXECUTION_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"handoffs": {}, "history": []}
    return {"handoffs": {}, "history": []}


def _save_persisted_executions(handoffs: Dict[str, Dict[str, Any]], history: List[Dict[str, Any]]) -> None:
    try:
        with open(ESCALATION_EXECUTION_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "handoffs": handoffs,
                "history": history[-500:]
            }, f, indent=2)
    except Exception:
        pass


def _record_handoff_history(
    handoff_id: str,
    action: str,
    previous_status: str,
    new_status: str,
    operator_id: str,
    reason: str,
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    previous_assignee: Optional[str] = None,
    new_assignee: Optional[str] = None
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    evt = {
        "event_id": f"hndhist_{uuid.uuid4().hex[:10]}",
        "handoff_id": handoff_id,
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "endpoint": endpoint,
        "action": action,
        "previous_status": previous_status,
        "new_status": new_status,
        "previous_assignee": previous_assignee,
        "new_assignee": new_assignee,
        "operator_id": operator_id,
        "reason": reason,
        "timestamp": now_iso
    }
    _handoff_history_store.append(evt)
    return evt


def execute_alert_escalation(
    alert_id: str,
    operator_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.25 - Converts escalation-policy decisions into a structured operator handoff.
    Idempotent: uses deterministic fingerprinting to avoid duplicate handoffs.
    """
    clean_alert_id = str(alert_id or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    from src.recovery_escalation_policy import evaluate_alert_escalation
    from src.recovery_alert_manager import get_managed_recovery_alert

    # 1. Re-evaluate policy decision
    eval_res = evaluate_alert_escalation(clean_alert_id, operator_id=operator_id)
    if not eval_res.get("success"):
        return eval_res

    payment_id = eval_res.get("payment_id")
    merchant_id = eval_res.get("merchant_id", "merchant_demo")
    endpoint = eval_res.get("endpoint", "payment-webhook")
    priority = eval_res.get("current_priority", "WARNING")
    level = eval_res.get("escalation_level", "NORMAL")
    reason = eval_res.get("escalation_reason", "")
    evidence = eval_res.get("evidence", "")
    rec_action = eval_res.get("recommended_action", "")

    # 2. Map escalation level to deterministic escalation action
    if level == "CRITICAL" or priority == "CRITICAL":
        escalation_action = EscalationAction.CRITICAL_INCIDENT_HANDOFF.value
        initial_status = HandoffStatus.PENDING.value
        target_role = "LEAD_ENGINEER"
    elif level == "HIGH" or priority == "HIGH":
        escalation_action = EscalationAction.LEAD_OPERATOR_REQUIRED.value
        initial_status = HandoffStatus.PENDING.value
        target_role = "LEAD_OPERATOR"
    elif level == "ELEVATED" or priority == "WARNING":
        escalation_action = EscalationAction.OPERATOR_QUEUE.value
        initial_status = HandoffStatus.PENDING.value
        target_role = "OPERATOR_QUEUE"
    else:
        escalation_action = EscalationAction.NO_ACTION.value
        initial_status = HandoffStatus.COMPLETED.value
        target_role = "NONE"

    # 3. Deterministic Fingerprint for Idempotency
    fingerprint = f"{payment_id}_{merchant_id}_{endpoint}_{clean_alert_id}_{level}"

    with _executor_lock:
        if not _handoffs_store:
            data = _load_persisted_executions()
            _handoffs_store.update(data.get("handoffs", {}))
            _handoff_history_store.extend(data.get("history", []))

        # Check for existing active handoff with same fingerprint
        for existing in _handoffs_store.values():
            if existing.get("fingerprint") == fingerprint and existing.get("handoff_status") not in (HandoffStatus.COMPLETED.value, HandoffStatus.CANCELLED.value):
                existing["updated_at"] = now_iso
                existing["priority"] = priority
                existing["escalation_level"] = level
                existing["reason"] = reason
                _save_persisted_executions(_handoffs_store, _handoff_history_store)
                return {
                    "success": True,
                    "handoff": existing,
                    "action_taken": "ESCALATION_HANDOFF_ALREADY_EXISTS",
                    "message": f"Active handoff {existing.get('handoff_id')} already exists for {clean_alert_id}.",
                    "idempotent": True
                }

        # Create new handoff record
        handoff_id = f"hnd_{uuid.uuid4().hex[:10]}"
        handoff_record = {
            "handoff_id": handoff_id,
            "fingerprint": fingerprint,
            "alert_id": clean_alert_id,
            "payment_id": payment_id,
            "merchant_id": merchant_id,
            "endpoint": endpoint,
            "priority": priority,
            "escalation_level": level,
            "escalation_action": escalation_action,
            "target_role": target_role,
            "handoff_status": initial_status,
            "assigned_to": None,
            "created_at": now_iso,
            "updated_at": now_iso,
            "reason": reason,
            "evidence": evidence,
            "recommended_action": rec_action,
            "source": "RECOVERY_ESCALATION_POLICY",
            "correlation_id": clean_alert_id
        }

        _handoffs_store[handoff_id] = handoff_record
        _record_handoff_history(
            handoff_id, "CREATE_HANDOFF", "NONE", initial_status,
            operator_id or "SYSTEM", f"Handoff created with action {escalation_action}: {reason}",
            payment_id, merchant_id, endpoint
        )
        _save_persisted_executions(_handoffs_store, _handoff_history_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=payment_id or "unknown",
            event_type="ESCALATION_HANDOFF_CREATED",
            actor_type="OPERATOR" if operator_id else "SYSTEM",
            source="RECOVERY_ESCALATION_EXECUTOR",
            status=priority,
            reason=f"Handoff {handoff_id} created: {escalation_action} ({reason})",
            merchant_id=merchant_id,
            endpoint=endpoint,
            correlation_id=handoff_id
        )
    except Exception:
        pass

    return {
        "success": True,
        "handoff": handoff_record,
        "action_taken": "ESCALATION_HANDOFF_CREATED",
        "message": f"Escalation handoff {handoff_id} created successfully."
    }


def list_recovery_escalations(
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    priority: Optional[str] = None,
    escalation_level: Optional[str] = None,
    handoff_status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.25 - Lists and filters escalation handoff records.
    """
    with _executor_lock:
        if not _handoffs_store:
            data = _load_persisted_executions()
            _handoffs_store.update(data.get("handoffs", {}))
            _handoff_history_store.extend(data.get("history", []))

        results = []
        for h in _handoffs_store.values():
            if payment_id and h.get("payment_id") != payment_id:
                continue
            if merchant_id and h.get("merchant_id") != merchant_id:
                continue
            if priority and h.get("priority") != priority:
                continue
            if escalation_level and h.get("escalation_level") != escalation_level:
                continue
            if handoff_status and h.get("handoff_status") != handoff_status:
                continue
            if assigned_to and h.get("assigned_to") != assigned_to:
                continue
            results.append(h)

        results.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
        return results[:limit]


def get_recovery_escalation(handoff_id: str) -> Optional[Dict[str, Any]]:
    """
    Topic 2.2.2.25 - Retrieves a specific escalation handoff record with history.
    """
    clean_id = str(handoff_id or "").strip()
    with _executor_lock:
        if not _handoffs_store:
            data = _load_persisted_executions()
            _handoffs_store.update(data.get("handoffs", {}))
            _handoff_history_store.extend(data.get("history", []))

        h = _handoffs_store.get(clean_id)
        if not h:
            return None

        history = [evt for evt in _handoff_history_store if evt.get("handoff_id") == clean_id]
        h_copy = dict(h)
        h_copy["history"] = sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)
        return h_copy


def acknowledge_recovery_escalation(
    handoff_id: str,
    operator_id: str,
    reason: str
) -> Dict[str, Any]:
    """
    Topic 2.2.2.25 - Acknowledges an escalation handoff.
    """
    clean_id = str(handoff_id or "").strip()
    clean_op = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_op:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Acknowledgement reason is required."}

    with _executor_lock:
        if not _handoffs_store:
            data = _load_persisted_executions()
            _handoffs_store.update(data.get("handoffs", {}))
            _handoff_history_store.extend(data.get("history", []))

        h = _handoffs_store.get(clean_id)
        if not h:
            return {"success": False, "error": "HANDOFF_NOT_FOUND", "message": f"Handoff {clean_id} not found."}

        prev_status = h.get("handoff_status", HandoffStatus.PENDING.value)
        if prev_status == HandoffStatus.ACKNOWLEDGED.value:
            return {"success": True, "handoff": h, "message": "Handoff was already acknowledged.", "duplicate": True}

        h["handoff_status"] = HandoffStatus.ACKNOWLEDGED.value
        h["updated_at"] = now_iso

        _record_handoff_history(
            clean_id, "ACKNOWLEDGE", prev_status, HandoffStatus.ACKNOWLEDGED.value,
            clean_op, clean_reason, h.get("payment_id"), h.get("merchant_id"), h.get("endpoint")
        )
        _save_persisted_executions(_handoffs_store, _handoff_history_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=h.get("payment_id", "unknown"),
            event_type="ESCALATION_HANDOFF_ACKNOWLEDGED",
            actor_type="OPERATOR",
            source="RECOVERY_ESCALATION_EXECUTOR",
            status="ACKNOWLEDGED",
            reason=f"Handoff {clean_id} acknowledged by {clean_op}: {clean_reason}",
            merchant_id=h.get("merchant_id"),
            endpoint=h.get("endpoint"),
            correlation_id=clean_id
        )
    except Exception:
        pass

    return {"success": True, "handoff": h, "message": f"Handoff {clean_id} acknowledged by {clean_op}."}


def assign_recovery_escalation(
    handoff_id: str,
    assignee_id: str,
    operator_id: str,
    reason: str
) -> Dict[str, Any]:
    """
    Topic 2.2.2.25 - Assigns or reassigns an escalation handoff.
    """
    clean_id = str(handoff_id or "").strip()
    clean_assignee = str(assignee_id or "").strip()
    clean_op = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_assignee:
        return {"success": False, "error": "ASSIGNEE_ID_REQUIRED", "message": "Assignee ID is required."}
    if not clean_op:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Assignment reason is required."}

    with _executor_lock:
        if not _handoffs_store:
            data = _load_persisted_executions()
            _handoffs_store.update(data.get("handoffs", {}))
            _handoff_history_store.extend(data.get("history", []))

        h = _handoffs_store.get(clean_id)
        if not h:
            return {"success": False, "error": "HANDOFF_NOT_FOUND", "message": f"Handoff {clean_id} not found."}

        prev_assignee = h.get("assigned_to")
        prev_status = h.get("handoff_status", HandoffStatus.PENDING.value)
        action_name = "REASSIGN" if prev_assignee and prev_assignee != clean_assignee else "ASSIGN"

        h["assigned_to"] = clean_assignee
        h["handoff_status"] = HandoffStatus.ASSIGNED.value
        h["updated_at"] = now_iso

        _record_handoff_history(
            clean_id, action_name, prev_status, HandoffStatus.ASSIGNED.value,
            clean_op, clean_reason, h.get("payment_id"), h.get("merchant_id"), h.get("endpoint"),
            prev_assignee, clean_assignee
        )
        _save_persisted_executions(_handoffs_store, _handoff_history_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=h.get("payment_id", "unknown"),
            event_type=f"ESCALATION_HANDOFF_{action_name}ED",
            actor_type="OPERATOR",
            source="RECOVERY_ESCALATION_EXECUTOR",
            status="ASSIGNED",
            reason=f"Handoff {clean_id} assigned to {clean_assignee} by {clean_op}: {clean_reason}",
            merchant_id=h.get("merchant_id"),
            endpoint=h.get("endpoint"),
            correlation_id=clean_id
        )
    except Exception:
        pass

    return {"success": True, "handoff": h, "message": f"Handoff {clean_id} assigned to {clean_assignee}."}


def complete_recovery_escalation(
    handoff_id: str,
    operator_id: str,
    reason: str
) -> Dict[str, Any]:
    """
    Topic 2.2.2.25 - Completes the operator escalation workflow.
    SAFETY GUARANTEE: Marks the handoff workflow complete without mutating PaymentState or CircuitState.
    """
    clean_id = str(handoff_id or "").strip()
    clean_op = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_op:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Completion reason is required."}

    with _executor_lock:
        if not _handoffs_store:
            data = _load_persisted_executions()
            _handoffs_store.update(data.get("handoffs", {}))
            _handoff_history_store.extend(data.get("history", []))

        h = _handoffs_store.get(clean_id)
        if not h:
            return {"success": False, "error": "HANDOFF_NOT_FOUND", "message": f"Handoff {clean_id} not found."}

        prev_status = h.get("handoff_status", HandoffStatus.PENDING.value)
        if prev_status == HandoffStatus.COMPLETED.value:
            return {"success": True, "handoff": h, "message": "Handoff was already completed.", "duplicate": True}

        h["handoff_status"] = HandoffStatus.COMPLETED.value
        h["completed_by"] = clean_op
        h["completed_at"] = now_iso
        h["completion_reason"] = clean_reason
        h["updated_at"] = now_iso

        _record_handoff_history(
            clean_id, "COMPLETE", prev_status, HandoffStatus.COMPLETED.value,
            clean_op, clean_reason, h.get("payment_id"), h.get("merchant_id"), h.get("endpoint")
        )
        _save_persisted_executions(_handoffs_store, _handoff_history_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=h.get("payment_id", "unknown"),
            event_type="ESCALATION_HANDOFF_COMPLETED",
            actor_type="OPERATOR",
            source="RECOVERY_ESCALATION_EXECUTOR",
            status="COMPLETED",
            reason=f"Handoff {clean_id} completed by {clean_op}: {clean_reason}",
            merchant_id=h.get("merchant_id"),
            endpoint=h.get("endpoint"),
            correlation_id=clean_id
        )
    except Exception:
        pass

    return {
        "success": True,
        "handoff": h,
        "message": f"Handoff {clean_id} completed by {clean_op}. (Note: Payment & circuit state remain authoritative)."
    }


def get_escalation_handoff_history(handoff_id: str) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.25 - Retrieves history events for a specific handoff.
    """
    clean_id = str(handoff_id or "").strip()
    with _executor_lock:
        if not _handoff_history_store:
            data = _load_persisted_executions()
            _handoff_history_store.extend(data.get("history", []))

        filtered = [evt for evt in _handoff_history_store if evt.get("handoff_id") == clean_id]
        return sorted(filtered, key=lambda x: x.get("timestamp", ""), reverse=True)


def reset_escalation_executor_state() -> None:
    """Helper to reset in-memory and persisted execution records."""
    with _executor_lock:
        _handoffs_store.clear()
        _handoff_history_store.clear()
        if os.path.exists(ESCALATION_EXECUTION_LOG_PATH):
            try:
                os.remove(ESCALATION_EXECUTION_LOG_PATH)
            except Exception:
                pass
