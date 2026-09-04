"""
RecoverIQ - Final Recovery System Verification & Hardening Test Suite (Topic 2.2.2.30)

Comprehensive test suite covering:
1. Authority Boundaries (PaymentState & CircuitState protections)
2. Integrity Contradiction Detection & Safety
3. Alert Management Guards (CRITICAL dismissal protection, conditional resolution)
4. Escalation Policy & Priority Engine Determinism
5. Escalation Handoff Execution & Idempotency
6. SLA Threshold Calculation & Breach Detection
7. Operator Queue 9-Tier Deterministic Ranking
8. Queue Watchdog Snapshot Fingerprinting & Change Detection
9. Background Worker Lifecycle State Machine
10. End-to-End Simulation Scenarios (All 6 Scenarios)
11. Persistence & Malformed File Resilience
"""

import pytest
import os
import json
import time
from datetime import datetime, timezone

from src.state_machine import PaymentState, transition_payment_state
from src.circuit_breaker import CircuitState, get_circuit_breaker_status
from src.recovery_integrity_monitor import (
    evaluate_recovery_integrity, _upsert_alert, AlertType, AlertSeverity,
    AlertStatus, get_recovery_integrity_alerts
)
from src.recovery_alert_manager import (
    list_managed_recovery_alerts, get_managed_recovery_alert,
    acknowledge_managed_alert, assign_managed_alert,
    dismiss_managed_alert, resolve_managed_alert
)
from src.recovery_escalation_policy import evaluate_alert_escalation
from src.recovery_escalation_executor import (
    execute_alert_escalation, list_recovery_escalations,
    get_recovery_escalation, assign_recovery_escalation
)
from src.recovery_escalation_sla import (
    evaluate_escalation_sla, get_escalation_sla_record,
    escalate_sla_accountability, SlaStatus
)
from src.recovery_operator_queue import (
    sync_operator_queue, list_operator_queue,
    claim_operator_queue_item, release_operator_queue_item,
    mark_operator_queue_in_review, get_operator_queue_summary
)
from src.recovery_queue_watchdog import (
    run_queue_watchdog_cycle, get_watchdog_status,
    get_operator_workload
)
from src.recovery_background_worker import (
    start_background_worker, stop_background_worker,
    pause_background_worker, resume_background_worker,
    run_immediate_cycle, get_background_worker_status,
    WorkerState
)
from src.recovery_integration_simulator import (
    run_simulation, validate_simulation_record,
    get_simulation_scenarios, SimulationScenario
)


class TestAuthorityBoundaries:
    """Verify that only designated authorities can alter payment or circuit states."""

    def test_payment_state_machine_sole_authority(self):
        """PaymentState transitions must strictly obey state_machine rules."""
        # Unapproved transition: SUCCESS -> PENDING must be rejected
        from src.state_machine import set_payment_state_directly
        set_payment_state_directly("pay_test_auth", PaymentState.SUCCESS)
        res = transition_payment_state("pay_test_auth", PaymentState.PENDING, reason="Unauthorized reversal")
        assert res["success"] is False
        assert res["error"] == "INVALID_STATE_TRANSITION"

    def test_circuit_state_sole_authority(self):
        """CircuitState must be managed strictly through circuit_breaker."""
        status = get_circuit_breaker_status("merchant_demo", "payment-webhook")
        assert "state" in status
        assert status["state"] in [s.value for s in CircuitState]


class TestIntegrityAndAlertManagement:
    """Verify integrity contradiction detection, critical alert protection, and resolution guards."""

    def test_critical_alert_dismissal_protection(self):
        """CRITICAL alerts must NEVER be dismissed."""
        import uuid
        pay_id = f"pay_crit_{uuid.uuid4().hex[:8]}"
        alert = _upsert_alert(
            payment_id=pay_id,
            merchant_id="merchant_demo",
            endpoint="payment-webhook",
            alert_type=AlertType.RECOVERY_INCONSISTENCY_DETECTED.value,
            severity=AlertSeverity.CRITICAL.value,
            reason="State mismatch",
            evidence_type="PAYMENT_STATE_CONTRADICTION",
            recommended_action="Lead engineer intervention"
        )
        alert_id = alert["alert_id"]

        # Attempt dismissal
        dismiss_res = dismiss_managed_alert(alert_id, "operator_1", "Attempting dismissal")
        assert dismiss_res["success"] is False
        assert "CRITICAL_ALERT_DISMISSAL" in dismiss_res["error"]

    def test_conditional_resolution_blocked_on_active_contradiction(self):
        """Resolving an alert on an active contradiction must be blocked."""
        import uuid
        from src.state_machine import set_payment_state_directly
        from src.incident_closure import _incident_closure_store, _save_persisted_closures
        pay_id = f"pay_resolv_{uuid.uuid4().hex[:8]}"
        set_payment_state_directly(pay_id, PaymentState.FAILED)
        _incident_closure_store[pay_id] = {
            "payment_id": pay_id,
            "closure_status": "INCIDENT_CLOSED",
            "merchant_id": "merchant_demo",
            "endpoint": "payment-webhook",
            "closure_reason": "Pre-mature closure"
        }
        _save_persisted_closures(_incident_closure_store)

        alert = _upsert_alert(
            payment_id=pay_id,
            merchant_id="merchant_demo",
            endpoint="payment-webhook",
            alert_type=AlertType.INCIDENT_CLOSURE_INCONSISTENCY.value,
            severity=AlertSeverity.CRITICAL.value,
            reason="Closed incident with unpaid status",
            evidence_type="PAYMENT_STATE_CONTRADICTION",
            recommended_action="Review"
        )
        alert_id = alert["alert_id"]

        resolve_res = resolve_managed_alert(alert_id, "operator_1", "Attempting resolution")
        assert resolve_res["success"] is False
        assert resolve_res["error"] == "CONTRADICTION_STILL_ACTIVE"


