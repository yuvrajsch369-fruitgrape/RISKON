from backend.routes.users import _rbac_role_for
from backend.services.auth import SESSION_COOKIE_NAME


def test_occupation_mapping_known_titles():
    assert _rbac_role_for("Plant Manager") == "plant_manager"
    assert _rbac_role_for("Safety Manager") == "hse_manager"
    assert _rbac_role_for("EHS Coordinator") == "hse_manager"
    assert _rbac_role_for("Executive") == "executive"


def test_occupation_mapping_default_is_employee():
    assert _rbac_role_for("Forklift Operator") == "employee"
    assert _rbac_role_for("Some Made Up Title") == "employee"


def test_signup_persists_and_returns_role(app_client):
    r = app_client.post("/api/users/signup", json={
        "name": "Jordan Rivera", "occupation": "Safety Manager", "post": "Rex North Plant",
        "email": "jordan.rivera@example.com", "password": "CorrectHorseBattery9",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Jordan Rivera"
    assert body["rbac_role"] == "hse_manager"
    assert body["user_id"].startswith("USR-")
    assert body["email"] == "jordan.rivera@example.com"
    assert "password" not in body and "password_hash" not in body
    assert SESSION_COOKIE_NAME in r.cookies

    r2 = app_client.get(f"/api/users/{body['user_id']}")
    assert r2.status_code == 200
    assert r2.json()["post"] == "Rex North Plant"
    assert "password_hash" not in r2.json()


def test_signup_unknown_occupation_defaults_to_employee(app_client):
    r = app_client.post("/api/users/signup", json={
        "name": "Casey Doe", "occupation": "Forklift Operator", "post": "Rex South Plant",
        "email": "casey.doe@example.com", "password": "CorrectHorseBattery9",
    })
    assert r.status_code == 201
    assert r.json()["rbac_role"] == "employee"


def test_signup_missing_field_is_422(app_client):
    r = app_client.post("/api/users/signup", json={"name": "No Occupation"})
    assert r.status_code == 422


def test_signup_short_password_is_422(app_client):
    r = app_client.post("/api/users/signup", json={
        "name": "Short Pw", "occupation": "Employee", "post": "Rex North Plant",
        "email": "short.pw@example.com", "password": "tooshort",
    })
    assert r.status_code == 422


def test_signup_invalid_email_is_422(app_client):
    r = app_client.post("/api/users/signup", json={
        "name": "Bad Email", "occupation": "Employee", "post": "Rex North Plant",
        "email": "not-an-email", "password": "CorrectHorseBattery9",
    })
    assert r.status_code == 422


def test_signup_duplicate_email_is_409(app_client):
    body = {"name": "First", "occupation": "Employee", "post": "Rex North Plant",
            "email": "dupe@example.com", "password": "CorrectHorseBattery9"}
    r1 = app_client.post("/api/users/signup", json=body)
    assert r1.status_code == 201
    body["name"] = "Second"
    body["email"] = "DUPE@example.com"  # case-insensitive collision
    r2 = app_client.post("/api/users/signup", json=body)
    assert r2.status_code == 409


def test_get_unknown_user_is_404(app_client):
    r = app_client.get("/api/users/USR-DOES-NOT-EXIST")
    assert r.status_code == 404


def test_login_succeeds_and_sets_cookie(app_client):
    app_client.post("/api/users/signup", json={
        "name": "Login User", "occupation": "Employee", "post": "Rex North Plant",
        "email": "login.user@example.com", "password": "CorrectHorseBattery9",
    })
    r = app_client.post("/api/users/login", json={
        "email": "login.user@example.com", "password": "CorrectHorseBattery9",
    })
    assert r.status_code == 200
    assert SESSION_COOKIE_NAME in r.cookies
    assert "password_hash" not in r.json()


def test_login_wrong_password_is_401(app_client):
    app_client.post("/api/users/signup", json={
        "name": "Wrong Pw", "occupation": "Employee", "post": "Rex North Plant",
        "email": "wrong.pw@example.com", "password": "CorrectHorseBattery9",
    })
    r = app_client.post("/api/users/login", json={
        "email": "wrong.pw@example.com", "password": "TotallyWrongPassword",
    })
    assert r.status_code == 401


def test_login_unknown_email_is_401(app_client):
    r = app_client.post("/api/users/login", json={
        "email": "nobody@example.com", "password": "WhateverPassword1",
    })
    assert r.status_code == 401


def test_me_reports_no_user_when_logged_out(app_client):
    r = app_client.get("/api/users/me")
    assert r.status_code == 200
    assert r.json() == {"user": None}


def test_me_reports_user_when_logged_in(app_client):
    app_client.post("/api/users/signup", json={
        "name": "Me Check", "occupation": "Employee", "post": "Rex North Plant",
        "email": "me.check@example.com", "password": "CorrectHorseBattery9",
    })
    r = app_client.get("/api/users/me")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "me.check@example.com"
    assert "password_hash" not in r.json()["user"]


def test_logout_then_me_reports_no_user(app_client):
    app_client.post("/api/users/signup", json={
        "name": "Logout Check", "occupation": "Employee", "post": "Rex North Plant",
        "email": "logout.check@example.com", "password": "CorrectHorseBattery9",
    })
    r_out = app_client.post("/api/users/logout")
    assert r_out.status_code == 204
    r_me = app_client.get("/api/users/me")
    assert r_me.json() == {"user": None}


def test_password_never_appears_in_any_response(app_client):
    password = "CorrectHorseBattery9"
    r1 = app_client.post("/api/users/signup", json={
        "name": "Secret Check", "occupation": "Employee", "post": "Rex North Plant",
        "email": "secret.check@example.com", "password": password,
    })
    r2 = app_client.post("/api/users/login", json={"email": "secret.check@example.com", "password": password})
    r3 = app_client.get("/api/users/me")
    for r in (r1, r2, r3):
        assert password not in r.text
        assert "password_hash" not in r.text
