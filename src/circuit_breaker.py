"""
RecoverIQ - Circuit Breaker State Definitions, Transitions, Request Gate,
Cooldown, Probing, and Persistence (Topics 2.2.2.1 – 2.2.2.5)

Authoritative backend engine for merchant endpoint protection:
- Closed / Open / Half-Open state definitions & legal transition matrix
- Thread-safe runtime state management & failure counting
- Monotonic cooldown tracking & automatic OPEN -> HALF_OPEN transitions
- Probe limit enforcement & generation tracking (stale probe protection)
- Atomic JSON persistence to logs/circuit_breaker_state.json & restart recovery
"""

import sys
import os
import json
import uuid
import time
import threading
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Callable

if __name__ in sys.modules:
    sys.modules['circuit_breaker'] = sys.modules[__name__]
    sys.modules['src.circuit_breaker'] = sys.modules[__name__]



# =========================================================================
# 1. STATE DEFINITIONS & METADATA (Topic 2.2.2.1)
# =========================================================================

class CircuitState(str, Enum):
    """Authoritative Merchant Endpoint Circuit Breaker States."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


# State metadata catalog
CIRCUIT_STATES: Dict[CircuitState, Dict[str, Any]] = {
    CircuitState.CLOSED: {
        "machine_value": "CLOSED",
        "label": "Closed",
        "description": "Merchant endpoint is considered available and healthy. Requests are allowed.",
        "is_protective_halt": False
    },
    CircuitState.OPEN: {
        "machine_value": "OPEN",
        "label": "Open",
        "description": "Merchant endpoint is considered unhealthy. Circuit is tripped and requests are blocked.",
        "is_protective_halt": True
    },
    CircuitState.HALF_OPEN: {
        "machine_value": "HALF_OPEN",
        "label": "Half-Open",
        "description": "Merchant endpoint is being cautiously probed with limited requests after an OPEN cooldown.",
        "is_protective_halt": False
    }
}

# Authoritative transition rules
VALID_CIRCUIT_TRANSITIONS: Dict[CircuitState, Set[CircuitState]] = {
    CircuitState.CLOSED: {CircuitState.OPEN},
    CircuitState.OPEN: {CircuitState.HALF_OPEN},
    CircuitState.HALF_OPEN: {CircuitState.CLOSED, CircuitState.OPEN}
}

# Legacy alias mappings for string inputs
LEGACY_CIRCUIT_STATE_MAPPINGS: Dict[str, CircuitState] = {
    "CLOSED": CircuitState.CLOSED,
    "CLOSE": CircuitState.CLOSED,
    "HEALTHY": CircuitState.CLOSED,
    "NORMAL": CircuitState.CLOSED,
    "OPEN": CircuitState.OPEN,
    "TRIPPED": CircuitState.OPEN,
    "HALTED": CircuitState.OPEN,
    "BLOCKED": CircuitState.OPEN,
    "HALF_OPEN": CircuitState.HALF_OPEN,
    "HALF-OPEN": CircuitState.HALF_OPEN,
    "HALFOPEN": CircuitState.HALF_OPEN,
    "PROBING": CircuitState.HALF_OPEN,
    "TESTING": CircuitState.HALF_OPEN
}

# Circuit breaker triggerable failure categories
CIRCUIT_BREAKER_FAILURES: Set[str] = {
    "TIMEOUT",
    "SERVER_ERROR",
    "RATE_LIMITED",
    "NETWORK_ERROR"
}

# Default configuration parameters
DEFAULT_FAILURE_THRESHOLD: int = 5
DEFAULT_COOLDOWN_DURATION_SEC: float = 30.0
DEFAULT_HALF_OPEN_PROBE_LIMIT: int = 3

CIRCUIT_BREAKER_CONFIG: Dict[str, Any] = {
    "failure_threshold": DEFAULT_FAILURE_THRESHOLD,
    "cooldown_duration_sec": DEFAULT_COOLDOWN_DURATION_SEC,
    "half_open_probe_limit": DEFAULT_HALF_OPEN_PROBE_LIMIT
}

# Persistent Storage Path (Topic 2.2.2.5)
CIRCUIT_STATE_STORAGE_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "circuit_breaker_state.json"
)


# =========================================================================
# 2. STATE HELPERS & TRANSITION ENGINE (Topic 2.2.2.1)
# =========================================================================

def normalize_circuit_state(value: Any) -> CircuitState:
    """
    Normalizes string, legacy alias, or enum values into an authoritative CircuitState.
    Raises ValueError if input value is unmapped or invalid.
    """
    if isinstance(value, CircuitState):
        return value

    if not value or not isinstance(value, (str, bytes)):
        raise ValueError(f"Invalid circuit state input: '{value}' (must be non-empty string or CircuitState)")

    cleaned = str(value).strip().upper().replace("-", "_").replace(" ", "_")

    if cleaned in CircuitState.__members__:
        return CircuitState[cleaned]

    if cleaned in LEGACY_CIRCUIT_STATE_MAPPINGS:
        return LEGACY_CIRCUIT_STATE_MAPPINGS[cleaned]

    raise ValueError(f"Unknown circuit state value: '{value}'")


def is_valid_circuit_transition(current_state: Any, next_state: Any) -> bool:
    """
    Determines whether a transition from current_state to next_state is legally allowed.
    """
    try:
        norm_current = normalize_circuit_state(current_state)
        norm_next = normalize_circuit_state(next_state)
    except (ValueError, TypeError):
        return False

    allowed = VALID_CIRCUIT_TRANSITIONS.get(norm_current, set())
    return norm_next in allowed


def get_allowed_circuit_transitions(current_state: Any) -> List[CircuitState]:
    """
    Returns the list of valid next states permitted from the given current_state.
    """
    try:
        norm_current = normalize_circuit_state(current_state)
    except (ValueError, TypeError):
        return []

    return sorted(list(VALID_CIRCUIT_TRANSITIONS.get(norm_current, set())), key=lambda s: s.value)


def is_circuit_breaker_failure(failure_category: Any) -> bool:
    """
    Checks if a given failure category counts towards tripping the circuit breaker.
    """
    if not failure_category:
        return False
    clean_cat = str(getattr(failure_category, "value", failure_category)).strip().upper()
    return clean_cat in CIRCUIT_BREAKER_FAILURES


# Operator override transition matrix (Topic 2.2.2.7)
VALID_OPERATOR_CIRCUIT_TRANSITIONS: Dict[CircuitState, Set[CircuitState]] = {
    CircuitState.CLOSED: {CircuitState.OPEN},
    CircuitState.OPEN: {CircuitState.HALF_OPEN, CircuitState.CLOSED},
    CircuitState.HALF_OPEN: {CircuitState.CLOSED, CircuitState.OPEN}
}


def transition_circuit_state(
    current_state: Any,
    next_state: Any,
    reason: Optional[str] = None,
    allow_operator_override: bool = False
) -> Dict[str, Any]:
    """
    Authoritative circuit breaker state transition engine.
    - Normalizes input states
    - Requires a non-empty reason
    - Validates against VALID_CIRCUIT_TRANSITIONS (or VALID_OPERATOR_CIRCUIT_TRANSITIONS when allow_operator_override=True)
    - Returns structured transition metadata
    - Rejects invalid transitions without mutating state
    """
    # 1. Validate required non-empty reason
    if not reason or not str(reason).strip():
        try:
            norm_curr = normalize_circuit_state(current_state)
            curr_val = norm_curr.value
        except Exception:
            curr_val = str(current_state)
        return {
            "success": False,
            "error": "TRANSITION_REASON_REQUIRED",
            "current_state": curr_val,
            "message": "A reason is required for circuit breaker state transitions."
        }

    clean_reason = str(reason).strip()

    # 2. Normalize current state
    try:
        norm_current = normalize_circuit_state(current_state)
    except Exception as e:
        return {
            "success": False,
            "error": "INVALID_CURRENT_STATE",
            "message": f"Invalid current circuit state: {str(e)}"
        }

    # 3. Normalize next state
    try:
        norm_next = normalize_circuit_state(next_state)
    except Exception as e:
        return {
            "success": False,
            "error": "INVALID_NEXT_STATE",
            "message": f"Invalid requested circuit state: {str(e)}"
        }

    # 4. Check transition validity
    allowed_matrix = VALID_OPERATOR_CIRCUIT_TRANSITIONS if allow_operator_override else VALID_CIRCUIT_TRANSITIONS
    allowed = allowed_matrix.get(norm_current, set())
    if norm_next not in allowed:
        return {
            "success": False,
            "error": "INVALID_CIRCUIT_TRANSITION",
            "current_state": norm_current.value,
            "requested_state": norm_next.value,
            "reason": clean_reason,
            "allowed_transitions": [s.value for s in sorted(list(allowed), key=lambda x: x.value)],
            "transition_status": "REJECTED",
            "message": f"Circuit transition from {norm_current.value} to {norm_next.value} is not allowed."
        }

    # 5. Successful transition
    return {
        "success": True,
        "from_state": norm_current.value,
        "to_state": norm_next.value,
        "reason": clean_reason,
        "transition_status": "SUCCESS",
        "message": f"Circuit state transitioned from {norm_current.value} to {norm_next.value}."
    }



# =========================================================================
# 3. RUNTIME CIRCUIT STORE & PERSISTENCE ENGINE (Topic 2.2.2.2 – 2.2.2.5)
# =========================================================================

_circuit_lock = threading.Lock()
# Key: f"{merchant_id}:{endpoint}"
_circuit_states: Dict[str, Dict[str, Any]] = {}

# In-memory telemetry logs
_blocked_requests_log: List[Dict[str, Any]] = []
_circuit_lifecycle_log: List[Dict[str, Any]] = []

# Persistence status tracking (PERSISTED, NOT_PERSISTED, LOAD_FAILED, WRITE_FAILED)
_persistence_status: str = "NOT_PERSISTED"
_last_persisted_at: Optional[str] = None


def _get_circuit_key(merchant_id: str, endpoint: str) -> str:
    m = str(merchant_id or "merchant_demo").strip()
    ep = str(endpoint or "payment-webhook").strip()
    return f"{m}:{ep}"


def record_circuit_lifecycle_event(
    merchant_id: str,
    endpoint: str,
    circuit_state: str,
    event_type: str,
    reason: str,
    failure_category: Optional[str] = None,
    circuit_generation: Optional[int] = None,
    payment_id: Optional[str] = None,
    actor_type: str = "SYSTEM",
    actor_id: str = "recovery_engine",
    source: str = "CIRCUIT_BREAKER_ENGINE"
) -> Dict[str, Any]:
    """
    Records a safe operational circuit lifecycle event with actor attribution (zero credentials or sensitive data stored).
    """
    event = {
        "event_id": f"cbl_{uuid.uuid4().hex[:10]}",
        "merchant_id": str(merchant_id or "merchant_demo").strip(),
        "endpoint": str(endpoint or "payment-webhook").strip(),
        "payment_id": payment_id,
        "circuit_state": circuit_state,
        "event_type": event_type,
        "reason": reason,
        "failure_category": failure_category,
        "circuit_generation": circuit_generation,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    _circuit_lifecycle_log.append(event)
    if len(_circuit_lifecycle_log) > 200:
        _circuit_lifecycle_log.pop(0)
    return event


def _save_circuit_states_to_disk() -> bool:
    """
    Atomically writes circuit breaker state to logs/circuit_breaker_state.json.
    Thread-safe and never crashes on I/O failure.
    """
    global _persistence_status, _last_persisted_at
    try:
        os.makedirs(os.path.dirname(CIRCUIT_STATE_STORAGE_PATH), exist_ok=True)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Build clean, credential-free serializable payload
        serializable_data = {}
        for key, entry in _circuit_states.items():
            serializable_data[key] = {
                "merchant_id": str(entry.get("merchant_id", "")),
                "endpoint": str(entry.get("endpoint", "")),
                "state": str(entry.get("state", CircuitState.CLOSED.value)),
                "consecutive_failures": int(entry.get("consecutive_failures", 0)),
                "total_failures": int(entry.get("total_failures", 0)),
                "last_failure_category": entry.get("last_failure_category"),
                "last_failure_at": entry.get("last_failure_at"),
                "opened_at": entry.get("opened_at"),
                "cooldown_duration_sec": float(entry.get("cooldown_duration_sec", DEFAULT_COOLDOWN_DURATION_SEC)),
                "half_open_probe_limit": int(entry.get("half_open_probe_limit", DEFAULT_HALF_OPEN_PROBE_LIMIT)),
                "circuit_generation": int(entry.get("circuit_generation", 0)),
                "last_persisted_at": now_iso
            }

        tmp_path = f"{CIRCUIT_STATE_STORAGE_PATH}.tmp_{uuid.uuid4().hex[:8]}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, CIRCUIT_STATE_STORAGE_PATH)
        _persistence_status = "PERSISTED"
        _last_persisted_at = now_iso
        return True
    except Exception as e:
        _persistence_status = "WRITE_FAILED"
        record_circuit_lifecycle_event(
            merchant_id="system",
            endpoint="persistence",
            circuit_state="UNKNOWN",
            event_type="CIRCUIT_PERSISTENCE_FAILURE",
            reason=f"Failed to persist circuit breaker state: {str(e)}"
        )
        return False


def _load_circuit_states_from_disk() -> bool:
    """
    Restores circuit breaker state from logs/circuit_breaker_state.json upon backend restart.
    - Accurately computes remaining cooldown from wall-clock opened_at.
    - Transitions expired OPEN circuits to HALF_OPEN automatically.
    - Resets in-flight probe counts and increments generation to invalidate stale probes.
    """
    global _persistence_status, _last_persisted_at
    if not os.path.exists(CIRCUIT_STATE_STORAGE_PATH):
        _persistence_status = "NOT_PERSISTED"
        return False

    try:
        with open(CIRCUIT_STATE_STORAGE_PATH, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, dict):
            _persistence_status = "LOAD_FAILED"
            return False

        now_utc = datetime.now(timezone.utc)
        now_mono = time.monotonic()

        with _circuit_lock:
            for key, raw_entry in raw_data.items():
                if not isinstance(raw_entry, dict):
                    continue

                merchant_id = str(raw_entry.get("merchant_id", "merchant_demo")).strip()
                endpoint = str(raw_entry.get("endpoint", "payment-webhook")).strip()

                try:
                    norm_state = normalize_circuit_state(raw_entry.get("state", "CLOSED")).value
                except Exception:
                    norm_state = CircuitState.CLOSED.value

                consecutive_failures = int(raw_entry.get("consecutive_failures", 0))
                total_failures = int(raw_entry.get("total_failures", 0))
                last_failure_category = raw_entry.get("last_failure_category")
                last_failure_at = raw_entry.get("last_failure_at")
                opened_at = raw_entry.get("opened_at")
                cooldown_dur = float(raw_entry.get("cooldown_duration_sec", DEFAULT_COOLDOWN_DURATION_SEC))
                probe_limit = int(raw_entry.get("half_open_probe_limit", DEFAULT_HALF_OPEN_PROBE_LIMIT))
                gen = int(raw_entry.get("circuit_generation", 0))

                opened_at_mono = None

                # 1. OPEN Restart Recovery: Re-evaluate elapsed cooldown
                if norm_state == CircuitState.OPEN.value:
                    if opened_at:
                        try:
                            opened_dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                            elapsed_sec = (now_utc - opened_dt).total_seconds()
                            remaining_sec = max(0.0, cooldown_dur - elapsed_sec)

                            if remaining_sec > 0.0:
                                # Cooldown still active -> remain OPEN with fresh monotonic anchor
                                opened_at_mono = now_mono - elapsed_sec
                                record_circuit_lifecycle_event(
                                    merchant_id=merchant_id,
                                    endpoint=endpoint,
                                    circuit_state="OPEN",
                                    event_type="CIRCUIT_STATE_RESTORED",
                                    reason=f"Restored active OPEN circuit with {round(remaining_sec, 2)}s cooldown remaining.",
                                    circuit_generation=gen
                                )
                            else:
                                # Cooldown expired during offline downtime -> Recover to HALF_OPEN
                                norm_state = CircuitState.HALF_OPEN.value
                                gen += 1
                                record_circuit_lifecycle_event(
                                    merchant_id=merchant_id,
                                    endpoint=endpoint,
                                    circuit_state="HALF_OPEN",
                                    event_type="CIRCUIT_RESTART_RECOVERY",
                                    reason="Cooldown expired while offline; automatically recovered OPEN -> HALF_OPEN on startup.",
                                    circuit_generation=gen
                                )
                        except Exception:
                            norm_state = CircuitState.HALF_OPEN.value
                            gen += 1
                    else:
                        norm_state = CircuitState.HALF_OPEN.value
                        gen += 1

                # 2. HALF_OPEN Restart Recovery: Reset in-flight probes & increment generation
                elif norm_state == CircuitState.HALF_OPEN.value:
                    gen += 1
                    record_circuit_lifecycle_event(
                        merchant_id=merchant_id,
                        endpoint=endpoint,
                        circuit_state="HALF_OPEN",
                        event_type="CIRCUIT_STATE_RESTORED",
                        reason="Restored HALF_OPEN state; reset active probe reservations and incremented generation.",
                        circuit_generation=gen
                    )

                # 3. CLOSED Restart Recovery
                elif norm_state == CircuitState.CLOSED.value:
                    record_circuit_lifecycle_event(
                        merchant_id=merchant_id,
                        endpoint=endpoint,
                        circuit_state="CLOSED",
                        event_type="CIRCUIT_STATE_RESTORED",
                        reason="Restored CLOSED circuit state with preserved total_failures.",
                        circuit_generation=gen
                    )

                _circuit_states[key] = {
                    "merchant_id": merchant_id,
                    "endpoint": endpoint,
                    "state": norm_state,
                    "consecutive_failures": consecutive_failures,
                    "total_failures": total_failures,
                    "last_failure_category": last_failure_category,
                    "last_failure_at": last_failure_at,
                    "opened_at": opened_at,
                    "opened_at_monotonic": opened_at_mono,
                    "failure_threshold": int(raw_entry.get("failure_threshold", DEFAULT_FAILURE_THRESHOLD)),
                    "cooldown_duration_sec": cooldown_dur,
                    "half_open_probe_limit": probe_limit,
                    "half_open_probe_count": 0,  # always reset runtime probe reservation on restart
                    "circuit_generation": gen
                }

        _persistence_status = "PERSISTED"
        _last_persisted_at = now_utc.isoformat()
        return True
    except Exception as e:
        _persistence_status = "LOAD_FAILED"
        record_circuit_lifecycle_event(
            merchant_id="system",
            endpoint="persistence",
            circuit_state="UNKNOWN",
            event_type="CIRCUIT_PERSISTENCE_FAILURE",
            reason=f"Failed to load circuit breaker state: {str(e)}"
        )
        return False


# Automatically load persisted state on module startup
_load_circuit_states_from_disk()


def get_or_create_circuit_state(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    failure_threshold: Optional[int] = None,
    cooldown_duration_sec: Optional[float] = None,
    half_open_probe_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Retrieves or initializes independent runtime circuit state for a merchant endpoint.
    """
    key = _get_circuit_key(merchant_id, endpoint)
    threshold = int(failure_threshold if failure_threshold is not None else DEFAULT_FAILURE_THRESHOLD)
    cooldown = float(cooldown_duration_sec if cooldown_duration_sec is not None else DEFAULT_COOLDOWN_DURATION_SEC)
    probe_limit = int(half_open_probe_limit if half_open_probe_limit is not None else DEFAULT_HALF_OPEN_PROBE_LIMIT)

    with _circuit_lock:
        if key not in _circuit_states:
            _circuit_states[key] = {
                "merchant_id": str(merchant_id or "merchant_demo").strip(),
                "endpoint": str(endpoint or "payment-webhook").strip(),
                "state": CircuitState.CLOSED.value,
                "consecutive_failures": 0,
                "total_failures": 0,
                "last_failure_category": None,
                "last_failure_at": None,
                "opened_at": None,
                "opened_at_monotonic": None,
                "failure_threshold": threshold,
                "cooldown_duration_sec": cooldown,
                "half_open_probe_limit": probe_limit,
                "half_open_probe_count": 0,
                "circuit_generation": 0
            }
            _save_circuit_states_to_disk()
        entry = _circuit_states[key]
        if failure_threshold is not None:
            entry["failure_threshold"] = threshold
        if cooldown_duration_sec is not None:
            entry["cooldown_duration_sec"] = cooldown
        if half_open_probe_limit is not None:
            entry["half_open_probe_limit"] = probe_limit
        return dict(entry)


