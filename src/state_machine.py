"""
RecoverIQ - Authoritative Payment State Machine Definitions (Topic 1.5.1)

Single source of truth for payment lifecycle states, metadata, categories,
and backward-compatibility normalization.
"""

import sys
from enum import Enum
from typing import Dict, Any, Optional, Set

# Ensure singleton across both 'state_machine' and 'src.state_machine' import paths
if __name__ in sys.modules:
    sys.modules['state_machine'] = sys.modules[__name__]
    sys.modules['src.state_machine'] = sys.modules[__name__]



class PaymentState(str, Enum):
    """Authoritative Payment Lifecycle States."""
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RECOVERING = "RECOVERING"
    RECOVERED = "RECOVERED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    REFUNDED = "REFUNDED"
    ESCALATED = "ESCALATED"
    STOPPED = "STOPPED"


class StateCategory(str, Enum):
    """High-level classification categories for payment states."""
    INITIAL = "INITIAL"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_INPUT = "AWAITING_INPUT"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    TERMINAL_SUCCESS = "TERMINAL_SUCCESS"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    TERMINAL_REFUND = "TERMINAL_REFUND"
    STOPPED = "STOPPED"


# Authoritative State Metadata Catalog
PAYMENT_STATES: Dict[PaymentState, Dict[str, Any]] = {
    PaymentState.CREATED: {
        "machine_value": "CREATED",
        "label": "Created",
        "description": "Payment transaction initialized in payment gateway.",
        "category": StateCategory.INITIAL.value,
        "is_terminal": False,
        "badge_color": "slate"
    },
    PaymentState.PROCESSING: {
        "machine_value": "PROCESSING",
        "label": "Processing",
        "description": "Payment transaction is currently in-flight with gateway or banking rails.",
        "category": StateCategory.IN_PROGRESS.value,
        "is_terminal": False,
        "badge_color": "blue"
    },
    PaymentState.SUCCESS: {
        "machine_value": "SUCCESS",
        "label": "Success",
        "description": "Payment was successfully captured by the payment gateway.",
        "category": StateCategory.TERMINAL_SUCCESS.value,
        "is_terminal": True,
        "badge_color": "emerald"
    },
    PaymentState.FAILED: {
        "machine_value": "FAILED",
        "label": "Failed",
        "description": "Payment capture failed or customer transaction was rejected.",
        "category": StateCategory.TERMINAL_FAILURE.value,
        "is_terminal": True,
        "badge_color": "rose"
    },
    PaymentState.PENDING: {
        "machine_value": "PENDING",
        "label": "Pending",
        "description": "Payment state is awaiting asynchronous verification or webhook confirmation.",
        "category": StateCategory.AWAITING_INPUT.value,
        "is_terminal": False,
        "badge_color": "amber"
    },
    PaymentState.HUMAN_REVIEW: {
        "machine_value": "HUMAN_REVIEW",
        "label": "Human Review",
        "description": "Payment requires operator approval before recovery.",
        "category": StateCategory.ACTION_REQUIRED.value,
        "is_terminal": False,
        "badge_color": "amber"
    },
    PaymentState.RECOVERING: {
        "machine_value": "RECOVERING",
        "label": "Recovering",
        "description": "An approved recovery action is being executed.",
        "category": StateCategory.IN_PROGRESS.value,
        "is_terminal": False,
        "badge_color": "blue"
    },
    PaymentState.RECOVERED: {
        "machine_value": "RECOVERED",
        "label": "Recovered",
        "description": "Recovery completed and payment state was successfully verified.",
        "category": StateCategory.TERMINAL_SUCCESS.value,
        "is_terminal": True,
        "badge_color": "emerald"
    },
    PaymentState.RECOVERY_FAILED: {
        "machine_value": "RECOVERY_FAILED",
        "label": "Recovery Failed",
        "description": "Recovery action executed but post-recovery verification failed.",
        "category": StateCategory.TERMINAL_FAILURE.value,
        "is_terminal": True,
        "badge_color": "rose"
    },
    PaymentState.REFUNDED: {
        "machine_value": "REFUNDED",
        "label": "Refunded",
        "description": "Transaction amount was refunded to customer account.",
        "category": StateCategory.TERMINAL_REFUND.value,
        "is_terminal": True,
        "badge_color": "purple"
    },
    PaymentState.ESCALATED: {
        "machine_value": "ESCALATED",
        "label": "Escalated",
        "description": "Incident routed to Merchant Engineering on-call for technical investigation.",
        "category": StateCategory.ACTION_REQUIRED.value,
        "is_terminal": False,
        "badge_color": "indigo"
    },
    PaymentState.STOPPED: {
        "machine_value": "STOPPED",
        "label": "Stopped",
        "description": "Automated processing was intentionally stopped.",
        "category": StateCategory.STOPPED.value,
        "is_terminal": True,
        "badge_color": "slate"
    },
}

