#!/usr/bin/env python3
"""
RISKON Continuous Learning Engine — synthetic learning-data generator.

Populates the 4 tables added to database/schema.sql Part 2 (ai_versions,
recommendations, learning_candidates, learning_evaluations) directly against
the ALREADY-BUILT database/riskon.db. This script never touches, deletes, or
regenerates any Part-1 table (facilities, incidents, actions, etc.) — it only
adds new tables and reads the existing ones as a real, immutable evidence
base. Re-running it is idempotent: it drops and recreates only the 4 new
tables each time.

Design discipline (same as risk_intelligence/engine.py and
database/generate_database.py before it):
  * Every recommendation is grounded in a real incident/hazard/facility row
    already in the database — recommendation TEXT is templated (same as the
    rest of this synthetic dataset), but WHICH incidents got WHICH decision
    is derived from whether a real corrective action already exists for that
    incident, not invented independently of the data.
  * Every aggregate number the dashboard will show (approval rate, signal
    counts, etc.) is computed later by learning_engine/engine.py from these
    rows — nothing is hand-typed as a finished statistic here or there.
  * Outcome measurement compares REAL incident timestamps before/after a
    REAL action's completion_date. No follow-up incident is invented.
  * The one "candidate version" evaluation in this file is explicitly a
    retrospective backtest against real historical decisions, never a
    fabricated future outcome — see LOGIC-002's learning_evaluations row and
    its `method_note` for the full disclosure.

Run: python3 learning_engine/generate_learning_data.py
"""
import json
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

random.seed(20260910)  # distinct from generate_database.py's seed — this
                        # script's randomness only governs which grounded
                        # incidents fall on which side of a decision split,
                        # never whether the underlying incident/action exists

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "database" / "riskon.db"
SCHEMA_PATH = ROOT / "database" / "schema.sql"

TODAY = date(2026, 9, 3)
FOLLOWUP_PERIOD_DAYS = 90  # prototype default — see docs/continuous-learning-engine.md §6

