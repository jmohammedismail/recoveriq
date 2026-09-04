"""
RecoverIQ - Test TXT Delimiter and Separator Cleaning
Verifies that decorative separators like '--------------------------------'
and trailing dashes are cleanly stripped from failure_reason / problem.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.pipeline import IngestionPipeline


def test_txt_with_separators():
    txt_content = """
    ==================================================
    RECOVERIQ PAYMENT INCIDENT LOG
    ==================================================

    Payment ID: pay_101
    Amount: 6200
    Status: FAILED
    Failure Reason: Customer card expired --------------------------------
    --------------------------------------------------

    Payment ID: pay_102
    Amount: ₹2,500
    Status: FAILED
    Problem: Payment gateway connection failure====================
    Root Cause: Merchant server unavailable
    --------------------------------------------------

    Payment ID: pay_103
    Amount: ₹12,000
    Status: FAILED
    Failure Reason: Internal server error (HTTP 500)
    --------------------------------------------------

    Payment ID: pay_104
    Amount: ₹5,600
    Status: SUCCESS
    Failure Reason: No failure detected
    __________________________________________________
    """

    res = IngestionPipeline.process_file("test_delimiters.txt", content_str=txt_content)
    assert res["records_found"] == 4, f"Expected 4 records, got {res['records_found']}"
    
    pay_101 = next(p for p in res["payments"] if p["payment_id"] == "pay_101")
    print(f"pay_101 failure_reason: '{pay_101['failure_reason']}'")
    assert pay_101["failure_reason"] == "Customer card expired", f"Unexpected failure_reason: {pay_101['failure_reason']}"
    assert pay_101["problem"] == "Customer card expired"
    assert pay_101["amount"] == 6200
    assert pay_101["status"] == "FAILED"

    pay_102 = next(p for p in res["payments"] if p["payment_id"] == "pay_102")
    print(f"pay_102 problem: '{pay_102['problem']}'")
    assert pay_102["problem"] == "Payment gateway connection failure"

    pay_104 = next(p for p in res["payments"] if p["payment_id"] == "pay_104")
    print(f"pay_104 problem: '{pay_104['problem']}'")
    assert pay_104["problem"] == "No payment failure detected"
    assert pay_104["status"] == "SUCCESS"
    assert pay_104["recommendation"] == "No Action"
    assert pay_104["action"] == "Healthy"

    print("\nALL TXT DELIMITER CLEANING TESTS PASSED!")


if __name__ == "__main__":
    test_txt_with_separators()