# Backward-compatibility alias lookup mapping
LEGACY_STATE_MAPPINGS: Dict[str, PaymentState] = {
    # Variations of HUMAN REVIEW
    "HUMAN REVIEW": PaymentState.HUMAN_REVIEW,
    "HUMAN_REVIEW": PaymentState.HUMAN_REVIEW,
    "PENDING_REVIEW": PaymentState.HUMAN_REVIEW,
    "MANUAL_REVIEW": PaymentState.HUMAN_REVIEW,
    "REVIEW": PaymentState.HUMAN_REVIEW,

    # Variations of AUTO RECOVERY / RECOVERING
    "AUTO RECOVERY": PaymentState.RECOVERING,
    "AUTO_RECOVERY": PaymentState.RECOVERING,
    "RECOVERING": PaymentState.RECOVERING,
    "RECOVERABLE": PaymentState.PENDING,

    # Variations of STOP
    "STOP": PaymentState.STOPPED,
    "STOPPED": PaymentState.STOPPED,
    "HALTED": PaymentState.STOPPED,

    # Variations of SUCCESS / HEALTHY
    "NO ACTION": PaymentState.SUCCESS,
    "NO_ACTION": PaymentState.SUCCESS,
    "HEALTHY": PaymentState.SUCCESS,
    "SUCCESS": PaymentState.SUCCESS,
    "SUCCESSFUL": PaymentState.SUCCESS,

    # Variations of RECOVERED
    "RECOVERED": PaymentState.RECOVERED,
    "RESOLVED": PaymentState.RECOVERED,

    # Variations of FAILED / RECOVERY_FAILED
    "FAILED": PaymentState.FAILED,
    "RECOVERY_FAILED": PaymentState.RECOVERY_FAILED,
    "FAILURE": PaymentState.FAILED,

    # Variations of PENDING / PROCESSING
    "PENDING": PaymentState.PENDING,
    "NOT_EXECUTED": PaymentState.PENDING,
    "PROCESSING": PaymentState.PROCESSING,
    "QUEUED": PaymentState.PROCESSING,
    "IN_PROGRESS": PaymentState.PROCESSING,
    "CREATED": PaymentState.CREATED,

    # Variations of REFUNDED / ESCALATED
    "REFUNDED": PaymentState.REFUNDED,
    "REFUND": PaymentState.REFUNDED,
    "ESCALATED": PaymentState.ESCALATED,
    "ESCALATE": PaymentState.ESCALATED,
}


def normalize_payment_state(raw_state: Optional[str]) -> PaymentState:
    """
    Normalizes any legacy, freeform, or case-variant state string into
    one of the 12 authoritative PaymentState enum values.
    """
    if not raw_state:
        return PaymentState.PENDING

    cleaned = str(raw_state).strip().upper()

    # Exact enum match
    if cleaned in PaymentState.__members__:
        return PaymentState[cleaned]

    # Alias / legacy lookup
    if cleaned in LEGACY_STATE_MAPPINGS:
        return LEGACY_STATE_MAPPINGS[cleaned]

    # Substring heuristic normalization
    if "HUMAN" in cleaned or "REVIEW" in cleaned:
        return PaymentState.HUMAN_REVIEW
    if "RECOVERED" in cleaned or "RESOLVED" in cleaned:
        return PaymentState.RECOVERED
    if "RECOVER" in cleaned:
        return PaymentState.RECOVERING
    if "STOP" in cleaned or "HALT" in cleaned:
        return PaymentState.STOPPED
    if "REFUND" in cleaned:
        return PaymentState.REFUNDED
    if "ESCALAT" in cleaned:
        return PaymentState.ESCALATED
    if "FAIL" in cleaned:
        return PaymentState.FAILED
    if "SUCCESS" in cleaned or "HEALTHY" in cleaned:
        return PaymentState.SUCCESS

    return PaymentState.PENDING


