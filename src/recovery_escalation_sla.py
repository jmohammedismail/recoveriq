"""
RecoverIQ - Recovery Escalation SLA, Stuck-Handoff Detection & Operator Accountability (Topic 2.2.2.26)

Authoritative SLA and accountability monitoring engine for recovery alerts and escalation handoffs.
Evaluates elapsed time against defined SLA thresholds, detects stuck handoffs, and triggers
accountability escalations without mutating financial or circuit breaker states.

STRICT BOUNDARIES:
- Observational and SLA accountability layer only; NEVER directly mutates PaymentState or CircuitState.
- NEVER automatically executes recoveries, retries, refunds, or auto-repairs.
- SLA completion is strictly tied to handoff workflow completion, never false confirmations.
- Thread-safe concurrency control via _sla_lock.
- Persists SLA records and history to logs/recovery_escalation_sla.json.
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
SLA_LOG_PATH = os.path.join(LOGS_DIR, "recovery_escalation_sla.json")

_sla_lock = threading.Lock()
_sla_store: Dict[str, Dict[str, Any]] = {}
_sla_history_store: List[Dict[str, Any]] = []

# Configurable SLA Thresholds (in seconds)
SLA_CONFIG = {
    "CRITICAL": {
        "ACKNOWLEDGEMENT_TARGET_SECONDS": 300,       # 5 minutes
        "ASSIGNMENT_TARGET_SECONDS": 600,            # 10 minutes
        "REVIEW_TARGET_SECONDS": 900                 # 15 minutes
    },
    "HIGH": {
        "ACKNOWLEDGEMENT_TARGET_SECONDS": 900,       # 15 minutes
        "ASSIGNMENT_TARGET_SECONDS": 1800,           # 30 minutes
        "REVIEW_TARGET_SECONDS": 2700                # 45 minutes
    },
    "WARNING": {
        "ACKNOWLEDGEMENT_TARGET_SECONDS": 1800,      # 30 minutes
        "ASSIGNMENT_TARGET_SECONDS": 3600,           # 60 minutes
        "REVIEW_TARGET_SECONDS": 5400                # 90 minutes
    },
    "ELEVATED": {
        "ACKNOWLEDGEMENT_TARGET_SECONDS": 1800,      # 30 minutes
        "ASSIGNMENT_TARGET_SECONDS": 3600,           # 60 minutes
        "REVIEW_TARGET_SECONDS": 5400                # 90 minutes
    },
    "INFO": {
        "ACKNOWLEDGEMENT_TARGET_SECONDS": 86400,     # 24 hours (non-critical)
        "ASSIGNMENT_TARGET_SECONDS": 86400,
        "REVIEW_TARGET_SECONDS": 86400
    },
    "NORMAL": {
        "ACKNOWLEDGEMENT_TARGET_SECONDS": 86400,
        "ASSIGNMENT_TARGET_SECONDS": 86400,
        "REVIEW_TARGET_SECONDS": 86400
    }
}


class SlaStatus(str, Enum):
    """Authoritative SLA health statuses."""
    WITHIN_SLA = "WITHIN_SLA"
    APPROACHING_SLA = "APPROACHING_SLA"
    SLA_BREACHED = "SLA_BREACHED"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    SLA_EVALUATION_UNAVAILABLE = "SLA_EVALUATION_UNAVAILABLE"


def _load_persisted_sla() -> Dict[str, Any]:
    if os.path.exists(SLA_LOG_PATH):
        try:
            with open(SLA_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"slas": {}, "history": []}
    return {"slas": {}, "history": []}


def _save_persisted_sla(slas: Dict[str, Dict[str, Any]], history: List[Dict[str, Any]]) -> None:
    try:
        with open(SLA_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "slas": slas,
                "history": history[-500:]
            }, f, indent=2)
    except Exception:
        pass


def _record_sla_history(
    sla_id: str,
    handoff_id: str,
    action: str,
    previous_status: str,
    new_status: str,
    reason: str,
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    evt = {
        "event_id": f"slahist_{uuid.uuid4().hex[:10]}",
        "sla_id": sla_id,
        "handoff_id": handoff_id,
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "endpoint": endpoint,
        "action": action,
        "previous_status": previous_status,
        "new_status": new_status,
        "reason": reason,
        "timestamp": now_iso
    }
    _sla_history_store.append(evt)
    return evt


def evaluate_escalation_sla(handoff_id: str) -> Dict[str, Any]:
    """
    Topic 2.2.2.26 - Evaluates SLA compliance, stuck conditions, and remaining time for a handoff.
    """
    clean_id = str(handoff_id or "").strip()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    from src.recovery_escalation_executor import get_recovery_escalation

    handoff = get_recovery_escalation(clean_id)
    if not handoff:
        return {
            "success": False,
            "error": "HANDOFF_NOT_FOUND",
            "message": f"Escalation handoff {clean_id} not found."
        }

    payment_id = handoff.get("payment_id")
    merchant_id = handoff.get("merchant_id", "merchant_demo")
    endpoint = handoff.get("endpoint", "payment-webhook")
    priority = handoff.get("priority", "WARNING").upper()
    level = handoff.get("escalation_level", "NORMAL").upper()
    status = handoff.get("handoff_status", "PENDING")
    assigned_to = handoff.get("assigned_to")
    created_at_str = handoff.get("created_at") or now_iso

    # Calculate Elapsed Time
    try:
        created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        elapsed_seconds = int((now - created_dt).total_seconds())
    except Exception:
        elapsed_seconds = 0

    if elapsed_seconds < 0:
        elapsed_seconds = 0

    # Determine Active SLA Type and Limit
    cfg = SLA_CONFIG.get(priority, SLA_CONFIG.get(level, SLA_CONFIG["WARNING"]))
    if status == "PENDING":
        sla_type = "ACKNOWLEDGEMENT_SLA"
        sla_limit = cfg["ACKNOWLEDGEMENT_TARGET_SECONDS"]
    elif status == "ACKNOWLEDGED":
        sla_type = "ASSIGNMENT_SLA"
        sla_limit = cfg["ASSIGNMENT_TARGET_SECONDS"]
    elif status in ("ASSIGNED", "IN_REVIEW"):
        sla_type = "REVIEW_RESOLUTION_SLA"
        sla_limit = cfg["REVIEW_TARGET_SECONDS"]
    else:
        sla_type = "COMPLETED_WORKFLOW"
        sla_limit = cfg["ACKNOWLEDGEMENT_TARGET_SECONDS"]

    remaining_seconds = max(0, sla_limit - elapsed_seconds)

    # Determine SLA Status and Stuck Conditions
    breach_reason = None
    breached_at = None
    recommended_action = "Maintain active operator monitoring."

    if status == "COMPLETED":
        sla_status = SlaStatus.COMPLETED.value
        reason = "Operator escalation workflow is authoritatively completed."
        recommended_action = "No action required."
    elif status == "CANCELLED":
        sla_status = SlaStatus.CANCELLED.value
        reason = "Escalation handoff was cancelled."
        recommended_action = "No action required."
    elif elapsed_seconds >= sla_limit:
        sla_status = SlaStatus.SLA_BREACHED.value
        breached_at = now_iso
        if status == "PENDING":
            breach_reason = f"PENDING handoff exceeded {sla_type} limit ({elapsed_seconds}s > {sla_limit}s)."
            recommended_action = "Immediate operator acknowledgement required."
        elif status == "ACKNOWLEDGED":
            breach_reason = f"ACKNOWLEDGED handoff unassigned beyond {sla_type} limit ({elapsed_seconds}s > {sla_limit}s)."
            recommended_action = "Assign to lead operator or engineering queue immediately."
        elif status in ("ASSIGNED", "IN_REVIEW"):
            breach_reason = f"Active handoff untouched/in review beyond {sla_type} limit ({elapsed_seconds}s > {sla_limit}s)."
            recommended_action = "Escalate accountability to team lead."
        else:
            breach_reason = f"Escalation SLA breached ({elapsed_seconds}s > {sla_limit}s)."
            recommended_action = "Operator investigation required."
        reason = breach_reason
    elif elapsed_seconds >= int(sla_limit * 0.75):
        sla_status = SlaStatus.APPROACHING_SLA.value
        reason = f"Handoff is approaching SLA deadline ({remaining_seconds}s remaining)."
        recommended_action = f"Prioritize action before {sla_type} deadline expires."
    else:
        sla_status = SlaStatus.WITHIN_SLA.value
        reason = f"Handoff is operating within defined {sla_type} ({remaining_seconds}s remaining)."
        recommended_action = "Proceed with standard operator triage."

    # Stuck Detection Checks
    if priority == "CRITICAL" and not assigned_to and status != "COMPLETED":
        reason += " [STUCK: CRITICAL escalation unassigned to lead engineer]"
        recommended_action = "Immediate lead engineer assignment required."
    elif priority == "HIGH" and not assigned_to and status != "COMPLETED" and elapsed_seconds > 900:
        reason += " [STUCK: HIGH escalation unassigned past 15 minutes]"
        recommended_action = "Assign to lead operator immediately."

    fingerprint = f"{clean_id}_{sla_type}_{sla_status}"
    sla_id = f"sla_{clean_id}"

    with _sla_lock:
        if not _sla_store:
            data = _load_persisted_sla()
            _sla_store.update(data.get("slas", {}))
            _sla_history_store.extend(data.get("history", []))

        prev_record = _sla_store.get(sla_id)
        prev_status = prev_record.get("sla_status", "NONE") if prev_record else "NONE"

        record = {
            "sla_id": sla_id,
            "fingerprint": fingerprint,
            "handoff_id": clean_id,
            "alert_id": handoff.get("alert_id"),
            "payment_id": payment_id,
            "merchant_id": merchant_id,
            "endpoint": endpoint,
            "priority": priority,
            "escalation_level": level,
            "handoff_status": status,
            "sla_status": sla_status,
            "sla_type": sla_type,
            "sla_limit_seconds": sla_limit,
            "elapsed_seconds": elapsed_seconds,
            "remaining_seconds": remaining_seconds,
            "assigned_to": assigned_to,
            "breach_reason": breach_reason,
            "recommended_action": recommended_action,
            "created_at": created_at_str,
            "evaluated_at": now_iso,
            "breached_at": breached_at or (prev_record.get("breached_at") if prev_record else None),
            "correlation_id": handoff.get("correlation_id")
        }

        _sla_store[sla_id] = record

        if prev_status != sla_status:
            _record_sla_history(
                sla_id, clean_id, f"SLA_{sla_status}", prev_status, sla_status,
                reason, payment_id, merchant_id, endpoint
            )
            _save_persisted_sla(_sla_store, _sla_history_store)

    # Emit audit telemetry if status changed or breached
    if prev_status != sla_status:
        try:
            from src.recovery_audit import record_recovery_audit_event
            event_type = "SLA_BREACHED" if sla_status == SlaStatus.SLA_BREACHED.value else f"SLA_{sla_status}"
            record_recovery_audit_event(
                payment_id=payment_id or "unknown",
                event_type=event_type,
                actor_type="SYSTEM",
                source="RECOVERY_ESCALATION_SLA",
                status=sla_status,
                reason=f"Escalation handoff {clean_id} SLA state: {sla_status} ({reason})",
                merchant_id=merchant_id,
                endpoint=endpoint,
                correlation_id=clean_id
            )
        except Exception:
            pass

    return {
        "success": True,
        "sla": record,
        "message": f"SLA evaluated: {sla_status} ({reason})"
    }


def get_escalation_sla_record(handoff_id: str) -> Optional[Dict[str, Any]]:
    """
    Topic 2.2.2.26 - Retrieves the SLA record for a specific handoff.
    """
    clean_id = str(handoff_id or "").strip()
    sla_id = f"sla_{clean_id}"

    # Re-evaluate live outside of lock (evaluate_escalation_sla manages its own lock)
    res = evaluate_escalation_sla(clean_id)
    if res.get("success"):
        return res.get("sla")

    with _sla_lock:
        if not _sla_store:
            data = _load_persisted_sla()
            _sla_store.update(data.get("slas", {}))
            _sla_history_store.extend(data.get("history", []))

        return _sla_store.get(sla_id)


def list_escalation_slas(
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    priority: Optional[str] = None,
    escalation_level: Optional[str] = None,
    sla_status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    handoff_status: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.26 - Lists and filters escalation SLA records.
    """
    from src.recovery_escalation_executor import list_recovery_escalations

    handoffs = list_recovery_escalations(payment_id=payment_id, limit=limit)
    results = []

    for h in handoffs:
        h_id = h.get("handoff_id")
        if h_id:
            eval_res = evaluate_escalation_sla(h_id)
            if eval_res.get("success"):
                sla = eval_res.get("sla")
                if merchant_id and sla.get("merchant_id") != merchant_id:
                    continue
                if priority and sla.get("priority") != priority:
                    continue
                if escalation_level and sla.get("escalation_level") != escalation_level:
                    continue
                if sla_status and sla.get("sla_status") != sla_status:
                    continue
                if assigned_to and sla.get("assigned_to") != assigned_to:
                    continue
                if handoff_status and sla.get("handoff_status") != handoff_status:
                    continue
                results.append(sla)

    results.sort(key=lambda x: x.get("elapsed_seconds", 0), reverse=True)
    return results[:limit]


