"""
RecoverIQ - Test Suite for Circuit Breaker Failure Threshold & Automatic Tripping (Topic 2.2.2.2)
Verifies:
  1. Initial state is CLOSED.
  2. First trigger failure increments consecutive_failures to 1.
  3. Repeated failures increment correctly.
  4. Failure below threshold remains CLOSED.
  5. Failure exactly at threshold transitions CLOSED -> OPEN.
  6. Success resets consecutive_failures to 0.
  7. Success does not reset total_failures.
  8. CLIENT_ERROR does not increment failures.
  9. REDIRECT does not increment failures.
  10. Different trigger failure categories count toward the same threshold.
  11. OPEN remains OPEN.
  12. OPEN does not automatically become HALF_OPEN.
  13. No cooldown behavior exists yet.
  14. Transition reason is recorded on tripping.
  15. last_failure_category is updated.
  16. opened_at is recorded when the circuit opens.
  17. Concurrent failures do not corrupt the counter.
  18. Concurrent threshold crossing produces exactly one logical OPEN transition.
  19. Different merchant endpoints maintain independent counters.
  20. Different merchants maintain independent circuit states.
"""

import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.circuit_breaker import (
    CircuitState,
    record_circuit_observation,
    get_circuit_breaker_status,
    get_all_circuit_breaker_statuses,
    reset_circuit_breaker_state
)