def get_state_metadata(state: Any) -> Dict[str, Any]:
    """
    Retrieves full metadata dictionary for any given state enum or string.
    """
    if isinstance(state, PaymentState):
        enum_val = state
    else:
        enum_val = normalize_payment_state(str(state))

    return PAYMENT_STATES.get(enum_val, PAYMENT_STATES[PaymentState.PENDING])


def get_all_states() -> Dict[str, Dict[str, Any]]:
    """
    Returns all 12 authoritative states formatted as a JSON-serializable dictionary.
    """
    return {
        state.value: {
            "machine_value": meta["machine_value"],
            "label": meta["label"],
            "description": meta["description"],
            "category": meta["category"],
            "is_terminal": meta["is_terminal"],
            "badge_color": meta["badge_color"]
        }
        for state, meta in PAYMENT_STATES.items()
    }


# =========================================================================
# TOPIC 1.5.2 — VALID STATE TRANSITIONS MAP & CENTRALIZED API
# =========================================================================

VALID_STATE_TRANSITIONS: Dict[PaymentState, Set[PaymentState]] = {
    PaymentState.CREATED: {
        PaymentState.PROCESSING
    },
    PaymentState.PROCESSING: {
        PaymentState.SUCCESS,
        PaymentState.FAILED,
        PaymentState.PENDING
    },
    PaymentState.PENDING: {
        PaymentState.SUCCESS,
        PaymentState.FAILED,
        PaymentState.HUMAN_REVIEW
    },
    PaymentState.FAILED: {
        PaymentState.HUMAN_REVIEW,
        PaymentState.STOPPED
    },
    PaymentState.HUMAN_REVIEW: {
        PaymentState.RECOVERING,
        PaymentState.ESCALATED,
        PaymentState.STOPPED
    },
    PaymentState.RECOVERING: {
        PaymentState.RECOVERED,
        PaymentState.RECOVERY_FAILED,
        PaymentState.ESCALATED
    },
    PaymentState.RECOVERY_FAILED: {
        PaymentState.HUMAN_REVIEW,
        PaymentState.ESCALATED,
        PaymentState.STOPPED
    },
    PaymentState.ESCALATED: {
        PaymentState.HUMAN_REVIEW,
        PaymentState.STOPPED
    },
    PaymentState.SUCCESS: {
        PaymentState.REFUNDED
    },
    PaymentState.RECOVERED: {
        PaymentState.REFUNDED
    },
    PaymentState.REFUNDED: set(),
    PaymentState.STOPPED: set()
}


def is_valid_transition(current_state: Any, next_state: Any) -> bool:
    """
    Validates if transitioning from current_state to next_state is legally allowed.
    Does NOT mutate any payment state.
    """
    curr = current_state if isinstance(current_state, PaymentState) else normalize_payment_state(str(current_state))
    nxt = next_state if isinstance(next_state, PaymentState) else normalize_payment_state(str(next_state))

    allowed = VALID_STATE_TRANSITIONS.get(curr, set())
    return nxt in allowed


def get_allowed_transitions(current_state: Any) -> List[PaymentState]:
    """
    Returns list of valid next PaymentState enum values for a given current state.
    Terminal states (REFUNDED, STOPPED) return an empty list.
    """
    curr = current_state if isinstance(current_state, PaymentState) else normalize_payment_state(str(current_state))
    allowed_set = VALID_STATE_TRANSITIONS.get(curr, set())
    return [s for s in PaymentState if s in allowed_set]


class StateTransitionIntent:
    """
    Prepared architectural contract for state transition requests (for Topic 1.5.4).
    """
    def __init__(
        self,
        payment_id: str,
        current_state: PaymentState,
        next_state: PaymentState,
        reason: Optional[str] = None,
        operator_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ):
        self.payment_id = payment_id
        self.current_state = current_state
        self.next_state = next_state
        self.reason = reason
        self.operator_id = operator_id
        self.idempotency_key = idempotency_key

    def is_valid(self) -> bool:
        return is_valid_transition(self.current_state, self.next_state)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payment_id": self.payment_id,
            "current_state": self.current_state.value,
            "next_state": self.next_state.value,
            "reason": self.reason,
            "operator_id": self.operator_id,
            "idempotency_key": self.idempotency_key
        }


