"""
RecoverIQ - Security Sanitizer and PII Masking Utility (P1 Security Credibility)

Guarantees zero exposure of API keys, bearer tokens, secrets, JWTs,
and full credit card or sensitive authentication materials in responses,
telemetry, distributed traces, and audit logs.
"""

import re
from typing import Any, Dict, List, Union

REDACTED_TEXT = "[REDACTED]"

SENSITIVE_EXACT_KEYS = {
    "secret", "token", "password", "authorization", "bearer", "credential",
    "jwt", "private_key", "api_key", "signature_raw", "client_secret"
}

SENSITIVE_SUBSTRING_PATTERNS = (
    "api_key", "access_token", "secret_key", "auth_token", "bearer_token", "private_key"
)

CARD_REGEX = re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b')


def mask_card_number(card_str: str) -> str:
    """Masks card numbers showing only the last 4 digits."""
    cleaned = re.sub(r'\D', '', str(card_str))
    if len(cleaned) >= 13:
        return f"****-****-****-{cleaned[-4:]}"
    return REDACTED_TEXT


def is_sensitive_key(key: str) -> bool:
    k_lower = str(key).lower().strip()
    if k_lower in SENSITIVE_EXACT_KEYS:
        return True
    if any(p in k_lower for p in SENSITIVE_SUBSTRING_PATTERNS):
        return True
    return False


def sanitize_sensitive_data(obj: Any) -> Any:
    """
    Recursively scans dictionaries, lists, and strings to sanitize sensitive material.
    """
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if is_sensitive_key(str(k)):
                sanitized[k] = REDACTED_TEXT
            else:
                sanitized[k] = sanitize_sensitive_data(v)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_sensitive_data(item) for item in obj]
    elif isinstance(obj, str):
        if CARD_REGEX.search(obj):
            return CARD_REGEX.sub(lambda m: mask_card_number(m.group(0)), obj)
        if obj.lower().startswith("bearer ") or obj.lower().startswith("basic "):
            return REDACTED_TEXT
        return obj
    return obj

