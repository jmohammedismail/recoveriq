"""
RecoverIQ - Recovery Queue Watchdog, SLA Monitor & Real-Time Workload Management (Topic 2.2.2.27)

Continuous watchdog engine that monitors escalation handoffs, SLA compliance deadlines,
and recovery integrity signals, automatically triggering operator work-queue synchronizations
upon detecting meaningful workload or priority changes.

STRICT BOUNDARIES:
- Read-only monitoring & change-detection layer; NEVER directly mutates PaymentState or CircuitState.
- NEVER triggers automated recoveries, retries, refunds, or auto-repairs.
- Delegates queue updates strictly to src/recovery_operator_queue.py and SLA to src/recovery_escalation_sla.py.
- Thread-safe concurrency control via _watchdog_lock.
- Persists watchdog state, metrics, and change history in logs/recovery_queue_watchdog.json.
- Zero credential, secret, password, or raw payload storage.
"""

import os
import json
import uuid
import hashlib
import threading
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
WATCHDOG_LOG_PATH = os.path.join(LOGS_DIR, "recovery_queue_watchdog.json")

_watchdog_lock = threading.Lock()
_watchdog_state: Dict[str, Any] = {
    "status": "WATCHING",
    "last_evaluation": None,
    "last_change_detected": None,
    "last_queue_sync": None,
    "cycle_count": 0,
    "refresh_count": 0,
    "monitored_handoff_count": 0,
    "last_snapshot_fingerprint": None,
    "degraded_reason": None
}
_watchdog_changes_store: List[Dict[str, Any]] = []


class WatchdogStatus(str, Enum):
    """Authoritative lifecycle status of the queue watchdog."""
    WATCHING = "WATCHING"
    CHANGE_DETECTED = "CHANGE_DETECTED"
    QUEUE_REFRESH_REQUIRED = "QUEUE_REFRESH_REQUIRED"
    QUEUE_REFRESHED = "QUEUE_REFRESHED"
    NO_CHANGE = "NO_CHANGE"
    WATCHDOG_DEGRADED = "WATCHDOG_DEGRADED"
    WATCHDOG_UNAVAILABLE = "WATCHDOG_UNAVAILABLE"


class WorkloadStatus(str, Enum):
    """Operator workload capacity indicator."""
    NORMAL = "NORMAL"
    BUSY = "BUSY"
    OVERLOADED = "OVERLOADED"
    CRITICAL_LOAD = "CRITICAL_LOAD"


def _load_persisted_watchdog() -> Dict[str, Any]:
    if os.path.exists(WATCHDOG_LOG_PATH):
        try:
            with open(WATCHDOG_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"state": _watchdog_state, "changes": []}
    return {"state": _watchdog_state, "changes": []}


def _save_persisted_watchdog(state: Dict[str, Any], changes: List[Dict[str, Any]]) -> None:
    try:
        with open(WATCHDOG_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "state": state,
                "changes": changes[-500:]
            }, f, indent=2)
    except Exception:
        pass


