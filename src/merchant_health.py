"""
RecoverIQ - Real Merchant Endpoint Health Telemetry Layer (Topic 2.2.1)

Measures, records, aggregates, and classifies real-time delivery health, HTTP status,
measured response latency (p95, average), timeout detection, and failure categorization
for merchant webhook and sync endpoints.
"""

import os
import json
import uuid
import time
import math
import threading
import logging
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("recoveriq.merchant_health")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
HEALTH_STORE_PATH = os.path.join(LOGS_DIR, "merchant_endpoint_health.json")

_health_lock = threading.Lock()


class FailureCategory(str, Enum):
    """Categorized failure types for merchant endpoint interactions."""
    SUCCESS = "SUCCESS"
    REDIRECT = "REDIRECT"
    CLIENT_ERROR = "CLIENT_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class EndpointHealthStatus(str, Enum):
    """Derived health classification of a merchant endpoint."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    NO_DATA = "NO_DATA"


def classify_status_code(status_code: Optional[int], timed_out: bool = False) -> FailureCategory:
    """
    Classifies HTTP response status code into a distinct failure category.
    """
    if timed_out or status_code == 504:
        return FailureCategory.TIMEOUT
    if status_code is None:
        return FailureCategory.NETWORK_ERROR
    if 200 <= status_code < 300:
        return FailureCategory.SUCCESS
    if 300 <= status_code < 400:
        return FailureCategory.REDIRECT
    if status_code == 429:
        return FailureCategory.RATE_LIMITED
    if 400 <= status_code < 500:
        return FailureCategory.CLIENT_ERROR
    if 500 <= status_code < 600:
        return FailureCategory.SERVER_ERROR
    return FailureCategory.UNKNOWN_ERROR


def calculate_p95(latencies: List[float]) -> Optional[float]:
    """
    Calculates the 95th percentile latency from a list of measured latency values.
    Returns None if no data is provided.
    """
    if not latencies:
        return None
    sorted_vals = sorted(latencies)
    n = len(sorted_vals)
    if n == 1:
        return round(float(sorted_vals[0]), 2)
    # Nearest rank method for deterministic P95
    idx = math.ceil(0.95 * n) - 1
    idx = max(0, min(idx, n - 1))
    return round(float(sorted_vals[idx]), 2)


# In-memory observations buffer per endpoint key: f"{merchant_id}:{endpoint}"
_endpoint_observations: Dict[str, List[Dict[str, Any]]] = {}


def _load_persisted_health() -> Dict[str, List[Dict[str, Any]]]:
    if os.path.exists(HEALTH_STORE_PATH):
        try:
            with open(HEALTH_STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_persisted_health(data: Dict[str, List[Dict[str, Any]]]) -> None:
    try:
        with open(HEALTH_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def record_endpoint_observation(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook",
    status_code: Optional[int] = 200,
    latency_ms: float = 0.0,
    timed_out: bool = False,
    retry_attempt: int = 0,
    payment_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Records a measured merchant endpoint interaction event.
    Guarantees no secret credentials or sensitive tokens are stored.
    """
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    clean_latency = max(0.0, round(float(latency_ms), 2))
    
    is_success = bool(status_code and (200 <= status_code < 300) and not timed_out)
    category = classify_status_code(status_code, timed_out=timed_out)

    event_id = f"mhe_{uuid.uuid4().hex[:10]}"
    timestamp = datetime.now(timezone.utc).isoformat()

    event = {
        "event_id": event_id,
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "status_code": status_code,
        "latency_ms": clean_latency,
        "success": is_success,
        "timed_out": bool(timed_out or status_code == 504),
        "retry_attempt": int(retry_attempt or 0),
        "failure_category": category.value,
        "timestamp": timestamp,
        "payment_id": payment_id
    }

    key = f"{clean_merchant_id}:{clean_endpoint}"

    with _health_lock:
        if not _endpoint_observations and os.path.exists(HEALTH_STORE_PATH):
            _endpoint_observations.update(_load_persisted_health())

        if key not in _endpoint_observations:
            _endpoint_observations[key] = []

        _endpoint_observations[key].append(event)
        # Cap in-memory history per endpoint to latest 200 observations
        if len(_endpoint_observations[key]) > 200:
            _endpoint_observations[key] = _endpoint_observations[key][-200:]

        _save_persisted_health(_endpoint_observations)

    # Topic 2.2.2.8 - Propagate health observation to circuit breaker
    try:
        try:
            from src.circuit_breaker import record_circuit_observation
        except ImportError:
            from circuit_breaker import record_circuit_observation
        record_circuit_observation(
            merchant_id=clean_merchant_id,
            endpoint=clean_endpoint,
            failure_category=category.value
        )
    except Exception as e:
        logger.warning(f"Could not forward health observation to circuit breaker: {str(e)}")

    logger.info(
        f"MERCHANT_HEALTH_OBSERVATION: {clean_merchant_id} ({clean_endpoint}) "
        f"status={status_code} latency={clean_latency}ms category={category.value}"
    )
    return event


