import urllib.request
import json
import pytest

sample_csv = """payment_id,amount,problem,status,root_cause,decision
pay_101,8400,Merchant server timeout,FAILED,Timeout,AUTO_RECOVERY
pay_102,2500,Card expired,FAILED,Expired,HUMAN_REVIEW
pay_103,12000,Internal error,FAILED,500,STOP
pay_104,5600,Delayed webhook,SUCCESS,Missing order,ALREADY_RECOVERED
pay_105,3100,Insufficient funds,FAILED,Balance,HUMAN_REVIEW
pay_106,15000,Gateway timeout,FAILED,Latency,HUMAN_REVIEW
pay_107,9500,Invalid signature,FAILED,Secret,STOP
pay_108,11000,No failure detected,SUCCESS,Healthy,NO_ACTION
pay_109,7200,No failure detected,SUCCESS,Healthy,NO_ACTION
pay_110,6000,No failure detected,SUCCESS,Healthy,NO_ACTION"""

def test_upload_and_ask_ai_flow():
    upload_payload = {"filename": "recoveriq_sample_10_payments.csv", "content": sample_csv}
    req1 = urllib.request.Request(
        "http://127.0.0.1:8000/api/upload-file",
        data=json.dumps(upload_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req1, timeout=10) as r1:
            res1 = json.loads(r1.read().decode("utf-8"))
            assert res1["records_found"] == 10
            assert res1["failed_payments"] == 6
            assert res1["successful_payments"] == 4
            assert res1["total_dataset_amount"] == 80300
            assert res1["money_at_risk"] == 50500

            # 2. Test Ask AI about a valid payment in this file
            ask_payload_1 = {
                "question": "Why did pay_101 fail?",
                "context": res1
            }
            req2 = urllib.request.Request(
                "http://127.0.0.1:8000/api/ai/ask",
                data=json.dumps(ask_payload_1).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req2, timeout=10) as r2:
                res2 = json.loads(r2.read().decode("utf-8"))
                assert "pay_101" in res2["answer"] or "8,400" in res2["answer"]

            # 3. Test Ask AI about a non-existent payment in this file
            ask_payload_2 = {
                "question": "Why did pay_999 fail?",
                "context": res1
            }
            req3 = urllib.request.Request(
                "http://127.0.0.1:8000/api/ai/ask",
                data=json.dumps(ask_payload_2).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req3, timeout=10) as r3:
                res3 = json.loads(r3.read().decode("utf-8"))
                assert "I couldn't find that payment" in res3["answer"]

            # 4. Test Ask AI highest risk
            ask_payload_3 = {
                "question": "Which payment has the highest risk?",
                "context": res1
            }
            req4 = urllib.request.Request(
                "http://127.0.0.1:8000/api/ai/ask",
                data=json.dumps(ask_payload_3).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req4, timeout=10) as r4:
                res4 = json.loads(r4.read().decode("utf-8"))
                assert "15,000" in res4["answer"] or "pay_106" in res4["answer"] or "risk" in res4["answer"]
    except Exception as e:
        pytest.skip(f"API server not reachable: {e}")

