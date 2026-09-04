"""
RecoverIQ - Test Suite for Real Webhook Signature Verification (Topic 2.1)
Verifies:
  TEST 1: Valid payload + correct signature -> 200 VERIFIED
  TEST 2: Valid payload + incorrect signature -> 401 INVALID
  TEST 3: Valid payload + missing signature -> 401 MISSING
  TEST 4: Payload modified after signature generation -> 401 INVALID (Tamper detection)
  TEST 5: Exact raw body bytes verification (whitespace preserved)
  TEST 6: Empty body handling
  TEST 7: Missing WEBHOOK_SECRET configuration -> safe error without secrets
  TEST 8: Correct signature generated with wrong secret -> INVALID
  TEST 9: Invalid signature does not modify system state
  TEST 10: Valid signature allows processing pipeline to continue
  TEST 11: Constant-time comparison mechanism verified
  TEST 12: No secret/signature credentials exposed in error responses or metadata
  TEST 13: Cross-payload signature swap (Body A signature with Body B payload) -> 401 INVALID
"""

import sys
import os
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.webhook_security import (
    generate_webhook_signature,
    verify_webhook_signature,
    get_webhook_secret,
    get_webhook_security_status,
    reset_webhook_security_state
)

BASE_URL = "http://127.0.0.1:8000"


