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
6. The reviewer's rejection/approval comment was accepted by the API and
   silently discarded -- no column existed to store it. Fixed by adding
   ai_incident_analyses.review_comment. Separately, reviewed_by_employee_id
   was never actually populated by the frontend (no caller ever sends
   reviewer_employee_id), so there was no record of WHO reviewed something.
   Fixed with a new reviewed_by_user_id column resolved from the real
   session cookie server-side (backend/services/auth.py) -- never trusted
   from the request body, so a client can't spoof who "reviewed" something.
7. A real review decision didn't survive a page reload: database/
   export_frontend_data.py derived incidents[].status purely from
   investigation_status/closure_status, which review_incident() never sets
   to anything reflecting Approved/Rejected -- so GET /api/bootstrap kept
   reporting "In Review" after a real review, re-showing the Approve/Reject
   form for an already-decided incident (clicking it then hit the (correct)
   idempotency 400, confusingly). Fixed by overriding status from the latest
   ai_incident_analyses.human_review_status when one exists.
8. POST /api/recommendations/{id}/decision had no guard at all -- confirmed:
   deciding an already-Approved recommendation a second time silently
   overwrote it to Rejected with 200, no trace the original decision ever
   existed. Fixed with the same one-way-transition idea as review_incident,
   scoped to only the three truly final decisions (Approved/Rejected/
   Modified) -- 'Pending' and 'Request More Information' are deliberately
   still revisable, since a real follow-up decision should be able to
   resolve them.
9. No request body size limit existed anywhere: Pydantic's max_length
   constraints (e.g. IncidentCreate.description, capped at 5000 chars) only
   reject AFTER FastAPI has already buffered and JSON-parsed the whole body
   -- confirmed a 50MB body was accepted, parsed, and only then 422'd on the
   length check, meaning the large-body cost was already paid regardless of
   the eventual rejection. Fixed with MaxBodySizeMiddleware, which checks
   Content-Length and 413s before any read/parse happens.
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


# --- 6. review comment + real reviewer identity ---------------------------------

def test_review_comment_persisted_on_reject(app_client, temp_db):
    incident_id = "INC-0036"
    _seed_fake_analysis(temp_db, incident_id, ["Do thing A"])

    r = app_client.post(f"/api/incidents/{incident_id}/review",
                         json={"decision": "Rejected", "comment": "AI missed that this was equipment failure."})
    assert r.status_code == 200

    analyses = app_client.get(f"/api/incidents/{incident_id}/analyses").json()["analyses"]
    assert analyses[0]["review_comment"] == "AI missed that this was equipment failure."
    assert analyses[0]["human_review_status"] == "Rejected"


def test_review_comment_persisted_on_approve(app_client, temp_db):
    incident_id = "INC-0036"
    _seed_fake_analysis(temp_db, incident_id, ["Do thing A"])

    r = app_client.post(f"/api/incidents/{incident_id}/review",
                         json={"decision": "Approved", "comment": "Agreed, assigning follow-up."})
    assert r.status_code == 200

    analyses = app_client.get(f"/api/incidents/{incident_id}/analyses").json()["analyses"]
    assert analyses[0]["review_comment"] == "Agreed, assigning follow-up."


def test_reviewed_by_user_id_is_null_without_a_real_session(app_client, temp_db):
    """The default, open 'Viewing as (demo)' flow has no real login -- there
    genuinely is no verified identity to record, and the column must say so
    honestly rather than guessing."""
    incident_id = "INC-0036"
    _seed_fake_analysis(temp_db, incident_id, ["Do thing A"])

    app_client.post(f"/api/incidents/{incident_id}/review", json={"decision": "Approved"})

    analyses = app_client.get(f"/api/incidents/{incident_id}/analyses").json()["analyses"]
    assert analyses[0]["reviewed_by_user_id"] is None


def test_reviewed_by_user_id_reflects_the_real_signed_in_session(app_client, temp_db):
    """A real logged-in session (via /api/users/signup, which sets the
    session cookie app_client carries on subsequent requests) must be
    recorded as the reviewer -- resolved server-side from that session, not
    from anything the client puts in the request body."""
    incident_id = "INC-0036"
    _seed_fake_analysis(temp_db, incident_id, ["Do thing A"])

    signup = app_client.post("/api/users/signup", json={
        "name": "Reviewer One", "occupation": "Safety Manager", "post": "Line",
        "email": "reviewer@test.riskon.local", "password": "ReviewerPassword123",
    })
    assert signup.status_code == 201
    real_user_id = signup.json()["user_id"]

    r = app_client.post(f"/api/incidents/{incident_id}/review", json={"decision": "Approved"})
    assert r.status_code == 200

    analyses = app_client.get(f"/api/incidents/{incident_id}/analyses").json()["analyses"]
    assert analyses[0]["reviewed_by_user_id"] == real_user_id


