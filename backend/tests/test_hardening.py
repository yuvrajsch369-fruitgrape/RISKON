"""
Regression tests for issues found during a full stress/hardening pass:

1. Concurrent writes produced duplicate-id IntegrityErrors (25 concurrent
   incident creates -> 21 failures; 25 concurrent signups -> 19 failures) --
   fixed by backend/services/ids.py's next_id_with_retry().
2. An unvalidated date_occurred ("not-a-date-at-all") stored into
   incidents.incident_datetime crashed GET /api/bootstrap for EVERY user via
   database/export_frontend_data.py's _derive_shift() -- fixed with both
   input validation (api_schemas.py) and a defensive guard at the source.
3. Unbounded `limit` query params accepted negative/huge values (SQLite's
   `LIMIT -1` means "no limit") -- fixed by clamping via FastAPI's Query().
4. Several free-text fields (location, comment, reason, modification_text,
   verification_method) had no max_length, allowing unbounded payloads.
5. POST /api/incidents/{id}/review had no idempotency guard -- a second
   Approved review (double-click, retried request) re-ran the action-creation
   loop and created a full duplicate set of corrective actions from the same
   analysis. Fixed with a one-way "already reviewed" check, same idiom as
   complete_action's "already Completed" guard.
"""
import json
import sqlite3
import threading
import uuid

import pytest

from backend.services import ids


# --- 1. ID-generation race -----------------------------------------------------

def test_next_id_with_retry_recovers_from_collision():
    """Simulates the exact race proven under load: the first insert_fn call
    collides (another connection already took that id), the second succeeds."""
    calls = []

    def insert_fn(candidate_id):
        calls.append(candidate_id)
        if len(calls) == 1:
            raise sqlite3.IntegrityError("UNIQUE constraint failed: incidents.incident_id")
        # second attempt succeeds

    class _FakeConn:
        def execute(self, *a, **k):
            class _Cur:
                def fetchone(self_inner):
                    return None
            return _Cur()

    result = ids.next_id_with_retry(_FakeConn(), "incidents", "incident_id", "INC", insert_fn)
    assert result == "INC-0001"
    assert len(calls) == 2  # first collided, second succeeded


def test_next_id_with_retry_does_not_retry_unrelated_collision():
    """A duplicate-email IntegrityError (a DIFFERENT constraint) must propagate
    immediately -- retrying with a new user_id can never fix it, and silently
    burning every attempt on it would turn a clean 409 into a confusing 500."""
    calls = []

    def insert_fn(candidate_id):
        calls.append(candidate_id)
        raise sqlite3.IntegrityError("UNIQUE constraint failed: app_users.email")

    class _FakeConn:
        def execute(self, *a, **k):
            class _Cur:
                def fetchone(self_inner):
                    return None
            return _Cur()

    with pytest.raises(sqlite3.IntegrityError, match="app_users.email"):
        ids.next_id_with_retry(_FakeConn(), "app_users", "user_id", "USR", insert_fn)
    assert len(calls) == 1  # must not have retried


