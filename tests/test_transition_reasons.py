"""
RecoverIQ - Test Suite for Topic 1.5.4 Explicit Payment State Transition Reasons
Tests:
  1. Valid transition with reason -> SUCCESS
  2. Missing reason -> 400 -> state unchanged
  3. Empty/whitespace reason -> 400 -> state unchanged
  4. Valid OPERATOR metadata -> stored correctly
  5. Valid AI_AGENT metadata -> stored correctly
  6. Valid SYSTEM metadata -> stored correctly
  7. Valid GATEWAY metadata -> stored correctly
  8. Correct source stored
  9. Invalid transition -> state unchanged
  10. Duplicate idempotent request -> no duplicate transition event
  11. Complete transition event fields inspection
"""

import sys
import os
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.state_machine import (
    PaymentState,
    ActorType,
    TransitionSource,
    transition_payment_state,
    get_current_payment_state,
    get_payment_transition_events,
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
    print("TOPIC 1.5.4 TRANSITION REASONS TEST SUITE")
    print("==================================================")

    reset_payment_state_store()

    # -------------------------------------------------------------
    # 1. Valid transition with explicit reason
    # -------------------------------------------------------------
    print("\n[TEST 1] Valid transition with explicit reason")
    set_payment_state_directly("pay_r_01", PaymentState.HUMAN_REVIEW)
    res1 = transition_payment_state(
        payment_id="pay_r_01",
        next_state=PaymentState.RECOVERING,
        reason="Operator approved AI-recommended webhook replay",
        actor_type=ActorType.OPERATOR,
        actor_id="demo-operator",
        source=TransitionSource.HUMAN_ACTION_CENTER
    )
    assert res1["success"] is True
    assert res1["from_state"] == "HUMAN_REVIEW"
    assert res1["to_state"] == "RECOVERING"
    assert res1["reason"] == "Operator approved AI-recommended webhook replay"
    print("  ✓ TEST 1 PASSED: State transitioned with explicit reason")

    # -------------------------------------------------------------
    # 2 & 3. Missing or whitespace reason rejection
    # -------------------------------------------------------------
    print("\n[TEST 2 & 3] Missing / whitespace reason rejection")
    set_payment_state_directly("pay_r_02", PaymentState.HUMAN_REVIEW)
    
    # None reason
    res_none = transition_payment_state("pay_r_02", PaymentState.RECOVERING, reason=None)
    assert res_none["success"] is False
    assert res_none["error"] == "TRANSITION_REASON_REQUIRED"
    assert get_current_payment_state("pay_r_02") == PaymentState.HUMAN_REVIEW

    # Empty whitespace reason
    res_empty = transition_payment_state("pay_r_02", PaymentState.RECOVERING, reason="   ")
    assert res_empty["success"] is False
    assert res_empty["error"] == "TRANSITION_REASON_REQUIRED"
    assert get_current_payment_state("pay_r_02") == PaymentState.HUMAN_REVIEW
    print("  ✓ TEST 2 & 3 PASSED: Empty reason rejected, state preserved")

    # -------------------------------------------------------------
    # 4, 5, 6, 7. Different Actor Types & Sources
    # -------------------------------------------------------------
    print("\n[TEST 4-8] Actor Types & Sources Recording")

    # 4. OPERATOR
    set_payment_state_directly("pay_r_03", PaymentState.HUMAN_REVIEW)
    res_op = transition_payment_state(
        "pay_r_03", PaymentState.ESCALATED,
        reason="Operator escalated to Merchant Engineering on-call",
        actor_type=ActorType.OPERATOR, actor_id="operator_sarah",
        source=TransitionSource.HUMAN_ACTION_CENTER
    )
    assert res_op["actor_type"] == "OPERATOR"
    assert res_op["actor_id"] == "operator_sarah"
    assert res_op["source"] == "HUMAN_ACTION_CENTER"

    # 5. AI_AGENT
    set_payment_state_directly("pay_r_04", PaymentState.PENDING)
    res_ai = transition_payment_state(
        "pay_r_04", PaymentState.HUMAN_REVIEW,
        reason="AI Agent detected confidence < 85% with 2 consumed retries",
        actor_type=ActorType.AI_AGENT, actor_id="recoveriq_agent_v2",
        source=TransitionSource.RECOVERY_ENGINE
    )
    assert res_ai["actor_type"] == "AI_AGENT"
    assert res_ai["source"] == "RECOVERY_ENGINE"

    # 6. SYSTEM
    set_payment_state_directly("pay_r_05", PaymentState.CREATED)
    res_sys = transition_payment_state(
        "pay_r_05", PaymentState.PROCESSING,
        reason="System batch ingestion started telemetry polling",
        actor_type=ActorType.SYSTEM, actor_id="ingestion_scheduler",
        source=TransitionSource.SYSTEM
    )
    assert res_sys["actor_type"] == "SYSTEM"
    assert res_sys["source"] == "SYSTEM"

    # 7. GATEWAY
    set_payment_state_directly("pay_r_06", PaymentState.PROCESSING)
    res_gw = transition_payment_state(
        "pay_r_06", PaymentState.SUCCESS,
        reason="Gateway webhook delivered capture confirmation",
        actor_type=ActorType.GATEWAY, actor_id="razorpay_webhook_rail",
        source=TransitionSource.WEBHOOK
    )
    assert res_gw["actor_type"] == "GATEWAY"
    assert res_gw["source"] == "WEBHOOK"
    print("  ✓ TEST 4-8 PASSED: OPERATOR, AI_AGENT, SYSTEM, GATEWAY actors & sources recorded accurately")

    # -------------------------------------------------------------
    # 9. Invalid transition preserves state & records rejection
    # -------------------------------------------------------------
    print("\n[TEST 9] Invalid transition diagnostics")
    set_payment_state_directly("pay_r_07", PaymentState.HUMAN_REVIEW)
    res_inv = transition_payment_state(
        "pay_r_07", PaymentState.RECOVERED,
        reason="Attempted premature jump"
    )
    assert res_inv["success"] is False
    assert res_inv["transition_status"] == "REJECTED"
    assert get_current_payment_state("pay_r_07") == PaymentState.HUMAN_REVIEW
    print("  ✓ TEST 9 PASSED: Invalid transition rejected with diagnostic context")

    # -------------------------------------------------------------
    # 10. Duplicate idempotent request does NOT duplicate events
    # -------------------------------------------------------------
    print("\n[TEST 10] Idempotency compatibility check via HTTP")
    set_payment_state_directly("pay_005", PaymentState.HUMAN_REVIEW)

    key = "pay_005_test_evt_key_001"
    status1, body1 = make_request("/payments/pay_005/approve-recovery", method="POST", payload={
        "idempotency_key": key,
        "recovery_strategy": "webhook_replay"
    })
    assert status1 == 200 and body1["duplicate"] is False

    events_after_1 = get_payment_transition_events("pay_005")
    count_1 = len(events_after_1)

    # Re-send same request
    status2, body2 = make_request("/payments/pay_005/approve-recovery", method="POST", payload={
        "idempotency_key": key,
        "recovery_strategy": "webhook_replay"
    })
    assert status2 == 200 and body2["duplicate"] is True

    events_after_2 = get_payment_transition_events("pay_005")
    count_2 = len(events_after_2)

    assert count_1 == count_2, f"Duplicate idempotent call created duplicate events! ({count_1} != {count_2})"
    print(f"  ✓ TEST 10 PASSED: Duplicate request did not add duplicate transition events (count={count_2})")

    # -------------------------------------------------------------
    # 11. Event Schema Field Completeness
    # -------------------------------------------------------------
    print("\n[TEST 11] Event Schema Validation")
    events = get_payment_transition_events("pay_r_01")
    assert len(events) >= 1
    sample = events[0]
    required_fields = [
        "event_id", "payment_id", "from_state", "to_state",
        "reason", "actor_type", "actor_id", "source",
        "timestamp", "transition_status"
    ]
    for field in required_fields:
        assert field in sample, f"Missing required transition event field: {field}"
        assert sample[field] is not None and str(sample[field]).strip() != "", f"Empty field: {field}"

    print("  Event Schema Verified:")
    for k, v in sample.items():
        print(f"    • {k:<18}: {v}")
    print("  ✓ TEST 11 PASSED: Complete event schema confirmed")

    print("\n==================================================")
    print("ALL TOPIC 1.5.4 TRANSITION REASON TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
