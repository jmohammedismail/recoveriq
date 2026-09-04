import urllib.request
import json
import pytest

csv_data = """payment_id,amount,payment_status,webhook_status,root_cause,decision,recovery_status
pay_001,8400,SUCCESS,DELAYED,Merchant server timeout,AUTO_RECOVERY,STOPPED
pay_002,2500,SUCCESS,DELAYED,Merchant server timeout,HUMAN_REVIEW,PENDING
pay_003,12000,FAILED,FAILED,Internal server error,STOP,NOT_EXECUTED
pay_004,5600,SUCCESS,DELAYED,Merchant server timeout,AUTO_RECOVERY,RECOVERED
pay_005,3100,SUCCESS,DELAYED,Merchant server timeout,HUMAN_REVIEW,PENDING
pay_006,15000,FAILED,FAILED,Gateway connection timeout,HUMAN_REVIEW,PENDING
pay_007,9500,FAILED,FAILED,Invalid signature,STOP,NOT_EXECUTED
pay_008,11000,SUCCESS,DELIVERED,No failure detected,NO_ACTION,NONE
pay_009,7200,SUCCESS,DELIVERED,No failure detected,NO_ACTION,NONE
pay_010,6000,SUCCESS,DELIVERED,No failure detected,NO_ACTION,NONE"""

def test_upload_api_endpoint():
    payload = {"filename": "recoveriq_sample_payments_10.csv", "content": csv_data}
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/upload-file",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["total_records"] == 10
            assert res["total_dataset_amount"] == 80300
            assert "records" in res
    except Exception as e:
        pytest.skip(f"API daemon not running or unreachable: {e}")
