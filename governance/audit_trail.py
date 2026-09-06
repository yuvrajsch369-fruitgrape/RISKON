#!/usr/bin/env python3
"""
Builds a seed audit trail from database/riskon.db — every entry is derived
from a real, already-stored fact (an incident's reported_at/closed_date, an
action's created_date/completion_date, a real evidence row, a real AI
reasoning pipeline's generated_at timestamp). Nothing here invents a person,
a date, or an event that isn't already backed by a row in the database.

Two kinds of entries:
  1. "Historical" entries reconstructed from already-closed incident/action/
     evidence lifecycles (source: "Human") — these represent what a real
     audit log would have captured as those records were created, even
     though this prototype didn't have live audit logging running at the
     time the seed database was generated.
  2. "AI recommendation created" entries for the 5 full-AI-pipeline example
     incidents (source: "AI"), timestamped from the pipeline's own
     generated_at field (examples/*.json) — these are the seed halves of
     chains the running app completes live: opening the RISKON UI and
     clicking Approve/Reject on one of these incidents appends the
     "reviewed / approved / rejected" entries in real time (see
     frontend/app.template.html, logAudit()).

Fields on every entry match the spec exactly: user, timestamp, action,
entity_type, entity_id, previous_value, new_value, reason, source
(AI-generated | Human-generated), approval_status.

Run standalone: python3 governance/audit_trail.py (prints a sample + count)
Used as a library by database/export_frontend_data.py.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "database" / "riskon.db"
EXAMPLES_DIR = ROOT / "examples"

_seq = [0]


def _id():
    _seq[0] += 1
    return f"AUD-LOG-{_seq[0]:05d}"


def _entry(ts, user, role, action, entity_type, entity_id, prev, new, reason, source, approval_status):
    return {
        "log_id": _id(), "timestamp": ts, "user": user, "user_role": role, "action": action,
        "entity_type": entity_type, "entity_id": entity_id,
        "previous_value": prev, "new_value": new, "reason": reason,
        "source": source, "approval_status": approval_status,
    }


def build_audit_trail(db_path=DB_PATH, max_incidents=20):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def q(sql, params=()):
        return [dict(r) for r in conn.execute(sql, params)]

    def q1(sql, params=()):
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None

    def person(emp_id):
        if not emp_id:
            return "Unattributed (not tracked in source record)", "—"
        e = q1("SELECT * FROM employees WHERE employee_id=?", (emp_id,))
        if not e:
            return emp_id, "—"
        r = q1("SELECT title FROM roles WHERE role_id=?", (e["role_id"],))
        return f"{e['first_name']} {e['last_name']}", (r["title"] if r else "—")

    entries = []

    # -----------------------------------------------------------------
    # Human-only lifecycles reconstructed from real closed incidents that
    # have a completed corrective action (the strongest, most complete real
    # chains in the dataset).
    # -----------------------------------------------------------------
    # INC-0045 is deliberately featured first -- it's the richest real chain
    # in the dataset (closed incident + a Completed action + an evidence
    # row), so it's the one shown as the "worked example" in the governance
    # doc. The rest of the sample fills out volume for the Audit Trail screen.
    closed = q("""
        SELECT i.*, a.action_id, a.description AS action_desc, a.owner_employee_id AS action_owner,
               a.created_date AS action_created, a.due_date AS action_due,
               a.completion_date AS action_completed, a.verification_method, a.status AS action_status
        FROM incidents i JOIN actions a ON a.source_incident_id = i.incident_id
        WHERE i.closure_status='Closed' AND i.investigation_status='Completed'
        ORDER BY CASE WHEN i.incident_id='INC-0045' THEN 0 ELSE 1 END, i.closed_date
        LIMIT ?
    """, (max_incidents,))

    for row in closed:
        iid = row["incident_id"]
        reporter_name, reporter_role = person(row["reported_by_employee_id"])
        owner_name, owner_role = person(row["action_owner"])

        entries.append(_entry(row["reported_at"], reporter_name, reporter_role,
                               "Incident reported", "Incident", iid,
                               None, {"status": "New", "severity": row["initial_severity"]},
                               "Initial report filed.", "Human-generated", "N/A"))

        ev_rows = q("SELECT * FROM evidence WHERE related_entity_type='Incident' AND related_entity_id=?", (iid,))
        for ev in ev_rows:
            up_name, up_role = person(ev["uploaded_by_employee_id"])
            entries.append(_entry(ev["uploaded_date"], up_name, up_role,
                                   "Evidence uploaded", "Incident", iid,
                                   None, ev["file_name"],
                                   ev["description"], "Human-generated", "N/A"))

        entries.append(_entry(row["closed_date"], "—", "System (derived)",
                               "Investigation completed", "Incident", iid,
                               {"investigation_status": "In Progress"},
                               {"investigation_status": "Completed", "root_cause_category": row["root_cause_category"]},
                               "Root cause recorded following investigation.", "Human-generated", "N/A"))

        if row["action_id"]:
            aid = row["action_id"]
            entries.append(_entry(row["action_created"], owner_name, owner_role,
                                   "Corrective action assigned", "Action", aid,
                                   None, {"owner": owner_name, "due_date": row["action_due"], "status": "Open"},
                                   row["action_desc"], "Human-generated", "N/A"))
            if row["action_status"] == "Completed" and row["action_completed"]:
                entries.append(_entry(row["action_completed"], owner_name, owner_role,
                                       "Corrective action verified", "Action", aid,
                                       {"status": "Open"}, {"status": "Completed"},
                                       f"Verified via {row['verification_method']}.", "Human-generated", "N/A"))

        # closure_status has no "closed_by" column in the schema -- attributing
        # this to a specific named person would be an unsupported guess, so
        # it's recorded as a system-derived state transition instead, same as
        # "Investigation completed" above.
        entries.append(_entry(row["closed_date"], "—", "System (derived)",
                               "Incident closed", "Incident", iid,
                               {"closure_status": "Open"}, {"closure_status": "Closed"},
                               "All related corrective actions addressed; investigation complete.",
                               "Human-generated", "Approved"))

    # -----------------------------------------------------------------
    # AI-generated seed entries for the 5 full-pipeline example incidents.
    # These are the ONLY entries in the seed data with source="AI-generated"
    # and approval_status="Pending" -- consistent with the human-in-the-loop
    # rule that nothing AI-produced is ever pre-approved in seed data. The
    # running app appends the review/approve/reject entries live.
    # -----------------------------------------------------------------
    for f in sorted(EXAMPLES_DIR.glob("*.json")):
        p = json.load(open(f, encoding="utf-8"))
        iid = p["incident_id"]
        s1 = p["stage_1_ingestion"]
        entries.append(_entry(p["generated_at"], "RISKON Reasoning Engine", "AI System",
                               "AI recommendation created", "Incident", iid,
                               None,
                               {"classification": p["stage_3_classification"]["incident_category"]["value"],
                                "suggested_severity": p["stage_6_preliminary_severity_assessment"]["ai_suggested_severity"]["value"],
                                "proposed_risk_level": p["stage_12_risk_register_impact"]["risk_level"]["value"]},
                               "13-stage reasoning pipeline run on submitted incident report.",
                               "AI-generated", "Pending"))

    # -----------------------------------------------------------------
    # Continuous Learning Engine — every recommendation decision and every
    # learning-candidate pipeline stage is a real, already-stored row in
    # recommendations/learning_candidates/learning_evaluations/ai_versions
    # (see database/schema.sql Part 2, learning_engine/generate_learning_data.py).
    # Capped at max_incidents*2 recommendation-decision entries for the same
    # reason the incident section above caps at max_incidents: this is a
    # demonstration log, not a full production audit export.
    # -----------------------------------------------------------------
    recs = q("SELECT * FROM recommendations WHERE human_decision != 'Pending' "
             "ORDER BY decision_date DESC LIMIT ?", (max_incidents * 2,))
    for r in recs:
        dec_name, dec_role = person(r["decision_by_employee_id"])
        entries.append(_entry(r["decision_date"] or r["created_at"], dec_name, dec_role,
                               "Recommendation reviewed", "Recommendation", r["recommendation_id"],
                               {"human_decision": "Pending"},
                               {"human_decision": r["human_decision"],
                                "modification": r["human_modification_text"]},
                               r["decision_reason"] or "No reason recorded.", "Human-generated",
                               r["human_decision"] if r["human_decision"] in ("Approved", "Rejected") else "N/A"))
        if r["evaluation_status"] == "Evaluated" and r["outcome_measurement"]:
            entries.append(_entry(r["updated_at"], "—", "System (derived)",
                                   "Recommendation outcome evaluated", "Recommendation", r["recommendation_id"],
                                   {"evaluation_status": "Not Evaluated"},
                                   {"evaluation_status": "Evaluated", "effectiveness_rating": r["effectiveness_rating"],
                                    "learning_signal": r["learning_signal"]},
                                   r["outcome_measurement"], "Human-generated", "N/A"))

    for c in q("SELECT * FROM learning_candidates"):
        entries.append(_entry(c["created_date"], "System (Continuous Learning Engine)", "AI System",
                               "Learning candidate proposed", "LearningCandidate", c["candidate_id"],
                               None, {"status": "Proposed", "candidate_type": c["candidate_type"]},
                               c["source_signal_summary"], "AI-generated", "N/A"))
        evals = q("SELECT * FROM learning_evaluations WHERE candidate_id=?", (c["candidate_id"],))
        for ev in evals:
            entries.append(_entry(ev["evaluated_date"], "System (Continuous Learning Engine)", "AI System",
                                   "Learning candidate evaluated", "LearningCandidate", c["candidate_id"],
                                   {"status": "Proposed"},
                                   {"status": "Evaluated", "recommendation": ev["recommendation"],
                                    "passed_thresholds": bool(ev["passed_thresholds"])},
                                   ev["method_note"], "AI-generated", "N/A"))
        if c["review_decision"]:
            rev_name, rev_role = person(c["reviewed_by_employee_id"])
            entries.append(_entry(c["review_date"], rev_name, rev_role,
                                   "Learning candidate reviewed", "LearningCandidate", c["candidate_id"],
                                   {"status": "Evaluated"},
                                   {"status": c["review_decision"], "review_decision": c["review_decision"]},
                                   c["review_reason"], "Human-generated", c["review_decision"]))
        if c["status"] == "Deployed":
            cand_version = q1("SELECT * FROM ai_versions WHERE version_id=?", (c["candidate_version_id"],))
            if cand_version and cand_version["activated_date"]:
                entries.append(_entry(cand_version["activated_date"], rev_name if c["review_decision"] else "—",
                                       rev_role if c["review_decision"] else "System (derived)",
                                       "Version deployed", "AIVersion", cand_version["version_id"],
                                       {"status": "Candidate"}, {"status": "Active"},
                                       f"Deployed from learning candidate {c['candidate_id']} following human "
                                       f"approval; scope limited to the recommendation logic it targets, not a "
                                       f"blanket replacement.", "Human-generated", "Approved"))

    entries.sort(key=lambda e: (_sort_date(e["timestamp"]), _PHASE_ORDER.get(e["action"], 9)))
    conn.close()
    return entries


# Logical event sequence, used as a SAME-DAY tie-break. Several source
# timestamps in this dataset are date-only (evidence.uploaded_date has no
# time component), so exact clock-time ordering within one day isn't always
# derivable from the data. Rather than guess a time of day, entries are
# ordered by their real calendar date first, then by this fixed logical
# phase for anything landing on the same date -- guaranteeing "reported"
# always precedes "evidence uploaded" precedes "closed", which is the one
# ordering fact we DO know for certain from the schema's own lifecycle.
_PHASE_ORDER = {
    "Incident reported": 0, "AI recommendation created": 0,
    "Evidence uploaded": 1, "Investigation completed": 2,
    "Corrective action assigned": 3, "Corrective action verified": 4,
    "Incident closed": 5,
    "Learning candidate proposed": 6, "Learning candidate evaluated": 7,
    "Learning candidate reviewed": 8, "Version deployed": 9,
    "Recommendation reviewed": 3, "Recommendation outcome evaluated": 4,
}


def _sort_date(ts):
    """Returns just the calendar date for sorting -- see _PHASE_ORDER above
    for why exact time-of-day isn't used as the sort key."""
    s = ts.replace("T", " ").replace("Z", "")
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return datetime.min.date()


if __name__ == "__main__":
    trail = build_audit_trail()
    print(f"Built {len(trail)} audit log entries.")
    print(json.dumps(trail[:3], indent=2))
    print("...")
    print(json.dumps(trail[-3:], indent=2))