def get_endpoint_health_summary(
    merchant_id: str = "merchant_demo",
    endpoint: str = "payment-webhook"
) -> Dict[str, Any]:
    """
    Computes an aggregated health summary from actual recorded telemetry observations.
    """
    clean_merchant_id = str(merchant_id or "merchant_demo").strip()
    clean_endpoint = str(endpoint or "payment-webhook").strip()
    key = f"{clean_merchant_id}:{clean_endpoint}"

    with _health_lock:
        if not _endpoint_observations and os.path.exists(HEALTH_STORE_PATH):
            _endpoint_observations.update(_load_persisted_health())
        events = list(_endpoint_observations.get(key, []))

    if not events:
        return {
            "merchant_id": clean_merchant_id,
            "endpoint": clean_endpoint,
            "health": EndpointHealthStatus.NO_DATA.value,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "timeouts": 0,
            "success_rate": 0.0,
            "average_latency_ms": None,
            "p95_latency_ms": None,
            "last_status_code": None,
            "last_failure_category": None,
            "last_checked_at": None,
            "recent_events": []
        }

    total_requests = len(events)
    successful_requests = sum(1 for e in events if e.get("success", False))
    failed_requests = total_requests - successful_requests
    timeouts = sum(1 for e in events if e.get("timed_out", False) or e.get("failure_category") == "TIMEOUT")

    success_rate = round((successful_requests / total_requests) * 100.0, 2)
    latencies = [float(e["latency_ms"]) for e in events if "latency_ms" in e]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    p95_latency = calculate_p95(latencies)

    latest_event = events[-1]
    last_status_code = latest_event.get("status_code")
    last_failure_category = latest_event.get("failure_category")
    last_checked_at = latest_event.get("timestamp")

    # Evaluate health status based on actual observations
    recent_failures = sum(1 for e in events[-5:] if not e.get("success", False))
    
    if success_rate >= 95.0 and timeouts == 0 and recent_failures == 0:
        health_status = EndpointHealthStatus.HEALTHY
    elif success_rate < 70.0 or recent_failures >= 3 or (timeouts >= 3 and total_requests <= 10):
        health_status = EndpointHealthStatus.UNHEALTHY
    else:
        health_status = EndpointHealthStatus.DEGRADED

    # Recent observations (safely stripped of any sensitive fields)
    recent_events_safe = [
        {
            "event_id": e.get("event_id"),
            "status_code": e.get("status_code"),
            "latency_ms": e.get("latency_ms"),
            "success": e.get("success"),
            "failure_category": e.get("failure_category"),
            "retry_attempt": e.get("retry_attempt", 0),
            "timestamp": e.get("timestamp")
        }
        for e in events[-10:]
    ]

    return {
        "merchant_id": clean_merchant_id,
        "endpoint": clean_endpoint,
        "health": health_status.value,
        "total_requests": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "timeouts": timeouts,
        "success_rate": success_rate,
        "average_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
        "last_status_code": last_status_code,
        "last_failure_category": last_failure_category,
        "last_checked_at": last_checked_at,
        "recent_events": recent_events_safe
    }


def get_all_merchant_endpoint_health() -> List[Dict[str, Any]]:
    """
    Returns health summaries for all tracked merchant endpoints.
    """
    with _health_lock:
        if not _endpoint_observations and os.path.exists(HEALTH_STORE_PATH):
            _endpoint_observations.update(_load_persisted_health())
        keys = list(_endpoint_observations.keys())

    if not keys:
        # Return default endpoint in NO_DATA state if empty
        return [get_endpoint_health_summary("merchant_demo", "payment-webhook")]

    summaries = []
    for k in keys:
        parts = k.split(":", 1)
        m_id = parts[0]
        ep = parts[1] if len(parts) > 1 else "payment-webhook"
        summaries.append(get_endpoint_health_summary(m_id, ep))
    return summaries


def reset_merchant_health_state():
    """Helper to clear health store during unit test execution."""
    with _health_lock:
        _endpoint_observations.clear()
        if os.path.exists(HEALTH_STORE_PATH):
            try:
                os.remove(HEALTH_STORE_PATH)
            except Exception:
                pass


# Seed initial baseline observation matching demo data if store is brand new
def seed_initial_demo_health_if_empty():
    with _health_lock:
        if not _endpoint_observations and not os.path.exists(HEALTH_STORE_PATH):
            # Seed 5 observations reflecting the telemetry batch
            record_endpoint_observation("merchant_demo", "payment-webhook", status_code=200, latency_ms=180.0, retry_attempt=0, payment_id="pay_001")
            record_endpoint_observation("merchant_demo", "payment-webhook", status_code=504, latency_ms=3100.0, timed_out=True, retry_attempt=1, payment_id="pay_002")
            record_endpoint_observation("merchant_demo", "payment-webhook", status_code=500, latency_ms=450.0, retry_attempt=2, payment_id="pay_003")
            record_endpoint_observation("merchant_demo", "payment-webhook", status_code=200, latency_ms=160.0, retry_attempt=0, payment_id="pay_004")
            record_endpoint_observation("merchant_demo", "payment-webhook", status_code=504, latency_ms=3050.0, timed_out=True, retry_attempt=2, payment_id="pay_005")