def record_circuit_observation(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    failure_category: Any = "SUCCESS",
    failure_threshold: Optional[int] = None,
    cooldown_duration_sec: Optional[float] = None
) -> Dict[str, Any]:
    """
    Records an operational observation against the merchant endpoint circuit.
    - Trigger failure while CLOSED -> increments consecutive_failures.
    - Threshold reached -> automatically trips CLOSED -> OPEN via transition_circuit_state.
    - SUCCESS while CLOSED -> resets consecutive_failures to 0.
    - CLIENT_ERROR / REDIRECT -> non-trigger, preserves counters.
    - Thread-safe, atomic, and automatically persisted.
    """
    key = _get_circuit_key(merchant_id, endpoint)
    threshold = int(failure_threshold if failure_threshold is not None else DEFAULT_FAILURE_THRESHOLD)
    cooldown = float(cooldown_duration_sec if cooldown_duration_sec is not None else DEFAULT_COOLDOWN_DURATION_SEC)
    cat_str = str(getattr(failure_category, "value", failure_category) or "SUCCESS").strip().upper()
    timestamp = datetime.now(timezone.utc).isoformat()
    now_mono = time.monotonic()

    with _circuit_lock:
        if key not in _circuit_states:
            _circuit_states[key] = {
                "merchant_id": str(merchant_id or "merchant_demo").strip(),
                "endpoint": str(endpoint or "payment-webhook").strip(),
                "state": CircuitState.CLOSED.value,
                "consecutive_failures": 0,
                "total_failures": 0,
                "last_failure_category": None,
                "last_failure_at": None,
                "opened_at": None,
                "opened_at_monotonic": None,
                "failure_threshold": threshold,
                "cooldown_duration_sec": cooldown,
                "half_open_probe_limit": DEFAULT_HALF_OPEN_PROBE_LIMIT,
                "half_open_probe_count": 0,
                "circuit_generation": 0
            }

        entry = _circuit_states[key]
        entry["failure_threshold"] = threshold
        if cooldown_duration_sec is not None:
            entry["cooldown_duration_sec"] = cooldown

        if is_circuit_breaker_failure(cat_str):
            # Trigger failure
            entry["total_failures"] += 1
            entry["last_failure_category"] = cat_str
            entry["last_failure_at"] = timestamp

            if entry["state"] == CircuitState.CLOSED.value:
                entry["consecutive_failures"] += 1

                # Check if threshold reached
                if entry["consecutive_failures"] >= threshold:
                    reason = f"Circuit opened after {entry['consecutive_failures']} consecutive {cat_str} failures."
                    trans_res = transition_circuit_state(
                        current_state=CircuitState.CLOSED,
                        next_state=CircuitState.OPEN,
                        reason=reason
                    )
                    if trans_res.get("success"):
                        entry["state"] = CircuitState.OPEN.value
                        entry["opened_at"] = timestamp
                        entry["opened_at_monotonic"] = now_mono
                        record_circuit_lifecycle_event(
                            merchant_id=merchant_id,
                            endpoint=endpoint,
                            circuit_state="OPEN",
                            event_type="CIRCUIT_OPENED",
                            reason=reason,
                            failure_category=cat_str,
                            circuit_generation=entry.get("circuit_generation", 0)
                        )

        elif cat_str == "SUCCESS":
            if entry["state"] == CircuitState.CLOSED.value:
                entry["consecutive_failures"] = 0

        # Persist mutations atomically
        _save_circuit_states_to_disk()
        return dict(entry)


