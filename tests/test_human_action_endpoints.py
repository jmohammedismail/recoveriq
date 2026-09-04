"""
RecoverIQ - Test Suite for Topic 1.3 Human Action Backend APIs
Tests:
  - POST /payments/{payment_id}/approve-recovery
  - POST /payments/{payment_id}/refund
  - POST /payments/{payment_id}/escalate
  - HTTP Status Codes: 200, 400, 404, 409, 422
  - Execution Records validation
"""

import sys
import os
import json
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
    print("TOPIC 1.3 HUMAN ACTION BACKEND APIs TEST SUITE")
    print("==================================================")

    # -------------------------------------------------------------
    # 1. TEST APPROVE-RECOVERY
    # -------------------------------------------------------------
    print("\n[1] Testing POST /payments/{payment_id}/approve-recovery")

    # Valid request on pay_005
    status, res = make_request("/payments/pay_005/approve-recovery", method="POST", payload={
        "idempotency_key": "pay_005_recovery_001",
        "recovery_strategy": "webhook_replay",
        "operator_id": "demo-operator"
    })
    print(f"  Valid approve-recovery status: {status}, response: {res}")
    assert status == 200, f"Expected 200, got {status}"
    assert res["success"] is True
    assert res["action"] == "APPROVE_RECOVERY"
    assert res["status"] == "QUEUED"
    assert "execution_id" in res and res["execution_id"].startswith("exec_rec_")
    print("  ✓ Valid approve-recovery passed")

    # Unknown payment
    status, res = make_request("/payments/pay_999/approve-recovery", method="POST", payload={
        "idempotency_key": "pay_999_recovery_001",
        "recovery_strategy": "webhook_replay"
    })
    print(f"  Unknown payment status: {status}")
    assert status == 404, f"Expected 404, got {status}"
    print("  ✓ 404 Not Found verified")

    # Missing idempotency_key
    status, res = make_request("/payments/pay_005/approve-recovery", method="POST", payload={
        "idempotency_key": "",
        "recovery_strategy": "webhook_replay"
    })
    print(f"  Missing idempotency_key status: {status}")
    assert status == 400, f"Expected 400, got {status}"
    print("  ✓ 400 Bad Request verified")

    # Unsupported strategy
    status, res = make_request("/payments/pay_005/approve-recovery", method="POST", payload={
        "idempotency_key": "pay_005_recovery_002",
        "recovery_strategy": "invalid_magic_recovery"
    })
    print(f"  Unsupported strategy status: {status}")
    assert status == 422, f"Expected 422, got {status}"
    print("  ✓ 422 Unprocessable Entity verified")

    # State conflict (e.g. pay_001 order already exists in merchant database)
    status, res = make_request("/payments/pay_001/approve-recovery", method="POST", payload={
        "idempotency_key": "pay_001_recovery_001",
        "recovery_strategy": "webhook_replay"
    })
    print(f"  Duplicate risk conflict status: {status}")
    assert status == 409, f"Expected 409, got {status}"
    print("  ✓ 409 Conflict verified")

    # -------------------------------------------------------------
    # 2. TEST REFUND
    # -------------------------------------------------------------
    print("\n[2] Testing POST /payments/{payment_id}/refund")

    # Valid refund on pay_005
    status, res = make_request("/payments/pay_005/refund", method="POST", payload={
        "amount": 3100,
        "currency": "INR",
        "idempotency_key": "pay_005_refund_001",
        "operator_id": "demo-operator"
    })
    print(f"  Valid refund status: {status}, response: {res}")
    assert status == 200, f"Expected 200, got {status}"
    assert res["success"] is True
    assert res["action"] == "REFUND"
    assert res["status"] == "QUEUED"
    assert "execution_id" in res and res["execution_id"].startswith("exec_ref_")
    print("  ✓ Valid refund passed")

    # Unknown payment
    status, res = make_request("/payments/pay_999/refund", method="POST", payload={
        "amount": 3100,
        "idempotency_key": "pay_999_refund_001"
    })
    print(f"  Unknown payment refund status: {status}")
    assert status == 404, f"Expected 404, got {status}"
    print("  ✓ 404 Not Found verified")

    # Invalid amount <= 0
    status, res = make_request("/payments/pay_005/refund", method="POST", payload={
        "amount": -500,
        "idempotency_key": "pay_005_refund_002"
    })
    print(f"  Invalid amount status: {status}")
    assert status == 422, f"Expected 422, got {status}"
    print("  ✓ 422 Unprocessable Entity for amount verified")

    # Missing idempotency key
    status, res = make_request("/payments/pay_005/refund", method="POST", payload={
        "amount": 3100,
        "idempotency_key": ""
    })
    print(f"  Missing idempotency key status: {status}")
    assert status == 400, f"Expected 400, got {status}"
    print("  ✓ 400 Bad Request verified")

    # -------------------------------------------------------------
    # 3. TEST ESCALATE
    # -------------------------------------------------------------
    print("\n[3] Testing POST /payments/{payment_id}/escalate")

    # Valid escalation on pay_005
    status, res = make_request("/payments/pay_005/escalate", method="POST", payload={
        "reason": "Merchant webhook timeout with retries consumed",
        "trace_id": "trc_pay_005_x89f",
        "operator_id": "demo-operator"
    })
    print(f"  Valid escalate status: {status}, response: {res}")
    assert status == 200, f"Expected 200, got {status}"
    assert res["success"] is True
    assert res["action"] == "ESCALATE"
    assert res["status"] == "QUEUED"
    assert "incident_id" in res and res["incident_id"].startswith("inc_")
    print("  ✓ Valid escalate passed")

    # Missing reason
    status, res = make_request("/payments/pay_005/escalate", method="POST", payload={
        "reason": ""
    })
    print(f"  Missing reason status: {status}")
    assert status == 400, f"Expected 400, got {status}"
    print("  ✓ 400 Bad Request verified")

    # -------------------------------------------------------------
    # 4. TEST OPERATOR EXECUTION RECORDS AUDIT
    # -------------------------------------------------------------
    print("\n[4] Testing GET /api/operator/executions")
    status, res = make_request("/api/operator/executions")
    assert status == 200
    assert len(res) >= 3, f"Expected at least 3 execution records, got {len(res)}"
    sample_rec = res[-1]
    print(f"  Latest execution record: {sample_rec}")
    for key in ["execution_id", "payment_id", "action", "operator_id", "requested_at", "status"]:
        assert key in sample_rec, f"Missing required execution record key: {key}"
    print("  ✓ Execution records audit verified")

    print("\n==================================================")
    print("ALL TOPIC 1.3 BACKEND HUMAN ACTION API TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
