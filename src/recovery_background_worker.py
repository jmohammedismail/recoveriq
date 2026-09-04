"""
RecoverIQ - Recovery Operator Queue Background Worker & Auto-Refresh Daemon (Topic 2.2.2.28)

Authoritative background execution layer that continuously schedules and executes the
queue watchdog cycle, keeping escalation handoffs, SLAs, and operator queue rankings
synchronized in real-time without requiring manual operator intervention.

STRICT BOUNDARIES:
- Observational background scheduler only; NEVER directly mutates PaymentState or CircuitState.
- NEVER triggers autonomous recoveries, retries, refunds, or auto-repairs.
- Delegates cycle execution strictly to src/recovery_queue_watchdog.py and queue updates to src/recovery_operator_queue.py.
- Thread-safe concurrency control via _worker_lock and _cycle_lock.
- Persists worker state and events to logs/recovery_background_worker.json.
- Zero credential, secret, password, or raw payload storage.
"""

import os
import json
import time
import uuid
import threading
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
WORKER_LOG_PATH = os.path.join(LOGS_DIR, "recovery_background_worker.json")

DEFAULT_INTERVAL_SECONDS = int(os.environ.get("RECOVERY_QUEUE_WATCHDOG_INTERVAL_SECONDS", "10"))

_worker_lock = threading.Lock()
_cycle_lock = threading.Lock()
_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_pause_event = threading.Event()


class WorkerState(str, Enum):
    """Lifecycle status of the recovery background worker."""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


_worker_metadata: Dict[str, Any] = {
    "worker_id": None,
    "current_state": WorkerState.STOPPED.value,
    "started_at": None,
    "stopped_at": None,
    "last_cycle_at": None,
    "next_cycle_at": None,
    "cycle_count": 0,
    "successful_cycles": 0,
    "failed_cycles": 0,
    "last_error": None,
    "configured_interval_seconds": DEFAULT_INTERVAL_SECONDS
}
_worker_history_store: List[Dict[str, Any]] = []


def _load_persisted_worker() -> Dict[str, Any]:
    if os.path.exists(WORKER_LOG_PATH):
        try:
            with open(WORKER_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"metadata": _worker_metadata, "history": []}
    return {"metadata": _worker_metadata, "history": []}


def _save_persisted_worker(metadata: Dict[str, Any], history: List[Dict[str, Any]]) -> None:
    try:
        with open(WORKER_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": metadata,
                "history": history[-500:]
            }, f, indent=2)
    except Exception:
        pass


