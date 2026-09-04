"""
RecoverIQ - Test Suite for Circuit Breaker Request Blocking / Fast-Fail (Topic 2.2.2.3)
Verifies:
  TEST 1: CLOSED circuit allows request.
  TEST 2: OPEN circuit blocks request.
  TEST 3: OPEN circuit returns CIRCUIT_OPEN.
  TEST 4: OPEN circuit produces HTTP 503 at the API layer.
  TEST 5: Merchant HTTP request function is NOT called when OPEN.
  TEST 6: CLOSED circuit reaches merchant request path.
  TEST 7: HALF_OPEN does not trigger automatic probing in this topic.
  TEST 8: Blocked request does not modify payment state.
  TEST 9: Blocked request does not create duplicate execution.
  TEST 10: Blocked request does not create a payment transition event.
  TEST 11: Blocked telemetry contains no secrets or credentials.
  TEST 12: Concurrent requests against OPEN are all blocked.
  TEST 13: Circuit state remains OPEN after blocked requests.
  TEST 14: Existing Topic 2.2.2.2 threshold/tripping behavior remains intact.
"""

import sys
import os
import json
import urllib.request
import urllib.error
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.circuit_breaker import (
    CircuitState,
    record_circuit_observation,
    check_circuit_request_allowed,
    execute_merchant_request_with_circuit_breaker,
    get_circuit_breaker_status,
    get_blocked_requests_telemetry,
    reset_circuit_breaker_state,
    transition_circuit_state
)
from src.api_bridge import dispatch_merchant_request_endpoint, MerchantDispatchRequest
from src.state_machine import (
    get_current_payment_state,
    get_payment_transition_events,
    set_payment_state_directly,
    PaymentState
)

BASE_URL = "http://127.0.0.1:8000"


