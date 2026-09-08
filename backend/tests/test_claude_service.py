"""
Tests for the Claude AI service — ALL of these use a mocked Anthropic client.
None of them prove the real Claude API integration works end-to-end; that
can only be verified by setting a real ANTHROPIC_API_KEY and making a real
call. What these DO verify, for real: environment-variable detection,
request construction, response parsing/validation, and every
failure-handling path this service defines.
"""
import json
import types

import anthropic
import pytest

from backend.config import settings
from backend.services.ai import claude_service


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


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


@pytest.fixture(autouse=True)
def _reset_client_singleton():
    claude_service._client = None
    yield
    claude_service._client = None


def test_not_configured_raises_before_any_network_call(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(claude_service.AIProviderNotConfiguredError):
        claude_service.analyze_incident({"incident": {"incident_id": "INC-TEST"}}, "INC-TEST")


def test_successful_response_is_parsed_and_validated(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-fake-test-key")

    fake_client = types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **kwargs: _FakeMessage(VALID_RESPONSE_JSON))
    )
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)

    result = claude_service.analyze_incident({"incident": {"incident_id": "INC-TEST"}}, "INC-TEST")
    assert result.summary == "Test summary."
    assert result.confidence == 0.7
    assert result.requires_human_review is True
    assert "INC-0001" in result.evidence


def test_response_wrapped_in_prose_is_still_extracted(monkeypatch):
    """The model sometimes wraps JSON in a sentence despite instructions —
    _parse_json_object must still find the object."""
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-fake-test-key")
    wrapped = f"Here is the analysis:\n{VALID_RESPONSE_JSON}\nEnd of analysis."
    fake_client = types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **kwargs: _FakeMessage(wrapped))
    )
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)
    result = claude_service.analyze_incident({"incident": {}}, "INC-TEST")
    assert result.summary == "Test summary."


def test_invalid_json_raises_response_invalid(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-fake-test-key")
    fake_client = types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **kwargs: _FakeMessage("not json at all"))
    )
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)
    with pytest.raises(claude_service.AIResponseInvalidError):
        claude_service.analyze_incident({"incident": {}}, "INC-TEST")


def test_schema_violation_raises_response_invalid(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-fake-test-key")
    bad = json.dumps({"summary": "ok", "confidence": 5.0})  # confidence out of [0,1] range, missing lists
    fake_client = types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **kwargs: _FakeMessage(bad))
    )
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)
    with pytest.raises(claude_service.AIResponseInvalidError):
        claude_service.analyze_incident({"incident": {}}, "INC-TEST")


def test_model_cannot_override_requires_human_review_false(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-fake-test-key")
    payload = json.loads(VALID_RESPONSE_JSON)
    payload["requires_human_review"] = False
    fake_client = types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **kwargs: _FakeMessage(json.dumps(payload)))
    )
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)
    # Pydantic's Literal[True] rejects `false` outright -- this is the
    # structural guardrail, not just a convention.
    with pytest.raises(claude_service.AIResponseInvalidError):
        claude_service.analyze_incident({"incident": {}}, "INC-TEST")


@pytest.mark.parametrize("exc_factory,reason", [
    (lambda: anthropic.APITimeoutError(request=object()), "timeout"),
    (lambda: anthropic.APIConnectionError(request=object()), "connection_error"),
])
def test_sdk_exceptions_map_to_typed_failures(monkeypatch, exc_factory, reason):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-fake-test-key")

    def _raise(**kwargs):
        raise exc_factory()

    fake_client = types.SimpleNamespace(messages=types.SimpleNamespace(create=_raise))
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)

    with pytest.raises(claude_service.AIRequestFailedError) as exc_info:
        claude_service.analyze_incident({"incident": {}}, "INC-TEST")
    assert exc_info.value.reason == reason


def test_rate_limit_error_maps_to_rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-fake-test-key")

    def _raise(**kwargs):
        raise anthropic.RateLimitError(
            message="rate limited", response=_FakeHTTPResponse(429), body=None,
        )

    fake_client = types.SimpleNamespace(messages=types.SimpleNamespace(create=_raise))
    monkeypatch.setattr(claude_service, "_get_client", lambda: fake_client)

    with pytest.raises(claude_service.AIRequestFailedError) as exc_info:
        claude_service.analyze_incident({"incident": {}}, "INC-TEST")
    assert exc_info.value.reason == "rate_limited"


class _FakeHTTPResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.headers = {}
        self.request = types.SimpleNamespace(method="POST", url="https://api.anthropic.com/v1/messages")
