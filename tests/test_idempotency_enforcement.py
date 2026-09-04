"""
RecoverIQ - Test Suite for Topic 1.4 Idempotency Enforcement
Tests:
  - TEST 1: First recovery request -> 200, new execution ID, duplicate=False
  - TEST 2: Same recovery request again -> 200, duplicate=True, same execution ID
  - TEST 3: Same idempotency key + different payment -> 409 Conflict
  - TEST 4: Same idempotency key + different action -> 409 Conflict
  - TEST 5: Concurrent simultaneous identical requests -> only ONE execution created
  - TEST 6: Refund repeated with same key -> same execution ID, duplicate=True
  - TEST 7: Escalation repeated with same key -> same execution/incident ID, duplicate=True
"""

import sys
import os
import json
import uuid
import concurrent.futures
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    print("TOPIC 1.4 IDEMPOTENCY ENFORCEMENT TEST SUITE")
    print("==================================================")

    test_run_id = uuid.uuid4().hex[:6]
    key_rec = f"pay_005_rec_{test_run_id}"
    key_ref = f"pay_005_ref_{test_run_id}"
    key_esc = f"pay_005_esc_{test_run_id}"
    key_shared = f"shared_key_{test_run_id}"

    # -------------------------------------------------------------
    # TEST 1: First recovery request
    # -------------------------------------------------------------
    print("\n[TEST 1] First recovery request (new execution)")
    status, res1 = make_request("/payments/pay_005/approve-recovery", method="POST", payload={
        "idempotency_key": key_rec,
        "recovery_strategy": "webhook_replay",
        "operator_id": "test-operator"
    })
    print(f"  Response: status={status}, exec={res1.get('execution_id')}, duplicate={res1.get('duplicate')}")
    assert status == 200, f"Expected 200, got {status}"
    assert res1["success"] is True
    assert res1["duplicate"] is False
    assert "execution_id" in res1
    exec_id_1 = res1["execution_id"]
    print("  ✓ TEST 1 PASSED: New execution created successfully")

    # -------------------------------------------------------------
    # TEST 2: Same recovery request again
    # -------------------------------------------------------------
    print("\n[TEST 2] Same recovery request again (idempotent duplicate)")
    status, res2 = make_request("/payments/pay_005/approve-recovery", method="POST", payload={
        "idempotency_key": key_rec,
        "recovery_strategy": "webhook_replay",
        "operator_id": "test-operator"
    })
    print(f"  Response: status={status}, exec={res2.get('execution_id')}, duplicate={res2.get('duplicate')}")
    assert status == 200, f"Expected 200, got {status}"
    assert res2["success"] is True
    assert res2["duplicate"] is True
    assert res2["execution_id"] == exec_id_1, f"Expected matching exec_id {exec_id_1}, got {res2['execution_id']}"
    print("  ✓ TEST 2 PASSED: Duplicate detected, returned original execution ID")

    # -------------------------------------------------------------
    # TEST 3: Same idempotency key + different payment
    # -------------------------------------------------------------
    print("\n[TEST 3] Same idempotency key + different payment (conflict check)")
    status, res3 = make_request("/payments/pay_002/approve-recovery", method="POST", payload={
        "idempotency_key": key_rec,
        "recovery_strategy": "webhook_replay",
        "operator_id": "test-operator"
    })
    print(f"  Response: status={status}, body={res3}")
    assert status == 409, f"Expected 409 Conflict, got {status}"
    print("  ✓ TEST 3 PASSED: 409 Conflict returned for mismatched payment")

    # -------------------------------------------------------------
    # TEST 4: Same idempotency key + different action
    # -------------------------------------------------------------
    print("\n[TEST 4] Same idempotency key + different action (conflict check)")
    status, res4 = make_request("/payments/pay_005/refund", method="POST", payload={
        "amount": 3100,
        "idempotency_key": key_rec,
        "operator_id": "test-operator"
    })
    print(f"  Response: status={status}, body={res4}")
    assert status == 409, f"Expected 409 Conflict, got {status}"
    print("  ✓ TEST 4 PASSED: 409 Conflict returned for mismatched action")

    # -------------------------------------------------------------
    # TEST 5: Concurrent simultaneous identical requests
    # -------------------------------------------------------------
    print("\n[TEST 5] Concurrent simultaneous identical requests (race-condition check)")
    key_concurrent = f"pay_005_concurrent_{test_run_id}"

    def send_concurrent_req():
        return make_request("/payments/pay_005/approve-recovery", method="POST", payload={
            "idempotency_key": key_concurrent,
            "recovery_strategy": "webhook_replay",
            "operator_id": "concurrency-tester"
        })

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_concurrent_req) for _ in range(5)]
        results = [f.result() for f in futures]

    statuses = [r[0] for r in results]
    exec_ids = {r[1].get("execution_id") for r in results if r[0] == 200}
    duplicates = [r[1].get("duplicate") for r in results if r[0] == 200]

    print(f"  Concurrent statuses: {statuses}")
    print(f"  Unique execution IDs: {exec_ids}")
    print(f"  Duplicate flags: {duplicates}")

    assert all(s == 200 for s in statuses), "All concurrent requests should return 200"
    assert len(exec_ids) == 1, f"Expected exactly 1 execution ID across concurrent calls, got {exec_ids}"
    assert duplicates.count(False) == 1, "Exactly ONE request must be original (duplicate=False)"
    assert duplicates.count(True) == 4, "Remaining 4 requests must be duplicates (duplicate=True)"
    print("  ✓ TEST 5 PASSED: Concurrency safe, exactly 1 execution created")

    # -------------------------------------------------------------
    # TEST 6: Refund repeated with same key
    # -------------------------------------------------------------
    print("\n[TEST 6] Refund repeated with same key")
    status, ref1 = make_request("/payments/pay_005/refund", method="POST", payload={
        "amount": 3100,
        "currency": "INR",
        "idempotency_key": key_ref,
        "operator_id": "test-operator"
    })
    assert status == 200 and ref1["duplicate"] is False
    exec_ref_id = ref1["execution_id"]

    status, ref2 = make_request("/payments/pay_005/refund", method="POST", payload={
        "amount": 3100,
        "currency": "INR",
        "idempotency_key": key_ref,
        "operator_id": "test-operator"
    })
    assert status == 200 and ref2["duplicate"] is True
    assert ref2["execution_id"] == exec_ref_id
    print("  ✓ TEST 6 PASSED: Refund idempotency verified")

    # -------------------------------------------------------------
    # TEST 7: Escalation repeated with same key
    # -------------------------------------------------------------
    print("\n[TEST 7] Escalation repeated with same key")
    status, esc1 = make_request("/payments/pay_005/escalate", method="POST", payload={
        "reason": "Webhook timeout",
        "idempotency_key": key_esc,
        "trace_id": "trc_esc_001",
        "operator_id": "test-operator"
    })
    assert status == 200 and esc1["duplicate"] is False
    exec_esc_id = esc1["execution_id"]
    inc_esc_id = esc1["incident_id"]

    status, esc2 = make_request("/payments/pay_005/escalate", method="POST", payload={
        "reason": "Webhook timeout",
        "idempotency_key": key_esc,
        "trace_id": "trc_esc_001",
        "operator_id": "test-operator"
    })
    assert status == 200 and esc2["duplicate"] is True
    assert esc2["execution_id"] == exec_esc_id
    assert esc2["incident_id"] == inc_esc_id
    print("  ✓ TEST 7 PASSED: Escalation idempotency verified")

    print("\n==================================================")
    print("ALL TOPIC 1.4 IDEMPOTENCY ENFORCEMENT TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
