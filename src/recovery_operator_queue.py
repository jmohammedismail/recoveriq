"""
RecoverIQ - Recovery Escalation SLA Automation & Operator Work Queue (Topic 2.2.2.26 / 2.2.2.27)

Authoritative operator work-queue orchestration layer that automatically ranks, organizes,
and manages active recovery escalation handoffs and SLAs for human operators.

STRICT BOUNDARIES:
- Visibility & workflow coordination layer only; NEVER directly mutates PaymentState or CircuitState.
- NEVER automatically triggers recoveries, retries, refunds, or auto-repairs.
- Delegates handoff status and assignment updates directly to src/recovery_escalation_executor.py.
- Obtains authoritative live SLA metrics directly from src/recovery_escalation_sla.py.
- Thread-safe concurrency control via _operator_queue_lock.
- Persists queue items and history to logs/recovery_operator_queue.json.
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
QUEUE_LOG_PATH = os.path.join(LOGS_DIR, "recovery_operator_queue.json")

_operator_queue_lock = threading.Lock()
_queue_store: Dict[str, Dict[str, Any]] = {}
_queue_history_store: List[Dict[str, Any]] = []


class QueueUrgency(str, Enum):
    """Urgency tiers for operator queue ranking."""
    CRITICAL_BREACHED = "CRITICAL_BREACHED"
    CRITICAL_APPROACHING = "CRITICAL_APPROACHING"
    HIGH_BREACHED = "HIGH_BREACHED"
    HIGH_APPROACHING = "HIGH_APPROACHING"
    CRITICAL_WITHIN_SLA = "CRITICAL_WITHIN_SLA"
    HIGH_WITHIN_SLA = "HIGH_WITHIN_SLA"
    WARNING_BREACHED = "WARNING_BREACHED"
    WARNING_APPROACHING = "WARNING_APPROACHING"
    STANDARD = "STANDARD"


class QueueItemStatus(str, Enum):
    """Lifecycle status of an operator work-queue item."""
    QUEUED = "QUEUED"
    URGENT = "URGENT"
    SLA_BREACHED = "SLA_BREACHED"
    ASSIGNED = "ASSIGNED"
    IN_REVIEW = "IN_REVIEW"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


def _load_persisted_queue() -> Dict[str, Any]:
    if os.path.exists(QUEUE_LOG_PATH):
        try:
            with open(QUEUE_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"items": {}, "history": []}
    return {"items": {}, "history": []}


def _save_persisted_queue(items: Dict[str, Dict[str, Any]], history: List[Dict[str, Any]]) -> None:
    try:
        with open(QUEUE_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "items": items,
                "history": history[-500:]
            }, f, indent=2)
    except Exception:
        pass


def _record_queue_history(
    queue_item_id: str,
    handoff_id: str,
    action: str,
    operator_id: str,
    reason: str,
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    evt = {
        "event_id": f"qhist_{uuid.uuid4().hex[:10]}",
        "queue_item_id": queue_item_id,
        "handoff_id": handoff_id,
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "endpoint": endpoint,
        "action": action,
        "operator_id": operator_id,
        "reason": reason,
        "timestamp": now_iso
    }
    _queue_history_store.append(evt)
    return evt


def _calculate_queue_rank(priority: str, sla_status: str, escalation_level: str) -> tuple:
    """
    Computes deterministic ranking tuple (lower value = higher priority in queue).
    1. CRITICAL + SLA_BREACHED (Tier 1)
    2. CRITICAL + APPROACHING_SLA (Tier 2)
    3. HIGH + SLA_BREACHED (Tier 3)
    4. HIGH + APPROACHING_SLA (Tier 4)
    5. CRITICAL + WITHIN_SLA (Tier 5)
    6. HIGH + WITHIN_SLA (Tier 6)
    7. WARNING / ELEVATED + SLA_BREACHED (Tier 7)
    8. WARNING / ELEVATED + APPROACHING_SLA (Tier 8)
    9. INFO / NORMAL (Tier 9)
    """
    p = str(priority or "WARNING").upper()
    sla = str(sla_status or "WITHIN_SLA").upper()

    if p == "CRITICAL" and sla == "SLA_BREACHED":
        tier = 1
        urgency = QueueUrgency.CRITICAL_BREACHED.value
    elif p == "CRITICAL" and sla == "APPROACHING_SLA":
        tier = 2
        urgency = QueueUrgency.CRITICAL_APPROACHING.value
    elif p == "HIGH" and sla == "SLA_BREACHED":
        tier = 3
        urgency = QueueUrgency.HIGH_BREACHED.value
    elif p == "HIGH" and sla == "APPROACHING_SLA":
        tier = 4
        urgency = QueueUrgency.HIGH_APPROACHING.value
    elif p == "CRITICAL":
        tier = 5
        urgency = QueueUrgency.CRITICAL_WITHIN_SLA.value
    elif p == "HIGH":
        tier = 6
        urgency = QueueUrgency.HIGH_WITHIN_SLA.value
    elif sla == "SLA_BREACHED":
        tier = 7
        urgency = QueueUrgency.WARNING_BREACHED.value
    elif sla == "APPROACHING_SLA":
        tier = 8
        urgency = QueueUrgency.WARNING_APPROACHING.value
    else:
        tier = 9
        urgency = QueueUrgency.STANDARD.value

    return tier, urgency


def sync_operator_queue(operator_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Topic 2.2.2.26 - Synchronizes active escalation handoffs and live SLA records into the operator queue.
    Deterministic and idempotent.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    from src.recovery_escalation_executor import list_recovery_escalations
    from src.recovery_escalation_sla import evaluate_escalation_sla

    handoffs = list_recovery_escalations(limit=200)

    with _operator_queue_lock:
        if not _queue_store:
            data = _load_persisted_queue()
            _queue_store.update(data.get("items", {}))
            _queue_history_store.extend(data.get("history", []))

        synced_count = 0
        new_items_count = 0

        for handoff in handoffs:
            h_id = handoff.get("handoff_id")
            if not h_id:
                continue

            alert_id = handoff.get("alert_id")
            payment_id = handoff.get("payment_id")
            merchant_id = handoff.get("merchant_id", "merchant_demo")
            endpoint = handoff.get("endpoint", "payment-webhook")
            priority = handoff.get("priority", "WARNING")
            level = handoff.get("escalation_level", "NORMAL")
            h_status = handoff.get("handoff_status", "PENDING")
            assigned_to = handoff.get("assigned_to")
            target_role = handoff.get("target_role", "OPERATOR_QUEUE")
            reason = handoff.get("reason", "")
            evidence = handoff.get("evidence", "")
            rec_action = handoff.get("recommended_action", "")
            correlation_id = handoff.get("correlation_id", h_id)

            # Get Live SLA Record
            sla_eval = evaluate_escalation_sla(h_id)
            sla_record = sla_eval.get("sla", {}) if sla_eval.get("success") else {}
            sla_status = sla_record.get("sla_status", "WITHIN_SLA")
            sla_allowed = sla_record.get("sla_limit_seconds", 1800)
            sla_elapsed = sla_record.get("elapsed_seconds", 0)
            sla_remaining = sla_record.get("remaining_seconds", 1800)

            tier, urgency = _calculate_queue_rank(priority, sla_status, level)

            # Derive Queue Status
            if h_status in ("COMPLETED", "CANCELLED"):
                q_status = h_status
            elif sla_status == "SLA_BREACHED":
                q_status = QueueItemStatus.SLA_BREACHED.value
            elif priority == "CRITICAL":
                q_status = QueueItemStatus.URGENT.value
            elif h_status == "ASSIGNED":
                q_status = QueueItemStatus.ASSIGNED.value
            elif h_status == "IN_REVIEW":
                q_status = QueueItemStatus.IN_REVIEW.value
            else:
                q_status = QueueItemStatus.QUEUED.value

            queue_item_id = f"qitem_{h_id}"
            is_new = queue_item_id not in _queue_store

            item_data = {
                "queue_item_id": queue_item_id,
                "handoff_id": h_id,
                "alert_id": alert_id,
                "payment_id": payment_id,
                "merchant_id": merchant_id,
                "endpoint": endpoint,
                "priority": priority,
                "escalation_level": level,
                "handoff_status": h_status,
                "queue_status": q_status,
                "sla_status": sla_status,
                "sla_allowed_seconds": sla_allowed,
                "sla_elapsed_seconds": sla_elapsed,
                "sla_remaining_seconds": sla_remaining,
                "assigned_to": assigned_to,
                "target_role": target_role,
                "tier": tier,
                "urgency": urgency,
                "recommended_action": rec_action,
                "reason": reason,
                "evidence": evidence,
                "created_at": handoff.get("created_at", now_iso),
                "updated_at": now_iso,
                "correlation_id": correlation_id
            }

            _queue_store[queue_item_id] = item_data
            synced_count += 1
            if is_new:
                new_items_count += 1
                _record_queue_history(
                    queue_item_id, h_id, "QUEUE_ITEM_CREATED",
                    operator_id or "SYSTEM", f"Item added to operator queue: {priority} ({urgency})",
                    payment_id, merchant_id, endpoint
                )

        _save_persisted_queue(_queue_store, _queue_history_store)

    # Emit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id="queue_sync",
            event_type="OPERATOR_QUEUE_SYNC_COMPLETED",
            actor_type="OPERATOR" if operator_id else "SYSTEM",
            source="RECOVERY_OPERATOR_QUEUE",
            status="SUCCESS",
            reason=f"Operator queue synchronized: {synced_count} items ({new_items_count} new)",
            merchant_id="merchant_demo",
            endpoint="payment-webhook",
            correlation_id=f"sync_{uuid.uuid4().hex[:8]}"
        )
    except Exception:
        pass

    return {
        "success": True,
        "synced_count": synced_count,
        "new_items_count": new_items_count,
        "message": f"Operator queue synchronized ({synced_count} items)."
    }


def list_operator_queue(
    payment_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    priority: Optional[str] = None,
    escalation_level: Optional[str] = None,
    sla_status: Optional[str] = None,
    handoff_status: Optional[str] = None,
    queue_status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    urgency: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.26 - Lists and deterministically ranks operator queue items.
    """
    # Trigger auto sync to ensure live data
    sync_operator_queue()

    with _operator_queue_lock:
        items = list(_queue_store.values())

    results = []
    for item in items:
        if active_only and item.get("handoff_status") in ("COMPLETED", "CANCELLED"):
            continue
        if payment_id and item.get("payment_id") != payment_id:
            continue
        if merchant_id and item.get("merchant_id") != merchant_id:
            continue
        if priority and item.get("priority") != priority:
            continue
        if escalation_level and item.get("escalation_level") != escalation_level:
            continue
        if sla_status and item.get("sla_status") != sla_status:
            continue
        if handoff_status and item.get("handoff_status") != handoff_status:
            continue
        if queue_status and item.get("queue_status") != queue_status:
            continue
        if assigned_to and item.get("assigned_to") != assigned_to:
            continue
        if urgency and item.get("urgency") != urgency:
            continue
        results.append(item)

    # Deterministic Ranking Sort:
    # 1. Tier (1 to 9)
    # 2. SLA remaining seconds (ascending)
    # 3. Elapsed seconds (descending)
    # 4. Unassigned (assigned_to is None) before assigned
    # 5. Created at (ascending - older first)
    results.sort(key=lambda x: (
        x.get("tier", 9),
        x.get("sla_remaining_seconds", 999999),
        -x.get("sla_elapsed_seconds", 0),
        0 if not x.get("assigned_to") else 1,
        x.get("created_at", "")
    ))

    # Assign queue_rank
    for idx, item in enumerate(results, 1):
        item["queue_rank"] = idx

    return results[:limit]