# =============================================================================
# Vocabulary — per hazard_category, the AI's standard recommendation text and
# (where established) the specific human-modification pattern reviewers tend
# to apply. Every hazard_category actually present in the incidents table
# gets an entry; nothing here is selected to make the numbers look better.
# =============================================================================
REC_TEMPLATES = {
    "Forklift / Vehicle Incident": {
        "type": "Engineering Control",
        "text": "Improve pedestrian segregation in forklift travel aisles (extend floor markings and add mirrors at blind corners).",
        "modification": "Add a physical barrier (guardrail) at the pedestrian crossing instead of relying on floor markings alone.",
        "mod_reason": "Painted-line segregation alone has not prevented repeated near misses at this crossing; a physical barrier is feasible within the current footprint.",
        "reject_reason": "Recommended control is not feasible in this facility because of production layout constraints in the affected aisle.",
    },
    "Machine Guarding Failure": {
        "type": "Engineering Control",
        "text": "Repair/upgrade the point-of-operation guard interlock and verify it cannot be bypassed or propped open.",
        "modification": "Replace the mechanical interlock with a light-curtain sensor guard.",
        "mod_reason": "Operators have previously propped open the mechanical guard during changeovers; a light curtain removes that workaround entirely.",
        "reject_reason": "A light-curtain retrofit was already evaluated for this press line and deferred pending capital budget approval; the standard interlock repair was assigned instead.",
    },
    "Heat Stress": {
        "type": "Administrative Control",
        "text": "Implement a heat-stress management program (work/rest cycles, hydration stations, heat-index-triggered action plan) for this area.",
        "modification": "Add portable evaporative cooling units at the two hottest workstations in addition to the work/rest schedule.",
        "mod_reason": "Work/rest scheduling alone was not sufficient during peak summer shifts at this facility last season.",
        "reject_reason": "Area already has an active heat-stress program; recommendation was a duplicate of an existing control.",
    },
    "Lockout/Tagout Violation": {
        "type": "Procedural Control",
        "text": "Reinforce LOTO procedure compliance through refresher training and supervisor verification checks before energized work begins.",
        "modification": "Add a physical lock-box audit step to the daily supervisor checklist.",
        "mod_reason": "Refresher training alone has not changed behavior on this line; a checklist with a physical verification step is more enforceable.",
        "reject_reason": "Root cause was traced to a contractor not covered by internal LOTO refresher training; recommendation did not address the actual population involved.",
    },
    "Caught-In / Caught-Between": {
        "type": "Engineering Control",
        "text": "Install/upgrade pinch-point guarding on the affected equipment and update the pre-operation inspection checklist.",
        "modification": None,
        "mod_reason": None,
        "reject_reason": "Equipment is scheduled for decommissioning within the quarter; guarding retrofit was not cost-justified.",
    },
    "Housekeeping / Walkway Obstruction": {
        "type": "Administrative Control",
        "text": "Implement a scheduled housekeeping/walkway-clearance inspection with assigned area ownership.",
        "modification": "Add designated material staging zones with floor marking so materials are never placed in walkway paths in the first place.",
        "mod_reason": "Reactive inspection alone has not stopped recurring obstruction; a designated staging area addresses the root cause instead of the symptom.",
        "reject_reason": "Area is under a separate 5S program already covering this walkway; recommendation was redundant.",
    },
    "Falling Object / Struck-By": {
        "type": "Engineering Control",
        "text": "Install overhead netting or toe-boards at elevated storage/work areas to prevent falling-object exposure.",
        "modification": None, "mod_reason": None,
        "reject_reason": "Insufficient information to confirm the exact elevated storage location involved; more detail requested before assigning a control.",
    },
    "Ergonomic Strain": {
        "type": "Administrative Control",
        "text": "Conduct an ergonomic assessment of the task and implement job rotation or mechanical lifting assistance.",
        "modification": None, "mod_reason": None,
        "reject_reason": None,
    },
    "Confined Space Hazard": {
        "type": "Procedural Control",
        "text": "Reinforce confined-space entry permit compliance, including atmospheric testing and attendant verification.",
        "modification": None, "mod_reason": None,
        "reject_reason": "Entry point identified in the incident is being permanently sealed as part of an unrelated process change; procedural reinforcement no longer applies.",
    },
    "Chemical Exposure": {
        "type": "Engineering Control",
        "text": "Improve local exhaust ventilation and reinforce PPE compliance for this chemical-handling task.",
        "modification": "Add secondary containment (spill berm) around the storage/transfer area in addition to the ventilation improvement.",
        "mod_reason": "Ventilation addresses inhalation exposure but does not address the spill/release pathway that caused this incident.",
        "reject_reason": "Chemical is being phased out for a lower-hazard substitute within the year; recommendation would be moot before completion.",
    },
    "Overhead Crane / Rigging Hazard": {
        "type": "Procedural Control",
        "text": "Reinforce pre-lift rigging inspection and load-chart compliance for overhead crane operations.",
        "modification": None, "mod_reason": None, "reject_reason": None,
    },
    "Electrical Hazard / Arc Flash": {
        "type": "PPE",
        "text": "Verify arc-flash PPE category compliance and reinforce energized-work permit requirements.",
        "modification": None, "mod_reason": None,
        "reject_reason": "An arc-flash study for this panel was already scheduled prior to this incident; recommendation is superseded by that study's findings once complete.",
    },
    "Noise Exposure": {
        "type": "PPE",
        "text": "Reinforce hearing-protection compliance and evaluate engineering noise-control options for this area.",
        "modification": None, "mod_reason": None, "reject_reason": None,
    },
    "Equipment Failure Risk": {
        "type": "Administrative Control",
        "text": "Move the affected equipment onto a preventive-maintenance schedule instead of run-to-failure.",
        "modification": None, "mod_reason": None, "reject_reason": None,
    },
    "Environmental Spill / Release": {
        "type": "Engineering Control",
        "text": "Add secondary containment and update the spill-response kit inventory for this area.",
        "modification": None, "mod_reason": None, "reject_reason": None,
    },
    "Slip/Trip/Fall": {
        "type": "Administrative Control",
        "text": "Address the flooring/housekeeping condition and reinforce spill-response and signage procedures.",
        "modification": None, "mod_reason": None, "reject_reason": None,
    },
    "Pressure System Failure": {
        "type": "Engineering Control",
        "text": "Verify pressure-relief device testing is current and reinforce pre-use inspection for this system.",
        "modification": None, "mod_reason": None, "reject_reason": None,
    },
    "Fire / Explosion Risk": {
        "type": "Engineering Control",
        "text": "Verify ignition-source controls and reinforce housekeeping to reduce combustible material accumulation.",
        "modification": None, "mod_reason": None, "reject_reason": None,
    },
    "Fall / Working at Height": {
        "type": "Engineering Control",
        "text": "Reinforce fall-protection anchor point inspection and harness/lanyard compliance for elevated work.",
        "modification": None, "mod_reason": None, "reject_reason": None,
    },
}
DEFAULT_MOD = "Broaden the control to an engineering measure in addition to the administrative step originally proposed."
DEFAULT_MOD_REASON = "Administrative controls alone have a track record of inconsistent compliance at this facility."
DEFAULT_REJECT_REASON = "Recommended control was judged not applicable to this specific case after review."
GENERIC_INFO_REASON = "Root cause not yet conclusively established; additional investigation requested before a control is assigned."

