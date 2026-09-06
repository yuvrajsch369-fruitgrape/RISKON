"""The demo-access gate must be a strict no-op when disabled (the default),
and must correctly challenge/allow when enabled — see backend/middleware.py."""
import base64

from backend.config import settings


def _basic(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_disabled_by_default_everything_open(app_client):
    r = app_client.get("/api/health")
    assert r.status_code == 200


def test_enabled_blocks_without_credentials(app_client, monkeypatch):
    monkeypatch.setattr(settings, "demo_access_username", "demo")
    monkeypatch.setattr(settings, "demo_access_password", "letmein")
    r = app_client.get("/")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


def test_enabled_allows_with_correct_credentials(app_client, monkeypatch):
    monkeypatch.setattr(settings, "demo_access_username", "demo")
    monkeypatch.setattr(settings, "demo_access_password", "letmein")
    r = app_client.get("/", headers=_basic("demo", "letmein"))
    assert r.status_code == 200


def test_enabled_rejects_wrong_password(app_client, monkeypatch):
    monkeypatch.setattr(settings, "demo_access_username", "demo")
    monkeypatch.setattr(settings, "demo_access_password", "letmein")
    r = app_client.get("/", headers=_basic("demo", "wrong"))
    assert r.status_code == 401


def test_health_endpoint_never_gated_for_platform_health_checks(app_client, monkeypatch):
    monkeypatch.setattr(settings, "demo_access_username", "demo")
    monkeypatch.setattr(settings, "demo_access_password", "letmein")
    r = app_client.get("/api/health")  # no credentials sent, deliberately
    assert r.status_code == 200


def test_enabled_blocks_api_routes_too(app_client, monkeypatch):
    monkeypatch.setattr(settings, "demo_access_username", "demo")
    monkeypatch.setattr(settings, "demo_access_password", "letmein")
    r = app_client.get("/api/incidents")
    assert r.status_code == 401
