"""
RecoverIQ - Ingestion Common Payment Schema & Normalization
Converts payment records from CSV, XLSX, XLS, JSON, TXT, PDF, DOCX
into a single, robust, normalized schema.
"""

import re
from typing import Dict, Any, Optional, Tuple, List


# Status Normalization Maps
SUCCESS_ALIASES = {"SUCCESS", "COMPLETED", "PAID", "SUCCEEDED", "SUCCESSFUL", "DELIVERED", "OK", "CAPTURED"}
FAILED_ALIASES = {"FAILED", "FAILURE", "DECLINED", "ERROR", "PAYMENT_FAILED", "STOPPED", "TIMEOUT", "EXPIRED", "REJECTED"}
PENDING_ALIASES = {"PENDING", "PROCESSING", "IN_PROGRESS", "INPROGRESS", "WAITING", "QUEUED", "DELAYED"}
CANCELLED_ALIASES = {"CANCELLED", "CANCELED", "ABORTED", "VOIDED"}
REFUNDED_ALIASES = {"REFUNDED", "REVERSED"}


def normalize_payment_id(raw_id: Any) -> Optional[str]:
    """Cleans and normalizes payment ID string."""
    if raw_id is None:
        return None
    s = str(raw_id).strip()
    s = s.strip("'\"`.,;:")
    if not s:
        return None
    return s


def clean_formatting_delimiters(text: Any) -> str:
    """
    Strips formatting and separator noise like '---', '===', '___', '***',
    tabs, leading/trailing whitespace, and border characters,
    while preserving legitimate alphanumeric characters, punctuation, and wording.
    """
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""

    # Check if the entire string is just a separator (e.g. '--------------------', '========')
    if set(s) <= {"-", "=", "_", "*", "#", "~", "+", "|", " ", "\t"}:
        return ""

    # Strip trailing or leading runs of 2 or more delimiter characters (e.g., '---', '===', '___')
    s = re.sub(r"[\s\t]*[-=_*#~+|]{2,}[\s\t]*$", "", s)
    s = re.sub(r"^[\s\t]*[-=_*#~+|]{2,}[\s\t]*", "", s)

    # Clean redundant whitespace / tabs
    s = re.sub(r"[\t\r\n]+", " ", s)
    s = re.sub(r" {2,}", " ", s)

    return s.strip()


def parse_monetary_amount(raw_amount: Any) -> Optional[float]:
    """
    Parses strings like '₹8,400', 'Rs. 8,400', 'INR 8400', '8,400.00', '8400'
    into numeric amounts. Returns None if unparseable.
    NEVER defaults to 5000.
    """
    if raw_amount is None:
        return None
    if isinstance(raw_amount, (int, float)):
        return float(raw_amount)

    s = str(raw_amount).strip()
    if not s:
        return None

    # Strip currency symbols and letters
    clean = re.sub(r"[₹$€£,]", "", s)
    clean = re.sub(r"(?i)\b(rs\.?|inr|usd|eur|gbp)\b", "", clean).strip()

    match = re.search(r"[-+]?\d*\.?\d+", clean)
    if match:
        try:
            val = float(match.group(0))
            return val
        except ValueError:
            return None
    return None


def normalize_status(raw_status: Any, problem_hint: str = "") -> str:
    """Normalizes raw status strings into a standard enum."""
    if not raw_status:
        # Infer from problem text if status is missing
        if "NO FAILURE" in problem_hint.upper() or "HEALTHY" in problem_hint.upper():
            return "SUCCESS"
        elif problem_hint:
            return "FAILED"
        return "UNKNOWN"

    s = str(raw_status).strip().upper()
    s_clean = re.sub(r"[\s_-]+", "", s)

    for alias in SUCCESS_ALIASES:
        if re.sub(r"[\s_-]+", "", alias) == s_clean:
            return "SUCCESS"

    for alias in FAILED_ALIASES:
        if re.sub(r"[\s_-]+", "", alias) == s_clean:
            return "FAILED"

    for alias in PENDING_ALIASES:
        if re.sub(r"[\s_-]+", "", alias) == s_clean:
            return "PENDING"

    for alias in CANCELLED_ALIASES:
        if re.sub(r"[\s_-]+", "", alias) == s_clean:
            return "CANCELLED"

    for alias in REFUNDED_ALIASES:
        if re.sub(r"[\s_-]+", "", alias) == s_clean:
            return "REFUNDED"

    if "SUCCESS" in s:
        return "SUCCESS"
    if "FAIL" in s or "ERR" in s or "DECLIN" in s:
        return "FAILED"
    if "PEND" in s or "WAIT" in s or "PROCESS" in s:
        return "PENDING"

    return "UNKNOWN"