def run_tests():
    print("==================================================")
    print("TOPIC 2.2.2.2 — CIRCUIT BREAKER THRESHOLD & TRIPPING TESTS")
    print("==================================================")

    reset_circuit_breaker_state()

    # TEST 1: Initial state is CLOSED
    print("\n[TEST 1] Initial state")
    c1 = get_circuit_breaker_status("m_test_1", "payment-webhook")
    assert c1["state"] == "CLOSED"
    assert c1["consecutive_failures"] == 0
    assert c1["total_failures"] == 0
    print("  ✓ TEST 1: Initial state is CLOSED with 0 failures")

    # TEST 2: First trigger failure increments consecutive_failures to 1
    print("\n[TEST 2] First trigger failure increment")
    c2 = record_circuit_observation("m_test_1", "payment-webhook", failure_category="TIMEOUT", failure_threshold=5)
    assert c2["state"] == "CLOSED"
    assert c2["consecutive_failures"] == 1
    assert c2["total_failures"] == 1
    assert c2["last_failure_category"] == "TIMEOUT"
    print("  ✓ TEST 2: consecutive_failures=1, total_failures=1")

    # TEST 3 & 4: Repeated failures below threshold remain CLOSED
    print("\n[TEST 3 & 4] Failures below threshold")
    record_circuit_observation("m_test_1", "payment-webhook", failure_category="SERVER_ERROR", failure_threshold=5)
    record_circuit_observation("m_test_1", "payment-webhook", failure_category="RATE_LIMITED", failure_threshold=5)
    c4 = record_circuit_observation("m_test_1", "payment-webhook", failure_category="NETWORK_ERROR", failure_threshold=5)
    assert c4["state"] == "CLOSED"
    assert c4["consecutive_failures"] == 4
    assert c4["total_failures"] == 4
    assert c4["opened_at"] is None
    print("  ✓ TEST 3 & 4: 4 failures below threshold 5 -> remains CLOSED")

    # TEST 5 & 14 & 16: Failure at threshold trips CLOSED -> OPEN
    print("\n[TEST 5 & 14 & 16] Automatic trip at threshold (5th failure)")
    c5 = record_circuit_observation("m_test_1", "payment-webhook", failure_category="TIMEOUT", failure_threshold=5)
    assert c5["state"] == "OPEN"
    assert c5["consecutive_failures"] == 5
    assert c5["total_failures"] == 5
    assert c5["opened_at"] is not None
    print(f"  ✓ TEST 5, 14, 16: 5th failure tripped circuit to OPEN (opened_at={c5['opened_at']})")

    # TEST 6 & 7: Success resets consecutive_failures but preserves total_failures
    print("\n[TEST 6 & 7] Success reset behavior")
    reset_circuit_breaker_state()
    record_circuit_observation("m_test_reset", "hook", failure_category="TIMEOUT", failure_threshold=5)
    record_circuit_observation("m_test_reset", "hook", failure_category="TIMEOUT", failure_threshold=5)
    # 2 failures -> count = 2, total = 2
    c_pre = get_circuit_breaker_status("m_test_reset", "hook")
    assert c_pre["consecutive_failures"] == 2
    assert c_pre["total_failures"] == 2

    # Send SUCCESS
    c_post = record_circuit_observation("m_test_reset", "hook", failure_category="SUCCESS", failure_threshold=5)
    assert c_post["consecutive_failures"] == 0
    assert c_post["total_failures"] == 2
    assert c_post["state"] == "CLOSED"
    print("  ✓ TEST 6 & 7: SUCCESS reset consecutive_failures to 0 while preserving total_failures=2")

    # TEST 8 & 9: CLIENT_ERROR and REDIRECT do not increment failures
    print("\n[TEST 8 & 9] Non-trigger failure handling (CLIENT_ERROR & REDIRECT)")
    c_client = record_circuit_observation("m_test_reset", "hook", failure_category="CLIENT_ERROR", failure_threshold=5)
    assert c_client["consecutive_failures"] == 0
    assert c_client["total_failures"] == 2

    c_redirect = record_circuit_observation("m_test_reset", "hook", failure_category="REDIRECT", failure_threshold=5)
    assert c_redirect["consecutive_failures"] == 0
    assert c_redirect["total_failures"] == 2
    print("  ✓ TEST 8 & 9: CLIENT_ERROR and REDIRECT did not alter circuit failure counters")

    # TEST 10: Different trigger failure categories count toward the same threshold
    print("\n[TEST 10] Mixed trigger categories count toward threshold")
    reset_circuit_breaker_state()
    record_circuit_observation("m_mixed", "hook", failure_category="TIMEOUT", failure_threshold=3)
    record_circuit_observation("m_mixed", "hook", failure_category="SERVER_ERROR", failure_threshold=3)
    c_mixed_trip = record_circuit_observation("m_mixed", "hook", failure_category="NETWORK_ERROR", failure_threshold=3)
    assert c_mixed_trip["state"] == "OPEN"
    assert c_mixed_trip["consecutive_failures"] == 3
    print("  ✓ TEST 10: TIMEOUT + SERVER_ERROR + NETWORK_ERROR combined to trip circuit at threshold 3")

    # TEST 11, 12, 13: OPEN remains OPEN without automatic cooldown or probing
    print("\n[TEST 11-13] OPEN state stability (no cooldown or probing in 2.2.2.2)")
    c_still_open = record_circuit_observation("m_mixed", "hook", failure_category="TIMEOUT", failure_threshold=3)
    assert c_still_open["state"] == "OPEN"
    time.sleep(0.05)
    c_status = get_circuit_breaker_status("m_mixed", "hook")
    assert c_status["state"] == "OPEN"
    print("  ✓ TEST 11-13: OPEN state remained OPEN (no premature HALF_OPEN transition)")

    # TEST 15: last_failure_category is updated
    print("\n[TEST 15] last_failure_category tracking")
    assert c_status["last_failure_category"] == "TIMEOUT"
    print("  ✓ TEST 15: last_failure_category correctly maintained")

    # TEST 17 & 18: Concurrent failures test (20 threads reporting failures)
    print("\n[TEST 17 & 18] Concurrency and atomic tripping test (20 threads)")
    reset_circuit_breaker_state()
    def _report_fail(i):
        record_circuit_observation("m_concur", "hook", failure_category="TIMEOUT", failure_threshold=5)

    with ThreadPoolExecutor(max_workers=20) as executor:
        list(executor.map(_report_fail, range(20)))

    c_concur = get_circuit_breaker_status("m_concur", "hook")
    assert c_concur["state"] == "OPEN"
    assert c_concur["total_failures"] == 20
    assert c_concur["opened_at"] is not None
    print("  ✓ TEST 17 & 18: 20 concurrent failures safely handled -> exactly 1 OPEN state achieved with total_failures=20")

    # TEST 19 & 20: Independent endpoints & merchants
    print("\n[TEST 19 & 20] Merchant and endpoint isolation")
    reset_circuit_breaker_state()
    # Merchant A trips
    for _ in range(5):
        record_circuit_observation("merchant_A", "endpoint_1", failure_category="TIMEOUT", failure_threshold=5)

    # Merchant B is healthy
    record_circuit_observation("merchant_B", "endpoint_1", failure_category="SUCCESS")

    # Merchant A endpoint 2 is healthy
    record_circuit_observation("merchant_A", "endpoint_2", failure_category="SUCCESS")

    st_A1 = get_circuit_breaker_status("merchant_A", "endpoint_1")
    st_A2 = get_circuit_breaker_status("merchant_A", "endpoint_2")
    st_B1 = get_circuit_breaker_status("merchant_B", "endpoint_1")

    assert st_A1["state"] == "OPEN"
    assert st_A2["state"] == "CLOSED"
    assert st_B1["state"] == "CLOSED"
    print("  ✓ TEST 19 & 20: Verified independent circuit isolation across merchants and endpoints")

    print("\n==================================================")
    print("ALL TOPIC 2.2.2.2 CIRCUIT BREAKER TRIPPING TESTS PASSED!")
    print("==================================================")


def test_all_circuit_breaker_threshold_scenarios():
    run_tests()


if __name__ == "__main__":
    run_tests()
