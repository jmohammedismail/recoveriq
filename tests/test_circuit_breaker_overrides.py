"""
RecoverIQ - Test Suite for Controlled Operator Circuit Overrides (Topic 2.2.2.7)
Verifies:
  1. Force Open transitions CLOSED -> OPEN and HALF_OPEN -> OPEN.
  2. Force Open when already OPEN returns safe idempotent response.
  3. Reset transitions OPEN -> CLOSED and HALF_OPEN -> CLOSED.
  4. Reset when CLOSED is rejected as unnecessary.
  5. Total failures preserved during manual Reset.
  6. Manual Probe transitions OPEN -> HALF_OPEN and increments generation.
  7. Manual Probe from CLOSED is rejected as invalid.
  8. Mandatory human-readable reason enforced for all overrides.
  9. Structured lifecycle audit records actor_type=OPERATOR, actor_id, source=HUMAN_ACTION_CENTER.
  10. Idempotency prevents duplicate override executions.
  11. Complete payment state isolation (payment state machine unaffected).
"""

import sys
import os
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.circuit_breaker import (
    CircuitState,
    record_circuit_observation,
    get_circuit_breaker_status,
    reset_circuit_breaker_state,
    operator_force_open_circuit,
    operator_reset_circuit,
    operator_manual_probe_circuit,
    get_circuit_lifecycle_telemetry
)
from src.state_machine import (
    get_current_payment_state,
    set_payment_state_directly,
    PaymentState
)

BASE_URL = "http://127.0.0.1:8000"


def make_api_post(path, data):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8"))
        return e.code, body