REVIEWER_ROLES = ("Safety Manager", "EHS Coordinator", "Plant Manager")


def d(offset_days_from_today):
    return (TODAY - timedelta(days=offset_days_from_today)).isoformat()


def stable_unit(seedable_id, salt=""):
    """Deterministic pseudo-random float in [0,1) from an id string — stable
    across re-runs (unlike random.random()'s draw order, which shifts if any
    earlier query changes row count). Used only to split otherwise-similar
    rows across decision categories, never to decide whether evidence exists."""
    h = 0
    for ch in (seedable_id + "|" + salt):
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return (h % 10000) / 10000.0


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    install_schema(conn)

    facilities = {r["facility_id"]: dict(r) for r in conn.execute("SELECT * FROM facilities")}
    hazards = {r["hazard_id"]: dict(r) for r in conn.execute("SELECT * FROM hazards")}
    employees = [dict(r) for r in conn.execute(
        "SELECT e.*, r.title AS role_title FROM employees e JOIN roles r ON e.role_id = r.role_id WHERE e.is_active=1")]
    incidents = [dict(r) for r in conn.execute("SELECT * FROM incidents ORDER BY incident_datetime")]
    actions_by_incident = {}
    for r in conn.execute("SELECT * FROM actions WHERE source_type='Incident'"):
        actions_by_incident.setdefault(r["source_incident_id"], dict(r))

    reviewer_by_facility = {}
    for fid in facilities:
        candidates = [e for e in employees if e["facility_id"] == fid and e["role_title"] in REVIEWER_ROLES]
        reviewer_by_facility[fid] = candidates[0] if candidates else next(
            (e for e in employees if e["facility_id"] == fid), employees[0])

    ai_versions = build_ai_versions()
    conn.executemany(
        "INSERT INTO ai_versions VALUES (:version_id,:version_type,:label,:status,:description,"
        ":parent_version_id,:created_date,:activated_date,:created_by)",
        ai_versions,
    )

    recommendations = []
    seq = 0
    for inc in incidents:
        if inc["investigation_status"] != "Completed":
            continue  # no completed investigation -> no recommendation was ever generated
        hz = hazards.get(inc["hazard_id"])
        if not hz:
            continue
        category = hz["hazard_category"]
        tmpl = REC_TEMPLATES.get(category)
        if not tmpl:
            continue
        seq += 1
        rec_id = f"REC-{seq:04d}"
        action = actions_by_incident.get(inc["incident_id"])
        reviewer = reviewer_by_facility.get(inc["facility_id"], employees[0])
        u = stable_unit(inc["incident_id"], "decision")

        n_trailing = conn.execute(
            "SELECT COUNT(*) FROM incidents i JOIN hazards h ON i.hazard_id=h.hazard_id "
            "WHERE h.hazard_category=? AND i.facility_id=?",
            (category, inc["facility_id"]),
        ).fetchone()[0]
        evidence_used = (
            f"Incident {inc['incident_id']} ({inc['initial_severity']} severity, {inc['incident_type']}) at "
            f"{facilities[inc['facility_id']]['name']}; hazard category '{category}'; {n_trailing} total incidents "
            f"recorded under this hazard category at this facility."
        )
        ai_confidence = round(0.55 + stable_unit(inc["incident_id"], "conf") * 0.35, 2)
        decision_date = (date.fromisoformat(inc["reported_at"][:10]) + timedelta(days=2 + int(u * 5))).isoformat()
        decision_date = min(decision_date, TODAY.isoformat())

        rec = {
            "recommendation_id": rec_id,
            "source_type": "AI Investigation",
            "incident_id": inc["incident_id"],
            "risk_register_id": None,
            "risk_signal_id": None,
            "hazard_id": inc["hazard_id"],
            "facility_id": inc["facility_id"],
            "equipment_id": inc["equipment_id"],
            "related_control_id": None,
            "recommendation_type": tmpl["type"],
            "recommendation_text": tmpl["text"],
            "evidence_used": evidence_used,
            "ai_confidence": ai_confidence,
            "prompt_version_id": "PROMPT-001",
            "logic_version_id": "LOGIC-001",
            "decision_by_employee_id": reviewer["employee_id"],
            "decision_date": decision_date,
            "created_at": inc["reported_at"],
            "updated_at": decision_date,
        }

        if action:
            is_modified = tmpl["modification"] is not None and u < 0.32
            rec["human_decision"] = "Modified" if is_modified else "Approved"
            rec["human_modification_text"] = tmpl["modification"] if is_modified else None
            rec["decision_reason"] = tmpl["mod_reason"] if is_modified else "Recommendation accepted as proposed; consistent with facility standard practice."
            rec["assigned_action_id"] = action["action_id"]
            rec["action_status"] = "Completed" if action["status"] == "Completed" else "Assigned"
            rec["action_completion_date"] = action["completion_date"] or None
            outcome = compute_outcome(conn, rec, category, action)
            rec.update(outcome)
        else:
            is_info_request = u >= 0.6
            rec["human_decision"] = "Request More Information" if is_info_request else "Rejected"
            rec["human_modification_text"] = None
            rec["decision_reason"] = (GENERIC_INFO_REASON if is_info_request else
                                       (tmpl["reject_reason"] or DEFAULT_REJECT_REASON))
            rec["assigned_action_id"] = None
            rec["action_status"] = "Not Assigned"
            rec["action_completion_date"] = None
            rec["followup_period_days"] = None
            rec["baseline_incident_count"] = None
            rec["followup_incident_count"] = None
            rec["followup_incident_ids"] = None
            rec["outcome_measurement"] = None
            rec["effectiveness_rating"] = None
            rec["evaluation_status"] = "Not Evaluated"
            rec["learning_signal"] = "Not Yet Determined"

        rec["user_feedback"] = None
        recommendations.append(rec)

    conn.executemany(
        "INSERT INTO recommendations VALUES (:recommendation_id,:source_type,:incident_id,:risk_register_id,"
        ":risk_signal_id,:hazard_id,:facility_id,:equipment_id,:related_control_id,:recommendation_type,"
        ":recommendation_text,:evidence_used,:ai_confidence,:prompt_version_id,:logic_version_id,"
        ":human_decision,:human_modification_text,:decision_reason,:decision_by_employee_id,:decision_date,"
        ":assigned_action_id,:action_status,:action_completion_date,:followup_period_days,"
        ":baseline_incident_count,:followup_incident_count,:followup_incident_ids,:outcome_measurement,"
        ":effectiveness_rating,:user_feedback,:learning_signal,:evaluation_status,:created_at,:updated_at)",
        recommendations,
    )
    conn.commit()

    build_forklift_candidate(conn, recommendations, facilities, reviewer_by_facility)
    conn.commit()

    n_approved = sum(1 for r in recommendations if r["human_decision"] == "Approved")
    n_modified = sum(1 for r in recommendations if r["human_decision"] == "Modified")
    n_rejected = sum(1 for r in recommendations if r["human_decision"] == "Rejected")
    n_info = sum(1 for r in recommendations if r["human_decision"] == "Request More Information")
    n_eval = sum(1 for r in recommendations if r["evaluation_status"] == "Evaluated")
    print(f"recommendations: {len(recommendations)} total "
          f"(Approved={n_approved} Modified={n_modified} Rejected={n_rejected} RequestInfo={n_info}) "
          f"| outcome-evaluated={n_eval}")
    conn.close()


