"""
The one place route handlers import from for AI analysis -- picks the
active provider (claude_service or nim_service) based on settings.ai_provider
so AI_PROVIDER=claude / AI_PROVIDER=nvidia_nim is a pure config change, with
zero code changes anywhere downstream.
"""
from backend.config import settings
from backend.models.ai_schemas import IncidentAIAnalysis
from backend.services.ai import claude_service, nim_service
from backend.services.ai.claude_service import (  # re-exported for route handlers
    AIProviderNotConfiguredError,
    AIRequestFailedError,
    AIResponseInvalidError,
)

_PROVIDERS = {
    "claude": claude_service,
    "nvidia_nim": nim_service,
}


def _active():
    provider = _PROVIDERS.get(settings.ai_provider)
    if provider is None:
        raise AIProviderNotConfiguredError(
            f"Unknown AI_PROVIDER '{settings.ai_provider}'. Expected one of: {', '.join(_PROVIDERS)}."
        )
    return provider


def is_configured() -> bool:
    return _active().is_configured()


def active_model_name() -> str:
    return settings.active_ai_model


def analyze_incident(context: dict, incident_id: str) -> IncidentAIAnalysis:
    return _active().analyze_incident(context, incident_id)
