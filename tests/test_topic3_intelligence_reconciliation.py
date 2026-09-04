"""
RecoverIQ - Topic 3 Comprehensive Verification Test Suite
Tests for AI Explainability, 4-Way Reconciliation, Distributed Tracing,
Batch Ingestion Intelligence, Quarantine Queue, and Selective Batch Recovery.
"""

import pytest
from src.recovery_ai_explainability import (
    evaluate_ai_decision_explanation, get_ai_decision_explanation,
    AIDecisionType, AIRiskLevel
)
from src.recovery_reconciliation import (
    evaluate_payment_reconciliation, get_payment_reconciliation,
    list_reconciliation_mismatches, ReconciliationStatus, ContradictionType
)
from src.recovery_trace import (
    generate_deterministic_trace_for_payment, get_distributed_trace,
    get_payment_distributed_traces
)
from src.recovery_batch_intelligence import (
    analyze_batch_file, get_batch_analysis, get_batch_quality,
    get_batch_quarantine, fix_and_reprocess_quarantined_record, QuarantineReason
)
from src.recovery_batch_executor import (
    generate_batch_recovery_plan, execute_selective_batch_recovery,
    get_batch_execution_status
)
from src.state_machine import get_current_payment_state, PaymentState
from src.circuit_breaker import get_circuit_breaker_status


class TestAIDecisionExplainability:
    """Tests for deterministic AI Decision Explainability (Topic 3 Capability 1)."""

    def test_auto_recovery_high_confidence(self):
        exp = evaluate_ai_decision_explanation(
            payment_id="pay_test_auto_exp",
            case_data={
                "amount": 5600.0,
                "http_status": 504,
                "retry_count": 0,
                "payment_status": "SUCCESS",
                "merchant_order_exists": False
            }
        )
        assert exp["decision"] == AIDecisionType.AUTO_RECOVER.value
        assert exp["confidence"] >= 85.0
        assert exp["risk_level"] == AIRiskLevel.LOW.value
        assert "HTTP 504" in exp["why_this_decision"] or "transient" in exp["why_this_decision"].lower()
        assert len(exp["why_not_auto_recover"]) == 0
        assert len(exp["evidence"]) > 0

    def test_human_review_when_retries_exhausted(self):
        exp = evaluate_ai_decision_explanation(
            payment_id="pay_test_hr_exp",
            case_data={
                "amount": 5600.0,
                "http_status": 504,
                "retry_count": 2,
                "payment_status": "SUCCESS",
                "merchant_order_exists": False
            }
        )
        assert exp["decision"] == AIDecisionType.HUMAN_REVIEW.value
        assert len(exp["why_not_auto_recover"]) > 0
        assert any("retry" in r.lower() for r in exp["why_not_auto_recover"])

    def test_stop_when_order_already_exists(self):
        exp = evaluate_ai_decision_explanation(
            payment_id="pay_test_stop_dup",
            case_data={
                "amount": 5600.0,
                "http_status": 200,
                "retry_count": 0,
                "payment_status": "SUCCESS",
                "merchant_order_exists": True
            }
        )
        assert exp["decision"] == AIDecisionType.STOP.value
        assert exp["recommended_action"] == "NO_ACTION_ORDER_ALREADY_EXISTS"
        assert any("already confirmed" in r.lower() for r in exp["why_not_auto_recover"])


class TestPaymentReconciliation:
    """Tests for 4-Way Reconciliation Engine (Topic 3 Capability 2)."""

    def test_reconciliation_mismatch_detection(self):
        rec = evaluate_payment_reconciliation(
            payment_id="pay_test_recon_mismatch",
            case_data={
                "amount": 3100.0,
                "payment_status": "SUCCESS",
                "merchant_order_exists": False,
                "webhook_status": "DELAYED"
            }
        )
        assert rec["reconciliation_status"] == ReconciliationStatus.MISMATCH.value
        assert rec["contradiction_type"] == ContradictionType.GATEWAY_SUCCESS_MERCHANT_NOT_CREATED.value
        assert rec["recommended_action"] == "IDEMPOTENT_ORDER_SYNC"
        assert len(rec["discrepancies"]) >= 2
        assert rec["vectors"]["gateway"]["verified"] is True
        assert rec["vectors"]["merchant"]["verified"] is False

    def test_reconciliation_contradiction_detection(self):
        rec = evaluate_payment_reconciliation(
            payment_id="pay_test_recon_contradiction",
            case_data={
                "amount": 7500.0,
                "payment_status": "FAILED",
                "merchant_order_exists": True
            }
        )
        assert rec["reconciliation_status"] == ReconciliationStatus.CONTRADICTION.value
        assert rec["contradiction_type"] == ContradictionType.MERCHANT_CREATED_GATEWAY_FAILED.value
        assert "Risk" in rec["reason"] or "Critical" in rec["reason"]

    def test_reconciliation_does_not_mutate_payment_state(self):
        pid = "pay_test_recon_read_only"
        initial_state = get_current_payment_state(pid)
        evaluate_payment_reconciliation(payment_id=pid, case_data={"payment_status": "SUCCESS", "merchant_order_exists": False})
        after_state = get_current_payment_state(pid)
        assert initial_state == after_state


