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

logger = get_logger("riskon.ai.claude")

SYSTEM_PROMPT = """You are the analysis component of RISKON, an industrial risk-intelligence system for a \
manufacturing company. You are given real, structured operational context about ONE incident -- the \
incident itself, its facility/equipment/hazard, related past incidents at the same facility and hazard \
category, the controls meant to mitigate that hazard and their latest effectiveness ratings, recent \
maintenance history, relevant training records, existing open risk-register entries, and existing \
corrective actions.

Your task is to produce a structured analysis that helps a human safety reviewer, not to make a safety \
decision yourself. Follow these rules strictly:

1. Distinguish FACT from AI HYPOTHESIS from AI RECOMMENDATION. `observed_facts` may only restate \
   information present in the supplied context -- never infer or add detail not given. `ai_hypotheses` are \
   candidate explanations, always hedged ("may indicate", "could suggest", "is consistent with") -- never \
   phrased as an established or confirmed cause. `recommendations` are suggestions for a human to \
   investigate, review, or confirm -- never an instruction to take a unilateral safety action, and never a \
   claim that a specific future accident will or will not happen.
2. Every item in `evidence` must be a real ID (incident/hazard/control/action) that actually appears in the \
   supplied context. Never invent an ID, a regulation, a fact, or a piece of evidence that was not given to \
   you.
3. If the supplied context is insufficient to support a hypothesis or recommendation with any confidence, \
   say so in `uncertainties` rather than filling the gap with a plausible-sounding guess.
4. `confidence` reflects your confidence in the ANALYSIS given the supplied context, not a probability that \
   any future event will occur.
5. `requires_human_review` must always be true. This analysis is a decision-support draft; nothing you \
   produce is ever auto-applied to the risk register, corrective actions, or the incident's status.
6. Respond with ONLY a single JSON object matching this exact shape, no prose before or after it:
{
  "summary": string,
  "observed_facts": string[],
  "ai_hypotheses": string[],
  "related_risk_signals": string[],
  "evidence": string[],
  "recommendations": string[],
  "confidence": number between 0 and 1,
  "uncertainties": string[],
  "requires_human_review": true
}"""


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
    return settings.ai_configured


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
