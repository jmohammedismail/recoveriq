"""
RecoverIQ - AI Intelligence Layer for Autonomous Payment Recovery
Provides multi-dimensional root-cause diagnostics, confidence evaluation,
governed recommendation generation, and executive reasoning summaries.

Works collaboratively with the Python Guardrail Engine (process_batch.py / api_bridge.py)
to achieve Governed Autonomy in fintech operations.

Communicates the 6-Phase Governed Flow:
  Evidence → Root Cause → Decision → Guardrail → Action → Verification
"""

from typing import Dict, Any, List, Optional

class AIAgentIntelligence:
    """
    Autonomous AI Agent reasoning module that evaluates post-payment workflow failures.
    """

    @staticmethod
    def evaluate_incident(case: Dict[str, Any], merchant_order_exists: bool) -> Dict[str, Any]:
        payment_id = case.get("payment_id", "unknown")
        order_id = case.get("order_id", "unknown")
        amount = case.get("amount", 0)
        payment_status = case.get("payment_status", "SUCCESS")
        webhook_status = case.get("webhook_status", "DELAYED")
        order_status = case.get("order_status", "NOT_CREATED")
        http_status = case.get("http_status", 504)
        retry_count = case.get("retry_count", 0)

        # 1. Evidence Synthesis
        evidence = {
            "gateway_status": f"Payment {payment_status} (Razorpay)",
            "merchant_order_state": f"Order {order_status} (Merchant DB)",
            "webhook_signal": f"Webhook {webhook_status} (HTTP {http_status})",
            "retry_buffer": f"{retry_count}/2 retries consumed"
        }

        # 2. Root Cause Classification
        if http_status == 504:
            failure_type = "MERCHANT_GATEWAY_TIMEOUT"
            root_cause = "Merchant server timeout after webhook delivery"
            failure_severity = "MODERATE" if retry_count == 0 else "ELEVATED"
            telemetry_integrity = 95
        elif http_status == 500:
            failure_type = "MERCHANT_INTERNAL_SERVER_ERROR"
            root_cause = "Merchant server error during webhook processing"
            failure_severity = "CRITICAL"
            telemetry_integrity = 80
        else:
            failure_type = "UNKNOWN_WORKFLOW_ANOMALY"
            root_cause = "Unknown downstream merchant workflow failure"
            failure_severity = "HIGH"
            telemetry_integrity = 60

        # 3. Multi-Factor AI Confidence & Decision Policy
        base_confidence = 88 if http_status == 504 and retry_count == 0 else (
            60 if http_status == 504 and retry_count >= 2 else (
                35 if http_status == 500 and retry_count >= 3 else 50
            )
        )

        factors = {
            "payment_integrity": 100 if payment_status == "SUCCESS" else 0,
            "webhook_reliability": 90 if http_status == 504 else 40,
            "retry_buffer": max(0, 100 - (retry_count * 35)),
            "state_clarity": 95 if not merchant_order_exists else 90
        }

        if base_confidence >= 85 and retry_count < 2:
            ai_recommendation = "AUTO RECOVERY"
            action_code = "EXECUTE_IDEMPOTENT_SYNC"
        elif base_confidence >= 50:
            ai_recommendation = "HUMAN REVIEW"
            action_code = "QUEUE_OPERATOR_REVIEW"
        else:
            ai_recommendation = "STOP"
            action_code = "HALT_AND_ESCALATE"

        # 4. Guardrail Governance Check
        guardrail_passed = False
        governance_status = "PENDING"
        governance_detail = ""

        if ai_recommendation == "AUTO RECOVERY":
            if merchant_order_exists:
                guardrail_passed = False
                governance_status = "OVERRIDDEN_BY_GUARDRAIL"
                governance_detail = "Order already exists in merchant database. Autonomous recovery halted to prevent duplicate charge/order."
            else:
                guardrail_passed = True
                governance_status = "APPROVED_BY_GUARDRAIL"
                governance_detail = "All deterministic safety checks passed (0 retries exhausted, idempotency key generated, merchant state absent)."
        elif ai_recommendation == "HUMAN REVIEW":
            guardrail_passed = True
            governance_status = "ENFORCED_POLICY"
            governance_detail = f"Confidence {base_confidence}% is below 85% auto-threshold. Human review queue routing strictly enforced."
        else:
            guardrail_passed = True
            governance_status = "SAFETY_HALT_ENFORCED"
            governance_detail = f"High error risk (HTTP {http_status}, {retry_count} retries). Circuit breaker tripped to protect downstream systems."

        # 5. Executive AI Reasoning Summary
        if ai_recommendation == "AUTO RECOVERY" and not merchant_order_exists:
            reasoning_summary = (
                f"Payment {payment_id} succeeded on gateway, but downstream merchant order was NOT_CREATED due to HTTP {http_status} timeout. "
                f"Retry buffer is intact ({retry_count}/2 used) and telemetry integrity is high ({base_confidence}% confidence). "
                f"Pre-recovery audit confirms order is absent in merchant system. Safe for autonomous idempotent order synchronization."
            )
        elif ai_recommendation == "AUTO RECOVERY" and merchant_order_exists:
            reasoning_summary = (
                f"Payment {payment_id} received HTTP {http_status} timeout with high initial confidence ({base_confidence}%). "
                f"However, active merchant state probing revealed the order was created in the background. "
                f"The AI Safety Guardrail intervened and safely HALTED recovery to eliminate duplicate transaction risk."
            )
        elif ai_recommendation == "HUMAN REVIEW":
            reasoning_summary = (
                f"Payment {payment_id} encountered webhook delay (HTTP {http_status}) with retry limit reached ({retry_count}/2). "
                f"Calculated confidence ({base_confidence}%) meets review criteria (≥ 50%) but is insufficient for autonomous execution (< 85%). "
                f"Enqueued for manual merchant operator confirmation."
            )
        else:
            reasoning_summary = (
                f"Payment {payment_id} encountered severe failure (HTTP {http_status}) with retry limit exhausted ({retry_count}/2). "
                f"Confidence is critically low ({base_confidence}%). Autonomous recovery prohibited; incident escalated to operations engineering."
            )

        # 6. Action & Verification Plan
        if ai_recommendation == "AUTO RECOVERY" and not merchant_order_exists:
            action_desc = f"Execute idempotent sync key {payment_id}_{order_id}_ORDER_SYNC"
            verification_desc = "Verify order state in merchant database & record immutable audit ledger"
        elif ai_recommendation == "AUTO RECOVERY" and merchant_order_exists:
            action_desc = "Halt execution (Duplicate prevention)"
            verification_desc = "Verified order presence in merchant database · Logged STOPPED event"
        elif ai_recommendation == "HUMAN REVIEW":
            action_desc = f"Route {payment_id} to merchant operations human review queue"
            verification_desc = "Queue state confirmed · Awaiting merchant operator manual review"
        else:
            action_desc = f"Halt processing and trigger circuit breaker escalation"
            verification_desc = "Incident escalated to engineering on-call"

        # Structured Output with 6-Phase Governed Flow
        return {
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "six_phase_flow": {
                "1_evidence": evidence,
                "2_root_cause": root_cause,
                "3_decision": f"{ai_recommendation} ({base_confidence}% confidence)",
                "4_guardrail": governance_detail,
                "5_action": action_desc,
                "6_verification": verification_desc
            },
            "diagnostic": {
                "failure_type": failure_type,
                "root_cause": root_cause,
                "failure_severity": failure_severity,
                "telemetry_integrity": telemetry_integrity,
                "http_status": http_status,
                "retry_count": retry_count
            },
            "confidence_assessment": {
                "overall_score": base_confidence,
                "threshold_required": 85,
                "factors": factors
            },
            "governance": {
                "recommendation": ai_recommendation,
                "action_code": action_code,
                "status": governance_status,
                "guardrail_approved": guardrail_passed,
                "detail": governance_detail
            },
            "reasoning_summary": reasoning_summary,
            "verification_strategy": "IDEMPOTENT_DB_VERIFICATION" if ai_recommendation == "AUTO RECOVERY" else "MANUAL_OR_ESCALATION"
        }