def check_circuit_request_allowed(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    payment_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.3 & 2.2.2.4 - Authoritative Request Gate with Cooldown & HALF_OPEN Probing.
    - CLOSED: allowed=True, is_probe=False.
    - OPEN (cooldown not expired): allowed=False, fast-fails with CIRCUIT_OPEN.
    - OPEN (cooldown expired): atomically transitions OPEN -> HALF_OPEN and evaluates probe.
    - HALF_OPEN (probe count < limit): allowed=True, is_probe=True, increments probe count.
    - HALF_OPEN (probe limit reached): allowed=False, blocks further requests with CIRCUIT_HALF_OPEN_PROBE_LIMIT.
    - Thread-safe under _circuit_lock.
    """
    key = _get_circuit_key(merchant_id, endpoint)
    timestamp = datetime.now(timezone.utc).isoformat()
    now_mono = time.monotonic()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()

    with _circuit_lock:
        if key not in _circuit_states:
            _circuit_states[key] = {
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "state": CircuitState.CLOSED.value,
                "consecutive_failures": 0,
                "total_failures": 0,
                "last_failure_category": None,
                "last_failure_at": None,
                "opened_at": None,
                "opened_at_monotonic": None,
                "failure_threshold": DEFAULT_FAILURE_THRESHOLD,
                "cooldown_duration_sec": DEFAULT_COOLDOWN_DURATION_SEC,
                "half_open_probe_limit": DEFAULT_HALF_OPEN_PROBE_LIMIT,
                "half_open_probe_count": 0,
                "circuit_generation": 0
            }

        entry = _circuit_states[key]
        curr_state = entry["state"]

        # 1. CLOSED STATE -> Allow request immediately
        if curr_state == CircuitState.CLOSED.value:
            return {
                "allowed": True,
                "blocked": False,
                "merchant_id": clean_merchant_id,
                "endpoint": clean_endpoint,
                "circuit_state": CircuitState.CLOSED.value,
                "is_probe": False,
                "circuit_generation": entry.get("circuit_generation", 0),
                "message": "Merchant endpoint request allowed."
            }

        # 2. OPEN STATE -> Check monotonic cooldown duration
        if curr_state == CircuitState.OPEN.value:
            opened_mono = entry.get("opened_at_monotonic")
            cooldown_dur = float(entry.get("cooldown_duration_sec", DEFAULT_COOLDOWN_DURATION_SEC))
            
            if opened_mono is not None:
                elapsed = now_mono - opened_mono
                remaining = max(0.0, cooldown_dur - elapsed)
            else:
                remaining = 0.0

            if remaining > 0.0:
                # Cooldown has NOT expired -> block request
                event_id = f"cb_block_{uuid.uuid4().hex[:10]}"
                block_event = {
                    "event_id": event_id,
                    "merchant_id": clean_merchant_id,
                    "endpoint": clean_endpoint,
                    "payment_id": payment_id,
                    "circuit_state": CircuitState.OPEN.value,
                    "event_type": "REQUEST_BLOCKED",
                    "reason": "CIRCUIT_OPEN",
                    "cooldown_remaining_sec": round(remaining, 2),
                    "timestamp": timestamp
                }
                _blocked_requests_log.append(block_event)
                if len(_blocked_requests_log) > 100:
                    _blocked_requests_log.pop(0)

                return {
                    "allowed": False,
                    "blocked": True,
                    "error": "CIRCUIT_OPEN",
                    "merchant_id": clean_merchant_id,
                    "endpoint": clean_endpoint,
                    "circuit_state": CircuitState.OPEN.value,
                    "cooldown_remaining_sec": round(remaining, 2),
                    "event_id": event_id,
                    "message": "Merchant endpoint request blocked because the circuit breaker is OPEN."
                }

            # Cooldown HAS expired -> Atomically transition OPEN -> HALF_OPEN
            trans_res = transition_circuit_state(
                current_state=CircuitState.OPEN,
                next_state=CircuitState.HALF_OPEN,
                reason="Cooldown period elapsed, entering HALF_OPEN probing state."
            )
            if trans_res.get("success"):
                entry["state"] = CircuitState.HALF_OPEN.value
                entry["circuit_generation"] = entry.get("circuit_generation", 0) + 1
                entry["half_open_probe_count"] = 0
                record_circuit_lifecycle_event(
                    merchant_id=clean_merchant_id,
                    endpoint=clean_endpoint,
                    circuit_state="HALF_OPEN",
                    event_type="CIRCUIT_HALF_OPENED",
                    reason="Cooldown period elapsed, entering HALF_OPEN probing state.",
                    circuit_generation=entry["circuit_generation"]
                )
                curr_state = CircuitState.HALF_OPEN.value
                _save_circuit_states_to_disk()

        # 3. HALF_OPEN STATE -> Evaluate probe admission
        if curr_state == CircuitState.HALF_OPEN.value:
            probe_count = entry.get("half_open_probe_count", 0)
            probe_limit = entry.get("half_open_probe_limit", DEFAULT_HALF_OPEN_PROBE_LIMIT)

            if probe_count < probe_limit:
                # Admit as probe
                entry["half_open_probe_count"] = probe_count + 1
                gen = entry.get("circuit_generation", 0)
                record_circuit_lifecycle_event(
                    merchant_id=clean_merchant_id,
                    endpoint=clean_endpoint,
                    circuit_state="HALF_OPEN",
                    event_type="CIRCUIT_PROBE_STARTED",
                    reason=f"Admitting probe request {entry['half_open_probe_count']} of {probe_limit}",
                    circuit_generation=gen,
                    payment_id=payment_id
                )
                _save_circuit_states_to_disk()
                return {
                    "allowed": True,
                    "blocked": False,
                    "is_probe": True,
                    "probe_number": entry["half_open_probe_count"],
                    "half_open_probe_limit": probe_limit,
                    "circuit_generation": gen,
                    "merchant_id": clean_merchant_id,
                    "endpoint": clean_endpoint,
                    "circuit_state": CircuitState.HALF_OPEN.value,
                    "message": "Probe request admitted in HALF_OPEN state."
                }
            else:
                # Probe limit reached -> block further requests until probes resolve
                event_id = f"cb_block_{uuid.uuid4().hex[:10]}"
                block_event = {
                    "event_id": event_id,
                    "merchant_id": clean_merchant_id,
                    "endpoint": clean_endpoint,
                    "payment_id": payment_id,
                    "circuit_state": CircuitState.HALF_OPEN.value,
                    "event_type": "REQUEST_BLOCKED",
                    "reason": "CIRCUIT_HALF_OPEN_PROBE_LIMIT",
                    "timestamp": timestamp
                }
                _blocked_requests_log.append(block_event)
                if len(_blocked_requests_log) > 100:
                    _blocked_requests_log.pop(0)

                return {
                    "allowed": False,
                    "blocked": True,
                    "error": "CIRCUIT_HALF_OPEN_PROBE_LIMIT",
                    "merchant_id": clean_merchant_id,
                    "endpoint": clean_endpoint,
                    "circuit_state": CircuitState.HALF_OPEN.value,
                    "half_open_probe_count": probe_count,
                    "half_open_probe_limit": probe_limit,
                    "circuit_generation": entry.get("circuit_generation", 0),
                    "event_id": event_id,
                    "message": "Circuit breaker is HALF_OPEN and the probe limit has been reached."
                }

        # Fallback safe denial
        return {
            "allowed": False,
            "blocked": True,
            "error": f"CIRCUIT_{curr_state}",
            "merchant_id": clean_merchant_id,
            "endpoint": clean_endpoint,
            "circuit_state": curr_state,
            "message": f"Merchant endpoint request blocked because circuit is {curr_state}."
        }


def record_half_open_probe_result(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    success: bool = True,
    failure_category: Optional[Any] = None,
    payment_id: Optional[str] = None,
    circuit_generation: Optional[int] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.4 - Authoritative HALF_OPEN Probe Result Recorder.
    - Success -> HALF_OPEN -> CLOSED (resets consecutive_failures, preserves total_failures).
    - Failure -> HALF_OPEN -> OPEN (resets cooldown timer, updates failure info).
    - Thread-safe, atomic persistence, and protected against stale probe results.
    """
    key = _get_circuit_key(merchant_id, endpoint)
    cat_str = str(getattr(failure_category, "value", failure_category) or "SERVER_ERROR").strip().upper()
    timestamp = datetime.now(timezone.utc).isoformat()
    now_mono = time.monotonic()

    with _circuit_lock:
        if key not in _circuit_states:
            return {"success": False, "ignored": True, "reason": "CIRCUIT_NOT_FOUND"}

        entry = _circuit_states[key]

        # 1. Stale generation check
        curr_gen = entry.get("circuit_generation", 0)
        if circuit_generation is not None and circuit_generation != curr_gen:
            return {
                "success": False,
                "ignored": True,
                "reason": "STALE_PROBE_GENERATION",
                "message": f"Probe result from generation {circuit_generation} ignored (current generation is {curr_gen})."
            }

        # 2. Check that circuit is still in HALF_OPEN state
        if entry["state"] != CircuitState.HALF_OPEN.value:
            return {
                "success": False,
                "ignored": True,
                "reason": "CIRCUIT_NOT_HALF_OPEN",
                "current_state": entry["state"],
                "message": f"Probe result ignored because circuit is already in {entry['state']} state."
            }

        # 3. Handle Successful Probe -> Recover to CLOSED
        if success or cat_str in ("SUCCESS", "CLIENT_ERROR", "REDIRECT"):
            reason = "Circuit closed after successful HALF_OPEN probe."
            trans_res = transition_circuit_state(
                current_state=CircuitState.HALF_OPEN,
                next_state=CircuitState.CLOSED,
                reason=reason
            )
            if trans_res.get("success"):
                entry["state"] = CircuitState.CLOSED.value
                entry["consecutive_failures"] = 0
                entry["half_open_probe_count"] = 0
                entry["opened_at"] = None
                entry["opened_at_monotonic"] = None
                record_circuit_lifecycle_event(
                    merchant_id=merchant_id,
                    endpoint=endpoint,
                    circuit_state="CLOSED",
                    event_type="CIRCUIT_CLOSED",
                    reason=reason,
                    circuit_generation=curr_gen,
                    payment_id=payment_id
                )
                _save_circuit_states_to_disk()
                return {
                    "success": True,
                    "state": CircuitState.CLOSED.value,
                    "recovered": True,
                    "message": "Circuit successfully recovered to CLOSED."
                }

        # 4. Handle Failed Probe -> Reopen to OPEN
        if is_circuit_breaker_failure(cat_str):
            reason = f"Circuit reopened after failed HALF_OPEN probe: {cat_str}."
            trans_res = transition_circuit_state(
                current_state=CircuitState.HALF_OPEN,
                next_state=CircuitState.OPEN,
                reason=reason
            )
            if trans_res.get("success"):
                entry["state"] = CircuitState.OPEN.value
                entry["opened_at"] = timestamp
                entry["opened_at_monotonic"] = now_mono
                entry["total_failures"] += 1
                entry["last_failure_category"] = cat_str
                entry["last_failure_at"] = timestamp
                entry["half_open_probe_count"] = 0
                record_circuit_lifecycle_event(
                    merchant_id=merchant_id,
                    endpoint=endpoint,
                    circuit_state="OPEN",
                    event_type="CIRCUIT_OPENED",
                    reason=reason,
                    failure_category=cat_str,
                    circuit_generation=curr_gen,
                    payment_id=payment_id
                )
                _save_circuit_states_to_disk()
                return {
                    "success": True,
                    "state": CircuitState.OPEN.value,
                    "reopened": True,
                    "message": "Circuit reopened to OPEN following failed probe."
                }

        return {"success": False, "message": "Unhandled probe outcome."}


def execute_merchant_request_with_circuit_breaker(
    merchant_id: str,
    endpoint: str,
    request_fn: Callable[[], Any],
    payment_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes an outgoing merchant interaction protected by the circuit breaker gate.
    - Fast-fails if OPEN (before cooldown) or if probe limit reached in HALF_OPEN.
    - If admitted as probe in HALF_OPEN, records probe outcome upon completion.
    """
    gate_check = check_circuit_request_allowed(
        merchant_id=merchant_id,
        endpoint=endpoint,
        payment_id=payment_id
    )

    if not gate_check.get("allowed"):
        return {
            "success": False,
            "fast_failed": True,
            **gate_check
        }

    is_probe = gate_check.get("is_probe", False)
    gen = gate_check.get("circuit_generation")

    # Proceed with actual request execution
    try:
        res = request_fn()
        if is_probe:
            record_half_open_probe_result(
                merchant_id=merchant_id,
                endpoint=endpoint,
                success=True,
                payment_id=payment_id,
                circuit_generation=gen
            )
        return {
            "success": True,
            "fast_failed": False,
            "result": res,
            "is_probe": is_probe,
            "circuit_state": gate_check.get("circuit_state")
        }
    except Exception as e:
        if is_probe:
            err_str = str(e).lower()
            if isinstance(e, TimeoutError) or "timeout" in err_str or "504" in err_str:
                cat = "TIMEOUT"
            elif "429" in err_str or "rate" in err_str:
                cat = "RATE_LIMITED"
            elif "connection" in err_str or "refused" in err_str or "network" in err_str:
                cat = "NETWORK_ERROR"
            else:
                cat = "SERVER_ERROR"

            record_half_open_probe_result(
                merchant_id=merchant_id,
                endpoint=endpoint,
                success=False,
                failure_category=cat,
                payment_id=payment_id,
                circuit_generation=gen
            )
        return {
            "success": False,
            "fast_failed": False,
            "error": str(e),
            "is_probe": is_probe,
            "circuit_state": gate_check.get("circuit_state")
        }


def get_circuit_breaker_status(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook"
) -> Dict[str, Any]:
    """
    Returns current circuit breaker state, probe stats, cooldown metrics, and persistence health.
    """
    state_copy = get_or_create_circuit_state(merchant_id, endpoint)
    now_mono = time.monotonic()

    with _circuit_lock:
        key = _get_circuit_key(merchant_id, endpoint)
        if key in _circuit_states:
            entry = _circuit_states[key]
            if entry["state"] == CircuitState.OPEN.value and entry.get("opened_at_monotonic") is not None:
                elapsed = now_mono - entry["opened_at_monotonic"]
                remaining = max(0.0, float(entry.get("cooldown_duration_sec", DEFAULT_COOLDOWN_DURATION_SEC)) - elapsed)
                state_copy["cooldown_remaining_sec"] = round(remaining, 2)
            else:
                state_copy["cooldown_remaining_sec"] = 0.0

            state_copy["half_open_probe_count"] = entry.get("half_open_probe_count", 0)
            state_copy["half_open_probe_limit"] = entry.get("half_open_probe_limit", DEFAULT_HALF_OPEN_PROBE_LIMIT)
            state_copy["circuit_generation"] = entry.get("circuit_generation", 0)

        # Topic 2.2.2.8 - Authoritative Decision Explanation
        st = state_copy.get("state", "CLOSED")
        fails = state_copy.get("consecutive_failures", 0)
        thresh = state_copy.get("failure_threshold", DEFAULT_FAILURE_THRESHOLD)
        cd_rem = state_copy.get("cooldown_remaining_sec", 0.0)
        last_cat = state_copy.get("last_failure_category")

        if st == CircuitState.CLOSED.value:
            if fails == 0:
                explanation = "Circuit closed — merchant endpoint currently healthy and accepting requests."
            else:
                explanation = f"Circuit closed with {fails} of {thresh} allowable consecutive failures before protective tripping."
        elif st == CircuitState.OPEN.value:
            explanation = f"Circuit open ({last_cat or 'failures'}) — downstream requests are temporarily blocked (cooldown: {cd_rem}s remaining)."
        elif st == CircuitState.HALF_OPEN.value:
            p_cnt = state_copy.get("half_open_probe_count", 0)
            p_lim = state_copy.get("half_open_probe_limit", DEFAULT_HALF_OPEN_PROBE_LIMIT)
            explanation = f"Circuit half-open — cautious recovery probing active ({p_cnt} of {p_lim} probes admitted)."
        else:
            explanation = f"Circuit is in {st} state."

        state_copy["decision_explanation"] = explanation

        state_copy["persistence"] = {
            "enabled": True,
            "status": _persistence_status,
            "last_persisted_at": _last_persisted_at
        }

    return state_copy


def get_all_circuit_breaker_statuses() -> List[Dict[str, Any]]:
    """
    Returns all registered merchant endpoint circuit breaker states.
    """
    keys = []
    with _circuit_lock:
        if not _circuit_states:
            return [get_circuit_breaker_status("merchant_demo", "payment-webhook")]
        keys = list(_circuit_states.keys())

    return [get_circuit_breaker_status(k.split(":")[0], k.split(":")[1]) for k in keys]


def get_merchant_resilience_summary(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook"
) -> Dict[str, Any]:
    """
    Topic 2.2.2.8 - Combined Merchant Endpoint Resilience Overview.
    Integrates Merchant Endpoint Health with Circuit Breaker status.
    """
    cb_status = get_circuit_breaker_status(merchant_id, endpoint)
    
    # Retrieve merchant health summary gracefully
    try:
        try:
            from src.merchant_health import get_endpoint_health_summary
        except ImportError:
            from merchant_health import get_endpoint_health_summary
        health_summary = get_endpoint_health_summary(merchant_id, endpoint)
    except Exception:
        health_summary = {
            "merchant_id": merchant_id,
            "endpoint": endpoint,
            "health": "NO_DATA",
            "success_rate": 0.0,
            "average_latency_ms": None,
            "p95_latency_ms": None,
            "timeouts": 0
        }

    cb_state = cb_status.get("state", "CLOSED")
    health_state = health_summary.get("health", "NO_DATA")
    consecutive_fails = cb_status.get("consecutive_failures", 0)

    # Determine request availability
    requests_allowed = (cb_state == "CLOSED") or (
        cb_state == "HALF_OPEN" and cb_status.get("half_open_probe_count", 0) < cb_status.get("half_open_probe_limit", 3)
    )

    # Determine risk level
    if cb_state == "OPEN":
        risk_level = "CRITICAL"
        decision = "BLOCK_REQUESTS"
    elif cb_state == "HALF_OPEN":
        risk_level = "HIGH"
        decision = "PROBE_RECOVERY"
    elif health_state == "UNHEALTHY":
        risk_level = "HIGH"
        decision = "ALLOW_REQUESTS"
    elif health_state == "DEGRADED" or consecutive_fails > 0:
        risk_level = "ELEVATED"
        decision = "ALLOW_REQUESTS"
    else:
        risk_level = "LOW"
        decision = "ALLOW_REQUESTS"

    # Contextual combined explanation
    explanation = f"Endpoint health is {health_state}; Circuit breaker is {cb_state}. Outgoing recovery requests are {'' if requests_allowed else 'NOT '}permitted."

    return {
        "merchant_id": merchant_id,
        "endpoint": endpoint,
        "merchant_health": health_summary,
        "circuit_breaker": cb_status,
        "resilience_summary": {
            "requests_allowed": requests_allowed,
            "risk_level": risk_level,
            "decision": decision,
            "explanation": explanation
        }
    }



def reset_circuit_breaker_state() -> None:
    """Helper to reset runtime circuit states and storage file for testing."""
    with _circuit_lock:
        _circuit_states.clear()
        _blocked_requests_log.clear()
        _circuit_lifecycle_log.clear()
        if os.path.exists(CIRCUIT_STATE_STORAGE_PATH):
            try:
                os.remove(CIRCUIT_STATE_STORAGE_PATH)
            except Exception:
                pass


def get_blocked_requests_telemetry(merchant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves safe blocked request telemetry.
    """
    with _circuit_lock:
        if not merchant_id:
            return list(_blocked_requests_log)
        return [e for e in _blocked_requests_log if e.get("merchant_id") == merchant_id]


def get_circuit_lifecycle_telemetry(merchant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves safe circuit lifecycle telemetry.
    """
    with _circuit_lock:
        if not merchant_id:
            return list(_circuit_lifecycle_log)
        return [e for e in _circuit_lifecycle_log if e.get("merchant_id") == merchant_id]


def persist_circuit_breaker_state() -> bool:
    """Explicitly triggers atomic disk persistence."""
    with _circuit_lock:
        return _save_circuit_states_to_disk()


def load_circuit_breaker_state() -> bool:
    """Explicitly triggers loading state from disk."""
    return _load_circuit_states_from_disk()


def get_circuit_persistence_status() -> Dict[str, Any]:
    """Returns persistence engine status metadata."""
    with _circuit_lock:
        return {
            "enabled": True,
            "status": _persistence_status,
            "storage_path": CIRCUIT_STATE_STORAGE_PATH,
            "last_persisted_at": _last_persisted_at
        }


# =========================================================================
# 4. TOPIC 2.2.2.7 — CONTROLLED OPERATOR CIRCUIT OVERRIDES
# =========================================================================

def operator_force_open_circuit(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    reason: str = "",
    operator_id: str = "demo-operator",
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.7 - Controlled Operator Force Open.
    - Transitions CLOSED -> OPEN or HALF_OPEN -> OPEN.
    - If already OPEN, returns safe already-in-state response.
    - Requires mandatory human-readable reason.
    - Preserves total_failures, re-anchors cooldown, persists state atomically.
    """
    clean_reason = str(reason or "").strip()
    if not clean_reason:
        return {
            "success": False,
            "error": "CIRCUIT_OVERRIDE_REASON_REQUIRED",
            "message": "Operator reason is required for Force Open."
        }

    key = _get_circuit_key(merchant_id, endpoint)
    timestamp = datetime.now(timezone.utc).isoformat()
    now_mono = time.monotonic()
    op_id = str(operator_id or "demo-operator").strip()

    with _circuit_lock:
        if key not in _circuit_states:
            _circuit_states[key] = {
                "merchant_id": str(merchant_id or "merchant_demo").strip(),
                "endpoint": str(endpoint or "payment-webhook").strip(),
                "state": CircuitState.CLOSED.value,
                "consecutive_failures": 0,
                "total_failures": 0,
                "last_failure_category": None,
                "last_failure_at": None,
                "opened_at": None,
                "opened_at_monotonic": None,
                "failure_threshold": DEFAULT_FAILURE_THRESHOLD,
                "cooldown_duration_sec": DEFAULT_COOLDOWN_DURATION_SEC,
                "half_open_probe_limit": DEFAULT_HALF_OPEN_PROBE_LIMIT,
                "half_open_probe_count": 0,
                "circuit_generation": 0
            }

        entry = _circuit_states[key]
        curr_state = entry["state"]

        if curr_state == CircuitState.OPEN.value:
            return {
                "success": True,
                "action": "FORCE_OPEN",
                "state": CircuitState.OPEN.value,
                "already_in_state": True,
                "merchant_id": merchant_id,
                "endpoint": endpoint,
                "message": "Circuit breaker is already in OPEN state."
            }

        # Transition to OPEN
        trans_res = transition_circuit_state(
            current_state=curr_state,
            next_state=CircuitState.OPEN,
            reason=f"Operator Force Open: {clean_reason}",
            allow_operator_override=True
        )
        if not trans_res.get("success"):
            return {
                "success": False,
                "error": trans_res.get("error", "INVALID_CIRCUIT_TRANSITION"),
                "current_state": curr_state,
                "message": trans_res.get("message", "Invalid circuit transition.")
            }

        entry["state"] = CircuitState.OPEN.value
        entry["opened_at"] = timestamp
        entry["opened_at_monotonic"] = now_mono
        entry["last_failure_category"] = "OPERATOR_OVERRIDE"
        entry["last_failure_at"] = timestamp
        entry["half_open_probe_count"] = 0

        record_circuit_lifecycle_event(
            merchant_id=merchant_id,
            endpoint=endpoint,
            circuit_state="OPEN",
            event_type="CIRCUIT_OVERRIDE",
            reason=f"Operator Force Open: {clean_reason}",
            failure_category="OPERATOR_OVERRIDE",
            circuit_generation=entry.get("circuit_generation", 0),
            actor_type="OPERATOR",
            actor_id=op_id,
            source="HUMAN_ACTION_CENTER"
        )
        _save_circuit_states_to_disk()

        return {
            "success": True,
            "action": "FORCE_OPEN",
            "state": CircuitState.OPEN.value,
            "from_state": curr_state,
            "merchant_id": merchant_id,
            "endpoint": endpoint,
            "operator_id": op_id,
            "reason": clean_reason,
            "message": "Circuit breaker force-opened successfully by operator."
        }


def operator_reset_circuit(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    reason: str = "",
    operator_id: str = "demo-operator",
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.7 - Controlled Operator Reset / Close.
    - Transitions OPEN -> CLOSED or HALF_OPEN -> CLOSED.
    - Rejects CLOSED -> CLOSED as redundant.
    - Requires mandatory human-readable reason.
    - Preserves historical total_failures, resets consecutive_failures = 0, clears cooldown.
    """
    clean_reason = str(reason or "").strip()
    if not clean_reason:
        return {
            "success": False,
            "error": "CIRCUIT_OVERRIDE_REASON_REQUIRED",
            "message": "Operator reason is required for Circuit Reset."
        }

    key = _get_circuit_key(merchant_id, endpoint)
    op_id = str(operator_id or "demo-operator").strip()

    with _circuit_lock:
        if key not in _circuit_states:
            _circuit_states[key] = {
                "merchant_id": str(merchant_id or "merchant_demo").strip(),
                "endpoint": str(endpoint or "payment-webhook").strip(),
                "state": CircuitState.CLOSED.value,
                "consecutive_failures": 0,
                "total_failures": 0,
                "last_failure_category": None,
                "last_failure_at": None,
                "opened_at": None,
                "opened_at_monotonic": None,
                "failure_threshold": DEFAULT_FAILURE_THRESHOLD,
                "cooldown_duration_sec": DEFAULT_COOLDOWN_DURATION_SEC,
                "half_open_probe_limit": DEFAULT_HALF_OPEN_PROBE_LIMIT,
                "half_open_probe_count": 0,
                "circuit_generation": 0
            }

        entry = _circuit_states[key]
        curr_state = entry["state"]

        if curr_state == CircuitState.CLOSED.value:
            return {
                "success": False,
                "error": "CIRCUIT_ALREADY_CLOSED",
                "current_state": CircuitState.CLOSED.value,
                "message": "Circuit is already CLOSED; reset rejected as unnecessary."
            }

        # Transition to CLOSED
        trans_res = transition_circuit_state(
            current_state=curr_state,
            next_state=CircuitState.CLOSED,
            reason=f"Operator Reset: {clean_reason}",
            allow_operator_override=True
        )
        if not trans_res.get("success"):
            return {
                "success": False,
                "error": trans_res.get("error", "INVALID_CIRCUIT_TRANSITION"),
                "current_state": curr_state,
                "message": trans_res.get("message", "Invalid circuit transition.")
            }

        entry["state"] = CircuitState.CLOSED.value
        entry["consecutive_failures"] = 0
        entry["half_open_probe_count"] = 0
        entry["opened_at"] = None
        entry["opened_at_monotonic"] = None

        record_circuit_lifecycle_event(
            merchant_id=merchant_id,
            endpoint=endpoint,
            circuit_state="CLOSED",
            event_type="CIRCUIT_OVERRIDE",
            reason=f"Operator Reset: {clean_reason}",
            circuit_generation=entry.get("circuit_generation", 0),
            actor_type="OPERATOR",
            actor_id=op_id,
            source="HUMAN_ACTION_CENTER"
        )
        _save_circuit_states_to_disk()

        return {
            "success": True,
            "action": "RESET",
            "state": CircuitState.CLOSED.value,
            "from_state": curr_state,
            "merchant_id": merchant_id,
            "endpoint": endpoint,
            "operator_id": op_id,
            "reason": clean_reason,
            "message": "Circuit breaker reset to CLOSED successfully by operator."
        }


def operator_manual_probe_circuit(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    reason: str = "",
    operator_id: str = "demo-operator",
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 2.2.2.7 - Controlled Operator Manual Probe.
    - Transitions OPEN -> HALF_OPEN (enables probe opportunity).
    - If already HALF_OPEN, returns safe already-in-state response.
    - If CLOSED, rejects transition (probing only legal from OPEN).
    - Requires mandatory human-readable reason.
    - Increments circuit_generation, resets half_open_probe_count = 0.
    """
    clean_reason = str(reason or "").strip()
    if not clean_reason:
        return {
            "success": False,
            "error": "CIRCUIT_OVERRIDE_REASON_REQUIRED",
            "message": "Operator reason is required to request a recovery probe."
        }

    key = _get_circuit_key(merchant_id, endpoint)
    op_id = str(operator_id or "demo-operator").strip()

    with _circuit_lock:
        if key not in _circuit_states:
            _circuit_states[key] = {
                "merchant_id": str(merchant_id or "merchant_demo").strip(),
                "endpoint": str(endpoint or "payment-webhook").strip(),
                "state": CircuitState.CLOSED.value,
                "consecutive_failures": 0,
                "total_failures": 0,
                "last_failure_category": None,
                "last_failure_at": None,
                "opened_at": None,
                "opened_at_monotonic": None,
                "failure_threshold": DEFAULT_FAILURE_THRESHOLD,
                "cooldown_duration_sec": DEFAULT_COOLDOWN_DURATION_SEC,
                "half_open_probe_limit": DEFAULT_HALF_OPEN_PROBE_LIMIT,
                "half_open_probe_count": 0,
                "circuit_generation": 0
            }

        entry = _circuit_states[key]
        curr_state = entry["state"]

        if curr_state == CircuitState.CLOSED.value:
            return {
                "success": False,
                "error": "INVALID_CIRCUIT_TRANSITION",
                "current_state": CircuitState.CLOSED.value,
                "message": "Cannot probe a CLOSED circuit. Recovery probing is only valid when circuit is OPEN."
            }

        if curr_state == CircuitState.HALF_OPEN.value:
            return {
                "success": True,
                "action": "MANUAL_PROBE",
                "state": CircuitState.HALF_OPEN.value,
                "already_in_state": True,
                "merchant_id": merchant_id,
                "endpoint": endpoint,
                "circuit_generation": entry.get("circuit_generation", 0),
                "message": "Circuit breaker is already in HALF_OPEN probing state."
            }

        # Transition OPEN -> HALF_OPEN
        trans_res = transition_circuit_state(
            current_state=CircuitState.OPEN,
            next_state=CircuitState.HALF_OPEN,
            reason=f"Operator Manual Probe: {clean_reason}",
            allow_operator_override=True
        )
        if not trans_res.get("success"):
            return {
                "success": False,
                "error": trans_res.get("error", "INVALID_CIRCUIT_TRANSITION"),
                "current_state": curr_state,
                "message": trans_res.get("message", "Invalid circuit transition.")
            }

        entry["state"] = CircuitState.HALF_OPEN.value
        entry["circuit_generation"] = entry.get("circuit_generation", 0) + 1
        entry["half_open_probe_count"] = 0

        record_circuit_lifecycle_event(
            merchant_id=merchant_id,
            endpoint=endpoint,
            circuit_state="HALF_OPEN",
            event_type="CIRCUIT_OVERRIDE",
            reason=f"Operator Manual Probe: {clean_reason}",
            circuit_generation=entry["circuit_generation"],
            actor_type="OPERATOR",
            actor_id=op_id,
            source="HUMAN_ACTION_CENTER"
        )
        _save_circuit_states_to_disk()

        return {
            "success": True,
            "action": "MANUAL_PROBE",
            "state": CircuitState.HALF_OPEN.value,
            "from_state": CircuitState.OPEN.value,
            "merchant_id": merchant_id,
            "endpoint": endpoint,
            "operator_id": op_id,
            "circuit_generation": entry["circuit_generation"],
            "reason": clean_reason,
            "message": "Circuit breaker moved to HALF_OPEN for recovery probing."
        }