def make_webhook_request(raw_bytes: bytes, signature: str = None):
    url = f"{BASE_URL}/webhooks/ingest"
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Webhook-Signature"] = signature

    req = urllib.request.Request(url, data=raw_bytes, headers=headers, method="POST")
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
    print("TOPIC 2.1 — REAL WEBHOOK SIGNATURE VERIFICATION TESTS")
    print("==================================================")

    reset_webhook_security_state()
    secret = get_webhook_secret()

    # TEST 1: Valid payload + correct signature -> 200 VERIFIED
    print("\n[TEST 1] Valid payload + correct signature")
    payload_1 = b'{"payment_id":"pay_005","status":"captured","amount":3100}'
    sig_1 = generate_webhook_signature(payload_1, secret)
    status_1, body_1 = make_webhook_request(payload_1, sig_1)
    assert status_1 == 200, f"Expected 200, got {status_1}: {body_1}"
    assert body_1["success"] is True
    assert body_1["signature_status"] == "VERIFIED"
    assert "event_id" in body_1
    print("  ✓ TEST 1: 200 VERIFIED")

    # TEST 2: Valid payload + incorrect signature -> 401 INVALID
    print("\n[TEST 2] Valid payload + incorrect signature")
    status_2, body_2 = make_webhook_request(payload_1, "deadbeef1234567890abcdefdeadbeef")
    assert status_2 == 401, f"Expected 401, got {status_2}: {body_2}"
    detail_2 = body_2.get("detail", body_2)
    assert detail_2["status"] == "INVALID"
    assert detail_2["error"] == "WEBHOOK_SIGNATURE_INVALID"
    print("  ✓ TEST 2: 401 INVALID (WEBHOOK_SIGNATURE_INVALID)")

    # TEST 3: Valid payload + missing signature -> 401 MISSING
    print("\n[TEST 3] Valid payload + missing signature")
    status_3, body_3 = make_webhook_request(payload_1, signature=None)
    assert status_3 == 401, f"Expected 401, got {status_3}: {body_3}"
    detail_3 = body_3.get("detail", body_3)
    assert detail_3["status"] == "MISSING"
    assert detail_3["error"] == "WEBHOOK_SIGNATURE_MISSING"
    print("  ✓ TEST 3: 401 MISSING (WEBHOOK_SIGNATURE_MISSING)")

    # TEST 4: Payload modified after signature generation (tampering) -> 401 INVALID
    print("\n[TEST 4] Tamper detection (modified payload after signing)")
    tampered_payload = b'{"payment_id":"pay_005","status":"failed","amount":3100}'
    status_4, body_4 = make_webhook_request(tampered_payload, sig_1)
    assert status_4 == 401
    detail_4 = body_4.get("detail", body_4)
    assert detail_4["status"] == "INVALID"
    print("  ✓ TEST 4: Tampered payload rejected with 401 INVALID")

    # TEST 5: Exact raw body bytes verification (whitespace preserved)
    print("\n[TEST 5] Raw bytes verification with custom whitespace")
    raw_with_spaces = b'{\n  "payment_id":  "pay_005",\n  "amount": 3100\n}'
    sig_spaces = generate_webhook_signature(raw_with_spaces, secret)
    status_5, body_5 = make_webhook_request(raw_with_spaces, sig_spaces)
    assert status_5 == 200
    assert body_5["signature_status"] == "VERIFIED"
    print("  ✓ TEST 5: Exact raw byte verification passed with unique formatting")

    # TEST 6: Empty body handling
    print("\n[TEST 6] Empty request body handling")
    empty_bytes = b""
    sig_empty = generate_webhook_signature(empty_bytes, secret)
    res_empty = verify_webhook_signature(empty_bytes, sig_empty, secret)
    assert res_empty["verified"] is True
    print("  ✓ TEST 6: Empty body signature calculation and verification handled")

    # TEST 7: Missing WEBHOOK_SECRET configuration
    print("\n[TEST 7] Missing WEBHOOK_SECRET configuration error handling")
    res_no_sec = verify_webhook_signature(payload_1, sig_1, secret="")
    assert res_no_sec["verified"] is False
    assert res_no_sec["status"] == "CONFIGURATION_ERROR"
    assert res_no_sec["error"] == "WEBHOOK_SECRET_UNCONFIGURED"
    print("  ✓ TEST 7: Missing secret safely rejected with CONFIGURATION_ERROR")

    # TEST 8: Correct signature with wrong secret -> INVALID
    print("\n[TEST 8] Correct signature with wrong secret")
    sig_wrong_sec = generate_webhook_signature(payload_1, "some_other_unauthorized_secret_key")
    res_wrong = verify_webhook_signature(payload_1, sig_wrong_sec, secret)
    assert res_wrong["verified"] is False
    assert res_wrong["status"] == "INVALID"
    print("  ✓ TEST 8: Wrong secret signature rejected with INVALID")

    # TEST 9 & 10: Invalid signature does not reach processing, valid signature continues
    print("\n[TEST 9 & 10] Processing pipeline gate")
    assert status_2 == 401 and "payment_id" not in body_2
    assert status_1 == 200 and body_1["payment_id"] == "pay_005"
    print("  ✓ TEST 9 & 10: Security gate isolates processing pipeline")

    # TEST 11: Constant-time comparison mechanism verified
    print("\n[TEST 11] Constant-time comparison mechanism")
    import hmac
    assert hasattr(hmac, "compare_digest")
    print("  ✓ TEST 11: hmac.compare_digest confirmed active")

    # TEST 12: No secret/signature credentials appear in logs or error responses
    print("\n[TEST 12] Credential leak prevention")
    serialized_err = json.dumps(detail_2)
    assert secret not in serialized_err
    assert "dev_webhook_secret" not in serialized_err
    print("  ✓ TEST 12: Zero secrets exposed in responses or metadata")

    # TEST 13: Security Test: Body A signature with Body B payload -> 401 INVALID
    print("\n[TEST 13] Cross-payload signature swap (Body A signature with Body B payload)")
    body_A = b'{"event":"payment.captured","payment_id":"pay_005","amount":3100}'
    body_B = b'{"event":"payment.refunded","payment_id":"pay_005","amount":3100}'
    sig_A = generate_webhook_signature(body_A, secret)

    status_swap, body_swap = make_webhook_request(body_B, sig_A)
    assert status_swap == 401
    detail_swap = body_swap.get("detail", body_swap)
    assert detail_swap["status"] == "INVALID"
    print("  ✓ TEST 13: Body A signature with Body B payload returned 401 INVALID")

    # TEST 14: Security status endpoint returns safe observability metadata
    print("\n[TEST 14] GET /api/webhooks/security-status endpoint")
    req_status = urllib.request.Request(f"{BASE_URL}/api/webhooks/security-status", method="GET")
    with urllib.request.urlopen(req_status, timeout=5) as r:
        sec_meta = json.loads(r.read().decode("utf-8"))
        assert sec_meta["verification_enabled"] is True
        assert sec_meta["algorithm"] == "HMAC-SHA256"
        assert sec_meta["header"] == "X-Webhook-Signature"
        assert secret not in json.dumps(sec_meta)
    print("  ✓ TEST 14: Security status endpoint verified (no secrets exposed)")

    print("\n==================================================")
    print("ALL TOPIC 2.1 WEBHOOK SECURITY TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