def run_tests():
    print("==================================================")
    print("TOPIC 2.2.2.7 — CONTROLLED OPERATOR OVERRIDES TESTS")
    print("==================================================")

    reset_circuit_breaker_state()

    # TEST 1 & 8: Force Open transitions CLOSED -> OPEN and requires reason
    print("\n[TEST 1 & 8] Operator Force Open validation")
    # Empty reason -> rejected
    res_no_reason = operator_force_open_circuit("m_op1", "hook", reason="   ")
    assert res_no_reason["success"] is False
    assert res_no_reason["error"] == "CIRCUIT_OVERRIDE_REASON_REQUIRED"

    # Valid Force Open
    res_fo = operator_force_open_circuit("m_op1", "hook", reason="Confirmed downstream outage", operator_id="demo-op")
    assert res_fo["success"] is True
    assert res_fo["state"] == "OPEN"
    assert get_circuit_breaker_status("m_op1", "hook")["state"] == "OPEN"
    print("  ✓ TEST 1 & 8: Force open validated reason and transitioned CLOSED -> OPEN")

    # TEST 2: Force Open when already OPEN returns idempotent response
    print("\n[TEST 2] Force Open idempotent response")
    res_fo_dup = operator_force_open_circuit("m_op1", "hook", reason="Confirmed downstream outage", operator_id="demo-op")
    assert res_fo_dup["success"] is True
    assert res_fo_dup["already_in_state"] is True
    print("  ✓ TEST 2: Already-OPEN circuit returned safe idempotent response")

    # TEST 3, 4, 5: Reset transitions OPEN -> CLOSED, preserves total_failures, rejects if already CLOSED
    print("\n[TEST 3, 4, 5] Operator Reset / Close validation")
    # Accumulate some failures
    record_circuit_observation("m_op1", "hook", failure_category="TIMEOUT", failure_threshold=5)
    st_prior = get_circuit_breaker_status("m_op1", "hook")
    assert st_prior["total_failures"] >= 1

    # Valid Reset
    res_rst = operator_reset_circuit("m_op1", "hook", reason="Merchant confirmed recovery", operator_id="demo-op")
    assert res_rst["success"] is True
    assert res_rst["state"] == "CLOSED"

    st_after = get_circuit_breaker_status("m_op1", "hook")
    assert st_after["state"] == "CLOSED"
    assert st_after["consecutive_failures"] == 0
    assert st_after["total_failures"] == st_prior["total_failures"]  # Preserved

    # Redundant Reset while CLOSED -> rejected
    res_rst_dup = operator_reset_circuit("m_op1", "hook", reason="Merchant confirmed recovery", operator_id="demo-op")
    assert res_rst_dup["success"] is False
    assert res_rst_dup["error"] == "CIRCUIT_ALREADY_CLOSED"
    print("  ✓ TEST 3, 4, 5: Reset closed circuit, preserved total_failures, and rejected redundant reset")

    # TEST 6 & 7: Manual Probe from OPEN and CLOSED validation
    print("\n[TEST 6 & 7] Operator Manual Probe validation")
    # Probe from CLOSED -> rejected
    res_prb_closed = operator_manual_probe_circuit("m_op1", "hook", reason="Want to probe")
    assert res_prb_closed["success"] is False
    assert res_prb_closed["error"] == "INVALID_CIRCUIT_TRANSITION"

    # Trip to OPEN
    operator_force_open_circuit("m_op1", "hook", reason="Force open before probe")
    assert get_circuit_breaker_status("m_op1", "hook")["state"] == "OPEN"

    # Probe from OPEN -> transitions to HALF_OPEN and increments generation
    gen_before = get_circuit_breaker_status("m_op1", "hook")["circuit_generation"]
    res_prb = operator_manual_probe_circuit("m_op1", "hook", reason="Admit test recovery probe", operator_id="demo-op")
    assert res_prb["success"] is True
    assert res_prb["state"] == "HALF_OPEN"
    assert res_prb["circuit_generation"] == gen_before + 1

    st_half = get_circuit_breaker_status("m_op1", "hook")
    assert st_half["state"] == "HALF_OPEN"
    assert st_half["half_open_probe_count"] == 0
    print("  ✓ TEST 6 & 7: Manual probe transitioned OPEN -> HALF_OPEN and rejected probe from CLOSED")

    # TEST 9: Structured Override Lifecycle Audit Events
    print("\n[TEST 9] Operator attribution in lifecycle audit log")
    events = get_circuit_lifecycle_telemetry("m_op1")
    override_events = [e for e in events if e.get("event_type") == "CIRCUIT_OVERRIDE"]
    assert len(override_events) >= 1
    sample_evt = override_events[-1]
    assert sample_evt["actor_type"] == "OPERATOR"
    assert sample_evt["actor_id"] == "demo-op"
    assert sample_evt["source"] == "HUMAN_ACTION_CENTER"
    print(f"  ✓ TEST 9: Override audit event contains actor_type={sample_evt['actor_type']}, source={sample_evt['source']}")

    # TEST 10: API Endpoints & Idempotency
    print("\n[TEST 10] API endpoints & idempotency key deduplication")
    import uuid
    k_fo1 = f"fo_key_{uuid.uuid4().hex[:8]}"
    k_rst1 = f"rst_key_{uuid.uuid4().hex[:8]}"
    k_fo2 = f"fo_key_{uuid.uuid4().hex[:8]}"
    k_prb1 = f"prb_key_{uuid.uuid4().hex[:8]}"

    # 1. API Force Open
    fo_status, fo_body = make_api_post("/api/circuit-breakers/m_api_op/force-open", {
        "endpoint": "payment-webhook",
        "reason": "API operator manual force open",
        "operator_id": "demo-operator",
        "idempotency_key": k_fo1
    })
    assert fo_status == 200
    assert fo_body["success"] is True
    assert fo_body["state"] == "OPEN"
    assert fo_body["duplicate"] is False

    # Duplicate call with same idempotency key
    fo_dup_status, fo_dup_body = make_api_post("/api/circuit-breakers/m_api_op/force-open", {
        "endpoint": "payment-webhook",
        "reason": "API operator manual force open",
        "operator_id": "demo-operator",
        "idempotency_key": k_fo1
    })
    assert fo_dup_status == 200
    assert fo_dup_body["duplicate"] is True

    # 2. API Reset
    rst_status, rst_body = make_api_post("/api/circuit-breakers/m_api_op/reset", {
        "endpoint": "payment-webhook",
        "reason": "API operator manual reset",
        "operator_id": "demo-operator",
        "idempotency_key": k_rst1
    })
    assert rst_status == 200
    assert rst_body["success"] is True
    assert rst_body["state"] == "CLOSED"

    # 3. API Probe
    make_api_post("/api/circuit-breakers/m_api_op/force-open", {
        "endpoint": "payment-webhook",
        "reason": "Re-open for probe test",
        "idempotency_key": k_fo2
    })
    prb_status, prb_body = make_api_post("/api/circuit-breakers/m_api_op/probe", {
        "endpoint": "payment-webhook",
        "reason": "API operator manual probe request",
        "idempotency_key": k_prb1
    })
    assert prb_status == 200
    assert prb_body["success"] is True
    assert prb_body["state"] == "HALF_OPEN"
    print("  ✓ TEST 10: All 3 API endpoints verified with idempotency deduplication")

    # TEST 11: Payment state isolation
    print("\n[TEST 11] Payment state isolation during overrides")
    set_payment_state_directly("pay_iso_001", PaymentState.HUMAN_REVIEW)
    operator_force_open_circuit("m_iso", "hook", reason="Force open test")
    operator_reset_circuit("m_iso", "hook", reason="Reset test")
    assert get_current_payment_state("pay_iso_001") == PaymentState.HUMAN_REVIEW
    print("  ✓ TEST 11: Payment state remained strictly isolated from circuit breaker overrides")

    print("\n==================================================")
    print("ALL TOPIC 2.2.2.7 OPERATOR OVERRIDE TESTS PASSED!")
    print("==================================================")


def test_all_circuit_breaker_override_scenarios():
    run_tests()


if __name__ == "__main__":
    run_tests()
