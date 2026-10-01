"""
Tests for backend/services/ai/provider.py — the dispatcher that routes
analyze_incident()/is_configured() to whichever backend AI_PROVIDER names.
Each underlying service has its own full test suite (test_claude_service.py,
test_nim_service.py); these tests only verify the dispatch logic itself.
"""
import pytest

from backend.config import settings
from backend.services.ai import provider


def test_defaults_to_claude(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "claude")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-fake")
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    assert provider.is_configured() is True
    assert provider.active_model_name() == settings.anthropic_model


def test_switches_to_nvidia_nim(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "nvidia_nim")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "nvidia_api_key", "nvapi-fake")
    assert provider.is_configured() is True
    assert provider.active_model_name() == settings.nvidia_nim_model


def test_inactive_providers_key_does_not_count(monkeypatch):
    """A key set for the provider that ISN'T active must not make
    ai_configured/is_configured report True -- that would silently claim AI
    works when the active provider actually has no key."""
    monkeypatch.setattr(settings, "ai_provider", "nvidia_nim")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-fake")
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    assert provider.is_configured() is False


def test_unknown_provider_raises_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "some_other_provider")
    with pytest.raises(provider.AIProviderNotConfiguredError):
        provider.is_configured()
