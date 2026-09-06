from backend.routes.users import _rbac_role_for


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
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Jordan Rivera"
    assert body["rbac_role"] == "hse_manager"
    assert body["user_id"].startswith("USR-")

    r2 = app_client.get(f"/api/users/{body['user_id']}")
    assert r2.status_code == 200
    assert r2.json()["post"] == "Rex North Plant"


def test_signup_unknown_occupation_defaults_to_employee(app_client):
    r = app_client.post("/api/users/signup", json={
        "name": "Casey Doe", "occupation": "Forklift Operator", "post": "Rex South Plant",
    })
    assert r.status_code == 201
    assert r.json()["rbac_role"] == "employee"


def test_signup_missing_field_is_422(app_client):
    r = app_client.post("/api/users/signup", json={"name": "No Occupation"})
    assert r.status_code == 422


def test_get_unknown_user_is_404(app_client):
    r = app_client.get("/api/users/USR-DOES-NOT-EXIST")
    assert r.status_code == 404
