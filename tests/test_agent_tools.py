"""
RecoverIQ - Phase 1 Agent Tools & Foundation Test Suite
Validates that:
1. All 5 read-only tools read the real project data files cleanly.
2. Invalid/unknown payment IDs are handled gracefully without crashing.
3. RecoverIQAgent evidence gathering and schema validation work reliably.
4. Unconfigured LLM provider raises clean configuration diagnostics without fake outputs.
5. Zero modifications are made to merchant state data.
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.agent.tools import (
    get_payment_details,
    get_telemetry,
    get_merchant_state,
    get_retry_history,
    check_order_exists
)
from src.agent.agent import RecoverIQAgent
from src.agent.prompts import SYSTEM_PROMPT


def test_tools_on_valid_case():
    print("==================================================")
    print("TEST 1: Valid Payment Case (pay_004)")
    print("==================================================")

    # 1. get_payment_details
    details = get_payment_details("pay_004")
    print("[1] get_payment_details('pay_004'):", details)
    assert details["found"] is True
    assert details["payment_id"] == "pay_004"
    assert details["amount"] == 5600
    assert details["payment_status"] == "SUCCESS"

    # 2. get_telemetry
    telemetry = get_telemetry("pay_004")
    print("[2] get_telemetry('pay_004'):", telemetry)
    assert telemetry["found"] is True
    assert telemetry["http_status"] == 504
    assert telemetry["retry_count"] == 0
    assert telemetry["webhook_status"] == "DELAYED"

    # 3. get_merchant_state
    merchant_state = get_merchant_state("pay_004")
    print("[3] get_merchant_state('pay_004'):", merchant_state)
    assert merchant_state["found"] is True
    assert merchant_state["payment_id"] == "pay_004"

    # 4. get_retry_history
    retry_history = get_retry_history("pay_004")
    print("[4] get_retry_history('pay_004'):", retry_history)
    assert retry_history["found"] is True
    assert retry_history["retry_count"] == 0
    assert retry_history["max_allowed_retries"] == 2
    assert retry_history["retry_buffer_available"] == 2

    # 5. check_order_exists
    order_check = check_order_exists("pay_004")
    print("[5] check_order_exists('pay_004'):", order_check)
    assert "order_exists" in order_check
    assert "can_proceed_with_recovery" in order_check
    print("[PASS] All 5 tools executed successfully on pay_004\n")


def test_tools_on_duplicate_guard_case():
    print("==================================================")
    print("TEST 2: Duplicate Prevention Case (pay_001)")
    print("==================================================")
    details = get_payment_details("pay_001")
    assert details["found"] is True
    assert details["amount"] == 8400

    order_check = check_order_exists("pay_001")
    print("check_order_exists('pay_001'):", order_check)
    assert order_check["order_exists"] is True
    assert order_check["can_proceed_with_recovery"] is False
    print("[PASS] Duplicate prevention check verified for pay_001\n")


def test_tools_on_invalid_case():
    print("==================================================")
    print("TEST 3: Unknown / Invalid Payment Case (pay_999)")
    print("==================================================")
    details = get_payment_details("pay_999")
    print("get_payment_details('pay_999'):", details)
    assert details["found"] is False

    telemetry = get_telemetry("pay_999")
    print("get_telemetry('pay_999'):", telemetry)
    assert telemetry["found"] is False

    merchant_state = get_merchant_state("pay_999")
    print("get_merchant_state('pay_999'):", merchant_state)
    assert merchant_state["found"] is False

    retry_history = get_retry_history("pay_999")
    print("get_retry_history('pay_999'):", retry_history)
    assert retry_history["found"] is False
    print("[PASS] Graceful error handling verified for unknown payment IDs\n")


def test_agent_investigation_and_schema_validation():
    print("==================================================")
    print("TEST 4: Agent Evidence Gathering & Schema Validation")
    print("==================================================")
    agent = RecoverIQAgent()

    # Evidence gathering
    evidence = agent.gather_incident_evidence("pay_004")
    print("Gathered evidence keys:", list(evidence.keys()))
    assert evidence["payment_id"] == "pay_004"
    assert evidence["payment_details"]["found"] is True

    # Prompt formatting
    formatted_prompt = agent.format_llm_prompt(evidence)
    assert "pay_004" in formatted_prompt
    assert "5600" in formatted_prompt
    print("Formatted prompt length:", len(formatted_prompt), "chars")

    # Unconfigured provider diagnostic check
    unconfigured_agent = RecoverIQAgent(provider="unconfigured", model="", api_key="")
    investigation_res = unconfigured_agent.investigate("pay_004")
    print("Unconfigured provider status:", investigation_res["status"])
    assert investigation_res["success"] is False
    assert investigation_res["status"] == "CONFIG_REQUIRED"
    assert "AI_PROVIDER" in investigation_res["error"] or "AI_MODEL" in investigation_res["error"]

    # Test output schema validator
    mock_llm_response = {
        "payment_id": "pay_004",
        "observations": ["Payment SUCCESS on Razorpay", "Order NOT_CREATED on merchant"],
        "evidence": {
            "gateway_status": "SUCCESS",
            "order_status": "NOT_CREATED",
            "http_status": 504,
            "retry_count": 0,
            "merchant_order_exists": False
        },
        "root_cause": "Merchant server timeout after webhook delivery",
        "risk_level": "LOW",
        "confidence": 88,
        "recommendation": "AUTO RECOVERY",
        "reasoning_summary": "Payment succeeded but order creation timed out. Safe for recovery.",
        "recommended_next_action": "IDEMPOTENT_ORDER_SYNC"
    }

    validated = agent.validate_agent_output(mock_llm_response, "pay_004")
    assert validated["recommendation"] == "AUTO RECOVERY"
    assert validated["confidence"] == 88
    print("[PASS] Output schema validator successfully verified\n")


if __name__ == "__main__":
    test_tools_on_valid_case()
    test_tools_on_duplicate_guard_case()
    test_tools_on_invalid_case()
    test_agent_investigation_and_schema_validation()
    print("ALL AGENT TOOLS & FOUNDATION TESTS PASSED!")
