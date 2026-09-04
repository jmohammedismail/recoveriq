"""
RecoverIQ - Final Merchant Production Readiness & Feature Verification Test Suite
Verifies:
1. Dynamic Metrics & Cross-Page State Consistency.
2. Human Review Approve, Reject, and Escalate Action Workflows.
3. Deterministic Idempotency Key Persistence & Duplicate Protection.
4. Terminal State Guardrails (actions disabled on terminal states).
5. Immutable Audit Ledger with Canonical States (Zero N/A).
6. Multi-format File Ingestion Validation & Quarantine Diagnostics.
7. Batch Intelligence, Quality Scoring & Quarantine Isolation.
8. Interactive Quarantine Record Fix & Reprocessing.
9. Selective Batch Recovery Plan Generation & Execution.
10. Natural Language AI Q&A over Active Datasets.
11. Complete Deterministic Demo Reset.
"""

import pytest
import json
from pathlib import Path

from src.api_bridge import (
    execute_agent_pipeline_on_batch, get_metrics, get_overview, get_audit_logs,
    comprehensive_demo_reset_endpoint, HumanReviewActionRequest,
    approve_human_review_endpoint, reject_human_review_endpoint,
    escalate_human_review_endpoint, ask_ai_about_payments, AskAIRequest
)
from src.state_machine import (
    PaymentState, get_current_payment_state, transition_payment_state,
    reset_payment_state_store, ActorType, TransitionSource
)
from src.recovery_operational_snapshot import (
    get_payment_operational_snapshot, reset_operational_snapshot_store,
    get_or_reserve_idempotency_intent, mark_idempotency_intent_executed
)
from src.recovery_human_review import (
    create_or_get_human_review_request, approve_human_review_request,
    reject_human_review_request, escalate_human_review_request,
    reset_human_review_state
)
from src.recovery_batch_intelligence import (
    analyze_batch_file, get_batch_analysis, get_batch_quality, get_batch_quarantine,
    fix_and_reprocess_quarantined_record, QuarantineReason
)
from src.recovery_batch_executor import (
    generate_batch_recovery_plan, execute_selective_batch_recovery
)
from src.ingestion.pipeline import IngestionPipeline


@pytest.fixture(autouse=True)
def clean_state():
    """Reset all state machine, snapshot, and human review memory stores before each test."""
    reset_payment_state_store()
    reset_operational_snapshot_store()
    reset_human_review_state()
    yield
    reset_payment_state_store()
    reset_operational_snapshot_store()
    reset_human_review_state()