def build_ai_versions():
    return [
        {"version_id": "PROMPT-001", "version_type": "Prompt", "label": "AI Investigation prompt v1.0",
         "status": "Active", "description": "Stage 2-13 reasoning-pipeline prompt set (engine/prompts.ts) used to "
         "generate per-incident recommendations in stage_11_recommended_actions.",
         "parent_version_id": None, "created_date": d(400), "activated_date": d(400),
         "created_by": "System (seed)"},
        {"version_id": "LOGIC-001", "version_type": "Recommendation Logic", "label": "Recommendation-logic v1.0",
         "status": "Active", "description": "Standard per-hazard-category recommendation templates (one control "
         "per hazard category, no facility-specific or historical-modification context).",
         "parent_version_id": None, "created_date": d(400), "activated_date": d(400),
         "created_by": "System (seed)"},
        {"version_id": "SCORE-001", "version_type": "Risk Scoring", "label": "Risk Signal Score formula v1.0",
         "status": "Active", "description": "Weighted 6-factor Risk Signal Score (see risk_intelligence/engine.py "
         "WEIGHTS) — unchanged by this pass.",
         "parent_version_id": None, "created_date": d(400), "activated_date": d(400),
         "created_by": "System (seed)"},
        {"version_id": "LEARN-001", "version_type": "Learning Configuration", "label": "Learning thresholds v1.0",
         "status": "Active", "description": "Signal-detection and candidate-promotion thresholds used by "
         "learning_engine/engine.py (min sample size, modification-rate ceiling, acceptance-rate floor).",
         "parent_version_id": None, "created_date": d(400), "activated_date": d(400),
         "created_by": "System (seed)"},
        # LOGIC-002 (the Forklift/Pedestrian candidate) is inserted later, once its
        # triggering pattern has actually been counted from the generated recommendations.
    ]