def test_client_cannot_spoof_reviewer_identity(app_client, temp_db):
    """IncidentReviewDecision has no reviewer-identity field a client can set
    for reviewed_by_user_id at all -- confirms it's only ever resolved from
    the session, never accepted as input, even if a request tries to smuggle
    one in."""
    incident_id = "INC-0036"
    _seed_fake_analysis(temp_db, incident_id, ["Do thing A"])

    r = app_client.post(f"/api/incidents/{incident_id}/review",
                         json={"decision": "Approved", "reviewed_by_user_id": "USR-9999", "user_id": "USR-9999"})
    assert r.status_code == 200

    analyses = app_client.get(f"/api/incidents/{incident_id}/analyses").json()["analyses"]
    assert analyses[0]["reviewed_by_user_id"] is None


# --- 7. bootstrap status reflects a real review after "reload" ------------------

def _bootstrap_status_for(app_client, incident_id):
    incidents = app_client.get("/api/bootstrap").json()["incidents"]
    match = [i for i in incidents if i["incident_id"] == incident_id]
    assert match, f"{incident_id} missing from /api/bootstrap response"
    return match[0]["status"]


def test_bootstrap_status_is_approved_after_a_real_review(app_client, temp_db):
    incident_id = "INC-0036"
    _seed_fake_analysis(temp_db, incident_id, ["Do thing A"])
    assert _bootstrap_status_for(app_client, incident_id) != "Approved"  # sanity: not approved yet

    r = app_client.post(f"/api/incidents/{incident_id}/review", json={"decision": "Approved"})
    assert r.status_code == 200

    # The real regression: this must come from a FRESH GET /api/bootstrap call
    # (simulating a page reload), not from any in-memory state the review
    # response itself returned.
    assert _bootstrap_status_for(app_client, incident_id) == "Approved"


def test_bootstrap_status_is_rejected_after_a_real_review(app_client, temp_db):
    incident_id = "INC-0036"
    _seed_fake_analysis(temp_db, incident_id, ["Do thing A"])

    r = app_client.post(f"/api/incidents/{incident_id}/review", json={"decision": "Rejected"})
    assert r.status_code == 200
    assert _bootstrap_status_for(app_client, incident_id) == "Rejected"


def test_bootstrap_status_unaffected_for_never_reviewed_incidents(app_client):
    """The new review-status lookup must only ever override status for
    incidents that actually have an Approved/Rejected analysis -- everything
    else still comes from the original investigation_status/closure_status
    derivation."""
    status = _bootstrap_status_for(app_client, "INC-0036")
    assert status in ("New", "In Review", "Closed")


# --- 8. recommendation decisions can't be silently overwritten -----------------

def test_second_decision_on_a_final_recommendation_is_rejected(app_client):
    rec_id = "REC-DEMO-001"
    r1 = app_client.post(f"/api/recommendations/{rec_id}/decision", json={"decision": "Approved"})
    assert r1.status_code == 200
    assert r1.json()["human_decision"] == "Approved"

    r2 = app_client.post(f"/api/recommendations/{rec_id}/decision",
                          json={"decision": "Rejected", "reason": "changed my mind"})
    assert r2.status_code == 400

    # The original decision must survive untouched -- this is the actual bug:
    # confirmed a second call silently overwrote Approved -> Rejected with 200.
    still = app_client.get("/api/recommendations").json()["recommendations"]
    match = [r for r in still if r["recommendation_id"] == rec_id][0]
    assert match["human_decision"] == "Approved"


def test_request_more_info_can_still_be_followed_by_a_real_decision(app_client):
    """'Request More Information' is an intermediate state, not a final
    decision -- a real follow-up decision must still be able to resolve it,
    unlike Approved/Rejected/Modified."""
    rec_id = "REC-DEMO-001"
    r1 = app_client.post(f"/api/recommendations/{rec_id}/decision",
                          json={"decision": "Request More Information", "reason": "need more context"})
    assert r1.status_code == 200
    assert r1.json()["human_decision"] == "Request More Information"

    r2 = app_client.post(f"/api/recommendations/{rec_id}/decision", json={"decision": "Approved"})
    assert r2.status_code == 200
    assert r2.json()["human_decision"] == "Approved"


# --- 9. request body size cap ---------------------------------------------------

def test_oversized_request_body_is_rejected_with_413(app_client):
    oversized = "A" * (3 * 1024 * 1024)  # over the 2MB default cap
    r = app_client.post("/api/incidents", json={
        "title": "t", "description": oversized, "facility_id": "FAC-001",
    })
    assert r.status_code == 413
    assert r.json()["error"] == "payload_too_large"


def test_normal_sized_request_body_still_works(app_client):
    r = app_client.post("/api/incidents", json={
        "title": "t", "description": "a normal-sized description", "facility_id": "FAC-001",
    })
    assert r.status_code == 201