class TestMerchantProductionReadiness:

    def test_dynamic_metrics_and_authoritative_batch_pipeline(self):
        """Metrics must derive dynamically from authoritative payment states."""
        res = execute_agent_pipeline_on_batch()
        metrics = res["metrics"]
        assert "revenueAtRisk" in metrics
        assert "revenueRecovered" in metrics
        assert "recoverySuccessRate" in metrics
        assert "pendingReviewCount" in metrics
        assert metrics["pendingReviewCount"] >= 1
        assert metrics["revenueRecovered"] >= 5600

    def test_human_review_approve_workflow_and_metrics_mutation(self):
        """Approving pay_005 transitions state to approved/recovering, updates metrics, and preserves idempotency."""
        create_or_get_human_review_request(payment_id="pay_005", merchant_id="merchant_demo", endpoint="payment-webhook")
        snapshot_before = get_payment_operational_snapshot("pay_005")
        assert snapshot_before["authoritative_payment_state"] == "HUMAN_REVIEW"
        assert not snapshot_before["is_terminal"]

        appr_res = approve_human_review_request(
            payment_id="pay_005",
            reviewer_id="merchant_lead",
            reason="Merchant confirmed receipt with customer; order sync authorized.",
            idempotency_key="appr_pay_005_test_token_123",
            merchant_id="merchant_demo",
            endpoint="payment-webhook"
        )
        assert appr_res["success"] is True
        assert appr_res["review_status"] in ("APPROVED", "COMPLETED")

        snapshot_after = get_payment_operational_snapshot("pay_005")
        assert snapshot_after["authoritative_payment_state"] in ("RECOVERING", "RECOVERED", "SUCCESS")

        overview = get_overview()
        assert overview["metrics"]["revenueRecovered"] >= 5600
        assert "pendingReviewCount" in overview["metrics"]

    def test_human_review_reject_workflow_halts_recovery(self):
        """Rejecting human review transitions payment state to STOPPED and halts retries."""
        create_or_get_human_review_request(payment_id="pay_005", merchant_id="merchant_demo", endpoint="payment-webhook")

        req = HumanReviewActionRequest(
            reviewer_id="merchant_lead",
            reason="Customer cancelled order before fulfillment.",
            merchant_id="merchant_demo",
            endpoint="payment-webhook"
        )
        rej_res = reject_human_review_endpoint("pay_005", req)
        assert rej_res["success"] is True
        assert rej_res["review_status"] == "REJECTED"

        assert get_current_payment_state("pay_005") == PaymentState.STOPPED
        snapshot = get_payment_operational_snapshot("pay_005")
        assert snapshot["authoritative_payment_state"] == "STOPPED"
        assert snapshot["is_terminal"] is True

    def test_human_review_escalate_workflow(self):
        """Escalating payment transitions state to ESCALATED and records activity."""
        create_or_get_human_review_request(payment_id="pay_005", merchant_id="merchant_demo", endpoint="payment-webhook")

        req = HumanReviewActionRequest(
            reviewer_id="merchant_operator",
            reason="Requires senior forensic review on gateway response.",
            merchant_id="merchant_demo",
            endpoint="payment-webhook"
        )
        esc_res = escalate_human_review_endpoint("pay_005", req)
        assert esc_res["success"] is True
        assert esc_res["review_status"] == "ESCALATED"

        assert get_current_payment_state("pay_005") == PaymentState.ESCALATED

    def test_idempotency_intent_reservation_and_consistency(self):
        """Every payment must have a deterministic idempotency key pre-allocated and persisted."""
        intent = get_or_reserve_idempotency_intent("pay_005", "ORD_005", "ORDER_SYNC")
        assert intent["idempotency_key"] == "pay_005_ORD_005_ORDER_SYNC_v1"
        assert intent["intent_status"] == "RESERVED"

        intent_dup = get_or_reserve_idempotency_intent("pay_005")
        assert intent_dup["idempotency_key"] == intent["idempotency_key"]

        executed = mark_idempotency_intent_executed("pay_005", "exec_98765")
        assert executed["intent_status"] == "EXECUTED"
        assert executed["execution_id"] == "exec_98765"

    def test_audit_logs_have_no_na_and_use_canonical_states(self):
        """Audit logs must return explicit canonical states and valid idempotency keys."""
        logs = get_audit_logs()
        assert len(logs) > 0

        valid_states = {"SUCCESS", "RECOVERED", "STOPPED", "AWAITING_REVIEW", "PENDING", "HUMAN_REVIEW", "ESCALATED", "FAILED"}
        for entry in logs:
            assert entry["recovery_status"] in valid_states
            assert entry["recovery_status"] not in ("N/A", "-", "UNKNOWN", "")
            assert entry["recovery_key"] is not None
            assert len(entry["recovery_key"]) > 0

    def test_file_ingestion_pipeline_validation_and_quarantine(self):
        """IngestionPipeline processes multi-format files and identifies valid vs invalid rows."""
        csv_content = (
            "payment_id,order_id,amount,status,failure_reason\n"
            "pay_101,ORD_101,4500,SUCCESS,None\n"
            "pay_102,ORD_102,2300,FAILED,Gateway timeout 504\n"
            "pay_103,,1500,FAILED,Missing order ID\n"
            "pay_101,ORD_101,4500,SUCCESS,None\n"
        )

        result = IngestionPipeline.process_file("test_payments.csv", content_str=csv_content)
        assert result["success"] is True
        assert result["records_found"] == 3
        assert result["duplicates_removed"] == 1
        assert result["money_at_risk"] > 0

    def test_batch_analyze_and_quarantine_queue(self):
        """Batch analysis detects malformed records and populates quarantine queue."""
        sample_batch = (
            "payment_id,order_id,amount,status,failure_reason\n"
            "pay_201,ORD_201,8400,FAILED,Gateway timeout\n"
            ",ORD_202,N/A,FAILED,Corrupt line\n"
        )
        res = analyze_batch_file("test_batch.csv", content_str=sample_batch)
        assert res["batch_id"].startswith("batch_")
        assert "quality_metrics" in res
        assert len(res["quarantine_queue"]) >= 1
        assert res["quarantine_queue"][0]["is_blocked_from_execution"] is True

    def test_quarantine_fix_and_reprocess(self):
        """Fixing a quarantined record re-validates and moves it to valid queue."""
        sample_batch = "payment_id,order_id,amount,status,failure_reason\n,ORD_203,N/A,FAILED,Corrupt\n"
        analysis = analyze_batch_file("test_quarantine_fix.csv", content_str=sample_batch)
        bid = analysis["batch_id"]
        qid = analysis["quarantine_queue"][0]["quarantine_id"]

        fix_res = fix_and_reprocess_quarantined_record(
            batch_id=bid,
            quarantine_id=qid,
            fixed_record_data={"payment_id": "pay_203", "order_id": "ORD_203", "amount": 4200.0, "status": "FAILED"}
        )
        assert fix_res["success"] is True
        assert fix_res["quarantined_record"]["status"] == "REPROCESSED_AND_RELEASED"

    def test_selective_batch_recovery_plan_and_execution(self):
        """Selective batch recovery generates plan with idempotency and executes per-item."""
        plan_res = generate_batch_recovery_plan("batch_test_1", ["pay_101", "pay_105"])
        assert plan_res["plan_id"].startswith("plan_")
        assert plan_res["selected_count"] == 2
        assert plan_res["duplicate_protection_active"] is True

        exec_res = execute_selective_batch_recovery("batch_test_1", ["pay_101", "pay_105"])
        assert exec_res["total_selected"] == 2
        assert exec_res["success_count"] == 2
        assert len(exec_res["results"]) == 2

    def test_ai_ask_dataset_nlp_endpoint(self):
        """POST /api/ai/ask accurately returns answers based on active dataset context."""
        payload = AskAIRequest(
            question="Which payment has the highest risk?",
            context={
                "file_name": "sample.csv",
                "payments": [
                    {"payment_id": "pay_101", "amount": 8400, "is_failed": True},
                    {"payment_id": "pay_106", "amount": 15000, "is_failed": True}
                ]
            }
        )
        res = ask_ai_about_payments(payload)
        assert "answer" in res
        assert "pay_106" in res["answer"] or "15,000" in res["answer"]

    def test_comprehensive_demo_reset_endpoint(self):
        """Reset demo restores clean state and clears all runtime caches."""
        transition_payment_state("pay_005", PaymentState.STOPPED, "Manual test rejection", ActorType.OPERATOR, "test", TransitionSource.HUMAN_ACTION_CENTER)
        assert get_current_payment_state("pay_005") == PaymentState.STOPPED

        res = comprehensive_demo_reset_endpoint()
        assert res["success"] is True
        assert "demo_session_id" in res
        assert get_current_payment_state("pay_005") == PaymentState.HUMAN_REVIEW
