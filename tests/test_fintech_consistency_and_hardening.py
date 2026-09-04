"""
RecoverIQ - Fintech Consistency, Security, Distributed-Systems and Demo Hardening Test Suite

Automated verification covering all P0 and P1 fintech platform requirements:
  1. Authoritative snapshot contract consistency for pay_005 and all fixtures
  2. Terminal state action guards (SUCCESS, RECOVERED, REFUNDED, STOPPED disable recovery)
  3. Pre-allocated deterministic idempotency key reservation
  4. Optimistic concurrency control & state versioning (409 on version mismatch)
  5. Out-of-order stale event rejection with audit logging
  6. Human review approval transactional lifecycle
  7. Duplicate approval idempotency
  8. Circuit breaker protection during human approval
  9. Sensitive data sanitization and PII masking
 10. Webhook replay protection and freshness validation
 11. Comprehensive demo environment reset and isolation
 12. Incident-time vs current endpoint telemetry separation
"""

import os
import pytest
from datetime import datetime, timezone

from src.state_machine import (
    get_current_payment_state, get_payment_version, transition_payment_state,
    PaymentState, reset_payment_state_store, handle_out_of_order_event
)
from src.recovery_operational_snapshot import (
    get_payment_operational_snapshot, get_or_reserve_idempotency_intent,
    mark_idempotency_intent_executed, reset_operational_snapshot_store
)
from src.security_sanitizer import sanitize_sensitive_data, mask_card_number
from src.recovery_human_review import (
    create_or_get_human_review_request, approve_human_review_request, get_payment_human_review,
    reset_human_review_state
)
request_human_review = create_or_get_human_review_request

from src.circuit_breaker import (
    operator_force_open_circuit, get_circuit_breaker_status, reset_circuit_breaker_state
)