def get_operator_queue_item(queue_item_id: str) -> Optional[Dict[str, Any]]:
    """
    Topic 2.2.2.26 - Retrieves a single queue item with current underlying handoff & SLA details.
    """
    clean_id = str(queue_item_id or "").strip()
    sync_operator_queue()

    with _operator_queue_lock:
        item = _queue_store.get(clean_id)
        if not item:
            return None

        history = [evt for evt in _queue_history_store if evt.get("queue_item_id") == clean_id]
        item_copy = dict(item)
        item_copy["history"] = sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)
        return item_copy


def claim_operator_queue_item(
    queue_item_id: str,
    operator_id: str,
    reason: str = "Claimed from operator queue"
) -> Dict[str, Any]:
    """
    Topic 2.2.2.26 - Claims an unassigned queue item for the specified operator.
    Delegates to recovery_escalation_executor.assign_recovery_escalation.
    """
    clean_id = str(queue_item_id or "").strip()
    clean_op = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()

    if not clean_op:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}

    with _operator_queue_lock:
        item = _queue_store.get(clean_id)
        if not item:
            return {"success": False, "error": "QUEUE_ITEM_NOT_FOUND", "message": f"Queue item {clean_id} not found."}
        handoff_id = item.get("handoff_id")

    from src.recovery_escalation_executor import assign_recovery_escalation
    assign_res = assign_recovery_escalation(
        handoff_id=handoff_id,
        assignee_id=clean_op,
        operator_id=clean_op,
        reason=clean_reason
    )

    if assign_res.get("success"):
        with _operator_queue_lock:
            if clean_id in _queue_store:
                _queue_store[clean_id]["assigned_to"] = clean_op
                _queue_store[clean_id]["queue_status"] = QueueItemStatus.ASSIGNED.value
                _queue_store[clean_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            _record_queue_history(
                clean_id, handoff_id, "OPERATOR_QUEUE_ITEM_CLAIMED",
                clean_op, clean_reason, item.get("payment_id"), item.get("merchant_id"), item.get("endpoint")
            )
            _save_persisted_queue(_queue_store, _queue_history_store)

    return assign_res


def release_operator_queue_item(
    queue_item_id: str,
    operator_id: str,
    reason: str = "Released back to queue"
) -> Dict[str, Any]:
    """
    Topic 2.2.2.26 - Releases an operator assignment back to unassigned state.
    """
    clean_id = str(queue_item_id or "").strip()
    clean_op = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()

    if not clean_op:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}

    with _operator_queue_lock:
        item = _queue_store.get(clean_id)
        if not item:
            return {"success": False, "error": "QUEUE_ITEM_NOT_FOUND", "message": f"Queue item {clean_id} not found."}
        handoff_id = item.get("handoff_id")

    from src.recovery_escalation_executor import _handoffs_store, _executor_lock, _save_persisted_executions, _handoff_history_store
    with _executor_lock:
        if handoff_id in _handoffs_store:
            _handoffs_store[handoff_id]["assigned_to"] = None
            _handoffs_store[handoff_id]["handoff_status"] = "PENDING"
            _handoffs_store[handoff_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_persisted_executions(_handoffs_store, _handoff_history_store)

    with _operator_queue_lock:
        if clean_id in _queue_store:
            _queue_store[clean_id]["assigned_to"] = None
            _queue_store[clean_id]["queue_status"] = QueueItemStatus.QUEUED.value
            _queue_store[clean_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _record_queue_history(
            clean_id, handoff_id, "OPERATOR_QUEUE_ITEM_RELEASED",
            clean_op, clean_reason, item.get("payment_id"), item.get("merchant_id"), item.get("endpoint")
        )
        _save_persisted_queue(_queue_store, _queue_history_store)

    return {
        "success": True,
        "queue_item_id": clean_id,
        "message": f"Queue item {clean_id} released back to queue by {clean_op}."
    }


def mark_operator_queue_in_review(
    queue_item_id: str,
    operator_id: str,
    reason: str = "Investigation in progress"
) -> Dict[str, Any]:
    """
    Topic 2.2.2.26 - Moves a queue item into IN_REVIEW state.
    """
    clean_id = str(queue_item_id or "").strip()
    clean_op = str(operator_id or "").strip()
    clean_reason = str(reason or "").strip()

    if not clean_op:
        return {"success": False, "error": "OPERATOR_ID_REQUIRED", "message": "Operator ID is required."}

    with _operator_queue_lock:
        item = _queue_store.get(clean_id)
        if not item:
            return {"success": False, "error": "QUEUE_ITEM_NOT_FOUND", "message": f"Queue item {clean_id} not found."}
        handoff_id = item.get("handoff_id")

    from src.recovery_escalation_executor import _handoffs_store, _executor_lock, _save_persisted_executions, _handoff_history_store
    with _executor_lock:
        if handoff_id in _handoffs_store:
            _handoffs_store[handoff_id]["handoff_status"] = "IN_REVIEW"
            if not _handoffs_store[handoff_id].get("assigned_to"):
                _handoffs_store[handoff_id]["assigned_to"] = clean_op
            _handoffs_store[handoff_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_persisted_executions(_handoffs_store, _handoff_history_store)

    with _operator_queue_lock:
        if clean_id in _queue_store:
            _queue_store[clean_id]["queue_status"] = QueueItemStatus.IN_REVIEW.value
            _queue_store[clean_id]["handoff_status"] = "IN_REVIEW"
            _queue_store[clean_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _record_queue_history(
            clean_id, handoff_id, "OPERATOR_QUEUE_ITEM_REVIEW_STARTED",
            clean_op, clean_reason, item.get("payment_id"), item.get("merchant_id"), item.get("endpoint")
        )
        _save_persisted_queue(_queue_store, _queue_history_store)

    return {
        "success": True,
        "queue_item_id": clean_id,
        "message": f"Queue item {clean_id} moved to IN_REVIEW by {clean_op}."
    }


def get_operator_queue_summary() -> Dict[str, Any]:
    """
    Topic 2.2.2.26 / 2.2.2.27 - Computes aggregate metrics from active and historical queue records.
    """
    sync_operator_queue()

    with _operator_queue_lock:
        items = list(_queue_store.values())

    total_active = 0
    critical_count = 0
    high_count = 0
    warning_count = 0
    sla_breached_count = 0
    approaching_sla_count = 0
    unassigned_count = 0
    assigned_count = 0
    in_review_count = 0
    blocked_count = 0
    completed_today_count = 0
    critical_unassigned_count = 0
    oldest_active_age = 0
    oldest_unassigned_age = 0
    total_active_age = 0

    now_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for item in items:
        status = item.get("handoff_status")
        priority = item.get("priority", "WARNING").upper()
        sla_status = item.get("sla_status")
        assigned = item.get("assigned_to")
        updated_at = item.get("updated_at", "")
        elapsed = item.get("sla_elapsed_seconds", 0)

        if status == "COMPLETED":
            if updated_at.startswith(now_date_str):
                completed_today_count += 1
            continue

        if status == "CANCELLED":
            continue

        total_active += 1
        total_active_age += elapsed

        if elapsed > oldest_active_age:
            oldest_active_age = elapsed

        if priority == "CRITICAL":
            critical_count += 1
        elif priority == "HIGH":
            high_count += 1
        elif priority in ("WARNING", "ELEVATED"):
            warning_count += 1

        if sla_status == "SLA_BREACHED":
            sla_breached_count += 1
        elif sla_status == "APPROACHING_SLA":
            approaching_sla_count += 1

        if not assigned:
            unassigned_count += 1
            if priority == "CRITICAL":
                critical_unassigned_count += 1
            if elapsed > oldest_unassigned_age:
                oldest_unassigned_age = elapsed
        else:
            assigned_count += 1

        if status == "IN_REVIEW":
            in_review_count += 1
        elif status == "BLOCKED":
            blocked_count += 1

    avg_active_age = int(total_active_age / total_active) if total_active > 0 else 0

    return {
        "success": True,
        "summary": {
            "total_active": total_active,
            "critical": critical_count,
            "high": high_count,
            "warning": warning_count,
            "sla_breached": sla_breached_count,
            "approaching_sla": approaching_sla_count,
            "unassigned": unassigned_count,
            "assigned": assigned_count,
            "in_review": in_review_count,
            "blocked": blocked_count,
            "completed_today": completed_today_count,
            "oldest_active_age_seconds": oldest_active_age,
            "oldest_unassigned_age_seconds": oldest_unassigned_age,
            "critical_unassigned_count": critical_unassigned_count,
            "average_active_age_seconds": avg_active_age,
            "synced_at": datetime.now(timezone.utc).isoformat()
        }
    }


def reset_operator_queue_state() -> None:
    """Helper to reset in-memory and persisted queue records."""
    with _operator_queue_lock:
        _queue_store.clear()
        _queue_history_store.clear()
        if os.path.exists(QUEUE_LOG_PATH):
            try:
                os.remove(QUEUE_LOG_PATH)
            except Exception:
                pass