# =========================================================================
# TOPIC 1.5.3 & 1.5.4 — STATE TRANSITION ENGINE & EXPLICIT REASON EVENTS
# =========================================================================

import uuid
import os
import json
import threading
from datetime import datetime, timezone


class ActorType(str, Enum):
    """Actors permitted to trigger payment state transitions."""
    OPERATOR = "OPERATOR"
    AI_AGENT = "AI_AGENT"
    SYSTEM = "SYSTEM"
    GATEWAY = "GATEWAY"


class TransitionSource(str, Enum):
    """Source subsystems initiating payment state transitions."""
    HUMAN_ACTION_CENTER = "HUMAN_ACTION_CENTER"
    RECOVERY_ENGINE = "RECOVERY_ENGINE"
    PAYMENT_GATEWAY = "PAYMENT_GATEWAY"
    WEBHOOK = "WEBHOOK"
    SYSTEM = "SYSTEM"
    FILE_ANALYSIS = "FILE_ANALYSIS"


LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
TRANSITION_EVENTS_STORE_PATH = os.path.join(LOGS_DIR, "payment_transition_events.json")

_state_lock = threading.RLock()

# Runtime state storage for active payment lifecycles
_runtime_payment_state_store: Dict[str, PaymentState] = {}
# Historical transition events indexed by payment_id
_payment_transition_events_store: Dict[str, List[Dict[str, Any]]] = {}
# Monotonic state version counters per payment_id
_payment_version_store: Dict[str, int] = {}