def classify_payment_decision(
    status: str,
    problem: str,
    root_cause: str,
    raw_decision: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates governed AI recommendation and action policy based on data.
    """
    text = f"{problem} {root_cause} {status} {raw_decision or ''}".upper()

    # 1. SUCCESS / No payment failure detected
    if status == "SUCCESS" or "NO FAILURE" in text or "HEALTHY" in text:
        return {
            "recommendation": "No Action",
            "ai_recommendation": "No Action",
            "action": "Healthy",
            "recommended_action": "NO_ACTION",
            "recovery_eligible": False,
            "risk_level": "LOW",
            "confidence": 100,
            "is_failed": False
        }

    # 2. Already Recovered
    if "ALREADY RECOVERED" in text or "RECOVERED" in text:
        return {
            "recommendation": "Already Recovered",
            "ai_recommendation": "Already Recovered",
            "action": "Recovered",
            "recommended_action": "ALREADY_RECOVERED",
            "recovery_eligible": True,
            "risk_level": "LOW",
            "confidence": 95,
            "is_failed": True
        }

    # 3. Duplicate Order Risk / Already in Merchant DB
    if "DUPLICATE" in text or "ALREADY EXISTS" in text or "DOUBLE" in text or "STOPPED" in text:
        return {
            "recommendation": "Do Not Double-Charge",
            "ai_recommendation": "Do Not Double-Charge",
            "action": "Protected",
            "recommended_action": "STOP",
            "recovery_eligible": False,
            "risk_level": "MEDIUM",
            "confidence": 90,
            "is_failed": True
        }

    # 4. Critical Error / 500 / Invalid Signature / Safety Halt
    if "INTERNAL SERVER" in text or "500" in text or "SIGNATURE" in text or "CIRCUIT" in text or "HALT" in text or "STOP" == (raw_decision or "").strip().upper():
        return {
            "recommendation": "Investigate / Safety Halt",
            "ai_recommendation": "Investigate / Safety Halt",
            "action": "Investigate",
            "recommended_action": "STOP",
            "recovery_eligible": False,
            "risk_level": "HIGH",
            "confidence": 92,
            "is_failed": True
        }

    # 5. Human Review (e.g. Card expired, insufficient funds, retries exhausted)
    if "HUMAN" in text or "REVIEW" in text or status == "PENDING" or "EXPIRED" in text or "INSUFFICIENT" in text or "2/2" in text:
        return {
            "recommendation": "Human Review",
            "ai_recommendation": "Human Review",
            "action": "Review",
            "recommended_action": "HUMAN_REVIEW",
            "recovery_eligible": False,
            "risk_level": "MEDIUM",
            "confidence": 75,
            "is_failed": True
        }

    # 6. Auto Recovery (missing order, gateway timeout, webhook delay with buffer)
    if "AUTO" in text or "MISSING ORDER" in text or "TIMEOUT" in text or "504" in text or "WEBHOOK" in text:
        return {
            "recommendation": "Auto Recovery",
            "ai_recommendation": "Auto Recovery",
            "action": "Run Recovery",
            "recommended_action": "AUTO_RECOVERY",
            "recovery_eligible": True,
            "risk_level": "LOW",
            "confidence": 88,
            "is_failed": True
        }

    # 7. Default fallback for failed payments
    return {
        "recommendation": "Human Review",
        "ai_recommendation": "Human Review",
        "action": "Review",
        "recommended_action": "HUMAN_REVIEW",
        "recovery_eligible": False,
        "risk_level": "MEDIUM",
        "confidence": 70,
        "is_failed": True
    }


def normalize_record(raw_dict: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Normalizes a dictionary into the common payment schema:
    Returns (record, error_message).
    """
    # Clean keys for matching
    clean_dict = {}
    for k, v in raw_dict.items():
        if k is not None:
            norm_k = re.sub(r"[\s_-]+", "_", str(k).strip().lower())
            clean_dict[norm_k] = v

    # 1. Resolve payment_id
    pid = None
    for k in ("payment_id", "paymentid", "payment", "transaction_id", "transactionid", "txn_id", "txnid", "id"):
        if k in clean_dict and clean_dict[k] is not None:
            pid = normalize_payment_id(clean_dict[k])
            if pid:
                break

    if not pid:
        return None, "Missing or empty payment_id"

    # 2. Resolve amount
    amt = None
    for k in ("amount", "payment_amount", "paymentamount", "transaction_amount", "transactionamount", "txn_amount", "amt", "value", "price", "total"):
        if k in clean_dict and clean_dict[k] is not None:
            amt = parse_monetary_amount(clean_dict[k])
            if amt is not None:
                break

    if amt is None:
        return None, f"Payment {pid} has invalid or missing monetary amount"

    # 3. Resolve status
    raw_status = None
    for k in ("status", "payment_status", "paymentstatus", "transaction_status", "transactionstatus", "txn_status", "state", "gateway_status"):
        if k in clean_dict and clean_dict[k] is not None:
            raw_status = clean_dict[k]
            break

    # 4. Resolve failure reason / problem
    problem = ""
    for k in ("failure_reason", "failurereason", "failure_reason_code", "failure_message", "failuremessage", "error_message", "errormessage", "problem", "issue", "error", "error_description", "error_detail", "failure", "reason", "root_cause", "rootcause", "cause"):
        if k in clean_dict and clean_dict[k] is not None:
            val = clean_formatting_delimiters(clean_dict[k])
            if val and not val.lower().startswith("col_"):
                problem = val
                break

    # 5. Resolve root cause
    root_cause = ""
    for k in ("root_cause", "rootcause", "cause", "detailed_reason", "root_cause_diagnostics"):
        if k in clean_dict and clean_dict[k] is not None:
            val = clean_formatting_delimiters(clean_dict[k])
            if val and not val.lower().startswith("col_"):
                root_cause = val
                break

    # Normalize status
    norm_status = normalize_status(raw_status, problem_hint=problem)

    # 6. Apply Problem Text Logic
    if norm_status == "SUCCESS":
        problem = "No payment failure detected"
        root_cause = None
    elif norm_status in ("FAILED", "PENDING", "CANCELLED", "REFUNDED", "UNKNOWN"):
        if not problem:
            problem = "Payment failed — reason not provided"
            root_cause = "Failure reason not specified in payment record"
        elif not root_cause:
            root_cause = problem

    # 7. Resolve decision / recommendation
    raw_decision = None
    for k in ("decision", "recommendation", "ai_recommendation", "action", "policy"):
        if k in clean_dict and clean_dict[k] is not None:
            raw_decision = str(clean_dict[k]).strip()
            break

    decision_info = classify_payment_decision(norm_status, problem, root_cause or "", raw_decision)

    # Optional metadata fields
    currency = clean_dict.get("currency") or "INR"
    order_id = clean_dict.get("order_id") or clean_dict.get("orderid") or clean_dict.get("order") or None
    merchant_id = clean_dict.get("merchant_id") or clean_dict.get("merchantid") or None
    customer_id = clean_dict.get("customer_id") or clean_dict.get("customerid") or None
    txn_id = clean_dict.get("transaction_id") or clean_dict.get("transactionid") or clean_dict.get("txn_id") or None
    timestamp = clean_dict.get("timestamp") or clean_dict.get("created_at") or clean_dict.get("time") or clean_dict.get("date") or None
    payment_method = clean_dict.get("payment_method") or clean_dict.get("method") or clean_dict.get("mode") or None
    gateway = clean_dict.get("gateway") or clean_dict.get("payment_gateway") or None

    record = {
        "payment_id": pid,
        "amount": int(amt) if amt.is_integer() else amt,
        "currency": currency,
        "status": norm_status,
        "problem": problem,
        "failure_reason": problem if decision_info["is_failed"] else None,
        "root_cause": root_cause,
        "recommendation": decision_info["recommendation"],
        "ai_recommendation": decision_info["ai_recommendation"],
        "action": decision_info["action"],
        "recommended_action": decision_info["recommended_action"],
        "recovery_eligible": decision_info["recovery_eligible"],
        "risk_level": decision_info["risk_level"],
        "confidence": decision_info["confidence"],
        "is_failed": decision_info["is_failed"],
        "order_id": order_id,
        "merchant_id": merchant_id,
        "customer_id": customer_id,
        "transaction_id": txn_id,
        "timestamp": timestamp,
        "payment_method": payment_method,
        "gateway": gateway,
        "raw_data": raw_dict
    }

    return record, None

classify_payment_action = classify_payment_decision
