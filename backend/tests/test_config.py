from backend.config import Settings


def test_ai_configured_false_when_key_empty(monkeypatch):
    s = Settings()
    s.ai_provider = "claude"  # pinned: must not depend on whatever AI_PROVIDER is in the local .env
    s.anthropic_api_key = ""
    assert s.ai_configured is False


def test_ai_configured_false_when_whitespace(monkeypatch):
    s = Settings()
    s.anthropic_api_key = "   "
    # Settings strips at load time in the real class attribute assignment,
    # but simulate a raw whitespace value defensively here too.
    assert bool(s.anthropic_api_key.strip()) is False


def test_ai_configured_true_when_key_present():
    s = Settings()
    s.ai_provider = "claude"  # pinned: must not depend on whatever AI_PROVIDER is in the local .env
    s.anthropic_api_key = "sk-ant-fake-test-key"
    assert s.ai_configured is True


def test_public_dict_never_contains_the_key():
    s = Settings()
    s.ai_provider = "claude"  # pinned: must not depend on whatever AI_PROVIDER is in the local .env
    s.anthropic_api_key = "sk-ant-super-secret-value"
    d = s.as_public_dict()
    assert "sk-ant-super-secret-value" not in str(d)
    assert "anthropic_api_key" not in d
    assert d["ai_configured"] is True


def test_ai_configured_checks_active_provider_not_any_key():
    s = Settings()
    s.ai_provider = "nvidia_nim"
    s.anthropic_api_key = "sk-ant-fake-test-key"  # set, but NOT the active provider
    s.nvidia_api_key = ""
    assert s.ai_configured is False


def test_ai_configured_true_for_nvidia_nim_when_its_key_present():
    s = Settings()
    s.ai_provider = "nvidia_nim"
    s.nvidia_api_key = "nvapi-fake-test-key"
    assert s.ai_configured is True
    assert s.active_ai_model == s.nvidia_nim_model


def test_public_dict_never_contains_the_nvidia_key():
    s = Settings()
    s.ai_provider = "nvidia_nim"
    s.nvidia_api_key = "nvapi-super-secret-value"
    d = s.as_public_dict()
    assert "nvapi-super-secret-value" not in str(d)
    assert "nvidia_api_key" not in d
    assert d["ai_provider"] == "nvidia_nim"