def _load_persisted_events() -> Dict[str, List[Dict[str, Any]]]:
    if os.path.exists(TRANSITION_EVENTS_STORE_PATH):
        try:
            with open(TRANSITION_EVENTS_STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_persisted_events(data: Dict[str, List[Dict[str, Any]]]) -> None:
    try:
        with open(TRANSITION_EVENTS_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def get_payment_version(payment_id: str) -> int:
    """
    Retrieves the current monotonic state revision / version for a payment.
    """
    clean_pid = str(payment_id or "").strip()
    with _state_lock:
        return _payment_version_store.get(clean_pid, 1)


def get_current_payment_state(payment_id: str, case_data: Optional[Dict[str, Any]] = None) -> PaymentState:
    """
    Retrieves the current authoritative state for a given payment_id.
    """
    clean_pid = str(payment_id or "").strip()
    with _state_lock:
        if clean_pid in _runtime_payment_state_store:
            return _runtime_payment_state_store[clean_pid]

    # Deterministic default state mappings for demo fixtures
    if clean_pid == "pay_005":
        state = PaymentState.HUMAN_REVIEW
    elif clean_pid == "pay_004":
        state = PaymentState.RECOVERED
    elif clean_pid == "pay_001":
        state = PaymentState.STOPPED
    elif clean_pid == "pay_002":
        state = PaymentState.HUMAN_REVIEW
    elif clean_pid == "pay_003":
        state = PaymentState.STOPPED
    elif case_data:
        rec_status = str(case_data.get("recovery_status", "")).upper()
        decision = str(case_data.get("decision", "")).upper()
        pay_status = str(case_data.get("payment_status", case_data.get("status", ""))).upper()
        retry_count = int(case_data.get("retry_count", 0))
        confidence = float(case_data.get("confidence", 100))
        order_exists = bool(case_data.get("merchant_order_exists", case_data.get("order_exists", False)))

        if rec_status in ("SUCCESS", "RECOVERED"):
            state = PaymentState.RECOVERED
        elif rec_status == "STOPPED" or decision == "STOP":
            state = PaymentState.STOPPED
        elif decision in ("HUMAN REVIEW", "HUMAN_REVIEW") or retry_count >= 2 or confidence < 85:
            state = PaymentState.HUMAN_REVIEW
        elif rec_status == "FAILED" or pay_status == "FAILED":
            state = PaymentState.FAILED
        elif pay_status == "SUCCESS" and order_exists:
            state = PaymentState.SUCCESS
        elif pay_status == "SUCCESS" and not order_exists:
            state = PaymentState.HUMAN_REVIEW if retry_count >= 2 else PaymentState.PENDING
        else:
            state = PaymentState.PENDING
    else:
        state = PaymentState.PENDING

    with _state_lock:
        _runtime_payment_state_store[clean_pid] = state
        if clean_pid not in _payment_version_store:
            _payment_version_store[clean_pid] = 1
    return state


def set_payment_state_directly(payment_id: str, state: PaymentState) -> None:
    """Internal test/seed helper to initialize a payment's state."""
    clean_pid = str(payment_id or "").strip()
    with _state_lock:
        _runtime_payment_state_store[clean_pid] = state
        _payment_version_store[clean_pid] = _payment_version_store.get(clean_pid, 1) + 1


def reset_payment_state_store() -> None:
    """Internal helper to reset runtime state store for testing."""
    with _state_lock:
        _runtime_payment_state_store.clear()
        _payment_transition_events_store.clear()
        _payment_version_store.clear()
        if os.path.exists(TRANSITION_EVENTS_STORE_PATH):
            try:
                os.remove(TRANSITION_EVENTS_STORE_PATH)
            except Exception:
                pass


def get_payment_transition_events(payment_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all historical transition events recorded for a given payment_id.
    """
    clean_pid = str(payment_id or "").strip()
    with _state_lock:
        if not _payment_transition_events_store and os.path.exists(TRANSITION_EVENTS_STORE_PATH):
            _payment_transition_events_store.update(_load_persisted_events())
        return list(_payment_transition_events_store.get(clean_pid, []))


def handle_out_of_order_event(
    payment_id: str,
    incoming_version: int,
    incoming_state: Any,
    event_id: Optional[str] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    P1 - Out-of-Order / Stale Event Handling.
    Safely rejects stale historical events that attempt to regress authoritative state.
    """
    clean_pid = str(payment_id or "").strip()
    current_state = get_current_payment_state(clean_pid)
    current_version = get_payment_version(clean_pid)

    if incoming_version < current_version:
        # Record audit event for stale event rejection
        try:
            from src.recovery_audit import record_recovery_audit_event
            record_recovery_audit_event(
                payment_id=clean_pid,
                event_type="STALE_PAYMENT_EVENT_IGNORED",
                actor_type="SYSTEM",
                source="STATE_MACHINE_GUARD",
                status="IGNORED",
                reason=f"Ignored stale event v{incoming_version} attempting to mutate current authoritative state {current_state.value} v{current_version}.",
                correlation_id=event_id,
                metadata={"incoming_version": incoming_version, "current_version": current_version, "trace_id": trace_id}
            )
        except Exception:
            pass

        return {
            "success": False,
            "status": "STALE_EVENT_IGNORED",
            "payment_id": clean_pid,
            "current_state": current_state.value,
            "current_version": current_version,
            "incoming_version": incoming_version,
            "message": f"Stale event ignored: current state is v{current_version} ({current_state.value}), incoming event was v{incoming_version}."
        }

    return {"success": True, "status": "EVENT_ACCEPTED", "payment_id": clean_pid}


def transition_payment_state(
    payment_id: str,
    next_state: Any,
    reason: Optional[str] = None,
    actor_type: Any = "SYSTEM",
    actor_id: Optional[str] = None,
    source: Any = "SYSTEM",
    case_data: Optional[Dict[str, Any]] = None,
    expected_version: Optional[int] = None
) -> Dict[str, Any]:
    """
    Authoritative state transition engine with explicit reasons, versioning, and actor metadata.
    """
    if not payment_id:
        raise ValueError("payment_id is required for state transition.")

    clean_pid = str(payment_id).strip()

    # 1. Validate required reason
    if not reason or not str(reason).strip():
        current_state = get_current_payment_state(clean_pid, case_data)
        return {
            "success": False,
            "error": "TRANSITION_REASON_REQUIRED",
            "payment_id": clean_pid,
            "current_state": current_state.value,
            "message": "A reason is required for payment state transitions."
        }

    clean_reason = str(reason).strip()

    # 2. Determine current state and version
    current_state = get_current_payment_state(clean_pid, case_data)
    current_version = get_payment_version(clean_pid)

    # 3. Optimistic Concurrency Check
    if expected_version is not None and expected_version != current_version:
        return {
            "success": False,
            "error": "STATE_CHANGED_SINCE_REVIEW",
            "status_code": 409,
            "payment_id": clean_pid,
            "current_state": current_state.value,
            "current_version": current_version,
            "expected_version": expected_version,
            "message": "Payment state changed after this operator view was loaded. Refresh before taking action."
        }

    # 4. Normalize next_state
    try:
        if isinstance(next_state, PaymentState):
            normalized_next = next_state
        else:
            cleaned = str(next_state).strip().upper()
            if cleaned not in PaymentState.__members__ and cleaned not in LEGACY_STATE_MAPPINGS:
                raise ValueError(f"Invalid state value: '{next_state}'")
            normalized_next = normalize_payment_state(cleaned)
    except Exception as e:
        raise ValueError(f"Invalid state value: '{next_state}'") from e

    # 5. Check transition validity
    if not is_valid_transition(current_state, normalized_next):
        allowed = get_allowed_transitions(current_state)
        return {
            "success": False,
            "error": "INVALID_STATE_TRANSITION",
            "payment_id": clean_pid,
            "current_state": current_state.value,
            "requested_state": normalized_next.value,
            "reason": clean_reason,
            "allowed_transitions": [s.value for s in allowed],
            "transition_status": "REJECTED",
            "message": f"Requested payment state transition from {current_state.value} to {normalized_next.value} is not allowed."
        }

    # 6. Apply state transition, increment version & create structured event
    clean_actor_type = str(actor_type.value if isinstance(actor_type, ActorType) else actor_type).upper()
    clean_source = str(source.value if isinstance(source, TransitionSource) else source).upper()
    clean_actor_id = str(actor_id or ("demo-operator" if clean_actor_type == "OPERATOR" else "system")).strip()

    event_id = f"evt_{uuid.uuid4().hex[:10]}"
    timestamp = datetime.now(timezone.utc).isoformat()
    new_version = current_version + 1

    event = {
        "event_id": event_id,
        "payment_id": clean_pid,
        "from_state": current_state.value,
        "to_state": normalized_next.value,
        "state_version": new_version,
        "reason": clean_reason,
        "actor_type": clean_actor_type,
        "actor_id": clean_actor_id,
        "source": clean_source,
        "timestamp": timestamp,
        "transition_status": "SUCCESS"
    }

    with _state_lock:
        _runtime_payment_state_store[clean_pid] = normalized_next
        _payment_version_store[clean_pid] = new_version
        if not _payment_transition_events_store and os.path.exists(TRANSITION_EVENTS_STORE_PATH):
            _payment_transition_events_store.update(_load_persisted_events())
        if clean_pid not in _payment_transition_events_store:
            _payment_transition_events_store[clean_pid] = []
        _payment_transition_events_store[clean_pid].append(event)
        _save_persisted_events(_payment_transition_events_store)

    # Safe correlation to Unified Recovery Audit Trail (Topic 2.2.2.14)
    try:
        from src.recovery_audit import record_recovery_audit_event, AuditEventType
        record_recovery_audit_event(
            payment_id=clean_pid,
            event_type=AuditEventType.PAYMENT_STATE_TRANSITION.value,
            actor_type=clean_actor_type,
            source=clean_source,
            status="SUCCESS",
            reason=f"{current_state.value} -> {normalized_next.value}: {clean_reason}",
            correlation_id=event_id,
            metadata={"state_version": new_version}
        )
    except Exception:
        pass

    return {
        "success": True,
        "event_id": event_id,
        "payment_id": clean_pid,
        "previous_state": current_state.value,
        "new_state": normalized_next.value,
        "from_state": current_state.value,
        "to_state": normalized_next.value,
        "state_version": new_version,
        "reason": clean_reason,
        "actor_type": clean_actor_type,
        "actor_id": clean_actor_id,
        "source": clean_source,
        "timestamp": timestamp,
        "transition_status": "SUCCESS",
        "message": "Payment state transitioned successfully."
    }




