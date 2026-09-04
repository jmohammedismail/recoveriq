import json
import time


# 1. Read telemetry data
with open("D:/post_payment_recovery_agent/data/telemetry.json", "r") as file:
    data = json.load(file)

print(data)


# 2. Detect workflow failure
if data["payment_status"] == "SUCCESS" and data["order_status"] == "NOT_CREATED":
    print("WORKFLOW FAILURE DETECTED")
else:
    print("WORKFLOW COMPLETED")


# 3. Calculate revenue at risk
if data["payment_status"] == "SUCCESS" and data["order_status"] == "NOT_CREATED":
    revenue_at_risk = data["amount"]
    print("Revenue at Risk: ₹", revenue_at_risk)


# 4. Find possible root cause
if data["webhook_status"] == "DELAYED":
    if data["http_status"] == 504:
        print("Possible Root Cause: Merchant server timeout after webhook delivery")
    else:
        print("Possible Root Cause: Webhook delivery delay")


# 5. Check retry limit
if data["retry_count"] < 2:
    print("Recovery Action: RETRY CAN BE CONSIDERED")
else:
    print("Recovery Action: STOP AND ESCALATE")


# 6. Cooldown check
COOLDOWN_SECONDS = 60

if data["webhook_status"] == "DELAYED":
    print("Cooldown Required: 60 seconds before recovery action")


# 7. Check current merchant state
with open("D:/post_payment_recovery_agent/data/merchant_state.json", "r") as file:
    merchant_state = json.load(file)

if merchant_state["order_exists"]:
    print("Order already exists. STOP recovery.")
else:
    print("Order does not exist. Recovery can continue.")


# 8. Create idempotency key
recovery_key = (
    data["payment_id"]
    + "_"
    + data["order_id"]
    + "_ORDER_SYNC"
)

print("Recovery Idempotency Key:", recovery_key)


# 9. AI confidence score
confidence = 88


# 10. Policy Gate
if confidence >= 85 and data["retry_count"] < 2:
    print("Policy Gate: AUTO RECOVERY ALLOWED")

elif confidence >= 50:
    print("Policy Gate: HUMAN REVIEW REQUIRED")

else:
    print("Policy Gate: STOP AND ESCALATE")


# 11. Default recovery status
recovery_status = "NOT_EXECUTED"


# 12. Recovery execution
if confidence >= 85 and data["retry_count"] < 2:

    print("Executing Recovery...")

    recovery_status = "SUCCESS"

    if recovery_status == "SUCCESS":
        print("Recovery Successful!")
        print("Revenue Recovered: ₹", data["amount"])

    else:
        print("Recovery Failed")


elif confidence >= 50:

    recovery_status = "PENDING_REVIEW"

else:

    recovery_status = "STOPPED"


# 13. Save recovery result
recovery_record = {
    "payment_id": data["payment_id"],
    "order_id": data["order_id"],
    "amount": data["amount"],
    "payment_status": data["payment_status"],
    "webhook_status": data["webhook_status"],
    "http_status": data["http_status"],
    "retry_count": data["retry_count"],
    "root_cause": "Merchant server timeout after webhook delivery",
    "confidence": confidence,
    "recovery_key": recovery_key,
    "recovery_status": recovery_status,
    "revenue_recovered": data["amount"] if recovery_status == "SUCCESS" else 0
}


with open(
    "D:/post_payment_recovery_agent/logs/recovery_log.json",
    "w"
) as file:

    json.dump([recovery_record], file, indent=4)


print("Recovery result saved to audit log.")