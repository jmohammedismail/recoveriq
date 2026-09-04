"""
RecoverIQ - Test Suite for Topic 1.5.3 Backend Payment State Enforcement
Tests:
  1. Valid: HUMAN_REVIEW -> RECOVERING
  2. Valid: RECOVERING -> RECOVERED
  3. Valid: RECOVERED -> REFUNDED
  4. Valid: SUCCESS -> REFUNDED
  5. Invalid: HUMAN_REVIEW -> RECOVERED (rejected with 409)
  6. Invalid: SUCCESS -> RECOVERING (rejected with 409)
  7. Invalid: RECOVERED -> RECOVERING (rejected with 409)
  8. Invalid: REFUNDED -> PROCESSING (rejected with 409)
  9. Invalid: STOPPED -> RECOVERING (rejected with 409)
  10. Unknown payment -> 404
  11. Invalid state value -> 422
  12. State remains unchanged after rejected transition
"""

import sys
import os
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.state_machine import (
    PaymentState,
    transition_payment_state,
    get_current_payment_state,
    set_payment_state_directly,
    reset_payment_state_store
)

BASE_URL = "http://127.0.0.1:8000"


def make_request(path, method="GET", payload=None):
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}


def run_tests():
    print("==================================================")
    print("TOPIC 1.5.3 STATE TRANSITION ENFORCEMENT TEST SUITE")
    print("==================================================")

    # -------------------------------------------------------------
    # 1. Direct Python Engine Tests
    # -------------------------------------------------------------
    print("\n[PART A] Direct Engine Enforcement Tests")
    reset_payment_state_store()

    # 1. Valid: HUMAN_REVIEW -> RECOVERING
    set_payment_state_directly("pay_test_01", PaymentState.HUMAN_REVIEW)
    res = transition_payment_state("pay_test_01", PaymentState.RECOVERING, reason="Operator approved recovery")
    assert res["success"] is True
    assert res["previous_state"] == "HUMAN_REVIEW"
    assert res["new_state"] == "RECOVERING"
    print("  ✓ 1. HUMAN_REVIEW -> RECOVERING: SUCCESS")

    # 2. Valid: RECOVERING -> RECOVERED
    res = transition_payment_state("pay_test_01", PaymentState.RECOVERED, reason="Recovery verified in DB")
    assert res["success"] is True
    assert res["previous_state"] == "RECOVERING"
    assert res["new_state"] == "RECOVERED"
    print("  ✓ 2. RECOVERING -> RECOVERED: SUCCESS")

    # 3. Valid: RECOVERED -> REFUNDED
    res = transition_payment_state("pay_test_01", PaymentState.REFUNDED, reason="Customer requested refund")
    assert res["success"] is True
    assert res["previous_state"] == "RECOVERED"
    assert res["new_state"] == "REFUNDED"
    print("  ✓ 3. RECOVERED -> REFUNDED: SUCCESS")

    # 4. Valid: SUCCESS -> REFUNDED
    set_payment_state_directly("pay_test_02", PaymentState.SUCCESS)
    res = transition_payment_state("pay_test_02", PaymentState.REFUNDED, reason="Merchant initiated refund")
    assert res["success"] is True
    assert res["previous_state"] == "SUCCESS"
    assert res["new_state"] == "REFUNDED"
    print("  ✓ 4. SUCCESS -> REFUNDED: SUCCESS")

    # 5. Invalid: HUMAN_REVIEW -> RECOVERED (illegal direct jump)
    set_payment_state_directly("pay_test_03", PaymentState.HUMAN_REVIEW)
    res = transition_payment_state("pay_test_03", PaymentState.RECOVERED, reason="Attempted direct jump")
    assert res["success"] is False
    assert res["error"] == "INVALID_STATE_TRANSITION"
    assert "RECOVERING" in res["allowed_transitions"]
    assert get_current_payment_state("pay_test_03") == PaymentState.HUMAN_REVIEW
    print("  ✓ 5. HUMAN_REVIEW -> RECOVERED: REJECTED (state unchanged)")

    # 6. Invalid: SUCCESS -> RECOVERING
    set_payment_state_directly("pay_test_04", PaymentState.SUCCESS)
    res = transition_payment_state("pay_test_04", PaymentState.RECOVERING)
    assert res["success"] is False
    assert get_current_payment_state("pay_test_04") == PaymentState.SUCCESS
    print("  ✓ 6. SUCCESS -> RECOVERING: REJECTED (state unchanged)")

    # 7. Invalid: RECOVERED -> RECOVERING
    set_payment_state_directly("pay_test_05", PaymentState.RECOVERED)
    res = transition_payment_state("pay_test_05", PaymentState.RECOVERING)
    assert res["success"] is False
    assert get_current_payment_state("pay_test_05") == PaymentState.RECOVERED
    print("  ✓ 7. RECOVERED -> RECOVERING: REJECTED (state unchanged)")

    # 8. Invalid: REFUNDED -> PROCESSING
    set_payment_state_directly("pay_test_06", PaymentState.REFUNDED)
    res = transition_payment_state("pay_test_06", PaymentState.PROCESSING)
    assert res["success"] is False
    assert get_current_payment_state("pay_test_06") == PaymentState.REFUNDED
    print("  ✓ 8. REFUNDED -> PROCESSING: REJECTED (state unchanged)")

    # 9. Invalid: STOPPED -> RECOVERING
    set_payment_state_directly("pay_test_07", PaymentState.STOPPED)
    res = transition_payment_state("pay_test_07", PaymentState.RECOVERING)
    assert res["success"] is False
    assert get_current_payment_state("pay_test_07") == PaymentState.STOPPED
    print("  ✓ 9. STOPPED -> RECOVERING: REJECTED (state unchanged)")

    # -------------------------------------------------------------
    # 2. HTTP Endpoint Tests (POST /payments/{id}/state-transition)
    # -------------------------------------------------------------
    print("\n[PART B] HTTP API Endpoint Tests")

    # Set pay_005 initial state to HUMAN_REVIEW
    set_payment_state_directly("pay_005", PaymentState.HUMAN_REVIEW)

    # 1. Valid API transition: HUMAN_REVIEW -> RECOVERING
    status, body = make_request("/payments/pay_005/state-transition", method="POST", payload={
        "next_state": "RECOVERING",
        "reason": "Operator approved AI-recommended webhook replay"
    })
    print(f"  Valid API transition status: {status}, body: {body}")
    assert status == 200, f"Expected 200, got {status}"
    assert body["success"] is True
    assert body["previous_state"] == "HUMAN_REVIEW"
    assert body["new_state"] == "RECOVERING"
    print("  ✓ HTTP Valid transition passed")

    # 5. Invalid API transition: RECOVERING -> REFUNDED (must recover first)
    status, body = make_request("/payments/pay_005/state-transition", method="POST", payload={
        "next_state": "REFUNDED",
        "reason": "Premature refund attempt"
    })
    print(f"  Invalid API transition status: {status}, error: {body.get('detail', body)}")
    assert status == 409, f"Expected 409 Conflict, got {status}"
    print("  ✓ HTTP 409 Conflict returned for illegal transition")

    # 10. Unknown payment -> 404
    status, body = make_request("/payments/pay_999/state-transition", method="POST", payload={
        "next_state": "RECOVERING"
    })
    print(f"  Unknown payment status: {status}")
    assert status == 404, f"Expected 404, got {status}"
    print("  ✓ HTTP 404 returned for unknown payment")

    # 11. Invalid state value -> 422
    status, body = make_request("/payments/pay_005/state-transition", method="POST", payload={
        "next_state": "MAGIC_UNREAL_STATE"
    })
    print(f"  Invalid state value status: {status}")
    assert status == 422, f"Expected 422, got {status}"
    print("  ✓ HTTP 422 returned for invalid state string")

    # 12. Verify state remains RECOVERING
    assert get_current_payment_state("pay_005") == PaymentState.RECOVERING
    print("  ✓ State verified unchanged after rejected transitions")

    print("\n==================================================")
    print("ALL TOPIC 1.5.3 ENFORCEMENT TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
