"""
RecoverIQ - Test Suite for Topic 1.5.2 Valid Payment State Transitions
Tests:
  - Valid state transitions mapping and is_valid_transition()
  - Invalid state transition rejection
  - Terminal state validation (REFUNDED, STOPPED return empty allowed lists)
  - Allowed transitions retrieval via get_allowed_transitions()
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.state_machine import (
    PaymentState,
    is_valid_transition,
    get_allowed_transitions,
    VALID_STATE_TRANSITIONS,
    StateTransitionIntent
)


def run_transition_tests():
    print("==================================================")
    print("TOPIC 1.5.2 PAYMENT STATE TRANSITIONS TEST SUITE")
    print("==================================================")

    # -------------------------------------------------------------
    # 1. VALID TRANSITIONS TEST
    # -------------------------------------------------------------
    print("\n[1] Testing All Legally Allowed Transitions")
    valid_cases = [
        (PaymentState.CREATED, PaymentState.PROCESSING),
        (PaymentState.PROCESSING, PaymentState.SUCCESS),
        (PaymentState.PROCESSING, PaymentState.FAILED),
        (PaymentState.PROCESSING, PaymentState.PENDING),
        (PaymentState.PENDING, PaymentState.SUCCESS),
        (PaymentState.PENDING, PaymentState.FAILED),
        (PaymentState.PENDING, PaymentState.HUMAN_REVIEW),
        (PaymentState.FAILED, PaymentState.HUMAN_REVIEW),
        (PaymentState.FAILED, PaymentState.STOPPED),
        (PaymentState.HUMAN_REVIEW, PaymentState.RECOVERING),
        (PaymentState.HUMAN_REVIEW, PaymentState.ESCALATED),
        (PaymentState.HUMAN_REVIEW, PaymentState.STOPPED),
        (PaymentState.RECOVERING, PaymentState.RECOVERED),
        (PaymentState.RECOVERING, PaymentState.RECOVERY_FAILED),
        (PaymentState.RECOVERING, PaymentState.ESCALATED),
        (PaymentState.RECOVERY_FAILED, PaymentState.HUMAN_REVIEW),
        (PaymentState.RECOVERY_FAILED, PaymentState.ESCALATED),
        (PaymentState.RECOVERY_FAILED, PaymentState.STOPPED),
        (PaymentState.ESCALATED, PaymentState.HUMAN_REVIEW),
        (PaymentState.ESCALATED, PaymentState.STOPPED),
        (PaymentState.SUCCESS, PaymentState.REFUNDED),
        (PaymentState.RECOVERED, PaymentState.REFUNDED),
    ]

    for curr, nxt in valid_cases:
        res = is_valid_transition(curr, nxt)
        assert res is True, f"Expected {curr.value} -> {nxt.value} to be VALID"
        print(f"  ✓ Valid: {curr.value:<16} -> {nxt.value}")

    print(f"  ✓ All {len(valid_cases)} valid transitions confirmed.")

    # -------------------------------------------------------------
    # 2. INVALID TRANSITIONS TEST
    # -------------------------------------------------------------
    print("\n[2] Testing Illegal / Invalid Transition Rejection")
    invalid_cases = [
        (PaymentState.RECOVERED, PaymentState.RECOVERING),
        (PaymentState.SUCCESS, PaymentState.RECOVERING),
        (PaymentState.REFUNDED, PaymentState.PROCESSING),
        (PaymentState.STOPPED, PaymentState.RECOVERING),
        (PaymentState.FAILED, PaymentState.RECOVERED),
        (PaymentState.HUMAN_REVIEW, PaymentState.RECOVERED),
        (PaymentState.RECOVERING, PaymentState.REFUNDED),
        (PaymentState.CREATED, PaymentState.SUCCESS),
        (PaymentState.REFUNDED, PaymentState.HUMAN_REVIEW),
        (PaymentState.STOPPED, PaymentState.PROCESSING),
        (PaymentState.CREATED, PaymentState.RECOVERED),
        (PaymentState.PENDING, PaymentState.RECOVERING),
        (PaymentState.RECOVERED, PaymentState.HUMAN_REVIEW),
    ]

    for curr, nxt in invalid_cases:
        res = is_valid_transition(curr, nxt)
        assert res is False, f"Expected {curr.value} -> {nxt.value} to be REJECTED"
        print(f"  ✓ Rejected: {curr.value:<16} -X-> {nxt.value}")

    print(f"  ✓ All {len(invalid_cases)} invalid transitions properly rejected.")

    # -------------------------------------------------------------
    # 3. TERMINAL AND NON-TERMINAL ALLOWED TRANSITIONS RETRIEVAL
    # -------------------------------------------------------------
    print("\n[3] Testing get_allowed_transitions() API")

    # Terminal states
    assert get_allowed_transitions(PaymentState.REFUNDED) == []
    assert get_allowed_transitions(PaymentState.STOPPED) == []
    print("  ✓ Terminal states (REFUNDED, STOPPED) return empty allowed list")

    # Non-terminal states
    hr_transitions = get_allowed_transitions(PaymentState.HUMAN_REVIEW)
    expected_hr = [PaymentState.RECOVERING, PaymentState.ESCALATED, PaymentState.STOPPED]
    assert set(hr_transitions) == set(expected_hr), f"Expected {expected_hr}, got {hr_transitions}"
    print(f"  ✓ HUMAN_REVIEW allowed transitions: {[s.value for s in hr_transitions]}")

    rec_transitions = get_allowed_transitions(PaymentState.RECOVERING)
    expected_rec = [PaymentState.RECOVERED, PaymentState.RECOVERY_FAILED, PaymentState.ESCALATED]
    assert set(rec_transitions) == set(expected_rec), f"Expected {expected_rec}, got {rec_transitions}"
    print(f"  ✓ RECOVERING allowed transitions: {[s.value for s in rec_transitions]}")

    # Success and Recovered refund transitions
    succ_transitions = get_allowed_transitions(PaymentState.SUCCESS)
    assert succ_transitions == [PaymentState.REFUNDED]
    recov_transitions = get_allowed_transitions(PaymentState.RECOVERED)
    assert recov_transitions == [PaymentState.REFUNDED]
    print("  ✓ SUCCESS and RECOVERED allow transition to REFUNDED")

    # -------------------------------------------------------------
    # 4. StateTransitionIntent Architecture Contract
    # -------------------------------------------------------------
    print("\n[4] Testing StateTransitionIntent contract")
    intent_valid = StateTransitionIntent(
        payment_id="pay_005",
        current_state=PaymentState.HUMAN_REVIEW,
        next_state=PaymentState.RECOVERING,
        reason="Operator approved auto recovery workflow",
        operator_id="demo-operator"
    )
    assert intent_valid.is_valid() is True
    intent_dict = intent_valid.to_dict()
    assert intent_dict["payment_id"] == "pay_005"
    assert intent_dict["current_state"] == "HUMAN_REVIEW"
    assert intent_dict["next_state"] == "RECOVERING"

    intent_invalid = StateTransitionIntent(
        payment_id="pay_005",
        current_state=PaymentState.HUMAN_REVIEW,
        next_state=PaymentState.RECOVERED,
        reason="Invalid direct jump to recovered"
    )
    assert intent_invalid.is_valid() is False
    print("  ✓ StateTransitionIntent validation contract verified")

    print("\n==================================================")
    print("ALL TOPIC 1.5.2 STATE TRANSITION TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_transition_tests()