def _record_worker_event(
    event_type: str,
    description: str,
    operator_id: Optional[str] = None
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    evt = {
        "event_id": f"wdevt_{uuid.uuid4().hex[:10]}",
        "worker_id": _worker_metadata.get("worker_id"),
        "event_type": event_type,
        "description": description,
        "operator_id": operator_id or "SYSTEM",
        "timestamp": now_iso
    }
    _worker_history_store.append(evt)
    return evt


def _execute_single_cycle(operator_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes a single cycle of the queue watchdog under _cycle_lock.
    Guarantees no overlapping cycles.
    """
    if not _cycle_lock.acquire(blocking=False):
        return {
            "success": False,
            "message": "Cycle already in progress. Skipping concurrent run.",
            "skipped": True
        }

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    try:
        from src.recovery_queue_watchdog import run_queue_watchdog_cycle

        _worker_metadata["last_cycle_at"] = now_iso
        _worker_metadata["cycle_count"] = _worker_metadata.get("cycle_count", 0) + 1

        cycle_res = run_queue_watchdog_cycle(operator_id=operator_id or "BACKGROUND_WORKER")

        if cycle_res.get("success"):
            _worker_metadata["successful_cycles"] = _worker_metadata.get("successful_cycles", 0) + 1
            _worker_metadata["last_error"] = None
            if _worker_metadata.get("current_state") == WorkerState.DEGRADED.value:
                _worker_metadata["current_state"] = WorkerState.RUNNING.value
        else:
            _worker_metadata["failed_cycles"] = _worker_metadata.get("failed_cycles", 0) + 1
            _worker_metadata["last_error"] = cycle_res.get("message")
            _worker_metadata["current_state"] = WorkerState.DEGRADED.value

        interval = _worker_metadata.get("configured_interval_seconds", DEFAULT_INTERVAL_SECONDS)
        next_cycle_dt = now + timedelta(seconds=interval)
        _worker_metadata["next_cycle_at"] = next_cycle_dt.isoformat()

        _save_persisted_worker(_worker_metadata, _worker_history_store)
        return cycle_res
    except Exception as e:
        _worker_metadata["failed_cycles"] = _worker_metadata.get("failed_cycles", 0) + 1
        _worker_metadata["last_error"] = str(e)
        _worker_metadata["current_state"] = WorkerState.DEGRADED.value
        _save_persisted_worker(_worker_metadata, _worker_history_store)
        return {
            "success": False,
            "error": "CYCLE_EXECUTION_ERROR",
            "message": f"Background cycle failed: {str(e)}"
        }
    finally:
        _cycle_lock.release()


def _worker_loop() -> None:
    """Main background daemon loop."""
    while not _stop_event.is_set():
        if _pause_event.is_set():
            time.sleep(0.5)
            continue

        _execute_single_cycle()

        interval = _worker_metadata.get("configured_interval_seconds", DEFAULT_INTERVAL_SECONDS)
        # Sleep in small increments for responsive stop/pause
        for _ in range(int(interval * 2)):
            if _stop_event.is_set():
                break
            time.sleep(0.5)

    with _worker_lock:
        _worker_metadata["current_state"] = WorkerState.STOPPED.value
        _worker_metadata["stopped_at"] = datetime.now(timezone.utc).isoformat()
        _worker_metadata["next_cycle_at"] = None
        _save_persisted_worker(_worker_metadata, _worker_history_store)


def start_background_worker(
    interval_seconds: Optional[int] = None,
    operator_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.28 - Starts the recovery background worker daemon safely.
    Idempotent: avoids duplicate worker threads.
    """
    global _worker_thread

    with _worker_lock:
        if not _worker_history_store:
            data = _load_persisted_worker()
            _worker_metadata.update(data.get("metadata", {}))
            _worker_history_store.extend(data.get("history", []))

        current_st = _worker_metadata.get("current_state")
        if current_st in (WorkerState.RUNNING.value, WorkerState.STARTING.value) and _worker_thread and _worker_thread.is_alive():
            return {
                "success": True,
                "worker": _worker_metadata,
                "message": f"Background worker {_worker_metadata.get('worker_id')} is already RUNNING.",
                "idempotent": True
            }

        now_iso = datetime.now(timezone.utc).isoformat()
        interval = interval_seconds or int(os.environ.get("RECOVERY_QUEUE_WATCHDOG_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS)))

        worker_id = f"worker_{uuid.uuid4().hex[:8]}"
        _worker_metadata["worker_id"] = worker_id
        _worker_metadata["current_state"] = WorkerState.STARTING.value
        _worker_metadata["started_at"] = now_iso
        _worker_metadata["stopped_at"] = None
        _worker_metadata["configured_interval_seconds"] = interval
        _worker_metadata["last_error"] = None

        _stop_event.clear()
        _pause_event.clear()

        _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name=f"RecoverIQ-Worker-{worker_id}")
        _worker_thread.start()

        _worker_metadata["current_state"] = WorkerState.RUNNING.value
        _record_worker_event("BACKGROUND_WORKER_STARTED", f"Background worker {worker_id} started (interval: {interval}s)", operator_id)
        _save_persisted_worker(_worker_metadata, _worker_history_store)

    # Telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id="background_worker",
            event_type="BACKGROUND_WORKER_STARTED",
            actor_type="OPERATOR" if operator_id else "SYSTEM",
            source="RECOVERY_BACKGROUND_WORKER",
            status="RUNNING",
            reason=f"Worker {worker_id} started with interval {interval}s",
            merchant_id="merchant_demo",
            endpoint="payment-webhook",
            correlation_id=worker_id
        )
    except Exception:
        pass

    return {
        "success": True,
        "worker": _worker_metadata,
        "message": f"Background worker {worker_id} started successfully."
    }


def stop_background_worker(operator_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Topic 2.2.2.28 - Safely stops the recovery background worker daemon.
    """
    global _worker_thread

    with _worker_lock:
        current_st = _worker_metadata.get("current_state")
        if current_st == WorkerState.STOPPED.value or not _worker_thread or not _worker_thread.is_alive():
            _worker_metadata["current_state"] = WorkerState.STOPPED.value
            return {
                "success": True,
                "worker": _worker_metadata,
                "message": "Background worker is already STOPPED.",
                "idempotent": True
            }

        _worker_metadata["current_state"] = WorkerState.STOPPING.value
        _stop_event.set()

    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=2.0)

    with _worker_lock:
        now_iso = datetime.now(timezone.utc).isoformat()
        _worker_metadata["current_state"] = WorkerState.STOPPED.value
        _worker_metadata["stopped_at"] = now_iso
        _worker_metadata["next_cycle_at"] = None
        _record_worker_event("BACKGROUND_WORKER_STOPPED", f"Background worker {_worker_metadata.get('worker_id')} stopped.", operator_id)
        _save_persisted_worker(_worker_metadata, _worker_history_store)

    # Telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id="background_worker",
            event_type="BACKGROUND_WORKER_STOPPED",
            actor_type="OPERATOR" if operator_id else "SYSTEM",
            source="RECOVERY_BACKGROUND_WORKER",
            status="STOPPED",
            reason=f"Worker stopped by {operator_id or 'SYSTEM'}",
            merchant_id="merchant_demo",
            endpoint="payment-webhook",
            correlation_id=_worker_metadata.get("worker_id", "worker_stopped")
        )
    except Exception:
        pass

    return {
        "success": True,
        "worker": _worker_metadata,
        "message": "Background worker stopped successfully."
    }


def pause_background_worker(operator_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Topic 2.2.2.28 - Pauses background evaluation cycles without destroying worker thread.
    """
    with _worker_lock:
        current_st = _worker_metadata.get("current_state")
        if current_st != WorkerState.RUNNING.value:
            return {
                "success": False,
                "error": "WORKER_NOT_RUNNING",
                "message": f"Cannot pause worker in state '{current_st}'."
            }

        _pause_event.set()
        _worker_metadata["current_state"] = WorkerState.PAUSED.value
        _record_worker_event("BACKGROUND_WORKER_PAUSED", "Background worker execution paused.", operator_id)
        _save_persisted_worker(_worker_metadata, _worker_history_store)

    return {
        "success": True,
        "worker": _worker_metadata,
        "message": "Background worker paused."
    }


def resume_background_worker(operator_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Topic 2.2.2.28 - Resumes background evaluation cycles.
    """
    with _worker_lock:
        current_st = _worker_metadata.get("current_state")
        if current_st != WorkerState.PAUSED.value:
            return {
                "success": False,
                "error": "WORKER_NOT_PAUSED",
                "message": f"Cannot resume worker in state '{current_st}'."
            }

        _pause_event.clear()
        _worker_metadata["current_state"] = WorkerState.RUNNING.value
        _record_worker_event("BACKGROUND_WORKER_RESUMED", "Background worker execution resumed.", operator_id)
        _save_persisted_worker(_worker_metadata, _worker_history_store)

    return {
        "success": True,
        "worker": _worker_metadata,
        "message": "Background worker resumed."
    }


def run_immediate_cycle(operator_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Topic 2.2.2.28 - Triggers an immediate safe execution cycle.
    """
    cycle_res = _execute_single_cycle(operator_id=operator_id or "OPERATOR_RUN_NOW")
    return {
        "success": cycle_res.get("success", False),
        "cycle_result": cycle_res,
        "worker": get_background_worker_status().get("worker")
    }


def get_background_worker_status() -> Dict[str, Any]:
    """
    Topic 2.2.2.28 - Retrieves current background worker status and operational history.
    """
    with _worker_lock:
        if not _worker_history_store:
            data = _load_persisted_worker()
            _worker_metadata.update(data.get("metadata", {}))
            _worker_history_store.extend(data.get("history", []))

        # Check if thread died unexpectedly
        if _worker_metadata.get("current_state") == WorkerState.RUNNING.value:
            if not _worker_thread or not _worker_thread.is_alive():
                _worker_metadata["current_state"] = WorkerState.STOPPED.value

        return {
            "success": True,
            "worker": dict(_worker_metadata),
            "history_count": len(_worker_history_store)
        }


def reset_background_worker_state() -> None:
    """Helper to stop thread and reset worker state."""
    stop_background_worker()
    with _worker_lock:
        _worker_metadata.update({
            "worker_id": None,
            "current_state": WorkerState.STOPPED.value,
            "started_at": None,
            "stopped_at": None,
            "last_cycle_at": None,
            "next_cycle_at": None,
            "cycle_count": 0,
            "successful_cycles": 0,
            "failed_cycles": 0,
            "last_error": None,
            "configured_interval_seconds": DEFAULT_INTERVAL_SECONDS
        })
        _worker_history_store.clear()
        if os.path.exists(WORKER_LOG_PATH):
            try:
                os.remove(WORKER_LOG_PATH)
            except Exception:
                pass
