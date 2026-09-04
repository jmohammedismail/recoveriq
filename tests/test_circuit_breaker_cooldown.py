"""
RecoverIQ - Test Suite for Circuit Breaker Cooldown, HALF_OPEN Probing & Recovery (Topic 2.2.2.4)
Verifies:
  1. OPEN circuit before cooldown remains OPEN.
  2. Cooldown expiration makes circuit eligible for HALF_OPEN.
  3. OPEN -> HALF_OPEN happens atomically.
  4. HALF_OPEN probe is admitted (is_probe=True).
  5. Probe limit is enforced.
  6. Successful probe transitions HALF_OPEN -> CLOSED.
  7. Successful probe resets consecutive_failures to 0.
  8. total_failures remains historically preserved.
  9. Failed probe transitions HALF_OPEN -> OPEN.
  10. Failed probe records failure category.
  11. Additional requests blocked when probe limit reached.
  12. Concurrent requests cannot exceed probe limit.
  13. Stale probe result cannot reopen a newer CLOSED circuit.
  14. Stale probe result cannot close a newer OPEN circuit.
  15. Payment state is unaffected.
  16. No secrets appear in telemetry.
  17. Existing threshold behavior remains intact.
  18. Existing OPEN fast-fail behavior remains intact.
"""

import sys
import os
import time
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.circuit_breaker import (
    CircuitState,
    record_circuit_observation,
    check_circuit_request_allowed,
    execute_merchant_request_with_circuit_breaker,
    record_half_open_probe_result,
    get_circuit_breaker_status,
    get_circuit_lifecycle_telemetry,
    reset_circuit_breaker_state
)
from src.state_machine import (
    get_current_payment_state,
    set_payment_state_directly,
    PaymentState
)


