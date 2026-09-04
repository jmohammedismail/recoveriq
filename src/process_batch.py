import json


MAX_RETRIES = 2
with open("D:/post_payment_recovery_agent/data/telemetry_batch.json", "r") as file:
    batch = json.load(file)

print("Total payment cases:", len(batch))

total_at_risk = 0
total_recovered = 0
audit_log = []

for case in batch:
    recovery_key = None
    print("--------------------")
    print("Payment ID:", case["payment_id"])
    if case["http_status"] == 504:
        root_cause = "Merchant server timeout after webhook delivery"

    elif case["http_status"] == 500:
        root_cause = "Merchant server error during webhook processing"

    else:
        root_cause = "Unknown merchant workflow failure"
    print("Amount: ₹", case["amount"])
    total_at_risk += case["amount"]
    print("Retry Count:", case["retry_count"])

    if case["http_status"] == 504 and case["retry_count"] == 0:
        confidence = 88

    elif case["http_status"] == 504 and case["retry_count"] >= 2:
        confidence = 60

    elif case["http_status"] == 500 and case["retry_count"] >= 3:
        confidence = 35

    else:
        confidence = 50

    if confidence >= 85 and case["retry_count"] < MAX_RETRIES:
        decision = "AUTO RECOVERY"

    elif confidence >= 50:
        decision = "HUMAN REVIEW"

    else:
        decision = "STOP"

    print("Decision:", decision)

    if decision == "AUTO RECOVERY":

                # Check merchant state before recovery
        with open("D:/post_payment_recovery_agent/data/merchant_state.json", "r") as file:
            merchant_state = json.load(file)

            current_state = None

            for state in merchant_state:
                if state["payment_id"] == case["payment_id"]:
                    current_state = state
                    break

            if current_state and current_state["order_exists"]:
                recovery_status = "STOPPED"
                print("Order already exists. Recovery stopped.")
            else:
                recovery_status = "SUCCESS"
                print("Order does not exist. Recovery can continue.")
                recovery_key = (
                    case["payment_id"]
                    + "_"
                    + case["order_id"]
                    + "_ORDER_SYNC"
                )

                print("Idempotency Key:", recovery_key)               

                if current_state:
                    current_state["order_exists"] = True

                    with open("D:/post_payment_recovery_agent/data/merchant_state.json", "w") as file:
                        json.dump(merchant_state, file, indent=4)

                    print("Merchant state updated: Order created.")


        if recovery_status == "SUCCESS":

            if current_state and current_state["order_exists"]:

                print("Recovery Verified: Order exists.")

                total_recovered += case["amount"]

                print("Recovery: SUCCESS")
                print("Recovered: ₹", case["amount"])

            else:

                recovery_status = "FAILED"
                print("Recovery Verification Failed.")

            
    else:
        recovery_status = "NOT_EXECUTED"
        print("Recovery: NOT EXECUTED")

    audit_record = {
        "payment_id": case["payment_id"],
        "amount": case["amount"],
        "root_cause": root_cause,
        "confidence": confidence,
        "recovery_key": recovery_key if decision == "AUTO RECOVERY" else None,
        "decision": decision,
        "recovery_status": recovery_status,
        "revenue_recovered": case["amount"] if recovery_status == "SUCCESS" else 0
    }

    audit_log.append(audit_record)



    
print("====================")
print("TOTAL REVENUE AT RISK: ₹", total_at_risk)
print("TOTAL REVENUE RECOVERED: ₹", total_recovered)
recovery_rate = (total_recovered / total_at_risk) * 100
print("RECOVERY RATE:", round(recovery_rate, 2), "%")

with open("D:/post_payment_recovery_agent/logs/batch_recovery_log.json", "w") as file:
    json.dump(audit_log, file, indent=4)

print("Audit log saved successfully.")