"""
End-to-end tests against the real FastAPI app, using a TestClient and a
throwaway copy of the database (see conftest.py's `temp_db`/`app_client`
fixtures) — safe to run repeatedly without ever touching the shipped seed
dataset. The AI-analysis test intentionally runs WITHOUT a real
ANTHROPIC_API_KEY and asserts the honest "not configured" failure path —
it does not, and cannot, prove the real Claude integration works end-to-end.
"""
import json

from backend.config import settings


def test_health_reports_db_ok_and_ai_not_configured(app_client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    r = app_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"]["ok"] is True
    assert body["ai_configured"] is False
    assert "anthropic_api_key" not in json.dumps(body)  # key name itself never leaks, let alone a value


def test_bootstrap_matches_static_export_shape(app_client):
    r = app_client.get("/api/bootstrap")
    assert r.status_code == 200
    body = r.json()
    for key in ("facilities", "incidents", "riskIntelligence", "executiveDashboard",
                "continuousLearning", "auditTrail"):
        assert key in body
    assert len(body["facilities"]) == 3


def test_list_and_get_incident(app_client):
    r = app_client.get("/api/incidents?limit=5")
    assert r.status_code == 200
    incidents = r.json()["incidents"]
    assert len(incidents) == 5
    one_id = incidents[0]["incident_id"]

    r2 = app_client.get(f"/api/incidents/{one_id}")
    assert r2.status_code == 200
    assert r2.json()["incident_id"] == one_id


def test_get_unknown_incident_is_404_not_500(app_client):
    r = app_client.get("/api/incidents/INC-DOES-NOT-EXIST")
    assert r.status_code == 404
    assert "error" not in r.json() or "traceback" not in json.dumps(r.json()).lower()


def test_create_incident_persists_to_db(app_client):
    r = app_client.get("/api/bootstrap")
    facility_id = r.json()["facilities"][0]["facility_id"]

    payload = {
        "title": "Test incident from automated test",
        "description": "A pallet shifted unexpectedly near the loading dock.",
        "facility_id": facility_id,
        "severity_reported": "Low",
    }
    r2 = app_client.post("/api/incidents", json=payload)
    assert r2.status_code == 201
    created = r2.json()
    assert created["facility_id"] == facility_id
    assert created["initial_severity"] == "Low"

    r3 = app_client.get(f"/api/incidents/{created['incident_id']}")
    assert r3.status_code == 200


def test_analyze_incident_without_api_key_returns_503_not_fake_success(app_client, monkeypatch):
    """The single most important safety test in this suite: with no
    ANTHROPIC_API_KEY configured, the AI endpoint must fail honestly, not
    fabricate a result."""
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    r = app_client.get("/api/incidents?limit=1")
    incident_id = r.json()["incidents"][0]["incident_id"]

    r2 = app_client.post(f"/api/incidents/{incident_id}/analyze")
    assert r2.status_code == 503
    assert "ANTHROPIC_API_KEY" in r2.json()["message"] or "not configured" in r2.json()["message"].lower()


def test_analyze_unknown_incident_is_404(app_client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    r = app_client.post("/api/incidents/INC-DOES-NOT-EXIST/analyze")
    assert r.status_code in (404, 503)  # 404 (incident check) is expected to win — asserted precisely below


def test_analyze_unknown_incident_checks_existence_before_ai_config(app_client):
    """Even WITH a fake key set, an unknown incident should 404, proving the
    incident lookup happens before any AI call is attempted."""
    from backend.config import settings as s
    s.anthropic_api_key = "sk-ant-fake-for-this-test-only"
    try:
        r = app_client.post("/api/incidents/INC-DOES-NOT-EXIST/analyze")
        assert r.status_code == 404
    finally:
        s.anthropic_api_key = ""


def test_complete_action(app_client):
    r = app_client.get("/api/actions?status=Open&limit=1")
    actions = r.json()["actions"]
    if not actions:
        return  # nothing Open in this snapshot; not a failure of the endpoint itself
    action_id = actions[0]["action_id"]
    r2 = app_client.post(f"/api/actions/{action_id}/complete", json={})
    assert r2.status_code == 200
    assert r2.json()["status"] == "Completed"

    r3 = app_client.post(f"/api/actions/{action_id}/complete", json={})
    assert r3.status_code == 400  # already completed


def test_recommendation_decision_requires_reason_unless_approved(app_client):
    r = app_client.get("/api/recommendations?limit=1")
    recs = r.json()["recommendations"]
    rec_id = recs[0]["recommendation_id"]

    r2 = app_client.post(f"/api/recommendations/{rec_id}/decision", json={"decision": "Rejected"})
    assert r2.status_code == 400

    r3 = app_client.post(f"/api/recommendations/{rec_id}/decision",
                          json={"decision": "Rejected", "reason": "Not feasible in this facility."})
    assert r3.status_code == 200
    assert r3.json()["human_decision"] == "Rejected"


def test_no_stack_trace_ever_reaches_client_on_bad_input(app_client):
    r = app_client.post("/api/incidents", json={"title": "", "description": "", "facility_id": "NOPE"})
    assert r.status_code in (400, 422)
    text = json.dumps(r.json())
    assert "Traceback" not in text and "File \"" not in text
