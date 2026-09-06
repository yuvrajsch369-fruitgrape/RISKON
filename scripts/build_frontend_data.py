#!/usr/bin/env python3
"""Consolidates synthetic-data/*.json + examples/*.json into one JSON blob
for embedding directly in the frontend prototype (frontend/riskon.html).

- Normalizes bulk incidents.json (severity_ai_classified -> severity_ai) and
  flags them has_full_ai_pipeline: false.
- Synthesizes 5 incident-list rows for the 5 fully-worked AI reasoning
  examples (has_full_ai_pipeline: true), deriving fields from each example's
  own stage_1/stage_2/stage_3/stage_6 output rather than inventing new facts.
- Computes a representative overall AI confidence per full-pipeline incident
  by averaging every numeric `confidence` found in that pipeline's JSON.
- Emits synthetic-data/frontend-data.json (consumed by build_frontend.py).
"""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return json.load(open(path, encoding="utf-8"))


facilities = load(ROOT / "synthetic-data/json/facilities.json")
employees = load(ROOT / "synthetic-data/json/employees.json")
equipment = load(ROOT / "synthetic-data/json/equipment.json")
sops = load(ROOT / "synthetic-data/json/sops.json")
incidents_bulk = load(ROOT / "synthetic-data/json/incidents.json")
risk_assessments = load(ROOT / "synthetic-data/json/risk_assessments.json")
corrective_actions = load(ROOT / "synthetic-data/json/corrective_actions.json")

example_files = sorted((ROOT / "examples").glob("*.json"))
pipelines = {}
for f in example_files:
    p = load(f)
    pipelines[p["incident_id"]] = p


def avg_confidence(node, acc):
    if isinstance(node, dict):
        if "confidence" in node and isinstance(node["confidence"], (int, float)):
            acc.append(node["confidence"])
        for v in node.values():
            avg_confidence(v, acc)
    elif isinstance(node, list):
        for v in node:
            avg_confidence(v, acc)


# ---------------------------------------------------------------------------
# Normalize bulk incidents to the unified shape used by the frontend
# ---------------------------------------------------------------------------
incidents = []
for r in incidents_bulk:
    incidents.append({
        "incident_id": r["incident_id"],
        "facility_id": r["facility_id"],
        "equipment_id": r["equipment_id"],
        "related_sop_id": r["related_sop_id"],
        "reporter_employee_id": r["reporter_employee_id"],
        "title": r["title"],
        "description": r["description"],
        "hazard_category": r["hazard_category"],
        "shift": r["shift"],
        "date_occurred": r["date_occurred"],
        "severity_reported": r["severity_reported"],
        "severity_ai": r["severity_ai_classified"],
        "ai_confidence": r["ai_confidence"],
        "status": r["status"],
        "ai_investigation_summary": r["ai_investigation_summary"],
        "ai_root_cause": r["ai_root_cause"],
        "created_at": r["created_at"],
        "has_full_ai_pipeline": False,
        "ai_pipeline_id": None,
    })

# ---------------------------------------------------------------------------
# Synthesize incident-list rows for the 5 fully-worked pipeline examples
# ---------------------------------------------------------------------------
EXAMPLE_META = {
    "INC-2101": {
        "title": "Forklift/Pedestrian Near Miss – Blind Aisle Corner",
        "severity_reported": "Low",
    },
    "INC-2102": {
        "title": "Machine Guard Defeated – Punch Press Jam Clearing",
        "severity_reported": "Medium",
    },
    "INC-2103": {
        "title": "Solvent Spill – Parts Cleaning Station",
        "severity_reported": "Low",
    },
    "INC-2104": {
        "title": "Ladder Instability – Ventilation Unit Maintenance",
        "severity_reported": "Medium",
    },
    "INC-2105": {
        "title": "Contractor LOTO/Permit Non-Compliance – Electrical Panel",
        "severity_reported": "Medium",
    },
}

for inc_id, meta in EXAMPLE_META.items():
    p = pipelines[inc_id]
    s1 = p["stage_1_ingestion"]
    s2 = p["stage_2_information_extraction"]
    s3 = p["stage_3_classification"]
    s6 = p["stage_6_preliminary_severity_assessment"]

    confs = []
    avg_confidence(p, confs)
    overall_confidence = round(statistics.mean(confs), 2) if confs else None

    date_occurred = s1["date_submitted"][:10]

    incidents.append({
        "incident_id": inc_id,
        "facility_id": s1["facility_id"],
        "equipment_id": None,
        "related_sop_id": None,
        "reporter_employee_id": s1["reporter_employee_id"],
        "title": meta["title"],
        "description": s1["raw_report_text"],
        "hazard_category": s3["incident_category"]["value"],
        "shift": "Day",
        "date_occurred": date_occurred,
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

# ---------------------------------------------------------------------------
# Write consolidated blob
# ---------------------------------------------------------------------------
out = {
    "facilities": facilities,
    "employees": employees,
    "equipment": equipment,
    "sops": sops,
    "incidents": incidents,
    "riskAssessments": risk_assessments,
    "correctiveActions": corrective_actions,
    "aiPipelines": pipelines,
}

out_path = ROOT / "synthetic-data" / "frontend-data.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=None, separators=(",", ":"))

print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")
print(f"Incidents: {len(incidents)} (5 with full AI pipeline)")
