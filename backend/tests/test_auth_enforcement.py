"""AUTH_REQUIRED must be a strict no-op when disabled (the default, which
keeps RISKON's open sales-demo experience exactly as it always has been),
and must correctly block/allow when enabled — see backend/middleware.py's
AuthRequiredMiddleware and backend/services/auth.py."""
from backend.config import settings

_SIGNUP_BODY = {
    "name": "Auth Enforcement Check", "occupation": "Employee", "post": "Rex North Plant",
    "email": "auth.enforcement@example.com", "password": "CorrectHorseBattery9",
}


def test_disabled_by_default_open_access(app_client):
    assert app_client.get("/api/incidents").status_code == 200


def test_enabled_blocks_unauthenticated(app_client, monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    r = app_client.get("/api/incidents")
    assert r.status_code == 401
    assert r.json()["error"] == "authentication_required"


def test_enabled_allows_authenticated(app_client, monkeypatch):
    app_client.post("/api/users/signup", json=_SIGNUP_BODY)  # session cookie now on the client
    monkeypatch.setattr(settings, "auth_required", True)
    assert app_client.get("/api/incidents").status_code == 200


def test_enabled_health_still_open(app_client, monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    assert app_client.get("/api/health").status_code == 200


def test_enabled_signup_and_login_still_reachable(app_client, monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    assert app_client.post("/api/users/signup", json=_SIGNUP_BODY).status_code == 201


def test_enabled_me_reachable_with_no_session(app_client, monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    r = app_client.get("/api/users/me")
    assert r.status_code == 200
    assert r.json() == {"user": None}


def test_enabled_frontend_root_still_reachable(app_client, monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    assert app_client.get("/").status_code == 200


def test_enabled_blocks_arbitrary_user_lookup(app_client, monkeypatch):
    """Confirmed real gap: the previous exemption matched on the "/api/users/"
    PREFIX, which also covered GET /api/users/{user_id} -- an arbitrary-id
    lookup the frontend never calls and has no legitimate pre-auth use case.
    With AUTH_REQUIRED on, that let anyone enumerate every real user's name/
    email/role/facility with zero session, just by incrementing the
    sequential USR-nnnn id. Must now require a real session like any other
    business-data route."""
    signup = app_client.post("/api/users/signup", json=_SIGNUP_BODY)
    user_id = signup.json()["user_id"]
    app_client.post("/api/users/logout")  # drop the session; keep the account

    monkeypatch.setattr(settings, "auth_required", True)
    r = app_client.get(f"/api/users/{user_id}")
    assert r.status_code == 401
    assert r.json()["error"] == "authentication_required"