class TestDistributedTracing:
    """Tests for Distributed Tracing & Observability (Topic 3 Capability 3)."""

    def test_trace_generation_and_spans(self):
        pid = "pay_test_trace_01"
        trace = generate_deterministic_trace_for_payment(pid, http_status=504)
        assert trace["payment_id"] == pid
        assert trace["trace_id"].startswith("tr_")
        assert trace["span_count"] == 5
        assert trace["total_latency_ms"] > 0

        # Check required services in spans
        services = [s["service"] for s in trace["spans"]]
        assert "api_gateway" in services
        assert "payment_service" in services
        assert "webhook_service" in services
        assert "recovery_ai_engine" in services
        assert "merchant_api" in services

        # Check AI diagnostics transparency
        assert trace["ai_diagnostics"]["telemetry_source"] == "MOCKED_FOR_DEMO"
        assert trace["ai_diagnostics"]["mock_indicator"] is True

    def test_trace_lookup_by_payment(self):
        pid = "pay_test_trace_lookup"
        traces = get_payment_distributed_traces(pid)
        assert len(traces) >= 1
        assert traces[0]["payment_id"] == pid


class TestBatchIntelligenceAndQuarantine:
    """Tests for Batch File Quality & Quarantine Isolation (Topic 3 Capability 4)."""

    def test_batch_ingestion_and_quality_metrics(self):
        csv_content = """payment_id,order_id,amount,http_status,retry_count,payment_status
pay_b1,ORD_b1,2500,504,0,SUCCESS
pay_b2,ORD_b2,3100,504,0,SUCCESS
,ORD_b3,4000,500,1,SUCCESS
pay_b4,ORD_b4,INVALID_AMT,504,0,SUCCESS
"""
        batch = analyze_batch_file(filename="test_batch.csv", content_str=csv_content)
        assert batch["batch_id"].startswith("batch_")
        assert batch["quality_metrics"]["total_records"] >= 4
        assert batch["quality_metrics"]["valid_count"] == 2
        assert batch["quality_metrics"]["malformed_count"] == 2

        # Check quarantine queue isolation
        quarantine = batch["quarantine_queue"]
        assert len(quarantine) == 2
        assert any(q["quarantine_reason"] == QuarantineReason.MISSING_PAYMENT_ID.value for q in quarantine)
        assert all(q["is_blocked_from_execution"] is True for q in quarantine)

    def test_fix_and_reprocess_quarantined_record(self):
        csv_content = """payment_id,order_id,amount,http_status,retry_count,payment_status
,ORD_q_fix,4500,504,0,SUCCESS
"""
        batch = analyze_batch_file(filename="test_q_fix.csv", content_str=csv_content)
        bid = batch["batch_id"]
        qid = batch["quarantine_queue"][0]["quarantine_id"]

        fix_res = fix_and_reprocess_quarantined_record(
            batch_id=bid,
            quarantine_id=qid,
            fixed_record_data={"payment_id": "pay_fixed_001", "amount": 4500.0, "order_id": "ORD_q_fix"}
        )
        assert fix_res["success"] is True
        assert fix_res["quarantined_record"]["status"] == "REPROCESSED_AND_RELEASED"


class TestSelectiveBatchRecovery:
    """Tests for Selective Batch Recovery (Topic 3 Capability 5)."""

    def test_batch_recovery_plan_generation(self):
        plan = generate_batch_recovery_plan(
            batch_id="batch_plan_test",
            selected_payment_ids=["pay_002", "pay_005"]
        )
        assert plan["selected_count"] == 2
        assert plan["total_recovery_amount"] == 5600.0
        assert plan["duplicate_protection_active"] is True
        assert len(plan["items"]) == 2

    def test_selective_batch_recovery_execution(self):
        exec_res = execute_selective_batch_recovery(
            batch_id="batch_exec_test",
            selected_payment_ids=["pay_002", "pay_005"]
        )
        assert exec_res["total_selected"] == 2
        assert exec_res["success_count"] == 2
        assert exec_res["total_recovered_amount"] == 5600.0
        for item in exec_res["results"]:
            assert item["final_status"] == "RECOVERED"
            assert len(item["stages"]) == 4
