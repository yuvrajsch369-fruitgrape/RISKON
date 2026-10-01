"""
NVIDIA NIM provider for `analyze_incident()` -- a free, OpenAI-compatible
alternative to claude_service.py, used for RISKON V0 while there's no
revenue to justify Claude's per-call cost. Swap back via the AI_PROVIDER
env var (see backend/config.py) once a real deployment needs Claude's
reliability -- nothing downstream of backend/services/ai/provider.py needs
to change either way.

Raises the exact same exception types claude_service.py does (imported, not
redefined) so route handlers need only one except-clause regardless of which
provider is active.
"""
import json
import time

import openai
from pydantic import ValidationError

from backend.config import settings
from backend.logging_config import get_logger, log_ai_request
from backend.models.ai_schemas import IncidentAIAnalysis
from backend.services.ai.claude_service import (
    AIProviderNotConfiguredError,
    AIRequestFailedError,
    AIResponseInvalidError,
)
from backend.services.ai.prompts import SYSTEM_PROMPT

logger = get_logger("riskon.ai.nim")

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_nim_base_url,
            timeout=settings.nvidia_nim_timeout_seconds,
        )
    return _client


def is_configured() -> bool:
    return bool(settings.nvidia_api_key)


def _parse_json_object(text: str) -> dict:
    trimmed = text.strip()
    start, end = trimmed.find("{"), trimmed.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("no JSON object found in model response", trimmed, 0)
    return json.loads(trimmed[start:end + 1])


def analyze_incident(context: dict, incident_id: str) -> IncidentAIAnalysis:
    """Same contract as claude_service.analyze_incident(): raises one of the
    three typed errors above on any failure, never returns a fabricated or
    partial result."""
    if not is_configured():
        raise AIProviderNotConfiguredError(
            "AI provider not configured. Add NVIDIA_API_KEY to the environment to enable AI features."
        )

    user_prompt = (
        "Analyze the following incident context and respond with the required JSON object only.\n\n"
        + json.dumps(context, indent=2, default=str)
    )

    started_at = time.time()
    try:
        completion = _get_client().chat.completions.create(
            model=settings.nvidia_nim_model,
            max_tokens=settings.nvidia_nim_max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except openai.APITimeoutError as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.nvidia_nim_model,
                        started_at=started_at, success=False, error="timeout")
        raise AIRequestFailedError("timeout", "AI analysis timed out. Please try again shortly.") from e
    except openai.RateLimitError as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.nvidia_nim_model,
                        started_at=started_at, success=False, error="rate_limited")
        raise AIRequestFailedError("rate_limited", "AI service is busy right now. Please try again shortly.") from e
    except openai.APIConnectionError as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.nvidia_nim_model,
                        started_at=started_at, success=False, error="connection_error")
        raise AIRequestFailedError("connection_error", "Could not reach the AI service. Please try again shortly.") from e
    except openai.APIStatusError as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.nvidia_nim_model,
                        started_at=started_at, success=False, error=f"api_status_{e.status_code}")
        raise AIRequestFailedError("api_error", "AI analysis temporarily unavailable. Please try again shortly.") from e
    except Exception as e:  # noqa: BLE001 — deliberately broad: any other SDK failure must not fall through
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.nvidia_nim_model,
                        started_at=started_at, success=False, error="unexpected")
        logger.exception("Unexpected error calling NVIDIA NIM for incident %s", incident_id)
        raise AIRequestFailedError("unexpected", "AI analysis failed unexpectedly. Please try again shortly.") from e

    choice = completion.choices[0] if completion.choices else None
    text = choice.message.content if choice and choice.message else None
    if not text:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.nvidia_nim_model,
                        started_at=started_at, success=False, error="no_text_content")
        raise AIResponseInvalidError("Model response contained no text content.")

    try:
        parsed = _parse_json_object(text)
        analysis = IncidentAIAnalysis.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.nvidia_nim_model,
                        started_at=started_at, success=False, validation_ok=False, error="invalid_schema")
        logger.warning("NIM response for incident %s failed validation: %s", incident_id, e)
        raise AIResponseInvalidError("AI returned a response that didn't match the expected format.") from e

    log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.nvidia_nim_model,
                    started_at=started_at, success=True, validation_ok=True)
    return analysis
