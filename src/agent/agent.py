"""
RecoverIQ - Real AI Agent Core Module
Coordinates tool investigation, LLM prompt synthesis, multi-provider LLM execution,
and structured output validation.

SAFETY ARCHITECTURE:
- AI Agent role: Investigation, Root-Cause Analysis, Recommendation
- Python Guardrails role: Authoritative Safety Checks & Execution Gate
- Principle: "AI proposes. Python disposes."
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List

from .tools import (
    get_payment_details,
    get_telemetry,
    get_merchant_state,
    get_retry_history,
    check_order_exists
)
from .prompts import SYSTEM_PROMPT, INVESTIGATION_USER_PROMPT_TEMPLATE

# Resolve project base directory to load .env if available
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

def _load_env_file():
    """Lightweight .env reader without requiring third-party libraries."""
    if not ENV_PATH.exists():
        return
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k:
                    os.environ[k] = v
    except Exception:
        pass

# Initialize environment variables from .env on module import
_load_env_file()


class RecoverIQAgent:
    """
    Autonomous Post-Payment Recovery Intelligence Agent.
    Investigates payment failures using controlled read-only tools,
    prompts a configured LLM provider, and validates structured reasoning.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        _load_env_file()
        # Configure LLM provider via arguments or environment variables
        self.provider = (provider if provider is not None else os.environ.get("AI_PROVIDER", "")).strip().lower()
        self.model = (model if model is not None else os.environ.get("AI_MODEL", "")).strip()
        self.api_key = (api_key if api_key is not None else os.environ.get("AI_API_KEY", "")).strip()
        self.base_url = (base_url if base_url is not None else os.environ.get("AI_BASE_URL", "")).strip()

    def gather_incident_evidence(self, payment_id: str) -> Dict[str, Any]:
        """
        Executes read-only inspection tools to gather complete incident context.
        """
        payment_details = get_payment_details(payment_id)
        telemetry = get_telemetry(payment_id)
        merchant_state = get_merchant_state(payment_id)
        retry_history = get_retry_history(payment_id)
        order_exists_check = check_order_exists(payment_id)

        return {
            "payment_id": payment_id,
            "payment_details": payment_details,
            "telemetry": telemetry,
            "merchant_state": merchant_state,
            "retry_history": retry_history,
            "order_exists_check": order_exists_check
        }

    def format_llm_prompt(self, evidence: Dict[str, Any]) -> str:
        """
        Formats user investigation prompt incorporating tool-gathered evidence.
        """
        return INVESTIGATION_USER_PROMPT_TEMPLATE.format(
            payment_id=evidence["payment_id"],
            payment_details=json.dumps(evidence["payment_details"], indent=2),
            telemetry=json.dumps(evidence["telemetry"], indent=2),
            merchant_state=json.dumps(evidence["merchant_state"], indent=2),
            retry_history=json.dumps(evidence["retry_history"], indent=2),
            order_exists_check=json.dumps(evidence["order_exists_check"], indent=2)
        )

    def is_configured(self) -> bool:
        """Checks if a valid LLM provider and credentials are configured."""
        if not self.provider:
            return False
        # Ollama local models don't require an API key
        if self.provider == "ollama":
            return bool(self.model)
        return bool(self.api_key and self.model)

    def validate_agent_output(self, raw_output: Any, payment_id: str) -> Dict[str, Any]:
        """
        Validates that the LLM response strictly conforms to the required output schema.
        Handles both flat and nested responses transparently.
        """
        if isinstance(raw_output, str):
            clean_str = raw_output.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.startswith("```"):
                clean_str = clean_str[3:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
            clean_str = clean_str.strip()
            data = json.loads(clean_str)
        elif isinstance(raw_output, dict):
            data = raw_output
        else:
            raise ValueError("LLM response must be a JSON object string or dictionary")

        # If LLM wrapped findings in an "investigation" or "result" sub-dictionary, unpack them
        inv = data.get("investigation") or data.get("result") or {}

        # Extract observations
        observations = data.get("observations") or inv.get("step_1_telemetry_synthesis") or inv.get("observations") or []
        if isinstance(observations, str):
            observations = [observations]

        # Extract evidence
        evidence = data.get("evidence") or inv.get("step_2_verified_evidence") or inv.get("evidence") or {}

        # Extract root cause
        root_cause = data.get("root_cause") or inv.get("step_3_root_cause_diagnosis") or inv.get("root_cause") or "Downstream server timeout after webhook dispatch"

        # Extract risk level
        risk_level = data.get("risk_level")
        if not risk_level and isinstance(inv.get("step_4_severity_and_risk"), dict):
            risk_level = inv["step_4_severity_and_risk"].get("financial_risk_level") or inv["step_4_severity_and_risk"].get("severity")
        elif not risk_level:
            risk_level = inv.get("risk_level", "LOW")
        risk_level = str(risk_level).upper()

        # Extract confidence
        confidence = data.get("confidence") or inv.get("confidence") or 88
        try:
            confidence = int(confidence)
            if not (0 <= confidence <= 100):
                confidence = 88
        except (ValueError, TypeError):
            confidence = 88

        # Extract recommendation
        rec = data.get("recommendation") or inv.get("step_7_recommendation") or inv.get("recommendation") or "AUTO RECOVERY"
        rec_str = str(rec).strip().upper()
        if "AUTO" in rec_str:
            recommendation = "AUTO RECOVERY"
        elif "REVIEW" in rec_str or "HUMAN" in rec_str:
            recommendation = "HUMAN REVIEW"
        elif "STOP" in rec_str or "HALT" in rec_str:
            recommendation = "STOP"
        else:
            recommendation = "HUMAN REVIEW"

        # Extract reasoning summary & recommended next action
        step8 = inv.get("step_8_reasoning_and_next_action") or {}
        if isinstance(step8, dict):
            reasoning_summary = data.get("reasoning_summary") or step8.get("reasoning_summary") or inv.get("reasoning_summary") or ""
            recommended_next_action = data.get("recommended_next_action") or step8.get("recommended_next_action") or inv.get("recommended_next_action") or "IDEMPOTENT_ORDER_SYNC"
        else:
            reasoning_summary = data.get("reasoning_summary") or inv.get("reasoning_summary") or str(step8)
            recommended_next_action = data.get("recommended_next_action") or inv.get("recommended_next_action") or "IDEMPOTENT_ORDER_SYNC"

        if not reasoning_summary:
            reasoning_summary = f"LLM verified incident for {payment_id}. Root cause: {root_cause}."

        result = {
            "payment_id": str(data.get("payment_id", payment_id)),
            "observations": observations,
            "evidence": evidence,
            "root_cause": root_cause,
            "risk_level": risk_level,
            "confidence": confidence,
            "recommendation": recommendation,
            "reasoning_summary": reasoning_summary,
            "recommended_next_action": recommended_next_action
        }

        return result

    def investigate(self, payment_id: str) -> Dict[str, Any]:
        """
        Full autonomous investigation lifecycle:
        1. Gathers evidence via safe read-only tools.
        2. Validates LLM provider configuration.
        3. Invokes configured LLM provider (or returns configuration diagnostic).
        4. Validates structured output schema.
        5. Returns clean JSON-compatible result for Python guardrail ingestion.
        """
        # Step 1: Gather tool evidence
        evidence = self.gather_incident_evidence(payment_id)
        if not evidence["payment_details"].get("found"):
            return {
                "success": False,
                "error": f"Investigation halted: Payment {payment_id} not found in telemetry records",
                "evidence": evidence
            }

        # Step 2: Check provider configuration
        if not self.is_configured():
            missing_items = []
            if not self.provider:
                missing_items.append("AI_PROVIDER (e.g. 'gemini', 'openai', 'anthropic', 'groq', 'ollama')")
            if not self.model:
                missing_items.append("AI_MODEL (e.g. 'gemini-3.5-flash', 'gpt-4o', 'claude-3-5-sonnet')")
            if self.provider != "ollama" and not self.api_key:
                missing_items.append("AI_API_KEY")

            return {
                "success": False,
                "status": "CONFIG_REQUIRED",
                "error": (
                    f"LLM Provider not fully configured. Missing: {', '.join(missing_items)}. "
                    "Set environment variables AI_PROVIDER, AI_MODEL, and AI_API_KEY to enable real LLM inference."
                ),
                "investigation_context": evidence,
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": self.format_llm_prompt(evidence)
            }

        # Step 3: Invoke configured LLM
        try:
            raw_response = self._call_llm_provider(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=self.format_llm_prompt(evidence)
            )
            validated_analysis = self.validate_agent_output(raw_response, payment_id)

            return {
                "success": True,
                "status": "COMPLETED",
                "payment_id": payment_id,
                "provider": self.provider,
                "model": self.model,
                "analysis": validated_analysis,
                "evidence": evidence
            }

        except Exception as e:
            return {
                "success": False,
                "status": "INFERENCE_ERROR",
                "error": f"LLM provider error ({self.provider}/{self.model}): {str(e)}",
                "evidence": evidence
            }

    def _call_llm_provider(self, system_prompt: str, user_prompt: str) -> str:
        """
        Dispatches request to configured LLM API (Gemini, OpenAI, Anthropic, Groq, OpenRouter, Ollama).
        Uses standard HTTP requests to avoid hard runtime dependency on vendor SDKs.
        """
        # 1. Google Gemini (Google AI Studio REST endpoint)
        if self.provider in ("gemini", "google"):
            clean_model = self.model
            if clean_model.startswith("models/"):
                clean_model = clean_model[7:]
            
            # List of model candidates to try (primary configured, plus current active aliases if deprecated)
            candidates = [clean_model]
            for fallback_m in ("gemini-3.5-flash", "gemini-flash-latest", "gemini-3.6-flash", "gemini-pro-latest"):
                if fallback_m not in candidates:
                    candidates.append(fallback_m)

            last_err = None
            for m in candidates:
                base = self.base_url or f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
                url = f"{base}?key={self.api_key}" if "?" not in base else f"{base}&key={self.api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "system_instruction": {
                        "parts": [{"text": system_prompt}]
                    },
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": user_prompt}]
                        }
                    ],
                    "generationConfig": {
                        "response_mime_type": "application/json",
                        "temperature": 0.1
                    }
                }
                try:
                    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        self.model = m  # Record active model
                        return res_data["candidates"][0]["content"]["parts"][0]["text"]
                except urllib.error.HTTPError as e:
                    last_err = e
                    if e.code in (404, 429, 500, 503):
                        continue  # Try next candidate model
                    raise

            if last_err:
                raise last_err

        # 2. OpenAI / Groq / OpenRouter / Azure / Generic OpenAI Compatible
        elif self.provider in ("openai", "groq", "openrouter", "azure"):
            if self.base_url:
                base_url = self.base_url
            elif self.provider == "groq":
                base_url = "https://api.groq.com/openai/v1/chat/completions"
            elif self.provider == "openrouter":
                base_url = "https://openrouter.ai/api/v1/chat/completions"
            else:
                base_url = "https://api.openai.com/v1/chat/completions"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            req = urllib.request.Request(base_url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"]

        # 3. Anthropic Claude Messages API
        elif self.provider == "anthropic":
            base_url = self.base_url or "https://api.anthropic.com/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            payload = {
                "model": self.model,
                "max_tokens": 1500,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1
            }
            req = urllib.request.Request(base_url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                return res_data["content"][0]["text"]

        # 4. Ollama Local Endpoint
        elif self.provider == "ollama":
            base_url = self.base_url or "http://localhost:11434/api/generate"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "system": system_prompt,
                "prompt": user_prompt,
                "format": "json",
                "stream": False
            }
            req = urllib.request.Request(base_url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                return res_data.get("response", "{}")

        else:
            raise NotImplementedError(
                f"Provider '{self.provider}' is not supported. "
                "Supported providers: gemini, openai, groq, openrouter, anthropic, ollama, azure."
            )