def compute_outcome(conn, rec, category, action):
    """Real before/after comparison using actual incidents.incident_datetime rows —
    see module docstring. Returns the outcome_* fields for one recommendation."""
    out = {"followup_period_days": FOLLOWUP_PERIOD_DAYS}
    completion = action.get("completion_date")
    if not completion or action["status"] != "Completed":
        out.update(baseline_incident_count=None, followup_incident_count=None, followup_incident_ids=None,
                    outcome_measurement=None, effectiveness_rating=None,
                    evaluation_status="Not Evaluated", learning_signal="Not Yet Determined")
        return out

    completion_date = date.fromisoformat(completion[:10])
    elapsed = (TODAY - completion_date).days
    if elapsed < 30:
        out.update(baseline_incident_count=None, followup_incident_count=None, followup_incident_ids=None,
                    outcome_measurement="Follow-up period not yet elapsed; effectiveness cannot be assessed yet.",
                    effectiveness_rating="Not Yet Measured",
                    evaluation_status="Not Evaluated", learning_signal="Not Yet Determined")
        return out

    window = min(elapsed, FOLLOWUP_PERIOD_DAYS)
    baseline_start = (completion_date - timedelta(days=window)).isoformat()
    baseline_end = completion_date.isoformat()
    followup_end = (completion_date + timedelta(days=window)).isoformat()

    baseline_n = conn.execute(
        "SELECT COUNT(*) FROM incidents i JOIN hazards h ON i.hazard_id=h.hazard_id "
        "WHERE h.hazard_category=? AND i.facility_id=? AND i.incident_datetime>=? AND i.incident_datetime<?",
        (category, rec["facility_id"], baseline_start, baseline_end),
    ).fetchone()[0]
    followup_rows = conn.execute(
        "SELECT incident_id FROM incidents i JOIN hazards h ON i.hazard_id=h.hazard_id "
        "WHERE h.hazard_category=? AND i.facility_id=? AND i.incident_datetime>=? AND i.incident_datetime<=?",
        (category, rec["facility_id"], baseline_end, followup_end),
    ).fetchall()
    followup_n = len(followup_rows)
    followup_ids = [r[0] for r in followup_rows]

    partial_note = "" if elapsed >= FOLLOWUP_PERIOD_DAYS else \
        f" (partial follow-up window: {window} of {FOLLOWUP_PERIOD_DAYS} days elapsed so far)"

    if baseline_n + followup_n < 2:
        out.update(baseline_incident_count=baseline_n, followup_incident_count=followup_n,
                    followup_incident_ids=json.dumps(followup_ids),
                    outcome_measurement=f"Insufficient incident history in this cluster to assess before/after "
                                         f"change with confidence ({baseline_n} before, {followup_n} after){partial_note}.",
                    effectiveness_rating="Uncertain", evaluation_status="Insufficient Data",
                    learning_signal="Insufficient Data")
        return out

    if followup_n < baseline_n:
        direction, signal = "Improved", "Positive"
        rating = "High" if baseline_n >= 3 else "Medium"
        narrative = (f"Observed improvement following implementation: {baseline_n} related incident(s) in the "
                     f"{window}-day period before completion vs. {followup_n} in the {window}-day period after"
                     f"{partial_note}. This is an observed association, not an established causal effect — other "
                     f"factors may have contributed.")
    elif followup_n == baseline_n:
        direction, signal, rating = "Unchanged", "Insufficient Data", "Low" if baseline_n >= 2 else "Uncertain"
        narrative = (f"Observed no clear change following implementation ({baseline_n} before vs. {followup_n} "
                     f"after{partial_note}).")
    else:
        direction, signal, rating = "Worsened", "Negative", "Low"
        narrative = (f"Observed an increase in related incidents following implementation ({baseline_n} before vs. "
                     f"{followup_n} after{partial_note}). This does not necessarily mean the control caused the "
                     f"increase — further investigation recommended.")

    out.update(baseline_incident_count=baseline_n, followup_incident_count=followup_n,
                followup_incident_ids=json.dumps(followup_ids), outcome_measurement=narrative,
                effectiveness_rating=rating, evaluation_status="Evaluated", learning_signal=signal)
    return out


