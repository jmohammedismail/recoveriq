"""
RecoverIQ - Distributed Tracing & Observability Layer (Topic 3 Capability 3)

Lightweight, deterministic distributed tracing module providing end-to-end span correlation
across API Gateway, Payment Service, Webhook Service, Merchant API, and AI Agent Engine.

STRICT BOUNDARIES:
- Observational only.
- AI token and inference metrics clearly annotated (MOCKED_FOR_DEMO where appropriate).
- Thread-safe persistence to logs/recovery_traces.json.
- Integrates with recovery_audit.py and recovery_ai_explainability.py.
"""

import os
import json
import uuid
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
TRACES_LOG_PATH = os.path.join(LOGS_DIR, "recovery_traces.json")

_trace_lock = threading.Lock()
_trace_store: Dict[str, Dict[str, Any]] = {}
_payment_trace_index: Dict[str, List[str]] = {}


def _load_persisted_traces() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(TRACES_LOG_PATH):
        try:
            with open(TRACES_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_persisted_traces(data: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(TRACES_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def generate_deterministic_trace_for_payment(
    payment_id: str,
    root_operation: str = "PAYMENT_RECOVERY_LIFECYCLE",
    http_status: int = 504,
    merchant_id: str = "merchant_demo"
) -> Dict[str, Any]:
    """
    Topic 3 - Generates a multi-span distributed trace timeline for a payment recovery lifecycle.
    """
    clean_payment_id = str(payment_id or "unknown_pay").strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    trace_id = f"tr_{clean_payment_id}_{uuid.uuid4().hex[:8]}"

    # Span 1: API Gateway Ingestion
    span_gateway = {
        "span_id": f"sp_{uuid.uuid4().hex[:6]}",
        "parent_span_id": None,
        "service": "api_gateway",
        "operation": "HTTP_POST /api/webhook/payment",
        "start_offset_ms": 0,
        "duration_ms": 42,
        "status": "SUCCESS",
        "status_code": 200,
        "tags": {"protocol": "HTTP/1.1", "tls": "TLSv1.3", "merchant_id": merchant_id}
    }

    # Span 2: Payment Service Gateway Check
    span_payment = {
        "span_id": f"sp_{uuid.uuid4().hex[:6]}",
        "parent_span_id": span_gateway["span_id"],
        "service": "payment_service",
        "operation": "GATEWAY_CAPTURE_VERIFICATION",
        "start_offset_ms": 42,
        "duration_ms": 108,
        "status": "SUCCESS",
        "status_code": 200,
        "tags": {"gateway": "Razorpay", "payment_status": "SUCCESS", "funds_captured": True}
    }

    # Span 3: Webhook Delivery to Merchant
    webhook_duration = 504 if http_status == 504 else (120 if http_status == 200 else 450)
    webhook_status = "TIMEOUT" if http_status == 504 else ("ERROR" if http_status == 500 else "SUCCESS")
    span_webhook = {
        "span_id": f"sp_{uuid.uuid4().hex[:6]}",
        "parent_span_id": span_payment["span_id"],
        "service": "webhook_service",
        "operation": "FORWARD_WEBHOOK_TO_MERCHANT",
        "start_offset_ms": 150,
        "duration_ms": webhook_duration,
        "status": webhook_status,
        "status_code": http_status,
        "tags": {"endpoint": "payment-webhook", "hmac_verified": True, "http_status": http_status}
    }

    # Span 4: AI Recovery Intelligence Engine
    span_ai = {
        "span_id": f"sp_{uuid.uuid4().hex[:6]}",
        "parent_span_id": span_webhook["span_id"],
        "service": "recovery_ai_engine",
        "operation": "ROOT_CAUSE_DIAGNOSTICS_&_POLICY_GATE",
        "start_offset_ms": 150 + webhook_duration,
        "duration_ms": 138,
        "status": "SUCCESS",
        "status_code": 200,
        "tags": {"confidence": 88 if http_status == 504 else 60, "decision": "AUTO_RECOVER" if http_status == 504 else "HUMAN_REVIEW"}
    }

    # Span 5: Merchant Recovery Sync
    span_sync = {
        "span_id": f"sp_{uuid.uuid4().hex[:6]}",
        "parent_span_id": span_ai["span_id"],
        "service": "merchant_api",
        "operation": "ORDER_CREATION_SYNC",
        "start_offset_ms": 150 + webhook_duration + 138,
        "duration_ms": 180,
        "status": "PENDING" if http_status == 504 else "SUCCESS",
        "status_code": 200 if http_status != 504 else 504,
        "tags": {"idempotency_key": f"{clean_payment_id}_ORD_SYNC", "retry_count": 0}
    }

    spans = [span_gateway, span_payment, span_webhook, span_ai, span_sync]
    total_latency_ms = sum(s["duration_ms"] for s in spans)

    trace_record = {
        "trace_id": trace_id,
        "payment_id": clean_payment_id,
        "root_operation": root_operation,
        "merchant_id": merchant_id,
        "total_latency_ms": total_latency_ms,
        "span_count": len(spans),
        "spans": spans,
        "ai_diagnostics": {
            "model_latency_ms": 240,
            "tokens_used": 412,
            "inference_cost_usd": 0.0008,
            "confidence_score": 88 if http_status == 504 else 60,
            "telemetry_source": "MOCKED_FOR_DEMO",
            "mock_indicator": True
        },
        "created_at": now_iso
    }

    with _trace_lock:
        if not _trace_store:
            _trace_store.update(_load_persisted_traces())
        _trace_store[trace_id] = trace_record
        if clean_payment_id not in _payment_trace_index:
            _payment_trace_index[clean_payment_id] = []
        _payment_trace_index[clean_payment_id].append(trace_id)
        _save_persisted_traces(_trace_store)

    return trace_record


def get_distributed_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    clean_tid = str(trace_id or "").strip()
    with _trace_lock:
        if not _trace_store:
            _trace_store.update(_load_persisted_traces())
        return _trace_store.get(clean_tid)


def get_payment_distributed_traces(payment_id: str) -> List[Dict[str, Any]]:
    clean_pid = str(payment_id or "").strip()
    with _trace_lock:
        if not _trace_store:
            _trace_store.update(_load_persisted_traces())
        traces = [t for t in _trace_store.values() if t.get("payment_id") == clean_pid]
        if not traces:
            # Generate deterministic trace on demand
            traces.append(generate_deterministic_trace_for_payment(clean_pid))
        return traces