def list_escalation_sla_breaches(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.26 - Lists only SLA breached handoffs.
    """
    return list_escalation_slas(sla_status=SlaStatus.SLA_BREACHED.value, limit=limit)


def escalate_sla_accountability(
    handoff_id: str,
    operator_id: str,
    reason: str
) -> Dict[str, Any]:
    """
    Topic 2.2.2.26 - Explicitly escalates accountability on a breached or stuck handoff.
    """
    clean_id = str(handoff_id or "").strip()
    clean_op = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not clean_op:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}
    if not clean_reason:
        return {"success": False, "error": "REASON_REQUIRED", "message": "Accountability escalation reason is required."}

    sla_record = get_escalation_sla_record(clean_id)
    if not sla_record:
        return {"success": False, "error": "SLA_RECORD_NOT_FOUND", "message": f"SLA record for {clean_id} not found."}

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=sla_record.get("payment_id", "unknown"),
            event_type="SLA_ACCOUNTABILITY_ESCALATED",
            actor_type="OPERATOR",
            source="RECOVERY_ESCALATION_SLA",
            status="ESCALATED",
            reason=f"SLA accountability escalated by {clean_op}: {clean_reason}",
            merchant_id=sla_record.get("merchant_id"),
            endpoint=sla_record.get("endpoint"),
            correlation_id=clean_id
        )
    except Exception:
        pass

    return {
        "success": True,
        "handoff_id": clean_id,
        "message": f"Accountability escalated for handoff {clean_id} by {clean_op}: {clean_reason}.",
        "sla": sla_record
    }


def reset_escalation_sla_state() -> None:
    """Helper to reset in-memory and persisted SLA records."""
    with _sla_lock:
        _sla_store.clear()
        _sla_history_store.clear()
        if os.path.exists(SLA_LOG_PATH):
            try:
                os.remove(SLA_LOG_PATH)
            except Exception:
                pass
