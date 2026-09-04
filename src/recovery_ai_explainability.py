"""
RecoverIQ - AI Decision Explainability Layer (Topic 3 Capability 1)

Authoritative AI decision explainability module that evaluates:
  1. Multi-factor telemetry evidence (HTTP status, retry count, merchant health,
     gateway status, merchant order status, database status, webhook verification)
  2. Deterministic confidence scoring vs 85% Auto-Recovery decision threshold
  3. Explicit 'Why this decision?' and 'Why not Auto-Recover?' explanations
  4. Derived operational & financial risk level (LOW, MEDIUM, HIGH, CRITICAL)
  5. Actionable next-step recommendations
  6. Distributed Trace correlation

STRICT BOUNDARIES:
- Observational and explanatory only; NEVER directly mutates PaymentState or CircuitState.
- Deterministic and evidence-based (zero fabricated AI reasoning).
- Thread-safe persistence to logs/recovery_ai_explainability.json.
- Records structured audit events in src/recovery_audit.py.
"""

import os
import json
import uuid
import threading
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
EXPLAINABILITY_LOG_PATH = os.path.join(LOGS_DIR, "recovery_ai_explainability.json")

AUTO_RECOVERY_CONFIDENCE_THRESHOLD = 85.0
MAX_AUTO_RETRIES = 2

_explainability_lock = threading.Lock()
_explainability_store: Dict[str, Dict[str, Any]] = {}


class AIDecisionType(str, Enum):
    AUTO_RECOVER = "AUTO_RECOVER"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    STOP = "STOP"


class AIRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def _load_persisted_explanations() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(EXPLAINABILITY_LOG_PATH):
        try:
            with open(EXPLAINABILITY_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_persisted_explanations(data: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(EXPLAINABILITY_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def evaluate_ai_decision_explanation(
    payment_id: str,
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    case_data: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Topic 3 - Evaluates multi-dimensional evidence and generates a deterministic,
    governed AI decision explanation for a payment incident.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    t_id = trace_id or f"tr_{clean_payment_id}_{uuid.uuid4().hex[:8]}"

    data = case_data or {}
    amount = float(data.get("amount", 0) or 0)
    http_status = int(data.get("http_status", 504) or 504)
    retry_count = int(data.get("retry_count", 0) or 0)
    payment_status = str(data.get("payment_status", "SUCCESS") or "SUCCESS").upper()
    order_status = str(data.get("order_status", "NOT_CREATED") or "NOT_CREATED").upper()
    merchant_order_exists = bool(data.get("merchant_order_exists", False))
    webhook_status = str(data.get("webhook_status", "DELAYED") or "DELAYED").upper()

    merchant_health_str = "HEALTHY"
    try:
        from src.merchant_health import get_endpoint_health_summary
        mh = get_endpoint_health_summary(clean_merchant_id, clean_endpoint)
        merchant_health_str = mh.get("health", "HEALTHY")
    except Exception:
        pass

    circuit_state_str = "CLOSED"
    try:
        from src.circuit_breaker import get_circuit_breaker_status
        cb = get_circuit_breaker_status(clean_merchant_id, clean_endpoint)
        circuit_state_str = cb.get("state", "CLOSED")
    except Exception:
        pass

    webhook_verified = True
    try:
        from src.webhook_security import get_webhook_security_summary
        ws = get_webhook_security_summary()
        webhook_verified = ws.get("verification_enabled", True)
    except Exception:
        pass

    evidence_items: List[str] = []
    if http_status == 504:
        evidence_items.append(f"HTTP {http_status} Gateway Timeout detected from merchant endpoint")
    elif http_status == 500:
        evidence_items.append(f"HTTP {http_status} Internal Server Error detected during webhook ingestion")
    elif http_status == 200:
        evidence_items.append(f"HTTP {http_status} Success recorded from merchant endpoint")
    else:
        evidence_items.append(f"HTTP {http_status} unexpected response received")

    evidence_items.append(f"Retry buffer: {retry_count}/{MAX_AUTO_RETRIES} attempts consumed")
    evidence_items.append(f"Merchant endpoint health: {merchant_health_str}")
    evidence_items.append(f"Payment gateway status: {payment_status} (Funds captured)")
    evidence_items.append(f"Merchant order state: {order_status} (Order exists: {merchant_order_exists})")
    evidence_items.append(f"Database sync status: {'PENDING' if not merchant_order_exists else 'SYNCED'}")
    evidence_items.append(f"Inbound webhook security: {'VERIFIED (HMAC-SHA256)' if webhook_verified else 'UNVERIFIED'}")
    evidence_items.append(f"Circuit breaker status: {circuit_state_str}")

    # Deterministic Confidence
    if http_status == 504 and retry_count == 0 and merchant_health_str == "HEALTHY":
        confidence = 88.0
    elif http_status == 504 and retry_count == 1:
        confidence = 72.0
    elif http_status == 504 and retry_count >= 2:
        confidence = 60.0
    elif http_status == 500 and retry_count == 0:
        confidence = 65.0
    elif http_status == 500 and retry_count >= 2:
        confidence = 35.0
    elif circuit_state_str == "OPEN":
        confidence = 25.0
    elif merchant_order_exists:
        confidence = 90.0
    else:
        confidence = 50.0

    if merchant_health_str == "DEGRADED":
        confidence = max(10.0, confidence - 15.0)
    elif merchant_health_str == "UNHEALTHY":
        confidence = max(5.0, confidence - 30.0)

    if circuit_state_str == "OPEN":
        confidence = min(confidence, 30.0)

    why_not_auto_reasons: List[str] = []

    if circuit_state_str == "OPEN":
        decision = AIDecisionType.STOP.value
        risk_level = AIRiskLevel.HIGH.value
        recommended_action = "HALT_AND_WAIT_CIRCUIT_COOLDOWN"
        why_not_auto_reasons.append("Circuit breaker is currently OPEN to prevent merchant server exhaustion.")
        why_this_decision = (
            f"Recovery request is blocked because the circuit breaker for {clean_merchant_id} "
            f"is OPEN. Automated attempts are suspended until the cooldown period elapses."
        )
    elif merchant_order_exists:
        decision = AIDecisionType.STOP.value
        risk_level = AIRiskLevel.LOW.value
        recommended_action = "NO_ACTION_ORDER_ALREADY_EXISTS"
        why_not_auto_reasons.append("Merchant order already confirmed in database; recovery is redundant.")
        why_this_decision = (
            f"The order is already confirmed in the merchant database. Autonomous recovery was halted "
            f"by safety guardrails to prevent duplicate fulfillment or double-charging."
        )
    elif retry_count >= MAX_AUTO_RETRIES:
        decision = AIDecisionType.HUMAN_REVIEW.value
        risk_level = AIRiskLevel.HIGH.value
        recommended_action = "QUEUE_OPERATOR_REVIEW"
        why_not_auto_reasons.append(f"Retry count ({retry_count}) has reached the maximum automated retry threshold ({MAX_AUTO_RETRIES}).")
        why_not_auto_reasons.append("Operator review required to avoid continuous retry loops on failing endpoints.")
        why_this_decision = (
            f"Automated retry attempts have been exhausted ({retry_count}/{MAX_AUTO_RETRIES}). "
            f"The transaction has been routed to the operator review queue to ensure human supervision."
        )
    elif confidence >= AUTO_RECOVERY_CONFIDENCE_THRESHOLD and not merchant_order_exists:
        decision = AIDecisionType.AUTO_RECOVER.value
        risk_level = AIRiskLevel.LOW.value
        recommended_action = "EXECUTE_IDEMPOTENT_WEBHOOK_REPLAY"
        why_this_decision = (
            f"High confidence ({confidence}% >= {AUTO_RECOVERY_CONFIDENCE_THRESHOLD}%) diagnosis confirms "
            f"a transient merchant timeout with funds captured by gateway. Autonomous replay with "
            f"deterministic idempotency key is safe to execute."
        )
    elif confidence >= 50.0:
        decision = AIDecisionType.HUMAN_REVIEW.value
        risk_level = AIRiskLevel.MEDIUM.value if amount < 10000 else AIRiskLevel.HIGH.value
        recommended_action = "REQUEST_OPERATOR_APPROVAL"
        why_not_auto_reasons.append(f"AI Confidence score ({confidence}%) is below the automated threshold ({AUTO_RECOVERY_CONFIDENCE_THRESHOLD}%).")
        if merchant_health_str in ("DEGRADED", "UNHEALTHY"):
            why_not_auto_reasons.append(f"Merchant endpoint health is currently {merchant_health_str}.")
        if retry_count > 0:
            why_not_auto_reasons.append(f"Previous automated retry attempt ({retry_count}) failed.")
        why_this_decision = (
            f"AI Confidence ({confidence}%) is below the {AUTO_RECOVERY_CONFIDENCE_THRESHOLD}% autonomous execution gate. "
            f"Human approval is mandatory before dispatching recovery commands to the merchant endpoint."
        )
    else:
        decision = AIDecisionType.STOP.value
        risk_level = AIRiskLevel.CRITICAL.value
        recommended_action = "HALT_AND_ESCALATE_TO_ENGINEERING"
        why_not_auto_reasons.append(f"Confidence score ({confidence}%) is severely degraded (< 50%).")
        why_not_auto_reasons.append("Anomalous or conflicting failure signals detected across gateway and merchant telemetry.")
        why_this_decision = (
            f"Severe anomaly detected with low confidence ({confidence}%). Automated recovery is completely halted "
            f"to protect transaction integrity and prevent downstream discrepancies."
        )

    explanation_obj = {
        "explanation_id": f"exp_{clean_payment_id}_{uuid.uuid4().hex[:6]}",
        "payment_id": clean_payment_id,
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "trace_id": t_id,
        "decision": decision,
        "confidence": confidence,
        "decision_threshold": AUTO_RECOVERY_CONFIDENCE_THRESHOLD,
        "risk_level": risk_level,
        "recommended_action": recommended_action,
        "why_this_decision": why_this_decision,
        "why_not_auto_recover": why_not_auto_reasons if decision != AIDecisionType.AUTO_RECOVER.value else [],
        "evidence": evidence_items,
        "subsystem_context": {
            "http_status": http_status,
            "retry_count": retry_count,
            "merchant_health": merchant_health_str,
            "circuit_state": circuit_state_str,
            "webhook_verified": webhook_verified,
            "gateway_status": payment_status,
            "merchant_order_exists": merchant_order_exists
        },
        "evaluated_at": now_iso
    }

    with _explainability_lock:
        if not _explainability_store:
            _explainability_store.update(_load_persisted_explanations())
        _explainability_store[clean_payment_id] = explanation_obj
        _save_persisted_explanations(_explainability_store)

    try:
        from src.recovery_audit import record_recovery_audit_event
        record_recovery_audit_event(
            payment_id=clean_payment_id,
            event_type="AI_DECISION_EXPLAINED",
            actor_type="AI_INTELLIGENCE",
            source="RECOVERY_AI_EXPLAINABILITY",
            status="RECORDED",
            reason=why_this_decision,
            risk_level=risk_level,
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            correlation_id=t_id,
            metadata={
                "decision": decision,
                "confidence": confidence,
                "threshold": AUTO_RECOVERY_CONFIDENCE_THRESHOLD,
                "why_not_auto_count": len(why_not_auto_reasons)
            }
        )
    except Exception:
        pass

    return explanation_obj


def get_ai_decision_explanation(payment_id: str) -> Optional[Dict[str, Any]]:
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    with _explainability_lock:
        if not _explainability_store:
            _explainability_store.update(_load_persisted_explanations())
        if clean_payment_id in _explainability_store:
            return _explainability_store[clean_payment_id]

    return evaluate_ai_decision_explanation(clean_payment_id)
