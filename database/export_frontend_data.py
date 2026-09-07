#!/usr/bin/env python3
"""
Exports database/riskon.db into the exact JSON shape frontend/app.template.html
expects (window.RISKON_DATA), replacing the older synthetic-data/*.json source
(Rex Industrial "Plant 1/2/3") with the authoritative Rex North/Central/South
Plant database built in database/generate_database.py.

Field-mapping notes (see docs/database-design.md §10 for the full rationale):
  - incidents.related_sop_id has no direct column in the new schema; derived
    best-effort via hazard_id -> controls.related_sop_id (first match).
  - incidents.status (New/In Review/Closed) is derived from the new schema's
    two real status columns (investigation_status, closure_status) rather than
    an AI-approval lifecycle, since the operational database has no AI-gate
    concept of its own — Approved/Rejected only ever appear once a reviewer
    acts on an incident inside the UI itself.
  - incidents.severity_ai / ai_confidence / ai_investigation_summary /
    ai_root_cause are null for every real incident: the operational database
    intentionally holds no AI output (see docs/ai-reasoning-engine.md — the
    reasoning engine is a separate, not-yet-wired component). The 5 example
    incidents from examples/*.json are the only ones with real AI fields,
    overlaid the same way the old export did.
  - risk_register + its current risk_assessment are flattened into one
    "riskAssessments" row per the frontend's existing (pre-register-table)
    shape; likelihood/severity are pulled from the current assessment,
    impact is just severity renamed for frontend compatibility.
  - actions map onto "correctiveActions" almost 1:1 (same lifecycle values).

This module is used two ways:
  1. As a CLI: `python3 database/export_frontend_data.py` — builds a fresh
     connection to database/riskon.db and writes synthetic-data/frontend-data.json
     (the file scripts/build_frontend.py splices into the static HTML).
  2. As a library: `backend/routes/bootstrap.py` imports `build_frontend_data()`
     directly and calls it against the backend's own live connection, so the
     `GET /api/bootstrap` endpoint and the offline static build produce BYTE-
     IDENTICAL output from the same database — one code path, not two that can
     drift apart. See RISKON_ARCHITECTURE.md "Why one data-shaping function."
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "database" / "riskon.db"
OUT_PATH = ROOT / "synthetic-data" / "frontend-data.json"
EXAMPLES_DIR = ROOT / "examples"

sys.path.insert(0, str(ROOT / "risk_intelligence"))
from engine import RiskIntelligenceEngine  # noqa: E402
sys.path.insert(0, str(ROOT / "governance"))
from audit_trail import build_audit_trail  # noqa: E402

# learning_engine/engine.py also happens to be named "engine.py" -- load it under
# a distinct module name via importlib so it doesn't collide with (or shadow)
# risk_intelligence's already-imported "engine" module above.
import importlib.util
_spec = importlib.util.spec_from_file_location("learning_engine_module", ROOT / "learning_engine" / "engine.py")
_learning_engine_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_learning_engine_module)
LearningEngine = _learning_engine_module.LearningEngine


EXAMPLE_META = {
    "INC-2101": {"title": "Forklift/Pedestrian Near Miss – Blind Aisle Corner", "severity_reported": "Low"},
    "INC-2102": {"title": "Machine Guard Defeated – Punch Press Jam Clearing", "severity_reported": "Medium"},
    "INC-2103": {"title": "Solvent Spill – Parts Cleaning Station", "severity_reported": "Low"},
    "INC-2104": {"title": "Ladder Instability – Ventilation Unit Maintenance", "severity_reported": "Medium"},
    "INC-2105": {"title": "Contractor LOTO/Permit Non-Compliance – Electrical Panel", "severity_reported": "Medium"},
}


def _derive_status(investigation_status, closure_status):
    if closure_status == "Closed":
        return "Closed"
    if investigation_status == "Not Started":
        return "New"
    return "In Review"  # In Progress, or Completed-but-not-yet-closed


def _derive_shift(incident_datetime):
    hour = int(incident_datetime[11:13])
    if 6 <= hour < 14:
        return "Day"
    if 14 <= hour < 22:
        return "Swing"
    return "Night"


def _avg_confidence(node, acc):
    if isinstance(node, dict):
        if "confidence" in node and isinstance(node["confidence"], (int, float)):
            acc.append(node["confidence"])
        for v in node.values():
            _avg_confidence(v, acc)
    elif isinstance(node, list):
        for v in node:
            _avg_confidence(v, acc)


def build_frontend_data(conn, db_path=DB_PATH):
    """Builds the full `window.RISKON_DATA`-shaped dict from an OPEN sqlite3
    connection. `db_path` is only needed because RiskIntelligenceEngine/
    LearningEngine open their own second connection internally (they were
    built as standalone, reusable analytics engines, not tied to one caller's
    connection) — everything else in this function reads through `conn`."""
    conn.row_factory = sqlite3.Row

    def rows(query, params=()):
        return [dict(r) for r in conn.execute(query, params)]

    def one(query, params=()):
        r = conn.execute(query, params).fetchone()
        return dict(r) if r else None

    facilities = rows("""
        SELECT facility_id, name, facility_type, city, state, country,
               (address) AS address, square_footage, year_established, employee_capacity
        FROM facilities
    """)

    employees = rows("""
        SELECT e.employee_id, e.first_name, e.last_name, e.email,
               r.title AS role, r.department, e.facility_id, e.hire_date, e.is_active
        FROM employees e JOIN roles r ON e.role_id = r.role_id
    """)

    equipment = rows("""
        SELECT equipment_id, equipment_type, category, manufacturer, model_number,
               serial_number, facility_id, install_date, last_maintenance_date, status, criticality
        FROM equipment
    """)

    sops = rows("""
        SELECT sop_id, title, category, version, effective_date, next_review_date,
               owner_employee_id, facility_id, status
        FROM sops
    """)

    controls = rows("""
        SELECT control_id, control_name, control_type, hazard_id
        FROM controls
    """)

    # -----------------------------------------------------------------------
    # hazards / maintenance / controlAssessments / training / inspections —
    # raw table exports for the Global Risk Map and related facility-level UI
    # work (previously hazards/maintenance/etc. were only ever folded into
    # incidents/risk rows above, never exposed as their own array). Additive
    # only: these are NEW top-level keys, nothing existing is reshaped.
    # -----------------------------------------------------------------------
    hazards = rows("""
        SELECT hazard_id, hazard_category, description, facility_id, equipment_id,
               typical_consequence, identified_date, identified_by_employee_id, status
        FROM hazards
    """)

    maintenance = rows("""
        SELECT maintenance_record_id, equipment_id, facility_id, maintenance_type,
               scheduled_date, actual_date, delay_days, performed_by_employee_id,
               description, status, related_incident_id
        FROM maintenance_records
    """)

    control_assessments = rows("""
        SELECT control_assessment_id, control_id, assessment_date, assessed_by_employee_id,
               effectiveness_rating, findings, related_incident_id, related_inspection_id
        FROM control_assessments
    """)

    training = rows("""
        SELECT training_record_id, employee_id, contractor_id, training_topic,
               training_date, expiry_date, status, conducted_by_employee_id, result
        FROM training_records
    """)

    inspections = rows("""
        SELECT inspection_id, facility_id, inspection_type, inspection_date,
               inspector_employee_id, equipment_id, area_location, findings_summary,
               deficiencies_found, status
        FROM inspections
    """)

    # hazard_id -> hazard_category / a representative related_sop_id (best effort,
    # via that hazard's first control) — used to enrich incidents below.
    hazard_lookup = {}
    for h in rows("SELECT hazard_id, hazard_category FROM hazards"):
        ctl = one("SELECT related_sop_id FROM controls WHERE hazard_id=? AND related_sop_id IS NOT NULL LIMIT 1", (h["hazard_id"],))
        hazard_lookup[h["hazard_id"]] = {
            "hazard_category": h["hazard_category"],
            "related_sop_id": ctl["related_sop_id"] if ctl else None,
        }

    equip_type_lookup = {e["equipment_id"]: e["equipment_type"] for e in equipment}

    # -----------------------------------------------------------------------
    # incidents — real ~100 rows, mapped to the frontend's flat shape
    # -----------------------------------------------------------------------
    incidents = []
    for r in rows("SELECT * FROM incidents"):
        hz = hazard_lookup.get(r["hazard_id"], {"hazard_category": "Unclassified", "related_sop_id": None})
        equip_label = equip_type_lookup.get(r["equipment_id"]) or hz["hazard_category"]
        incidents.append({
            "incident_id": r["incident_id"],
            "facility_id": r["facility_id"],
            "equipment_id": r["equipment_id"],
            "related_sop_id": hz["related_sop_id"],
            "reporter_employee_id": r["reported_by_employee_id"],
            "title": f"{hz['hazard_category']} – {equip_label}",
            "description": r["description"],
            "hazard_category": hz["hazard_category"],
            "shift": _derive_shift(r["incident_datetime"]),
            "date_occurred": r["incident_datetime"][:10],
            "severity_reported": r["initial_severity"],
            "severity_ai": None,
            "ai_confidence": None,
            "status": _derive_status(r["investigation_status"], r["closure_status"]),
            "ai_investigation_summary": None,
            "ai_root_cause": None,
            "created_at": r["reported_at"],
            "has_full_ai_pipeline": False,
            "ai_pipeline_id": None,
        })

    # -----------------------------------------------------------------------
    # riskAssessments — one row per risk_register entry, flattened with its
    # current risk_assessment's likelihood/severity (frontend calls it "impact")
    # -----------------------------------------------------------------------
    risk_assessments = []
    for rr in rows("SELECT * FROM risk_register"):
        ra = one("SELECT * FROM risk_assessments WHERE risk_assessment_id=?", (rr["current_risk_assessment_id"],))
        hz = hazard_lookup.get(rr["hazard_id"], {"hazard_category": "Unclassified", "related_sop_id": None})
        src_incident = one("SELECT incident_id FROM incidents WHERE hazard_id=? ORDER BY incident_datetime DESC LIMIT 1", (rr["hazard_id"],))
        ctl_names = [c["control_name"] for c in rows("SELECT control_name FROM controls WHERE hazard_id=?", (rr["hazard_id"],))]
        risk_assessments.append({
            "risk_assessment_id": rr["risk_register_id"],
            "facility_id": rr["facility_id"],
            "hazard_category": hz["hazard_category"],
            "equipment_id": ra["equipment_id"] if ra else None,
            "source_incident_id": src_incident["incident_id"] if src_incident else None,
            "related_sop_id": hz["related_sop_id"],
            "likelihood": ra["likelihood"] if ra else None,
            "impact": ra["severity"] if ra else None,
            "risk_score": rr["current_score"],
            "risk_level": rr["current_level"],
            "existing_controls": "; ".join(ctl_names) if ctl_names else "No documented control on file.",
            "recommended_controls": ra["methodology_notes"] if ra else "",
            "assessed_by_employee_id": ra["assessed_by_employee_id"] if ra else rr["owner_employee_id"],
            "assessment_date": rr["last_reviewed_date"],
            "status": rr["status"],
        })

    # -----------------------------------------------------------------------
    # correctiveActions — actions table maps ~1:1
    # -----------------------------------------------------------------------
    corrective_actions = rows("""
        SELECT action_id AS corrective_action_id, source_incident_id AS incident_id,
               source_risk_assessment_id AS risk_assessment_id, facility_id,
               (SELECT equipment_id FROM incidents WHERE incident_id = actions.source_incident_id) AS equipment_id,
               action_type, description, owner_employee_id, created_date, due_date,
               status, completion_date, verification_method
        FROM actions
    """)

    # -----------------------------------------------------------------------
    # 5 AI-reasoning example incidents (overlay, same as the previous export) —
    # facility ids are compatible (same FAC-001/002/003 scheme, same underlying
    # cities/states in both datasets), so these carry over unchanged.
    # -----------------------------------------------------------------------
    pipelines = {}
    for f in sorted(EXAMPLES_DIR.glob("*.json")):
        p = json.load(open(f, encoding="utf-8"))
        pipelines[p["incident_id"]] = p

    employee_ids = {e["employee_id"] for e in employees}

    for inc_id, meta in EXAMPLE_META.items():
        p = pipelines[inc_id]
        s1, s3, s6 = (p["stage_1_ingestion"], p["stage_3_classification"],
                      p["stage_6_preliminary_severity_assessment"])
        confs = []
        _avg_confidence(p, confs)
        overall_confidence = round(sum(confs) / len(confs), 2) if confs else None

        reporter = s1["reporter_employee_id"] if s1["reporter_employee_id"] in employee_ids else employees[0]["employee_id"]

        incidents.append({
            "incident_id": inc_id,
            "facility_id": s1["facility_id"],
            "equipment_id": None,
            "related_sop_id": None,
            "reporter_employee_id": reporter,
            "title": meta["title"],
            "description": s1["raw_report_text"],
            "hazard_category": s3["incident_category"]["value"],
            "shift": "Day",
            "date_occurred": s1["date_submitted"][:10],
            "severity_reported": meta["severity_reported"],
            "severity_ai": s6["ai_suggested_severity"]["value"],
            "ai_confidence": overall_confidence,
            "status": "In Review",
            "ai_investigation_summary": p["stage_13_human_review_package"]["summary_for_reviewer"],
            "ai_root_cause": p["stage_8_root_cause_hypotheses"]["hypotheses"][0]["statement"],
            "created_at": s1["date_submitted"],
            "has_full_ai_pipeline": True,
            "ai_pipeline_id": inc_id,
        })

    # -----------------------------------------------------------------------
    # riskIntelligence — computed fresh from the same database by the Risk
    # Intelligence Engine (risk_intelligence/engine.py). Nothing here is
    # hand-authored: every emerging risk and every Q&A finding is the direct
    # output of RiskIntelligenceEngine.answer_all() / .all_emerging_risks(),
    # run against database/riskon.db at export time.
    # -----------------------------------------------------------------------
    ri_engine = RiskIntelligenceEngine(db_path)
    all_risks = ri_engine.all_emerging_risks()
    risk_intelligence = {
        "generatedAt": "2026-09-03",
        "allRisks": all_risks,
        "topRisks": all_risks[:5],
        "qa": ri_engine.answer_all(),
    }

    # -----------------------------------------------------------------------
    # executiveDashboard — the 7-section Executive Dashboard data, all computed
    # fresh from the same engine (see risk_intelligence/engine.py's enterprise_*
    # and facility_comparison/corrective_action_intelligence/management_brief
    # methods). Nothing here is hand-authored.
    # -----------------------------------------------------------------------
    executive_dashboard = {
        "overview": ri_engine.enterprise_overview(),
        "topRisks": all_risks[:5],
        "facilityComparison": ri_engine.facility_comparison(),
        "riskTrend": ri_engine.enterprise_risk_trend(6),
        "correctiveActionIntelligence": ri_engine.corrective_action_intelligence(),
        "managementBrief": ri_engine.management_brief(),
    }

    # -----------------------------------------------------------------------
    # continuousLearning — the Continuous Learning Engine's data, computed fresh
    # from database/riskon.db's Part-2 tables (ai_versions, recommendations,
    # learning_candidates, learning_evaluations) by learning_engine/engine.py.
    # See docs/continuous-learning-engine.md. Every recommendation row is
    # included (not just a capped sample) so the frontend's per-recommendation
    # feedback demo and Learning Graph can look up any of them by id.
    # -----------------------------------------------------------------------
    learn_engine = LearningEngine(db_path)
    learn_categories = sorted(set(r["hazard_category"] for r in learn_engine.recommendations))
    continuous_learning = {
        "generatedAt": "2026-09-03",
        "overview": learn_engine.learning_overview(),
        "performanceByPattern": learn_engine.performance_by_pattern(),
        "signals": learn_engine.detect_signals(),
        "expertFeedbackPatterns": learn_engine.expert_feedback_patterns(),
        "multiFacilityLearning": learn_engine.multi_facility_learning(),
        "versions": learn_engine.versions(),
        "candidates": learn_engine.candidates_with_evaluations(),
        "recommendations": [{k: v for k, v in r.items() if not k.startswith("_")} for r in learn_engine.recommendations],
        "contextAwareNotes": {cat: learn_engine.context_aware_note(cat) for cat in learn_categories
                              if learn_engine.context_aware_note(cat)},
    }

    # -----------------------------------------------------------------------
    # auditTrail — seed log built from real, already-stored lifecycle data (see
    # governance/audit_trail.py). The running app appends live entries to this
    # same array as the user takes actions (approve/reject/submit) — see
    # frontend/app.template.html's logAudit(). The backend's own live-persisted
    # actions (see backend/routes/) are additionally reconstructed here since
    # build_audit_trail() reads straight from the tables those routes write to.
    # -----------------------------------------------------------------------
    audit_trail = build_audit_trail(db_path, max_incidents=20)

    return {
        "facilities": facilities,
        "employees": employees,
        "equipment": equipment,
        "sops": sops,
        "controls": controls,
        "hazards": hazards,
        "maintenance": maintenance,
        "controlAssessments": control_assessments,
        "training": training,
        "inspections": inspections,
        "incidents": incidents,
        "riskAssessments": risk_assessments,
        "correctiveActions": corrective_actions,
        "aiPipelines": pipelines,
        "riskIntelligence": risk_intelligence,
        "executiveDashboard": executive_dashboard,
        "continuousLearning": continuous_learning,
        "auditTrail": audit_trail,
    }


def main():
    conn = sqlite3.connect(DB_PATH)
    out = build_frontend_data(conn, DB_PATH)
    conn.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))

    all_risks = out["riskIntelligence"]["allRisks"]
    audit_trail = out["auditTrail"]
    cl = out["continuousLearning"]
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size/1024:.1f} KB)")
    print(f"facilities={len(out['facilities'])} employees={len(out['employees'])} "
          f"equipment={len(out['equipment'])} sops={len(out['sops'])}")
    print(f"incidents={len(out['incidents'])} (5 with full AI pipeline) "
          f"riskAssessments={len(out['riskAssessments'])} correctiveActions={len(out['correctiveActions'])}")
    print(f"riskIntelligence: {len(all_risks)} emerging risk clusters computed, "
          f"top band = {all_risks[0]['risk_band']} ({all_risks[0]['risk_name']})")
    print(f"auditTrail: {len(audit_trail)} seed entries "
          f"({sum(1 for a in audit_trail if a['source']=='AI-generated')} AI-generated, "
          f"{sum(1 for a in audit_trail if a['source']=='Human-generated')} Human-generated)")
    print(f"continuousLearning: {len(cl['recommendations'])} recommendations, "
          f"{len(cl['signals'])} learning signals, {len(cl['candidates'])} candidate(s)")


if __name__ == "__main__":
    main()
