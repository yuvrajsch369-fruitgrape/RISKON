"""
The ONE place in this backend that talks to Claude. Every AI-communication
requirement routes through `analyze_incident()` below — no route handler,
and nothing in the frontend, ever constructs a prompt or calls the Anthropic
SDK directly.

Design note — why one Claude call, not the 13-stage pipeline in
engine/pipeline.ts: that design (real, still valid, still undeleted) makes 13
sequential model calls per incident. For a PoC's first genuinely-wired AI
workflow, one well-structured call producing the schema in
backend/models/ai_schemas.py is the right-sized choice — 13x the latency and
cost for a first working feature would be over-building ahead of demonstrated
need. A future stage-by-stage pipeline could reuse this same service's error
handling and context-building patterns.
"""
import json
import time

import anthropic
from pydantic import ValidationError

from backend.config import settings
from backend.logging_config import get_logger, log_ai_request
from backend.models.ai_schemas import IncidentAIAnalysis
from backend.services.ai.prompts import SYSTEM_PROMPT

logger = get_logger("riskon.ai.claude")


class AIProviderNotConfiguredError(RuntimeError):
    """Raised before any network call is attempted when ANTHROPIC_API_KEY is
    empty/missing. Route handlers map this to HTTP 503 with the exact message
    the spec requires: 'AI provider not configured. Add ANTHROPIC_API_KEY to
    the environment to enable AI features.'"""


class AIRequestFailedError(RuntimeError):
    """The API call itself failed (timeout, rate limit, connection, or a
    non-2xx status from Anthropic). `reason` is a short machine-readable
    code; the human-readable message is safe to show a user as-is."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class AIResponseInvalidError(RuntimeError):
    """Claude responded, but the response wasn't valid JSON or didn't match
    IncidentAIAnalysis. The raw validation error is logged server-side only —
    never returned to a client."""


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # Reads ANTHROPIC_API_KEY from settings explicitly (not the SDK's own
        # os.environ default) so a key set only in .env — not the process
        # environment `uvicorn` was launched from — is still picked up.
        _client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.anthropic_timeout_seconds,
        )
    return _client


def is_configured() -> bool:
    """Whether CLAUDE specifically is configured -- independent of which
    provider is currently active (see settings.ai_provider). Must check the
    Anthropic key directly, not settings.ai_configured: that property
    reflects the ACTIVE provider, and this module can be asked about by the
    dispatcher (backend/services/ai/provider.py) regardless of which
    provider is active."""
    return bool(settings.anthropic_api_key)


def _parse_json_object(text: str) -> dict:
    trimmed = text.strip()
    start, end = trimmed.find("{"), trimmed.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("no JSON object found in model response", trimmed, 0)
    return json.loads(trimmed[start:end + 1])


def analyze_incident(context: dict, incident_id: str) -> IncidentAIAnalysis:
    """The one real, executable AI workflow in RISKON today. Raises one of
    the three typed errors above on any failure — never returns a fabricated
    or partial result."""
    if not is_configured():
        raise AIProviderNotConfiguredError(
            "AI provider not configured. Add ANTHROPIC_API_KEY to the environment to enable AI features."
        )

    user_prompt = (
        "Analyze the following incident context and respond with the required JSON object only.\n\n"
        + json.dumps(context, indent=2, default=str)
    )

    started_at = time.time()
    try:
        message = _get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APITimeoutError as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.anthropic_model,
                        started_at=started_at, success=False, error="timeout")
        raise AIRequestFailedError("timeout", "AI analysis timed out. Please try again shortly.") from e
    except anthropic.RateLimitError as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.anthropic_model,
                        started_at=started_at, success=False, error="rate_limited")
        raise AIRequestFailedError("rate_limited", "AI service is busy right now. Please try again shortly.") from e
    except anthropic.APIConnectionError as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.anthropic_model,
                        started_at=started_at, success=False, error="connection_error")
        raise AIRequestFailedError("connection_error", "Could not reach the AI service. Please try again shortly.") from e
    except anthropic.APIStatusError as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.anthropic_model,
                        started_at=started_at, success=False, error=f"api_status_{e.status_code}")
        raise AIRequestFailedError("api_error", "AI analysis temporarily unavailable. Please try again shortly.") from e
    except Exception as e:  # noqa: BLE001 — deliberately broad: any other SDK failure must not fall through
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.anthropic_model,
                        started_at=started_at, success=False, error="unexpected")
        logger.exception("Unexpected error calling Claude for incident %s", incident_id)
        raise AIRequestFailedError("unexpected", "AI analysis failed unexpectedly. Please try again shortly.") from e

    text_block = next((b for b in message.content if getattr(b, "type", None) == "text"), None)
    if text_block is None:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.anthropic_model,
                        started_at=started_at, success=False, error="no_text_content")
        raise AIResponseInvalidError("Model response contained no text content.")

    try:
        parsed = _parse_json_object(text_block.text)
        analysis = IncidentAIAnalysis.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as e:
        log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.anthropic_model,
                        started_at=started_at, success=False, validation_ok=False, error="invalid_schema")
        logger.warning("Claude response for incident %s failed validation: %s", incident_id, e)
        raise AIResponseInvalidError("AI returned a response that didn't match the expected format.") from e

    log_ai_request(request_type="incident_analysis", record_id=incident_id, model=settings.anthropic_model,
                    started_at=started_at, success=True, validation_ok=True)
    return analysis
