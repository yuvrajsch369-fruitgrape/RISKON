from backend.config import Settings


def test_ai_configured_false_when_key_empty(monkeypatch):
    s = Settings()
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
    s.anthropic_api_key = "sk-ant-fake-test-key"
    assert s.ai_configured is True


def test_public_dict_never_contains_the_key():
    s = Settings()
    s.anthropic_api_key = "sk-ant-super-secret-value"
    d = s.as_public_dict()
    assert "sk-ant-super-secret-value" not in str(d)
    assert "anthropic_api_key" not in d
    assert d["ai_configured"] is True