def _record_watchdog_change(
    event_type: str,
    handoff_id: Optional[str],
    payment_id: Optional[str],
    description: str,
    previous_val: Optional[str] = None,
    new_val: Optional[str] = None,
    operator_id: Optional[str] = None
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    evt = {
        "change_id": f"qchg_{uuid.uuid4().hex[:10]}",
        "event_type": event_type,
        "handoff_id": handoff_id,
        "payment_id": payment_id,
        "description": description,
        "previous_value": previous_val,
        "new_value": new_val,
        "operator_id": operator_id or "WATCHDOG",
        "timestamp": now_iso
    }
    _watchdog_changes_store.append(evt)
    return evt


def _compute_snapshot_fingerprint(handoffs: List[Dict[str, Any]]) -> str:
    """Computes deterministic hash across active handoffs and their live states."""
    parts = []
    for h in sorted(handoffs, key=lambda x: x.get("handoff_id", "")):
        h_id = h.get("handoff_id", "")
        status = h.get("handoff_status", "")
        priority = h.get("priority", "")
        assigned = h.get("assigned_to", "")
        level = h.get("escalation_level", "")
        parts.append(f"{h_id}:{status}:{priority}:{assigned}:{level}")
    raw_str = "|".join(parts)
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def run_queue_watchdog_cycle(operator_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Topic 2.2.2.27 - Runs one complete evaluation cycle of the SLA & workload watchdog.
    Detects priority changes, SLA transitions, and contradictions, auto-syncing the queue.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        from src.recovery_escalation_executor import list_recovery_escalations
        from src.recovery_escalation_sla import evaluate_escalation_sla
        from src.recovery_operator_queue import sync_operator_queue

        handoffs = list_recovery_escalations(limit=200)
    except Exception as e:
        with _watchdog_lock:
            _watchdog_state["status"] = WatchdogStatus.WATCHDOG_DEGRADED.value
            _watchdog_state["last_evaluation"] = now_iso
            _watchdog_state["degraded_reason"] = f"Failed to query escalation signals: {str(e)}"
            _save_persisted_watchdog(_watchdog_state, _watchdog_changes_store)
        return {
            "success": False,
            "status": WatchdogStatus.WATCHDOG_DEGRADED.value,
            "message": f"Queue watchdog degraded: {str(e)}",
            "cycle_summary": {"changes_detected": 0, "queue_refreshed": False}
        }

    # Analyze Handoffs and SLA Signals
    changes_detected = []
    has_critical_issue = False
    has_sla_breach = False

    current_fingerprint = _compute_snapshot_fingerprint(handoffs)

    with _watchdog_lock:
        if not _watchdog_changes_store:
            data = _load_persisted_watchdog()
            _watchdog_state.update(data.get("state", {}))
            _watchdog_changes_store.extend(data.get("changes", []))

        prev_fingerprint = _watchdog_state.get("last_snapshot_fingerprint")
        _watchdog_state["cycle_count"] = _watchdog_state.get("cycle_count", 0) + 1
        _watchdog_state["last_evaluation"] = now_iso
        _watchdog_state["monitored_handoff_count"] = len(handoffs)

        # Inspect individual handoff SLA health
        for h in handoffs:
            h_id = h.get("handoff_id")
            pay_id = h.get("payment_id")
            prio = h.get("priority", "WARNING")

            if prio == "CRITICAL" and h.get("handoff_status") not in ("COMPLETED", "CANCELLED"):
                has_critical_issue = True

            # Evaluate Live SLA
            sla_res = evaluate_escalation_sla(h_id)
            if sla_res.get("success"):
                sla_rec = sla_res.get("sla", {})
                sla_st = sla_rec.get("sla_status")
                if sla_st == "SLA_BREACHED":
                    has_sla_breach = True

        # Check if snapshot fingerprint changed
        fingerprint_changed = prev_fingerprint != current_fingerprint

        if fingerprint_changed or has_critical_issue or has_sla_breach:
            sync_res = sync_operator_queue(operator_id=operator_id or "WATCHDOG")
            _watchdog_state["refresh_count"] = _watchdog_state.get("refresh_count", 0) + 1
            _watchdog_state["last_queue_sync"] = now_iso
            _watchdog_state["last_snapshot_fingerprint"] = current_fingerprint
            _watchdog_state["last_change_detected"] = now_iso

            if has_critical_issue and has_sla_breach:
                watchdog_status = WatchdogStatus.CHANGE_DETECTED.value
                change_desc = "CRITICAL escalation & SLA breach detected; queue synchronized."
                evt_type = "QUEUE_CRITICAL_ESCALATION_DETECTED"
            elif has_critical_issue:
                watchdog_status = WatchdogStatus.CHANGE_DETECTED.value
                change_desc = "CRITICAL recovery issue active; queue updated."
                evt_type = "QUEUE_CRITICAL_ESCALATION_DETECTED"
            elif has_sla_breach:
                watchdog_status = WatchdogStatus.CHANGE_DETECTED.value
                change_desc = "SLA breach detected; queue reordered."
                evt_type = "QUEUE_SLA_BREACH_DETECTED"
            else:
                watchdog_status = WatchdogStatus.QUEUE_REFRESHED.value
                change_desc = "Escalation handoff state changed; queue synchronized."
                evt_type = "QUEUE_PRIORITY_CHANGED"

            _watchdog_state["status"] = watchdog_status
            _record_watchdog_change(evt_type, None, None, change_desc, prev_fingerprint, current_fingerprint, operator_id)
            _save_persisted_watchdog(_watchdog_state, _watchdog_changes_store)

            # Telemetry
            try:
                from src.recovery_audit import record_recovery_audit_event
                record_recovery_audit_event(
                    payment_id="queue_watchdog",
                    event_type="QUEUE_WATCHDOG_REFRESH_COMPLETED",
                    actor_type="SYSTEM",
                    source="RECOVERY_QUEUE_WATCHDOG",
                    status="SUCCESS",
                    reason=change_desc,
                    merchant_id="merchant_demo",
                    endpoint="payment-webhook",
                    correlation_id=f"wd_{uuid.uuid4().hex[:8]}"
                )
            except Exception:
                pass

            return {
                "success": True,
                "status": watchdog_status,
                "message": change_desc,
                "cycle_summary": {
                    "changes_detected": 1,
                    "queue_refreshed": True,
                    "monitored_handoffs": len(handoffs),
                    "cycle_count": _watchdog_state["cycle_count"]
                }
            }
        else:
            _watchdog_state["status"] = WatchdogStatus.NO_CHANGE.value
            _save_persisted_watchdog(_watchdog_state, _watchdog_changes_store)
            return {
                "success": True,
                "status": WatchdogStatus.NO_CHANGE.value,
                "message": "Watchdog cycle complete. No workload or priority changes detected.",
                "cycle_summary": {
                    "changes_detected": 0,
                    "queue_refreshed": False,
                    "monitored_handoffs": len(handoffs),
                    "cycle_count": _watchdog_state["cycle_count"]
                }
            }


def get_watchdog_status() -> Dict[str, Any]:
    """
    Topic 2.2.2.27 - Retrieves current watchdog state, cycle counts, and health indicator.
    """
    with _watchdog_lock:
        if not _watchdog_changes_store:
            data = _load_persisted_watchdog()
            _watchdog_state.update(data.get("state", {}))
            _watchdog_changes_store.extend(data.get("changes", []))

        return {
            "success": True,
            "watchdog": dict(_watchdog_state)
        }


def get_operator_workload(
    operator_id: Optional[str] = None,
    priority: Optional[str] = None,
    escalation_level: Optional[str] = None,
    sla_status: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.27 - Computes workload capacity, assigned volume, and backlog health for an operator.
    """
    from src.recovery_operator_queue import list_operator_queue

    items = list_operator_queue(
        priority=priority,
        escalation_level=escalation_level,
        sla_status=sla_status,
        active_only=True,
        limit=200
    )

    clean_op = str(operator_id or "").strip()
    now = datetime.now(timezone.utc)

    assigned_count = 0
    in_review_count = 0
    breached_count = 0
    approaching_count = 0
    critical_count = 0
    oldest_age = 0

    for item in items:
        assigned = item.get("assigned_to")
        if clean_op and assigned != clean_op:
            continue

        assigned_count += 1
        if item.get("queue_status") == "IN_REVIEW" or item.get("handoff_status") == "IN_REVIEW":
            in_review_count += 1
        if item.get("sla_status") == "SLA_BREACHED":
            breached_count += 1
        elif item.get("sla_status") == "APPROACHING_SLA":
            approaching_count += 1
        if item.get("priority") == "CRITICAL":
            critical_count += 1

        elapsed = item.get("sla_elapsed_seconds", 0)
        if elapsed > oldest_age:
            oldest_age = elapsed

    # Compute Workload Status Tier
    if critical_count > 0 or breached_count >= 3:
        workload_status = WorkloadStatus.CRITICAL_LOAD.value
    elif assigned_count >= 8 or breached_count > 0:
        workload_status = WorkloadStatus.OVERLOADED.value
    elif assigned_count >= 4 or approaching_count >= 2:
        workload_status = WorkloadStatus.BUSY.value
    else:
        workload_status = WorkloadStatus.NORMAL.value

    return {
        "success": True,
        "operator_id": clean_op or "ALL_OPERATORS",
        "workload": {
            "assigned_count": assigned_count,
            "in_review_count": in_review_count,
            "breached_count": breached_count,
            "approaching_count": approaching_count,
            "critical_count": critical_count,
            "oldest_assignment_age_seconds": oldest_age,
            "workload_status": workload_status,
            "evaluated_at": now.isoformat()
        }
    }


def get_recent_queue_changes(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.27 - Returns chronological list of recent queue-impacting change events.
    """
    with _watchdog_lock:
        if not _watchdog_changes_store:
            data = _load_persisted_watchdog()
            _watchdog_changes_store.extend(data.get("changes", []))

        return sorted(_watchdog_changes_store, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]


def reset_queue_watchdog_state() -> None:
    """Helper to reset in-memory and persisted watchdog records."""
    with _watchdog_lock:
        _watchdog_state.update({
            "status": "WATCHING",
            "last_evaluation": None,
            "last_change_detected": None,
            "last_queue_sync": None,
            "cycle_count": 0,
            "refresh_count": 0,
            "monitored_handoff_count": 0,
            "last_snapshot_fingerprint": None,
            "degraded_reason": None
        })
        _watchdog_changes_store.clear()
        if os.path.exists(WATCHDOG_LOG_PATH):
            try:
                os.remove(WATCHDOG_LOG_PATH)
            except Exception:
                pass
