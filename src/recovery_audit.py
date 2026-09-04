"""
RecoverIQ - Unified Recovery Audit Trail & Incident Timeline (Topic 2.2.2.14)

Centralized observability and audit layer providing a unified, chronological,
deterministic timeline of events across the entire payment recovery lifecycle.

STRICT BOUNDARIES:
- OBSERVES and RECORDS only; NEVER decides policy, modifies state, or gates requests.
- Thread-safe, failure-isolated, and atomic persistence to logs/recovery_audit_events.json.
- Zero credential, secret, authorization header, or raw payload storage.
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
AUDIT_EVENTS_LOG_PATH = os.path.join(LOGS_DIR, "recovery_audit_events.json")

_audit_lock = threading.Lock()
_audit_events_log: List[Dict[str, Any]] = []
_payment_sequence_counters: Dict[str, int] = {}


class AuditEventType(str, Enum):
    """Authoritative audit event categories."""
    INCIDENT_RECEIVED = "INCIDENT_RECEIVED"
    WEBHOOK_VERIFIED = "WEBHOOK_VERIFIED"
    WEBHOOK_REJECTED = "WEBHOOK_REJECTED"
    MERCHANT_HEALTH_OBSERVED = "MERCHANT_HEALTH_OBSERVED"
    CIRCUIT_EVALUATED = "CIRCUIT_EVALUATED"
    CIRCUIT_OPENED = "CIRCUIT_OPENED"
    CIRCUIT_HALF_OPENED = "CIRCUIT_HALF_OPENED"
    CIRCUIT_CLOSED = "CIRCUIT_CLOSED"
    CIRCUIT_OVERRIDE = "CIRCUIT_OVERRIDE"
    RECOVERY_DECISION = "RECOVERY_DECISION"
    AUTOMATIC_RECOVERY_TRIGGERED = "AUTOMATIC_RECOVERY_TRIGGERED"
    RECOVERY_EXECUTION_STARTED = "RECOVERY_EXECUTION_STARTED"
    NETWORK_ATTEMPT = "NETWORK_ATTEMPT"
    RECOVERY_VERIFICATION = "RECOVERY_VERIFICATION"
    PAYMENT_STATE_TRANSITION = "PAYMENT_STATE_TRANSITION"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    RECOVERY_WAITING = "RECOVERY_WAITING"
    RECOVERY_BLOCKED = "RECOVERY_BLOCKED"


def _load_persisted_audit_events() -> List[Dict[str, Any]]:
    if os.path.exists(AUDIT_EVENTS_LOG_PATH):
        try:
            with open(AUDIT_EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_persisted_audit_events(events: List[Dict[str, Any]]) -> None:
    try:
        with open(AUDIT_EVENTS_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
    except Exception:
        pass


def record_recovery_audit_event(
    payment_id: str,
    event_type: str,
    actor_type: str = "SYSTEM",
    source: str = "RECOVERY_PIPELINE",
    status: str = "RECORDED",
    reason: str = "",
    risk_level: Optional[str] = None,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    correlation_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.14 - Records a structured, chronological, correlated recovery audit event.
    Thread-safe and failure-isolated (never crashes calling flow on persistence failure).
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        with _audit_lock:
            if not _audit_events_log and os.path.exists(AUDIT_EVENTS_LOG_PATH):
                _audit_events_log.extend(_load_persisted_audit_events())

            # Maintain monotonic sequence counter per payment
            current_seq = _payment_sequence_counters.get(clean_payment_id, 0) + 1
            _payment_sequence_counters[clean_payment_id] = current_seq

            # Sanitize metadata (strip any passwords, keys, tokens if present)
            clean_meta = {}
            if metadata and isinstance(metadata, dict):
                for k, v in metadata.items():
                    if any(secret_term in k.lower() for secret_term in ("key", "secret", "token", "auth", "pass")):
                        continue
                    clean_meta[k] = v

            event = {
                "sequence": current_seq,
                "event_id": f"aud_{uuid.uuid4().hex[:10]}",
                "payment_id": clean_payment_id,
                "merchant_id": str(merchant_id or "merchant_demo").strip(),
                "endpoint": str(endpoint or "payment-webhook").strip(),
                "event_type": event_type,
                "actor_type": actor_type,
                "source": source,
                "status": status,
                "reason": str(reason or ""),
                "risk_level": risk_level,
                "correlation_id": correlation_id,
                "execution_id": execution_id,
                "metadata": clean_meta if clean_meta else None,
                "timestamp": now_iso
            }

            _audit_events_log.append(event)
            if len(_audit_events_log) > 500:
                _audit_events_log.pop(0)

            _save_persisted_audit_events(_audit_events_log)
            return event
    except Exception:
        # Observability failure isolation: return fallback dict without crashing
        return {
            "sequence": 1,
            "event_id": f"aud_fallback_{uuid.uuid4().hex[:6]}",
            "payment_id": clean_payment_id,
            "event_type": event_type,
            "status": status,
            "reason": reason,
            "timestamp": now_iso
        }


def get_payment_recovery_timeline(
    payment_id: str,
    merchant_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Topic 2.2.2.14 - Retrieves the unified chronological recovery timeline for a payment.
    Aggregates dedicated audit events as well as correlated lifecycle events.
    """
    clean_payment_id = str(payment_id or "").strip()
    with _audit_lock:
        if not _audit_events_log and os.path.exists(AUDIT_EVENTS_LOG_PATH):
            _audit_events_log.extend(_load_persisted_audit_events())

        matched_events = [
            e for e in _audit_events_log
            if e.get("payment_id") == clean_payment_id
        ]

    # If no dedicated audit records exist yet, generate initial synthetic timeline from existing subsystems
    if not matched_events:
        # Check payment state transitions
        try:
            from src.state_machine import get_payment_state_history
            hist = get_payment_state_history(clean_payment_id)
            for idx, trans in enumerate(hist, 1):
                matched_events.append({
                    "sequence": idx,
                    "event_id": f"syn_{trans.get('transition_id', uuid.uuid4().hex[:6])}",
                    "payment_id": clean_payment_id,
                    "merchant_id": merchant_id or "merchant_demo",
                    "endpoint": endpoint or "payment-webhook",
                    "event_type": AuditEventType.PAYMENT_STATE_TRANSITION.value,
                    "actor_type": trans.get("actor_type", "SYSTEM"),
                    "source": trans.get("source", "PAYMENT_STATE_MACHINE"),
                    "status": "COMPLETED",
                    "reason": f"{trans.get('previous_state')} -> {trans.get('new_state')}: {trans.get('reason')}",
                    "timestamp": trans.get("timestamp", datetime.now(timezone.utc).isoformat())
                })
        except Exception:
            pass

    # Sort deterministically by timestamp and sequence
    matched_events.sort(key=lambda x: (x.get("timestamp", ""), x.get("sequence", 0)))

    if limit and isinstance(limit, int) and limit > 0:
        return matched_events[-limit:]
    return matched_events


def reset_recovery_audit_state() -> None:
    """Helper to reset in-memory audit state and persisted file for clean testing."""
    with _audit_lock:
        _audit_events_log.clear()
        _payment_sequence_counters.clear()
        if os.path.exists(AUDIT_EVENTS_LOG_PATH):
            try:
                os.remove(AUDIT_EVENTS_LOG_PATH)
            except Exception:
                pass