def make_api_post(path: str, payload: dict):
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

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
    print("TOPIC 2.2.2.3 — CIRCUIT BREAKER REQUEST BLOCKING TESTS")
    print("==================================================")

    reset_circuit_breaker_state()

    # TEST 1 & 6: CLOSED circuit allows request and calls network function
    print("\n[TEST 1 & 6] CLOSED circuit allows request")
    mock_network_call = MagicMock(return_value={"status": "order_synced", "order_id": "ORD_001"})
    res_closed = execute_merchant_request_with_circuit_breaker(
        merchant_id="m_closed",
        endpoint="payment-webhook",
        request_fn=mock_network_call,
        payment_id="pay_001"
    )
    assert res_closed["success"] is True
    assert res_closed["fast_failed"] is False
    assert mock_network_call.call_count == 1
    print("  ✓ TEST 1 & 6: CLOSED circuit allowed request and executed network function")

    # Trip the circuit for m_trip
    print("\nTripping circuit for merchant 'm_trip' (5 consecutive TIMEOUT failures)...")
    for _ in range(5):
        record_circuit_observation("m_trip", "payment-webhook", failure_category="TIMEOUT", failure_threshold=5)

    st_trip = get_circuit_breaker_status("m_trip", "payment-webhook")
    assert st_trip["state"] == "OPEN"

    # TEST 2, 3, 5: OPEN circuit blocks request and does NOT call network function
    print("\n[TEST 2, 3, 5] OPEN circuit fast-fail blocking")
    mock_network_call_blocked = MagicMock()
    res_open = execute_merchant_request_with_circuit_breaker(
        merchant_id="m_trip",
        endpoint="payment-webhook",
        request_fn=mock_network_call_blocked,
        payment_id="pay_005"
    )
    assert res_open["success"] is False
    assert res_open["fast_failed"] is True
    assert res_open["error"] == "CIRCUIT_OPEN"
    assert res_open["blocked"] is True
    assert mock_network_call_blocked.call_count == 0  # Network function NEVER called
    print("  ✓ TEST 2, 3, 5: OPEN circuit blocked request before execution (0 network calls made)")

    # TEST 4: HTTP 503 at API layer (direct dispatch endpoint check & HTTP request)
    print("\n[TEST 4] API HTTP 503 response on OPEN circuit")
    try:
        dispatch_merchant_request_endpoint(MerchantDispatchRequest(
            merchant_id="m_trip",
            endpoint="payment-webhook",
            payment_id="pay_005"
        ))
        assert False, "Expected HTTPException 503"
    except HTTPException as exc:
        assert exc.status_code == 503
        assert exc.detail["error"] == "CIRCUIT_OPEN"
        assert exc.detail["circuit_state"] == "OPEN"

    # Also test via HTTP server endpoint
    for _ in range(5):
        make_api_post("/api/circuit-breakers/observe", {
            "merchant_id": "m_http_trip",
            "endpoint": "payment-webhook",
            "failure_category": "TIMEOUT",
            "failure_threshold": 5
        })

    http_status_open, body_open = make_api_post("/api/merchant/dispatch", {
        "merchant_id": "m_http_trip",
        "endpoint": "payment-webhook",
        "payment_id": "pay_005"
    })
    assert http_status_open == 503
    detail_open = body_open.get("detail", body_open)
    assert detail_open["error"] == "CIRCUIT_OPEN"
    print("  ✓ TEST 4: API returned HTTP 503 Service Unavailable with CIRCUIT_OPEN")

    # TEST 7: HALF_OPEN does not trigger automatic probing
    print("\n[TEST 7] HALF_OPEN fail-safe blocking")
    reset_circuit_breaker_state()
    # Transition manually to HALF_OPEN
    for _ in range(5):
        record_circuit_observation("m_half", "hook", failure_category="TIMEOUT", failure_threshold=5)
    transition_circuit_state("m_half", "hook", reason="Cooldown elapsed")  # OPEN -> HALF_OPEN
    
    st_half = get_circuit_breaker_status("m_half", "hook")
    # Gate check
    mock_half_call = MagicMock()
    res_half = execute_merchant_request_with_circuit_breaker(
        merchant_id="m_half",
        endpoint="hook",
        request_fn=mock_half_call
    )
    assert res_half["allowed"] is False
    assert mock_half_call.call_count == 0
    print("  ✓ TEST 7: HALF_OPEN conservatively blocked without automatic probing")

    # TEST 8, 9, 10: Blocked request does not mutate payment state or create events
    print("\n[TEST 8, 9, 10] Payment state isolation & event integrity")
    # Ensure m_trip is in OPEN state
    for _ in range(5):
        record_circuit_observation("m_trip", "payment-webhook", failure_category="TIMEOUT", failure_threshold=5)

    set_payment_state_directly("pay_005", PaymentState.HUMAN_REVIEW)
    initial_state = get_current_payment_state("pay_005")
    initial_events_count = len(get_payment_transition_events("pay_005"))

    # Blocked request
    check_circuit_request_allowed("m_trip", "payment-webhook", payment_id="pay_005")

    # Verify payment state is completely unchanged
    assert get_current_payment_state("pay_005") == initial_state
    assert len(get_payment_transition_events("pay_005")) == initial_events_count
    print("  ✓ TEST 8, 9, 10: Payment state and transition events remained untouched")

    # TEST 11: Blocked telemetry contains no secrets or credentials
    print("\n[TEST 11] Telemetry privacy verification")
    blocked_telemetry = get_blocked_requests_telemetry("m_trip")
    assert len(blocked_telemetry) >= 1
    sample_tel = blocked_telemetry[-1]
    assert sample_tel["event_type"] == "REQUEST_BLOCKED"
    assert sample_tel["reason"] == "CIRCUIT_OPEN"
    serialized_tel = json.dumps(sample_tel)
    assert "secret" not in serialized_tel.lower()
    assert "token" not in serialized_tel.lower()
    assert "authorization" not in serialized_tel.lower()
    print("  ✓ TEST 11: Blocked telemetry verified free of credentials")

    # TEST 12: Concurrent requests against OPEN are all blocked
    print("\n[TEST 12] Concurrency test on OPEN circuit (30 parallel requests)")
    def _attempt_req(i):
        return check_circuit_request_allowed("m_trip", "payment-webhook", payment_id=f"pay_{i}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(_attempt_req, range(30)))

    assert all(r["allowed"] is False for r in results)
    assert all(r["error"] == "CIRCUIT_OPEN" for r in results)
    print("  ✓ TEST 12: All 30 concurrent requests were blocked by the OPEN circuit")

    # TEST 13: Circuit state remains OPEN after blocked requests
    print("\n[TEST 13] OPEN state stability")
    assert get_circuit_breaker_status("m_trip", "payment-webhook")["state"] == "OPEN"
    print("  ✓ TEST 13: Circuit state remained consistently OPEN")

    # TEST 14: Existing Topic 2.2.2.2 threshold/tripping behavior remains intact
    print("\n[TEST 14] Topic 2.2.2.2 regression check")
    reset_circuit_breaker_state()
    for _ in range(4):
        record_circuit_observation("m_regress", "hook", failure_category="TIMEOUT", failure_threshold=5)
    assert check_circuit_request_allowed("m_regress", "hook")["allowed"] is True
    # 5th failure trips it
    record_circuit_observation("m_regress", "hook", failure_category="TIMEOUT", failure_threshold=5)
    assert check_circuit_request_allowed("m_regress", "hook")["allowed"] is False
    print("  ✓ TEST 14: Threshold tripping mechanism confirmed functional")

    print("\n==================================================")
    print("ALL TOPIC 2.2.2.3 REQUEST BLOCKING TESTS PASSED!")
    print("==================================================")


def test_all_circuit_breaker_request_blocking_scenarios():
    run_tests()


if __name__ == "__main__":
    run_tests()