def build_forklift_candidate(conn, recommendations, facilities, reviewer_by_facility):
    """The flagship demo: a real, computed Modification pattern on the
    'Forklift / Vehicle Incident' category produces one learning candidate,
    one retrospective evaluation, human approval, and a deployed v1.1 logic
    version — then one new 'Pending' recommendation generated under that
    deployed version, ready for the interactive demo in the frontend."""
    category = "Forklift / Vehicle Incident"
    fk_recs = [r for r in recommendations if r["hazard_id"] and
               conn.execute("SELECT hazard_category FROM hazards WHERE hazard_id=?", (r["hazard_id"],)).fetchone()[0] == category]
    decided = [r for r in fk_recs if r["human_decision"] in ("Approved", "Modified", "Rejected")]
    modified = [r for r in fk_recs if r["human_decision"] == "Modified"]
    segregation_mod = [r for r in modified if r["human_modification_text"] and "barrier" in r["human_modification_text"].lower()]

    if len(segregation_mod) < 2:
        # Not enough real evidence for this pattern this run — do not fabricate a candidate.
        print("forklift candidate: skipped (fewer than 2 real Modified cases with a segregation edit)")
        return

    n = len(decided)
    baseline_mod_rate = round(len(modified) / n, 2) if n else 0.0
    # Retrospective backtest assumption (disclosed): recommendations whose ONLY human edit was the
    # segregation addendum would not have required modification if the candidate template already
    # included it; every other historical decision is assumed unchanged.
    candidate_mod_rate = round((len(modified) - len(segregation_mod)) / n, 2) if n else 0.0
    baseline_accept_rate = round(sum(1 for r in decided if r["human_decision"] == "Approved") / n, 2) if n else 0.0
    candidate_accept_rate = round(baseline_accept_rate + (len(segregation_mod) / n), 2) if n else 0.0
    evaluated = [r for r in fk_recs if r["evaluation_status"] == "Evaluated"]
    baseline_eff_rate = round(sum(1 for r in evaluated if r["effectiveness_rating"] in ("High", "Medium")) / len(evaluated), 2) if evaluated else None

    thresholds = {"min_sample_size": 5, "max_candidate_modification_rate": 0.15, "min_candidate_acceptance_rate": 0.85}
    passed = (n >= thresholds["min_sample_size"] and
              candidate_mod_rate <= thresholds["max_candidate_modification_rate"] and
              candidate_accept_rate >= thresholds["min_candidate_acceptance_rate"])
    recommendation = "Promote" if passed else ("Insufficient Data" if n < thresholds["min_sample_size"] else "Do Not Promote")

    facility_ids = sorted(set(r["facility_id"] for r in segregation_mod))
    fac_names = ", ".join(facilities[f]["name"] for f in facility_ids)

    signal_summary = (
        f"{len(modified)} of {n} decided '{category}' recommendations were Modified by a human reviewer "
        f"({baseline_mod_rate*100:.0f}%), and in {len(segregation_mod)} of those the reviewer's modification "
        f"specifically added a physical barrier/segregation control not present in the AI's original text, "
        f"across {len(facility_ids)} facilit{'y' if len(facility_ids)==1 else 'ies'} ({fac_names})."
    )

    created_date = d(45)
    evaluated_date = d(30)
    review_date = d(21)
    activated_date = d(14)

    conn.execute(
        "INSERT INTO ai_versions VALUES (:version_id,:version_type,:label,:status,:description,"
        ":parent_version_id,:created_date,:activated_date,:created_by)",
        {"version_id": "LOGIC-002", "version_type": "Recommendation Logic",
         "label": "Recommendation-logic v1.1 — forklift/pedestrian segregation addendum",
         "status": "Active", "description": (
             "For the 'Forklift / Vehicle Incident' hazard category only: appends a hedged, clearly-sourced "
             "addendum recommending consideration of physical segregation, based on the repeated human "
             "modification pattern described in learning candidate LCAND-001. All other categories unchanged "
             "from v1.0."),
         "parent_version_id": "LOGIC-001", "created_date": created_date, "activated_date": activated_date,
         "created_by": "System (Continuous Learning Engine)"},
    )
    # LOGIC-001 stays 'Active' (v1.0 still generates every other category's recommendations);
    # only the forklift-specific behavior changed under v1.1 — see docs/continuous-learning-engine.md §5.

    conn.execute(
        "INSERT INTO learning_candidates VALUES (:candidate_id,:candidate_type,:title,:description,"
        ":source_signal_summary,:source_recommendation_ids,:proposed_change,:baseline_version_id,"
        ":candidate_version_id,:status,:created_date,:created_by,:reviewed_by_employee_id,"
        ":review_decision,:review_reason,:review_date)",
        {
            "candidate_id": "LCAND-001", "candidate_type": "Recommendation Logic",
            "title": "Add physical-segregation addendum to Forklift/Pedestrian recommendation template",
            "description": "Repeated human modification detected on Forklift/Vehicle Incident recommendations: "
                            "reviewers consistently add a physical barrier the standard template does not "
                            "suggest. Proposing the template itself surface that option going forward, framed as "
                            "historical organizational learning rather than a guaranteed fix.",
            "source_signal_summary": signal_summary,
            "source_recommendation_ids": json.dumps([r["recommendation_id"] for r in segregation_mod]),
            "proposed_change": "Recommendation-logic v1.1 appends: 'Based on similar historical cases, consider "
                                "physical segregation in addition to the standard control' to Forklift/Vehicle "
                                "Incident recommendations only — explicitly labeled as historical organizational "
                                "learning, not a universal rule, and not auto-applied to any other hazard category.",
            "baseline_version_id": "LOGIC-001", "candidate_version_id": "LOGIC-002",
            "status": "Deployed", "created_date": created_date, "created_by": "System (Continuous Learning Engine)",
            "reviewed_by_employee_id": reviewer_by_facility[facility_ids[0]]["employee_id"],
            "review_decision": "Approved",
            "review_reason": (f"Evaluation showed the retrospective candidate modification rate "
                               f"({candidate_mod_rate*100:.0f}%) and acceptance rate ({candidate_accept_rate*100:.0f}%) "
                               f"met the configured thresholds; pattern was corroborated across {len(facility_ids)} "
                               f"facilit{'y' if len(facility_ids)==1 else 'ies'}. Approved for deployment to the "
                               f"Forklift/Vehicle Incident category only, with monitoring."),
            "review_date": review_date,
        },
    )

    method_note = (
        "Candidate-side rates are a RETROSPECTIVE BACKTEST against the same historical recommendations, not a "
        "live production A/B test: a Modified recommendation is assumed to require no further modification under "
        "v1.1 only if its historical modification was specifically the segregation addendum now included in the "
        "template; every other historical decision is assumed unchanged. Candidate effectiveness (outcome-based) "
        "cannot be computed retrospectively, because no historical case was ever generated under v1.1 — it is left "
        "unmeasured here and will be tracked going forward under the Monitoring stage, not assumed."
    )
    conn.execute(
        "INSERT INTO learning_evaluations VALUES (:evaluation_id,:candidate_id,:baseline_version_id,"
        ":candidate_version_id,:baseline_sample_size,:candidate_sample_size,:baseline_modification_rate,"
        ":candidate_modification_rate,:baseline_acceptance_rate,:candidate_acceptance_rate,"
        ":baseline_effectiveness_rate,:candidate_effectiveness_rate,:thresholds_json,:passed_thresholds,"
        ":recommendation,:method_note,:evaluated_date)",
        {
            "evaluation_id": "LEVAL-001", "candidate_id": "LCAND-001",
            "baseline_version_id": "LOGIC-001", "candidate_version_id": "LOGIC-002",
            "baseline_sample_size": n, "candidate_sample_size": n,
            "baseline_modification_rate": baseline_mod_rate, "candidate_modification_rate": candidate_mod_rate,
            "baseline_acceptance_rate": baseline_accept_rate, "candidate_acceptance_rate": candidate_accept_rate,
            "baseline_effectiveness_rate": baseline_eff_rate, "candidate_effectiveness_rate": None,
            "thresholds_json": json.dumps(thresholds), "passed_thresholds": 1 if passed else 0,
            "recommendation": recommendation, "method_note": method_note, "evaluated_date": evaluated_date,
        },
    )

    # One new, live 'Pending' recommendation generated under the now-deployed LOGIC-002 — the
    # interactive demo item: pick the facility with the most Forklift incidents.
    fac_counts = {}
    for r in fk_recs:
        fac_counts[r["facility_id"]] = fac_counts.get(r["facility_id"], 0) + 1
    demo_facility = max(fac_counts.items(), key=lambda kv: kv[1])[0]
    hazard_row = conn.execute("SELECT hazard_id FROM hazards WHERE hazard_category=? AND facility_id=? LIMIT 1",
                               (category, demo_facility)).fetchone()
    if not hazard_row:
        hazard_row = conn.execute("SELECT hazard_id FROM hazards WHERE hazard_category=? LIMIT 1", (category,)).fetchone()
    demo_hazard_id = hazard_row[0] if hazard_row else None

    demo_text = (
        REC_TEMPLATES[category]["text"] + " Based on similar historical cases at this facility, consider physical "
        "segregation (a barrier) in addition to the standard control — this is historical organizational learning "
        "from repeated human modification of this recommendation, not a universal rule; local validation is still "
        "recommended before implementation."
    )
    demo_evidence = (
        f"Generated under Recommendation-logic v1.1 (LOGIC-002), deployed {activated_date}. Trigger: "
        f"{signal_summary}"
    )
    conn.execute(
        "INSERT INTO recommendations VALUES (:recommendation_id,:source_type,:incident_id,:risk_register_id,"
        ":risk_signal_id,:hazard_id,:facility_id,:equipment_id,:related_control_id,:recommendation_type,"
        ":recommendation_text,:evidence_used,:ai_confidence,:prompt_version_id,:logic_version_id,"
        ":human_decision,:human_modification_text,:decision_reason,:decision_by_employee_id,:decision_date,"
        ":assigned_action_id,:action_status,:action_completion_date,:followup_period_days,"
        ":baseline_incident_count,:followup_incident_count,:followup_incident_ids,:outcome_measurement,"
        ":effectiveness_rating,:user_feedback,:learning_signal,:evaluation_status,:created_at,:updated_at)",
        {
            "recommendation_id": "REC-DEMO-001", "source_type": "Emerging Risk", "incident_id": None,
            "risk_register_id": None, "risk_signal_id": "ERISK-FORKLIFT-DEMO", "hazard_id": demo_hazard_id,
            "facility_id": demo_facility, "equipment_id": None, "related_control_id": None,
            "recommendation_type": "Engineering Control", "recommendation_text": demo_text,
            "evidence_used": demo_evidence, "ai_confidence": 0.81,
            "prompt_version_id": "PROMPT-001", "logic_version_id": "LOGIC-002",
            "human_decision": "Pending", "human_modification_text": None, "decision_reason": None,
            "decision_by_employee_id": None, "decision_date": None,
            "assigned_action_id": None, "action_status": "Not Assigned", "action_completion_date": None,
            "followup_period_days": None, "baseline_incident_count": None, "followup_incident_count": None,
            "followup_incident_ids": None, "outcome_measurement": None, "effectiveness_rating": None,
            "user_feedback": None, "learning_signal": "Not Yet Determined", "evaluation_status": "Not Evaluated",
            "created_at": TODAY.isoformat(), "updated_at": TODAY.isoformat(),
        },
    )
    print(f"forklift candidate: LCAND-001 built from {len(segregation_mod)} real segregation modifications "
          f"(of {len(modified)} Modified / {n} decided) -> {recommendation}; demo recommendation REC-DEMO-001 "
          f"seeded at {facilities[demo_facility]['name']} under LOGIC-002")


def install_schema(conn):
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    start = text.index("-- PART 2 — CONTINUOUS LEARNING ENGINE")
    end = text.index("-- END PART 2") + len("-- END PART 2")
    part2_sql = text[start:end]
    for tbl in ("learning_evaluations", "learning_candidates", "recommendations", "ai_versions"):
        conn.execute(f"DROP TABLE IF EXISTS {tbl}")
    conn.executescript(part2_sql)


if __name__ == "__main__":
    main()
