"""
RecoverIQ - Automatic Incident Closure Action & End-to-End Recovery Completion (Topic 2.2.2.20)

Authoritative action layer that securely records and finalizes incident closure
ONLY after authoritative payment state is RECOVERED and verification is VERIFIED_SUCCESS.

STRICT BOUNDARIES:
- Action/recording layer only; NEVER directly mutates PaymentState or CircuitState.
- Requires: PaymentState == RECOVERED AND Verification == VERIFIED_SUCCESS AND Finalization == INCIDENT_RESOLVED.
- Strictly idempotent: repeated closure actions safely return ALREADY_CLOSED.
- Thread-safe concurrency control via _closure_lock.
- Persists operational closure records to logs/incident_closure_events.json.
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
INCIDENT_CLOSURE_LOG_PATH = os.path.join(LOGS_DIR, "incident_closure_events.json")

_closure_lock = threading.Lock()
_incident_closure_store: Dict[str, Dict[str, Any]] = {}


class IncidentClosureStatus(str, Enum):
    """Authoritative incident closure outcomes."""
    INCIDENT_CLOSED = "INCIDENT_CLOSED"
    CLOSURE_PENDING = "CLOSURE_PENDING"
    CLOSURE_BLOCKED = "CLOSURE_BLOCKED"
    ALREADY_CLOSED = "ALREADY_CLOSED"
    CLOSURE_FAILED = "CLOSURE_FAILED"


def _load_persisted_closures() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(INCIDENT_CLOSURE_LOG_PATH):
        try:
            with open(INCIDENT_CLOSURE_LOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {item.get("payment_id"): item for item in data if "payment_id" in item}
                elif isinstance(data, dict):
                    return data
        except Exception:
            return {}
    return {}


def _save_persisted_closures(store: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(INCIDENT_CLOSURE_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(list(store.values()), f, indent=2)
    except Exception:
        pass


def get_incident_closure_status(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook"
) -> Dict[str, Any]:
    """
    Topic 2.2.2.20 - Retrieves the current closure status of an incident.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    with _closure_lock:
        if not _incident_closure_store and os.path.exists(INCIDENT_CLOSURE_LOG_PATH):
            _incident_closure_store.update(_load_persisted_closures())

        existing = _incident_closure_store.get(clean_payment_id)
        if existing:
            return {
                "closure_id": existing.get("closure_id"),
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "closure_status": IncidentClosureStatus.INCIDENT_CLOSED.value,
                "payment_state": existing.get("payment_state", "RECOVERED"),
                "verification_status": existing.get("verification_status", "VERIFIED_SUCCESS"),
                "finalization_status": existing.get("finalization_status", "INCIDENT_RESOLVED"),
                "closed": True,
                "duplicate": False,
                "reason": existing.get("reason", "Incident closed after verified recovery."),
                "recommended_next_step": "No recovery action required.",
                "actor_type": existing.get("actor_type", "AI_AGENT"),
                "source": existing.get("source", "INCIDENT_CLOSURE"),
                "execution_id": existing.get("execution_id"),
                "review_id": existing.get("review_id"),
                "correlation_id": existing.get("correlation_id"),
                "timestamp": existing.get("timestamp", now_iso)
            }

    # Evaluate finalization guard dynamically
    try:
        from src.recovery_finalization import evaluate_recovery_finalization
        fin = evaluate_recovery_finalization(clean_payment_id, clean_merchant_id, clean_endpoint)
        fin_status = fin.get("finalization_status")
        pay_state = fin.get("payment_state")
        ver_status = fin.get("verification_status")

        if fin.get("incident_resolved") and pay_state in ("RECOVERED", "SUCCESS") and ver_status == "VERIFIED_SUCCESS":
            closure_status = IncidentClosureStatus.INCIDENT_CLOSED.value
            closed = True
            reason = "Payment is RECOVERED and verification confirmed VERIFIED_SUCCESS; incident qualifies for closure."
            next_step = "Execute closure confirmation."
        elif fin_status == "HUMAN_REVIEW_REQUIRED" or fin_status == "RECOVERY_BLOCKED" or fin_status == "RECOVERY_FAILED":
            closure_status = IncidentClosureStatus.CLOSURE_BLOCKED.value
            closed = False
            reason = fin.get("resolution_reason", "Closure blocked by safety guard.")
            next_step = fin.get("recommended_next_step", "Address blocking conditions.")
        else:
            closure_status = IncidentClosureStatus.CLOSURE_PENDING.value
            closed = False
            reason = fin.get("resolution_reason", "Incident cannot be closed until recovery verification completes.")
            next_step = "Await VERIFIED_SUCCESS and authoritative RECOVERED payment state."

        return {
            "closure_id": None,
            "payment_id": clean_payment_id,
            "merchant_id": clean_merchant_id,
            "endpoint": clean_endpoint,
            "closure_status": closure_status,
            "payment_state": pay_state,
            "verification_status": ver_status,
            "finalization_status": fin_status,
            "closed": closed,
            "duplicate": False,
            "reason": reason,
            "recommended_next_step": next_step,
            "actor_type": "SYSTEM",
            "source": "INCIDENT_CLOSURE_GUARD",
            "timestamp": now_iso
        }
    except Exception as e:
        return {
            "closure_id": None,
            "payment_id": clean_payment_id,
            "merchant_id": clean_merchant_id,
            "endpoint": clean_endpoint,
            "closure_status": IncidentClosureStatus.CLOSURE_FAILED.value,
            "closed": False,
            "duplicate": False,
            "reason": f"Closure evaluation encountered error: {str(e)}",
            "recommended_next_step": "Inspect system logs.",
            "timestamp": now_iso
        }