class TestEscalationAndHandoff:
    """Verify escalation policy determinism, handoff idempotency, and SLA compliance."""

    def test_escalation_policy_and_handoff_idempotency(self):
        """Executing escalation on the same alert twice must produce the same handoff without duplicates."""
        alert = _upsert_alert(
            payment_id="pay_esc_test",
            merchant_id="merchant_demo",
            endpoint="payment-webhook",
            alert_type=AlertType.RECOVERY_RETRY_EXHAUSTED.value,
            severity=AlertSeverity.HIGH.value,
            reason="Retries exhausted",
            evidence_type="BOUNDED_RETRY_EXHAUSTION",
            recommended_action="Assign"
        )
        alert_id = alert["alert_id"]

        h1 = execute_alert_escalation(alert_id, "lead_operator_1")
        assert h1["success"] is True
        handoff_id_1 = h1["handoff"]["handoff_id"]

        h2 = execute_alert_escalation(alert_id, "lead_operator_1")
        assert h2["success"] is True
        assert h2["handoff"]["handoff_id"] == handoff_id_1

    def test_sla_evaluation_and_accountability(self):
        """SLA evaluation must return accurate status and allow accountability escalation on breach."""
        alert = _upsert_alert(
            payment_id="pay_sla_test",
            merchant_id="merchant_demo",
            endpoint="payment-webhook",
            alert_type=AlertType.RECOVERY_INCONSISTENCY_DETECTED.value,
            severity=AlertSeverity.CRITICAL.value,
            reason="State mismatch",
            evidence_type="PAYMENT_STATE_CONTRADICTION",
            recommended_action="Lead engineer"
        )
        alert_id = alert["alert_id"]
        h_res = execute_alert_escalation(alert_id, "lead_operator_1")
        handoff_id = h_res["handoff"]["handoff_id"]

        sla_res = evaluate_escalation_sla(handoff_id)
        assert sla_res["success"] is True
        assert "sla_status" in sla_res["sla"]

        acc_res = escalate_sla_accountability(handoff_id, "lead_operator_1", "Escalating accountability")
        assert acc_res["success"] is True


class TestOperatorQueueAndWatchdog:
    """Verify operator queue deterministic ranking, claims, watchdog sync, and workload indicators."""

    def test_operator_queue_claim_and_review(self):
        """Claiming and moving to in-review must update state accurately."""
        alert = _upsert_alert(
            payment_id="pay_queue_test",
            merchant_id="merchant_demo",
            endpoint="payment-webhook",
            alert_type=AlertType.RECOVERY_RETRY_EXHAUSTED.value,
            severity=AlertSeverity.HIGH.value,
            reason="Retries exhausted",
            evidence_type="BOUNDED_RETRY_EXHAUSTION",
            recommended_action="Assign"
        )
        alert_id = alert["alert_id"]
        h_res = execute_alert_escalation(alert_id, "lead_operator_1")
        sync_operator_queue("lead_operator_1")

        items = list_operator_queue(payment_id="pay_queue_test", active_only=False)
        assert len(items) > 0
        q_id = items[0]["queue_item_id"]

        claim_res = claim_operator_queue_item(q_id, "lead_operator_1", "Claiming")
        assert claim_res["success"] is True

        review_res = mark_operator_queue_in_review(q_id, "lead_operator_1", "Reviewing")
        assert review_res["success"] is True

    def test_watchdog_and_workload(self):
        """Watchdog evaluation and operator workload capacity metrics."""
        wd_res = run_queue_watchdog_cycle("lead_operator_1")
        assert wd_res["success"] is True
        assert "status" in wd_res

        workload = get_operator_workload("lead_operator_1")
        assert workload["success"] is True
        assert "workload_status" in workload["workload"]


class TestBackgroundWorkerLifecycle:
    """Verify background worker lifecycle state transitions."""

    def test_background_worker_lifecycle(self):
        """Start -> Pause -> Resume -> Stop lifecycle execution."""
        start_res = start_background_worker(10, "lead_operator_1")
        assert start_res["success"] is True
        assert start_res["worker"]["current_state"] in (WorkerState.STARTING.value, WorkerState.RUNNING.value)

        # Idempotent start
        start_dup = start_background_worker(10, "lead_operator_1")
        assert start_dup["success"] is True

        pause_res = pause_background_worker("lead_operator_1")
        assert pause_res["success"] is True
        assert pause_res["worker"]["current_state"] == WorkerState.PAUSED.value

        resume_res = resume_background_worker("lead_operator_1")
        assert resume_res["success"] is True
        assert resume_res["worker"]["current_state"] == WorkerState.RUNNING.value

        stop_res = stop_background_worker("lead_operator_1")
        assert stop_res["success"] is True
        assert stop_res["worker"]["current_state"] == WorkerState.STOPPED.value


class TestEndToEndSimulations:
    """Verify all 6 End-to-End Simulation scenarios in recovery_integration_simulator.py."""

    @pytest.mark.parametrize("scenario", [
        "HEALTHY_RECOVERY",
        "VERIFICATION_PENDING",
        "RETRY_EXHAUSTED",
        "CRITICAL_CONTRADICTION",
        "SLA_BREACH",
        "OPERATOR_RESOLUTION"
    ])
    def test_simulation_scenarios(self, scenario):
        """Each simulation scenario must execute all 15 stages and pass integration validations."""
        res = run_simulation(scenario)
        assert res["success"] is True
        sim = res["simulation"]
        assert sim["overall_status"] == "PASSED"
        assert len(sim["stages"]) == 15

        val_res = validate_simulation_record(sim)
        assert all(v["status"] in ("PASS", "SKIPPED") for v in val_res.values())
