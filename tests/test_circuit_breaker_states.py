"""
RecoverIQ - Test Suite for Circuit Breaker State Definitions & Transition Rules (Topic 2.2.2.1)
Verifies:
  1. Authoritative circuit states (CLOSED, OPEN, HALF_OPEN)
  2. Valid transitions (CLOSED -> OPEN, OPEN -> HALF_OPEN, HALF_OPEN -> CLOSED, HALF_OPEN -> OPEN)
  3. Invalid transitions rejected (OPEN -> CLOSED, CLOSED -> HALF_OPEN, self-transitions, invalid states)
  4. State normalization with aliases and formatting
  5. Mandatory transition reasons requirement
  6. Transition metadata structure
  7. Failure category classifications
  8. Configuration defaults and constants
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.circuit_breaker import (
    CircuitState,
    CIRCUIT_STATES,
    VALID_CIRCUIT_TRANSITIONS,
    CIRCUIT_BREAKER_FAILURES,
    CIRCUIT_BREAKER_CONFIG,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_COOLDOWN_DURATION_SEC,
    DEFAULT_HALF_OPEN_PROBE_LIMIT,
    normalize_circuit_state,
    is_valid_circuit_transition,
    get_allowed_circuit_transitions,
    is_circuit_breaker_failure,
    transition_circuit_state
)


def test_circuit_states_exist():
    """Verify that all 3 authoritative circuit states exist and have metadata."""
    assert CircuitState.CLOSED.value == "CLOSED"
    assert CircuitState.OPEN.value == "OPEN"
    assert CircuitState.HALF_OPEN.value == "HALF_OPEN"
    assert len(CircuitState) == 3

    for state in CircuitState:
        assert state in CIRCUIT_STATES
        assert "machine_value" in CIRCUIT_STATES[state]
        assert "label" in CIRCUIT_STATES[state]
        assert "description" in CIRCUIT_STATES[state]


def test_valid_transitions():
    """Verify all 4 legally allowed circuit transitions pass."""
    # 1. CLOSED -> OPEN
    assert is_valid_circuit_transition(CircuitState.CLOSED, CircuitState.OPEN) is True
    res1 = transition_circuit_state(CircuitState.CLOSED, CircuitState.OPEN, reason="Consecutive timeout threshold exceeded")
    assert res1["success"] is True
    assert res1["from_state"] == "CLOSED"
    assert res1["to_state"] == "OPEN"
    assert res1["transition_status"] == "SUCCESS"

    # 2. OPEN -> HALF_OPEN
    assert is_valid_circuit_transition(CircuitState.OPEN, CircuitState.HALF_OPEN) is True
    res2 = transition_circuit_state(CircuitState.OPEN, CircuitState.HALF_OPEN, reason="Cooldown period elapsed, probing endpoint")
    assert res2["success"] is True
    assert res2["from_state"] == "OPEN"
    assert res2["to_state"] == "HALF_OPEN"

    # 3. HALF_OPEN -> CLOSED
    assert is_valid_circuit_transition(CircuitState.HALF_OPEN, CircuitState.CLOSED) is True
    res3 = transition_circuit_state(CircuitState.HALF_OPEN, CircuitState.CLOSED, reason="Probing succeeded, recovery verified")
    assert res3["success"] is True
    assert res3["from_state"] == "HALF_OPEN"
    assert res3["to_state"] == "CLOSED"

    # 4. HALF_OPEN -> OPEN
    assert is_valid_circuit_transition(CircuitState.HALF_OPEN, CircuitState.OPEN) is True
    res4 = transition_circuit_state(CircuitState.HALF_OPEN, CircuitState.OPEN, reason="Probe failed, reopening circuit")
    assert res4["success"] is True
    assert res4["from_state"] == "HALF_OPEN"
    assert res4["to_state"] == "OPEN"


def test_invalid_transitions():
    """Verify invalid transitions are rejected without state mutation."""
    # OPEN -> CLOSED is illegal
    assert is_valid_circuit_transition(CircuitState.OPEN, CircuitState.CLOSED) is False
    res_oc = transition_circuit_state(CircuitState.OPEN, CircuitState.CLOSED, reason="Attempting direct close without probing")
    assert res_oc["success"] is False
    assert res_oc["error"] == "INVALID_CIRCUIT_TRANSITION"
    assert res_oc["transition_status"] == "REJECTED"

    # CLOSED -> HALF_OPEN is illegal
    assert is_valid_circuit_transition(CircuitState.CLOSED, CircuitState.HALF_OPEN) is False
    res_ch = transition_circuit_state(CircuitState.CLOSED, CircuitState.HALF_OPEN, reason="Illegal skip")
    assert res_ch["success"] is False
    assert res_ch["error"] == "INVALID_CIRCUIT_TRANSITION"

    # Self-transitions are illegal
    assert is_valid_circuit_transition(CircuitState.CLOSED, CircuitState.CLOSED) is False
    assert is_valid_circuit_transition(CircuitState.OPEN, CircuitState.OPEN) is False
    assert is_valid_circuit_transition(CircuitState.HALF_OPEN, CircuitState.HALF_OPEN) is False

    for st in CircuitState:
        res_self = transition_circuit_state(st, st, reason="Self transition")
        assert res_self["success"] is False
        assert res_self["error"] == "INVALID_CIRCUIT_TRANSITION"


def test_get_allowed_circuit_transitions():
    """Verify get_allowed_circuit_transitions returns exact subsets."""
    assert get_allowed_circuit_transitions(CircuitState.CLOSED) == [CircuitState.OPEN]
    assert get_allowed_circuit_transitions(CircuitState.OPEN) == [CircuitState.HALF_OPEN]
    assert sorted([s.value for s in get_allowed_circuit_transitions(CircuitState.HALF_OPEN)]) == ["CLOSED", "OPEN"]


def test_normalize_circuit_state():
    """Verify normalization of strings, aliases, casing, and hyphens."""
    assert normalize_circuit_state("closed") == CircuitState.CLOSED
    assert normalize_circuit_state("OPEN") == CircuitState.OPEN
    assert normalize_circuit_state("half_open") == CircuitState.HALF_OPEN
    assert normalize_circuit_state("half-open") == CircuitState.HALF_OPEN
    assert normalize_circuit_state("HALFOPEN") == CircuitState.HALF_OPEN
    assert normalize_circuit_state("TRIPPED") == CircuitState.OPEN
    assert normalize_circuit_state("PROBING") == CircuitState.HALF_OPEN
    assert normalize_circuit_state(CircuitState.CLOSED) == CircuitState.CLOSED

    # Invalid values raise ValueError
    with pytest.raises(ValueError):
        normalize_circuit_state("UNKNOWN_STATE")
    with pytest.raises(ValueError):
        normalize_circuit_state("")
    with pytest.raises(ValueError):
        normalize_circuit_state(None)


def test_transition_reason_required():
    """Verify that a non-empty reason is strictly required."""
    res_blank = transition_circuit_state(CircuitState.CLOSED, CircuitState.OPEN, reason="")
    assert res_blank["success"] is False
    assert res_blank["error"] == "TRANSITION_REASON_REQUIRED"

    res_none = transition_circuit_state(CircuitState.CLOSED, CircuitState.OPEN, reason=None)
    assert res_none["success"] is False
    assert res_none["error"] == "TRANSITION_REASON_REQUIRED"

    res_spaces = transition_circuit_state(CircuitState.CLOSED, CircuitState.OPEN, reason="   ")
    assert res_spaces["success"] is False
    assert res_spaces["error"] == "TRANSITION_REASON_REQUIRED"


def test_failure_categories():
    """Verify circuit breaker failure classifications."""
    assert is_circuit_breaker_failure("TIMEOUT") is True
    assert is_circuit_breaker_failure("SERVER_ERROR") is True
    assert is_circuit_breaker_failure("RATE_LIMITED") is True
    assert is_circuit_breaker_failure("NETWORK_ERROR") is True

    assert is_circuit_breaker_failure("SUCCESS") is False
    assert is_circuit_breaker_failure("CLIENT_ERROR") is False
    assert is_circuit_breaker_failure("REDIRECT") is False
    assert is_circuit_breaker_failure(None) is False


def test_configuration_constants():
    """Verify configuration parameters and defaults."""
    assert DEFAULT_FAILURE_THRESHOLD == 5
    assert DEFAULT_COOLDOWN_DURATION_SEC == 30.0
    assert DEFAULT_HALF_OPEN_PROBE_LIMIT == 3

    assert CIRCUIT_BREAKER_CONFIG["failure_threshold"] == 5
    assert CIRCUIT_BREAKER_CONFIG["cooldown_duration_sec"] == 30.0
    assert CIRCUIT_BREAKER_CONFIG["half_open_probe_limit"] == 3


if __name__ == "__main__":
    print("Running Topic 2.2.2.1 Circuit Breaker State Tests directly...")
    test_circuit_states_exist()
    test_valid_transitions()
    test_invalid_transitions()
    test_get_allowed_circuit_transitions()
    test_normalize_circuit_state()
    test_transition_reason_required()
    test_failure_categories()
    test_configuration_constants()
    print("All Topic 2.2.2.1 tests passed successfully!")