def run_tests():
    print("==================================================")
    print("TOPIC 2.2.2.4 — CIRCUIT BREAKER COOLDOWN & RECOVERY TESTS")
    print("==================================================")

    reset_circuit_breaker_state()

    # TEST 1 & 18: OPEN circuit before cooldown remains OPEN and fast-fails
    print("\n[TEST 1 & 18] OPEN circuit before cooldown expiry")
    # Trip circuit with 0.1s cooldown for fast testing
    for _ in range(5):
        record_circuit_observation("m_cd", "hook", failure_category="TIMEOUT", failure_threshold=5, cooldown_duration_sec=0.15)

    st_open = get_circuit_breaker_status("m_cd", "hook")
    assert st_open["state"] == "OPEN"
    assert st_open["cooldown_remaining_sec"] > 0.0

    # Immediate request while cooldown is active -> blocked
    res_blocked = check_circuit_request_allowed("m_cd", "hook", payment_id="pay_001")
    assert res_blocked["allowed"] is False
    assert res_blocked["error"] == "CIRCUIT_OPEN"
    print(f"  ✓ TEST 1 & 18: Request blocked during cooldown (remaining: {res_blocked['cooldown_remaining_sec']}s)")

    # TEST 2, 3, 4: Cooldown expiration allows atomic transition to HALF_OPEN and admits probe
    print("\n[TEST 2, 3, 4] Cooldown expiration and HALF_OPEN probe admission")
    time.sleep(0.18)  # Wait for 0.15s cooldown to expire

    probe1 = check_circuit_request_allowed("m_cd", "hook", payment_id="pay_002")
    assert probe1["allowed"] is True
    assert probe1["is_probe"] is True
    assert probe1["probe_number"] == 1
    assert probe1["circuit_state"] == "HALF_OPEN"
    print("  ✓ TEST 2, 3, 4: Circuit atomically moved OPEN -> HALF_OPEN; probe 1 admitted")

    # TEST 5 & 11: Probe limit enforcement (limit=3)
    print("\n[TEST 5 & 11] HALF_OPEN probe limit enforcement")
    probe2 = check_circuit_request_allowed("m_cd", "hook", payment_id="pay_003")
    probe3 = check_circuit_request_allowed("m_cd", "hook", payment_id="pay_004")
    assert probe2["allowed"] is True and probe2["probe_number"] == 2
    assert probe3["allowed"] is True and probe3["probe_number"] == 3

    # 4th request exceeds probe limit 3 -> blocked
    probe4 = check_circuit_request_allowed("m_cd", "hook", payment_id="pay_005")
    assert probe4["allowed"] is False
    assert probe4["error"] == "CIRCUIT_HALF_OPEN_PROBE_LIMIT"
    assert probe4["circuit_state"] == "HALF_OPEN"
    print("  ✓ TEST 5 & 11: Probe 2 and 3 admitted; probe 4 blocked by probe limit")

    # TEST 6, 7, 8: Successful probe transitions HALF_OPEN -> CLOSED, resets consecutive_failures, preserves total_failures
    print("\n[TEST 6, 7, 8] Successful probe recovery")
    res_rec = record_half_open_probe_result("m_cd", "hook", success=True, payment_id="pay_002", circuit_generation=probe1["circuit_generation"])
    assert res_rec["success"] is True
    assert res_rec["state"] == "CLOSED"

    st_closed = get_circuit_breaker_status("m_cd", "hook")
    assert st_closed["state"] == "CLOSED"
    assert st_closed["consecutive_failures"] == 0
    assert st_closed["total_failures"] == 5  # historically preserved
    assert st_closed["half_open_probe_count"] == 0
    print("  ✓ TEST 6, 7, 8: Circuit recovered to CLOSED; consecutive_failures=0, total_failures=5 preserved")

    # TEST 9 & 10: Failed probe transitions HALF_OPEN -> OPEN and records failure category
    print("\n[TEST 9 & 10] Failed probe reopens circuit")
    reset_circuit_breaker_state()
    for _ in range(5):
        record_circuit_observation("m_fail", "hook", failure_category="TIMEOUT", failure_threshold=5, cooldown_duration_sec=0.05)

    time.sleep(0.08)  # Wait for cooldown
    pr = check_circuit_request_allowed("m_fail", "hook")
    assert pr["allowed"] is True and pr["circuit_state"] == "HALF_OPEN"

    # Failed probe result
    res_reopen = record_half_open_probe_result(
        "m_fail", "hook",
        success=False,
        failure_category="SERVER_ERROR",
        circuit_generation=pr["circuit_generation"]
    )
    assert res_reopen["success"] is True
    assert res_reopen["state"] == "OPEN"

    st_reopened = get_circuit_breaker_status("m_fail", "hook")
    assert st_reopened["state"] == "OPEN"
    assert st_reopened["last_failure_category"] == "SERVER_ERROR"
    assert st_reopened["total_failures"] == 6
    print("  ✓ TEST 9 & 10: Failed probe transitioned HALF_OPEN -> OPEN with SERVER_ERROR")

    # TEST 12: Concurrent requests cannot exceed probe limit
    print("\n[TEST 12] Concurrency test for probe limit (20 concurrent requests)")
    reset_circuit_breaker_state()
    for _ in range(5):
        record_circuit_observation("m_concur_p", "hook", failure_category="TIMEOUT", failure_threshold=5, cooldown_duration_sec=0.05)
    time.sleep(0.08)

    def _probe_req(i):
        return check_circuit_request_allowed("m_concur_p", "hook", payment_id=f"pay_c_{i}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        c_results = list(executor.map(_probe_req, range(20)))

    admitted = [r for r in c_results if r["allowed"] is True]
    blocked = [r for r in c_results if r["allowed"] is False]
    assert len(admitted) == 3  # Exactly 3 admitted probes
    assert len(blocked) == 17
    print(f"  ✓ TEST 12: Exactly {len(admitted)} probes admitted, {len(blocked)} blocked across 20 threads")

    # TEST 13 & 14: Stale probe protection across circuit generations
    print("\n[TEST 13 & 14] Stale probe protection across circuit generations")
    reset_circuit_breaker_state()
    # Generation 1
    for _ in range(5):
        record_circuit_observation("m_gen", "hook", failure_category="TIMEOUT", failure_threshold=5, cooldown_duration_sec=0.05)
    time.sleep(0.08)
    pr_gen1 = check_circuit_request_allowed("m_gen", "hook")
    gen1_id = pr_gen1["circuit_generation"]

    # Close circuit with successful probe
    record_half_open_probe_result("m_gen", "hook", success=True, circuit_generation=gen1_id)
    assert get_circuit_breaker_status("m_gen", "hook")["state"] == "CLOSED"

    # Stale probe from gen1 attempting to reopen an already closed circuit -> must be rejected
    stale_fail_res = record_half_open_probe_result("m_gen", "hook", success=False, failure_category="TIMEOUT", circuit_generation=gen1_id)
    assert stale_fail_res["ignored"] is True
    assert get_circuit_breaker_status("m_gen", "hook")["state"] == "CLOSED"

    # Trip to Generation 2
    for _ in range(5):
        record_circuit_observation("m_gen", "hook", failure_category="TIMEOUT", failure_threshold=5, cooldown_duration_sec=0.05)
    time.sleep(0.08)
    pr_gen2 = check_circuit_request_allowed("m_gen", "hook")
    gen2_id = pr_gen2["circuit_generation"]
    assert gen2_id > gen1_id

    # Fail gen2 -> OPEN
    record_half_open_probe_result("m_gen", "hook", success=False, failure_category="TIMEOUT", circuit_generation=gen2_id)
    assert get_circuit_breaker_status("m_gen", "hook")["state"] == "OPEN"

    # Stale success probe from gen1 attempting to close newly OPEN gen2 -> must be rejected
    stale_succ_res = record_half_open_probe_result("m_gen", "hook", success=True, circuit_generation=gen1_id)
    assert stale_succ_res["ignored"] is True
    assert get_circuit_breaker_status("m_gen", "hook")["state"] == "OPEN"
    print("  ✓ TEST 13 & 14: Stale probe results successfully ignored across generations")

    # TEST 15: Payment state is completely unaffected
    print("\n[TEST 15] Payment state isolation")
    set_payment_state_directly("pay_005", PaymentState.HUMAN_REVIEW)
    record_half_open_probe_result("m_gen", "hook", success=True, payment_id="pay_005")
    assert get_current_payment_state("pay_005") == PaymentState.HUMAN_REVIEW
    print("  ✓ TEST 15: Payment state remained strictly isolated from circuit events")

    # TEST 16: Telemetry privacy verification
    print("\n[TEST 16] Lifecycle telemetry privacy verification")
    events = get_circuit_lifecycle_telemetry("m_gen")
    assert len(events) >= 1
    serialized = json.dumps(events)
    assert "secret" not in serialized.lower()
    assert "token" not in serialized.lower()
    assert "authorization" not in serialized.lower()
    print("  ✓ TEST 16: Zero secrets found across all lifecycle telemetry records")

    # TEST 17: execute_merchant_request_with_circuit_breaker integration
    print("\n[TEST 17] Request executor automatic probe resolution")
    reset_circuit_breaker_state()
    for _ in range(5):
        record_circuit_observation("m_exec", "hook", failure_category="TIMEOUT", failure_threshold=5, cooldown_duration_sec=0.05)
    time.sleep(0.08)

    mock_good_net = MagicMock(return_value={"status": "recovered"})
    exec_res = execute_merchant_request_with_circuit_breaker("m_exec", "hook", request_fn=mock_good_net)
    assert exec_res["success"] is True
    assert exec_res["is_probe"] is True
    assert mock_good_net.call_count == 1
    # Circuit recovered automatically
    assert get_circuit_breaker_status("m_exec", "hook")["state"] == "CLOSED"
    print("  ✓ TEST 17: Request executor ran probe and automatically closed circuit on success")

    print("\n==================================================")
    print("ALL TOPIC 2.2.2.4 COOLDOWN & RECOVERY TESTS PASSED!")
    print("==================================================")


def test_all_circuit_breaker_cooldown_scenarios():
    run_tests()


if __name__ == "__main__":
    run_tests()