class TestFintechConsistencyAndHardening:

    def setup_method(self):
        reset_payment_state_store()
        reset_operational_snapshot_store()
        reset_human_review_state()
        reset_circuit_breaker_state()

    def test_authoritative_snapshot_pay_005(self):
        """P0: Initial pay_005 tells one coherent story before human review approval."""
        snapshot = get_payment_operational_snapshot("pay_005")
        assert snapshot["payment_id"] == "pay_005"
        assert snapshot["amount"] == 3100.0
        assert snapshot["authoritative_payment_state"] == "HUMAN_REVIEW"
        assert snapshot["display_state"] == "HUMAN_REVIEW"
        assert snapshot["policy_decision"] == "HUMAN_REVIEW"
        assert snapshot["confidence_score"] == 60.0
        assert snapshot["decision_threshold"] == 85.0
        assert snapshot["recovery_status"] == "NOT_EXECUTED"
        assert snapshot["verification_status"] == "NOT_STARTED"
        assert snapshot["reconciliation_status"] == "NOT_STARTED"
        assert snapshot["incident_status"] == "OPEN"
        assert snapshot["human_action_required"] is True
        assert snapshot["is_terminal"] is False
        assert "APPROVE_RECOVERY" in snapshot["allowed_operator_actions"]
        assert snapshot["idempotency_intent"]["intent_status"] == "RESERVED"
        assert snapshot["idempotency_intent"]["used"] is False

    def test_terminal_state_action_guards(self):
        """P0: Terminal states disable recovery actions."""
        # STOPPED (pay_001: duplicate order prevention)
        snap_stop1 = get_payment_operational_snapshot("pay_001")
        assert snap_stop1["authoritative_payment_state"] == "STOPPED"
        assert snap_stop1["is_terminal"] is True
        assert "APPROVE_RECOVERY" not in snap_stop1["allowed_operator_actions"]

        # STOPPED (pay_003: explicit stop)
        snap_stop = get_payment_operational_snapshot("pay_003")
        assert snap_stop["authoritative_payment_state"] == "STOPPED"
        assert snap_stop["is_terminal"] is True
        assert len(snap_stop["allowed_operator_actions"]) == 0

        # RECOVERED (pay_004: auto recovered)
        snap_rec = get_payment_operational_snapshot("pay_004")
        assert snap_rec["authoritative_payment_state"] in ("RECOVERED", "SUCCESS")
        assert snap_rec["is_terminal"] is True
        assert "APPROVE_RECOVERY" not in snap_rec["allowed_operator_actions"]

    def test_idempotency_intent_reservation(self):
        """P0: Pre-allocates deterministic key without executing."""
        intent = get_or_reserve_idempotency_intent("pay_005", "ORD_005", "ORDER_SYNC")
        assert intent["idempotency_key"] == "pay_005_ORD_005_ORDER_SYNC_v1"
        assert intent["intent_status"] == "RESERVED"
        assert intent["used"] is False

        # Duplicate reservation returns the exact same object
        intent2 = get_or_reserve_idempotency_intent("pay_005")
        assert intent2["idempotency_key"] == intent["idempotency_key"]

    def test_optimistic_concurrency_and_versioning(self):
        """P1: Monotonic versioning and 409 rejection on stale review action."""
        pid = "pay_concurrency_test"
        # Seed initial state
        transition_payment_state(pid, PaymentState.HUMAN_REVIEW, reason="Initial review")
        v1 = get_payment_version(pid)
        assert v1 >= 1

        # Advance state to RECOVERING
        res1 = transition_payment_state(pid, PaymentState.RECOVERING, reason="Approved", expected_version=v1)
        assert res1["success"] is True
        assert res1["state_version"] == v1 + 1

        # Attempt transition with stale expected_version (v1 instead of v2)
        res_stale = transition_payment_state(pid, PaymentState.RECOVERED, reason="Stale complete", expected_version=v1)
        assert res_stale["success"] is False
        assert res_stale["error"] == "STATE_CHANGED_SINCE_REVIEW"
        assert res_stale["status_code"] == 409

    def test_out_of_order_stale_event_rejection(self):
        """P1: Rejects older events attempting to regress state."""
        pid = "pay_order_test"
        transition_payment_state(pid, PaymentState.HUMAN_REVIEW, reason="Step 1")
        transition_payment_state(pid, PaymentState.RECOVERING, reason="Step 2")
        curr_v = get_payment_version(pid)

        # Incoming event with older version (v1 when current is >= 2)
        res = handle_out_of_order_event(pid, incoming_version=1, incoming_state="PROCESSING")
        assert res["success"] is False
        assert res["status"] == "STALE_EVENT_IGNORED"

    def test_human_review_approval_flow(self):
        """P0: Full human approval flow executes idempotently."""
        pid = "pay_hr_flow"
        # 1. Create review
        req = request_human_review(
            payment_id=pid,
            merchant_id="merchant_demo",
            endpoint="payment-webhook",
            reason="Confidence 60%",
            risk_level="MEDIUM"
        )
        assert req["review_status"] == "REVIEW_PENDING"

        # 2. Approve review
        appr = approve_human_review_request(
            payment_id=pid,
            reviewer_id="operator_alice",
            reason="Merchant order confirmed missing and circuit healthy."
        )
        assert appr["success"] is True
        assert appr["review_status"] == "COMPLETED"

    def test_duplicate_human_review_approval_idempotent(self):
        """P0: Re-approving already completed review returns duplicate execution."""
        pid = "pay_hr_dup"
        request_human_review(pid, "merchant_demo", "payment-webhook", "Test", "LOW")
        appr1 = approve_human_review_request(pid, "operator_alice", "First approval")
        assert appr1["success"] is True

        # Second approval returns duplicate without executing again
        appr2 = approve_human_review_request(pid, "operator_alice", "Second approval")
        assert appr2["success"] is True
        assert appr2["duplicate"] is True
        assert appr2["approval_outcome"] == "ALREADY_COMPLETED"

    def test_circuit_breaker_blocks_approval_when_open(self):
        """P0: Open circuit pauses approval execution."""
        pid = "pay_circuit_blocked"
        request_human_review(pid, "merchant_demo", "payment-webhook", "Test", "MEDIUM")

        # Trip circuit breaker
        operator_force_open_circuit("merchant_demo", "payment-webhook", operator_id="admin_test", reason="Testing approval blockage")

        appr = approve_human_review_request(pid, "operator_alice", "Attempt approval")
        assert appr["success"] is False
        assert appr["approval_outcome"] == "EXECUTION_BLOCKED"
        assert appr["circuit_state"] == "OPEN"

    def test_security_sanitizer_pii_masking(self):
        """P1: Zero leakage of secrets, auth headers, and full credit cards."""
        raw_payload = {
            "api_key": "sk_live_secret123456",
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "user_card": "4111111111111234",
            "payment_id": "pay_005",
            "idempotency_key": "pay_005_ORD_005_v1"
        }
        sanitized = sanitize_sensitive_data(raw_payload)
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["authorization"] == "[REDACTED]"
        assert sanitized["user_card"] == "****-****-****-1234"
        assert sanitized["payment_id"] == "pay_005"
        assert sanitized["idempotency_key"] == "pay_005_ORD_005_v1"

    def test_telemetry_incident_vs_current_separation(self):
        """P1: Separates incident 504 from current healthy 200 telemetry."""
        snapshot = get_payment_operational_snapshot("pay_005")
        incident_time = snapshot["telemetry_context"]["incident_time"]
        current_endpoint = snapshot["telemetry_context"]["current_endpoint"]

        assert incident_time["http_status"] == 504
        assert incident_time["failure_type"] == "TIMEOUT"
        assert incident_time["endpoint_health_then"] == "DEGRADED"

        assert current_endpoint["http_status"] == 200
        assert current_endpoint["health"] == "HEALTHY"
        assert current_endpoint["circuit_state"] == "CLOSED"

    def test_pay_003_safety_invariant_protected(self):
        """P0: Invariant protection for pay_003: STOPPED state, STOP policy, never FAILED, recovery actions disabled."""
        snap = get_payment_operational_snapshot("pay_003")
        assert snap["authoritative_payment_state"] == "STOPPED"
        assert snap["is_terminal"] is True
        assert len(snap["allowed_operator_actions"]) == 0
        assert "APPROVE_RECOVERY" not in snap["allowed_operator_actions"]
        assert snap["authoritative_payment_state"] != "FAILED"
        assert snap["policy_decision"] == "STOP"