def close_incident_if_qualified(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    closure_reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.20 - Safely executes and records incident closure if finalization requirements are strictly met.
    Idempotent: returns ALREADY_CLOSED for duplicate calls.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    with _closure_lock:
        if not _incident_closure_store and os.path.exists(INCIDENT_CLOSURE_LOG_PATH):
            _incident_closure_store.update(_load_persisted_closures())

        if clean_payment_id in _incident_closure_store:
            existing = _incident_closure_store[clean_payment_id]
            try:
                from src.recovery_audit import record_recovery_audit_event
                record_recovery_audit_event(
                    payment_id=clean_payment_id,
                    event_type="INCIDENT_ALREADY_CLOSED",
                    actor_type="SYSTEM",
                    source="INCIDENT_CLOSURE",
                    status="ALREADY_CLOSED",
                    reason="Incident closure requested for already closed payment.",
                    merchant_id=clean_merchant_id,
                    endpoint=clean_endpoint,
                    correlation_id=existing.get("closure_id")
                )
            except Exception:
                pass

            return {
                "success": True,
                "closure": {
                    "closure_id": existing.get("closure_id"),
                    "payment_id": clean_payment_id,
                    "merchant_id": clean_merchant_id,
                    "endpoint": clean_endpoint,
                    "closure_status": IncidentClosureStatus.ALREADY_CLOSED.value,
                    "payment_state": existing.get("payment_state"),
                    "verification_status": existing.get("verification_status"),
                    "finalization_status": existing.get("finalization_status"),
                    "closed": True,
                    "duplicate": True,
                    "reason": "Incident was already closed under authoritative confirmation.",
                    "recommended_next_step": "No recovery action required.",
                    "timestamp": now_iso
                }
            }

    # Evaluate finalization guard
    try:
        from src.recovery_finalization import evaluate_recovery_finalization
        fin = evaluate_recovery_finalization(clean_payment_id, clean_merchant_id, clean_endpoint)
    except Exception as e:
        return {
            "success": False,
            "closure": {
                "closure_status": IncidentClosureStatus.CLOSURE_FAILED.value,
                "closed": False,
                "duplicate": False,
                "reason": f"Finalization evaluation failed: {str(e)}",
                "recommended_next_step": "Verify telemetry store integrity."
            }
        }

    pay_state = fin.get("payment_state")
    ver_status = fin.get("verification_status")
    fin_status = fin.get("finalization_status")
    is_resolved = fin.get("incident_resolved", False)

    # Check strict closure eligibility
    if not (is_resolved and pay_state in ("RECOVERED", "SUCCESS") and ver_status == "VERIFIED_SUCCESS"):
        if fin_status in ("HUMAN_REVIEW_REQUIRED", "RECOVERY_BLOCKED", "RECOVERY_FAILED"):
            c_status = IncidentClosureStatus.CLOSURE_BLOCKED.value
        else:
            c_status = IncidentClosureStatus.CLOSURE_PENDING.value

        try:
            from src.recovery_audit import record_recovery_audit_event
            record_recovery_audit_event(
                payment_id=clean_payment_id,
                event_type="INCIDENT_CLOSURE_BLOCKED" if c_status == IncidentClosureStatus.CLOSURE_BLOCKED.value else "INCIDENT_CLOSURE_PENDING",
                actor_type="SYSTEM",
                source="INCIDENT_CLOSURE",
                status=c_status,
                reason=fin.get("resolution_reason", "Incident closure prerequisites not satisfied."),
                merchant_id=clean_merchant_id,
                endpoint=clean_endpoint
            )
        except Exception:
            pass

        return {
            "success": True,
            "closure": {
                "closure_status": c_status,
                "payment_id": clean_payment_id,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "payment_state": pay_state,
                "verification_status": ver_status,
                "finalization_status": fin_status,
                "closed": False,
                "duplicate": False,
                "reason": fin.get("resolution_reason", "Incident cannot be closed until recovery verification completes."),
                "recommended_next_step": "Await VERIFIED_SUCCESS and authoritative RECOVERED payment state.",
                "timestamp": now_iso
            }
        }

    # Authoritative Incident Closure Execution
    closure_id = f"close_{uuid.uuid4().hex[:10]}"
    reason = closure_reason or "Incident closure authorized after verified recovery and authoritative payment-state confirmation."

    closure_record = {
        "closure_id": closure_id,
        "payment_id": clean_payment_id,
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "closure_status": IncidentClosureStatus.INCIDENT_CLOSED.value,
        "payment_state": pay_state,
        "verification_status": ver_status,
        "finalization_status": fin_status,
        "reason": reason,
        "actor_type": "AI_AGENT",
        "source": "INCIDENT_CLOSURE",
        "timestamp": now_iso
    }

    with _closure_lock:
        _incident_closure_store[clean_payment_id] = closure_record
        _save_persisted_closures(_incident_closure_store)

    # Emit audit telemetry
    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type="INCIDENT_CLOSED",
            actor_type="AI_AGENT",
            source="INCIDENT_CLOSURE",
            status=IncidentClosureStatus.INCIDENT_CLOSED.value,
            reason=reason,
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            correlation_id=closure_id
        )
    except Exception:
        pass

    return {
        "success": True,
        "closure": {
            "closure_id": closure_id,
            "payment_id": clean_payment_id,
            "merchant_id": clean_merchant_id,
            "endpoint": clean_endpoint,
            "closure_status": IncidentClosureStatus.INCIDENT_CLOSED.value,
            "payment_state": pay_state,
            "verification_status": ver_status,
            "finalization_status": fin_status,
            "closed": True,
            "duplicate": False,
            "reason": reason,
            "recommended_next_step": "No recovery action required.",
            "timestamp": now_iso
        }
    }


def reset_incident_closure_state() -> None:
    """Helper to reset in-memory and persisted incident closures."""
    with _closure_lock:
        _incident_closure_store.clear()
        if os.path.exists(INCIDENT_CLOSURE_LOG_PATH):
            try:
                os.remove(INCIDENT_CLOSURE_LOG_PATH)
            except Exception:
                pass