def test_concurrent_incident_creates_never_collide(app_client):
    """End-to-end regression for the real failure: 10 simultaneous
    POST /api/incidents must all succeed with unique ids, not raise
    IntegrityError 500s."""
    results = []
    lock = threading.Lock()

    def _create(i):
        r = app_client.post("/api/incidents", json={
            "title": f"Concurrent {i}", "description": "race regression test", "facility_id": "FAC-001",
        })
        with lock:
            results.append(r)

    threads = [threading.Thread(target=_create, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    statuses = [r.status_code for r in results]
    assert statuses == [201] * 10, f"expected all 201, got {statuses}"
    ids_created = [r.json()["incident_id"] for r in results]
    assert len(set(ids_created)) == 10, f"duplicate ids generated: {ids_created}"


def test_concurrent_signups_never_collide(app_client):
    results = []
    lock = threading.Lock()

    def _signup(i):
        r = app_client.post("/api/users/signup", json={
            "name": f"Concurrent User {i}", "occupation": "Employee", "post": "Line",
            "email": f"concurrent{i}@test.riskon.local", "password": "ConcurrentTest123",
        })
        with lock:
            results.append(r)

    threads = [threading.Thread(target=_signup, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    statuses = [r.status_code for r in results]
    assert statuses == [201] * 10, f"expected all 201, got {statuses}"
    user_ids = [r.json()["user_id"] for r in results]
    assert len(set(user_ids)) == 10, f"duplicate ids generated: {user_ids}"


def test_duplicate_email_signup_still_returns_409_not_500(app_client):
    """Guards against the retry wrapper misfiring on a DIFFERENT collision
    (see test_next_id_with_retry_does_not_retry_unrelated_collision above),
    exercised through the real route this time."""
    body = {"name": "First", "occupation": "Employee", "post": "Line",
            "email": "dupe@test.riskon.local", "password": "FirstPassword123"}
    r1 = app_client.post("/api/users/signup", json=body)
    assert r1.status_code == 201
    r2 = app_client.post("/api/users/signup", json={**body, "name": "Second", "password": "SecondPassword123"})
    assert r2.status_code == 409


# --- 2. date validation + _derive_shift fragility --------------------------------

@pytest.mark.parametrize("bad_date", ["not-a-date-at-all", "2026-02-30", "26-01-01", ""])
def test_incident_create_rejects_invalid_date_occurred(app_client, bad_date):
    r = app_client.post("/api/incidents", json={
        "title": "ok", "description": "ok", "facility_id": "FAC-001", "date_occurred": bad_date,
    })
    assert r.status_code == 422


def test_incident_create_accepts_valid_date_occurred(app_client):
    r = app_client.post("/api/incidents", json={
        "title": "ok", "description": "ok", "facility_id": "FAC-001", "date_occurred": "2026-01-15",
    })
    assert r.status_code == 201


def test_derive_shift_survives_malformed_incident_datetime():
    """The actual production failure: ONE bad incident_datetime value crashed
    GET /api/bootstrap for every user. Must degrade gracefully instead."""
    from database.export_frontend_data import _derive_shift
    assert _derive_shift("not-a-date-at-all 00:00:00") == "Unknown"
    assert _derive_shift("") == "Unknown"
    assert _derive_shift(None) == "Unknown"
    assert _derive_shift("2026-09-02 12:45:00") == "Day"


# --- 3. limit clamping ------------------------------------------------------------

@pytest.mark.parametrize("path", ["/api/incidents", "/api/actions", "/api/recommendations"])
@pytest.mark.parametrize("bad_limit", [-1, 0, 100000])
def test_list_endpoints_reject_out_of_range_limit(app_client, path, bad_limit):
    r = app_client.get(path, params={"limit": bad_limit})
    assert r.status_code == 422


@pytest.mark.parametrize("path", ["/api/incidents", "/api/actions", "/api/recommendations"])
def test_list_endpoints_accept_boundary_limit(app_client, path):
    assert app_client.get(path, params={"limit": 1}).status_code == 200
    assert app_client.get(path, params={"limit": 1000}).status_code == 200


# --- 4. free-text field length caps --------------------------------------------

def test_incident_location_over_maxlen_rejected(app_client):
    r = app_client.post("/api/incidents", json={
        "title": "ok", "description": "ok", "facility_id": "FAC-001", "location": "L" * 301,
    })
    assert r.status_code == 422


def test_incident_location_at_maxlen_accepted(app_client):
    r = app_client.post("/api/incidents", json={
        "title": "ok", "description": "ok", "facility_id": "FAC-001", "location": "L" * 300,
    })
    assert r.status_code == 201


# --- 5. double-review idempotency -------------------------------------------------

def _seed_fake_analysis(db_path, incident_id, recommendations):
    conn = sqlite3.connect(db_path)
    analysis_id = f"AIAN-{uuid.uuid4().hex[:12]}"
    response = {
        "summary": "t", "observed_facts": [], "ai_hypotheses": [], "related_risk_signals": [],
        "evidence": [], "recommendations": recommendations, "confidence": 0.5, "uncertainties": [],
        "requires_human_review": True,
    }
    conn.execute("""INSERT INTO ai_incident_analyses (analysis_id, incident_id, created_at, model,
        prompt_version_id, context_json, response_json, summary, confidence, requires_human_review,
        human_review_status) VALUES (?,?,?,?,?,?,?,?,?,1,'Pending')""",
        (analysis_id, incident_id, "2026-01-01 00:00:00", "test-model", None, "{}", json.dumps(response), "t", 0.5))
    conn.commit()
    conn.close()
    return analysis_id


def test_double_review_does_not_create_duplicate_actions(app_client, temp_db):
    # INC-0036 is "Not Started" in the shipped seed data (unlike INC-0001,
    # which seed data already marks Completed as one of the demo-pipeline
    # incidents) -- a fresh incident is needed to exercise the first-review
    # success path before the guard blocks the second.
    incident_id = "INC-0036"
    _seed_fake_analysis(temp_db, incident_id, ["Do thing A", "Do thing B"])

    r1 = app_client.post(f"/api/incidents/{incident_id}/review", json={"decision": "Approved"})
    assert r1.status_code == 200
    assert len(r1.json()["actions_created"]) == 2

    r2 = app_client.post(f"/api/incidents/{incident_id}/review", json={"decision": "Approved"})
    assert r2.status_code == 400

    actions = app_client.get("/api/actions", params={"limit": 1000}).json()["actions"]
    created_for_incident = [a for a in actions if a.get("source_incident_id") == incident_id]
    assert len(created_for_incident) == 2, f"expected exactly 2 actions, found {len(created_for_incident)}"
