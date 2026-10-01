"""
Tests for the NVIDIA NIM AI service — ALL of these use a mocked OpenAI
client. None of them prove the real NIM API integration works end-to-end;
that can only be verified by setting a real NVIDIA_API_KEY and making a real
call. What these DO verify, for real: environment-variable detection,
request construction, response parsing/validation, and every
failure-handling path this service defines — mirroring test_claude_service.py
so both providers are held to the identical contract.
"""
import json
import types

import openai
import pytest

from backend.config import settings
from backend.services.ai import nim_service

VALID_RESPONSE_JSON = json.dumps({
    "summary": "Test summary.",
    "observed_facts": ["Fact one."],
    "ai_hypotheses": ["Hypothesis one, may indicate X."],
    "related_risk_signals": ["Signal one."],
    "evidence": ["INC-0001"],
    "recommendations": ["Recommend reviewing control X."],
    "confidence": 0.7,
    "uncertainties": ["Uncertainty one."],
    "requires_human_review": True,
})


def _fake_completion(text):
    message = types.SimpleNamespace(content=text)
    choice = types.SimpleNamespace(message=message)
    return types.SimpleNamespace(choices=[choice])


@pytest.fixture(autouse=True)
def _reset_client_singleton():
    nim_service._client = None
    yield
    nim_service._client = None


def test_not_configured_raises_before_any_network_call(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    with pytest.raises(nim_service.AIProviderNotConfiguredError):
        nim_service.analyze_incident({"incident": {"incident_id": "INC-TEST"}}, "INC-TEST")


def test_successful_response_is_parsed_and_validated(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvapi-fake-test-key")

    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda **kwargs: _fake_completion(VALID_RESPONSE_JSON))
        )
    )
    monkeypatch.setattr(nim_service, "_get_client", lambda: fake_client)

    result = nim_service.analyze_incident({"incident": {"incident_id": "INC-TEST"}}, "INC-TEST")
    assert result.summary == "Test summary."
    assert result.confidence == 0.7
    assert result.requires_human_review is True
    assert "INC-0001" in result.evidence


def test_response_wrapped_in_prose_is_still_extracted(monkeypatch):
    """The model sometimes wraps JSON in a sentence despite instructions —
    _parse_json_object must still find the object."""
    monkeypatch.setattr(settings, "nvidia_api_key", "nvapi-fake-test-key")
    wrapped = f"Here is the analysis:\n{VALID_RESPONSE_JSON}\nEnd of analysis."
    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda **kwargs: _fake_completion(wrapped))
        )
    )
    monkeypatch.setattr(nim_service, "_get_client", lambda: fake_client)
    result = nim_service.analyze_incident({"incident": {}}, "INC-TEST")
    assert result.summary == "Test summary."


def test_invalid_json_raises_response_invalid(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvapi-fake-test-key")
    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda **kwargs: _fake_completion("not json at all"))
        )
    )
    monkeypatch.setattr(nim_service, "_get_client", lambda: fake_client)
    with pytest.raises(nim_service.AIResponseInvalidError):
        nim_service.analyze_incident({"incident": {}}, "INC-TEST")


def test_schema_violation_raises_response_invalid(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvapi-fake-test-key")
    bad = json.dumps({"summary": "ok", "confidence": 5.0})  # confidence out of [0,1] range, missing lists
    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda **kwargs: _fake_completion(bad))
        )
    )
    monkeypatch.setattr(nim_service, "_get_client", lambda: fake_client)
    with pytest.raises(nim_service.AIResponseInvalidError):
        nim_service.analyze_incident({"incident": {}}, "INC-TEST")


def test_model_cannot_override_requires_human_review_false(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvapi-fake-test-key")
    payload = json.loads(VALID_RESPONSE_JSON)
    payload["requires_human_review"] = False
    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda **kwargs: _fake_completion(json.dumps(payload)))
        )
    )
    monkeypatch.setattr(nim_service, "_get_client", lambda: fake_client)
    # Pydantic's Literal[True] rejects `false` outright -- this is the
    # structural guardrail, not just a convention.
    with pytest.raises(nim_service.AIResponseInvalidError):
        nim_service.analyze_incident({"incident": {}}, "INC-TEST")


@pytest.mark.parametrize("exc_factory,reason", [
    (lambda: openai.APITimeoutError(request=_FakeHTTPXRequest()), "timeout"),
    (lambda: openai.APIConnectionError(request=_FakeHTTPXRequest()), "connection_error"),
])
def test_sdk_exceptions_map_to_typed_failures(monkeypatch, exc_factory, reason):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvapi-fake-test-key")

    def _raise(**kwargs):
        raise exc_factory()

    fake_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=_raise)))
    monkeypatch.setattr(nim_service, "_get_client", lambda: fake_client)

    with pytest.raises(nim_service.AIRequestFailedError) as exc_info:
        nim_service.analyze_incident({"incident": {}}, "INC-TEST")
    assert exc_info.value.reason == reason


def test_rate_limit_error_maps_to_rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "nvapi-fake-test-key")

    def _raise(**kwargs):
        raise openai.RateLimitError(
            message="rate limited", response=_FakeHTTPResponse(429), body=None,
        )

    fake_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=_raise)))
    monkeypatch.setattr(nim_service, "_get_client", lambda: fake_client)

    with pytest.raises(nim_service.AIRequestFailedError) as exc_info:
        nim_service.analyze_incident({"incident": {}}, "INC-TEST")
    assert exc_info.value.reason == "rate_limited"


class _FakeHTTPXRequest:
    def __init__(self):
        self.method = "POST"
        self.url = "https://integrate.api.nvidia.com/v1/chat/completions"


class _FakeHTTPResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.headers = {}
        self.request = _FakeHTTPXRequest()
