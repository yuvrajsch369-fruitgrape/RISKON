#!/usr/bin/env python3
"""
RISKON V0.1 — database consistency validator.

Runs independently against database/riskon.db (does not re-generate data)
and checks exactly the items requested in the spec:
  - no broken foreign keys
  - no impossible dates
  - no duplicate IDs
  - every corrective/preventive action has a valid related issue
  - every incident belongs to a facility
  - every risk belongs to a valid hazard
  - every equipment-related incident references valid equipment
  - historical events have logically consistent statuses
Plus SQLite's own PRAGMA foreign_key_check as a blanket safety net.

Writes database/validation_report.md and exits non-zero if any check fails.
"""
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "database" / "riskon.db"
TODAY = date(2026, 9, 3)
WINDOW_START = date(2025, 1, 1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON;")

results = []  # (check_name, passed: bool, detail: str)

def check(name, query_or_fn, expect_empty=True):
    if callable(query_or_fn):
        rows = query_or_fn()
    else:
        rows = conn.execute(query_or_fn).fetchall()
    passed = (len(rows) == 0) if expect_empty else True
    detail = f"{len(rows)} violation(s)" if rows else "OK"
    if rows and len(rows) <= 10:
        detail += ": " + ", ".join(str(dict(r)) for r in rows[:10])
    results.append((name, passed, detail))
    return passed

# -----------------------------------------------------------------------
# 1. SQLite's blanket FK check (catches anything a manual check might miss)
# -----------------------------------------------------------------------
check("SQLite PRAGMA foreign_key_check (all tables)", "PRAGMA foreign_key_check;")

# -----------------------------------------------------------------------
# 2. No duplicate primary keys (redundant with PK constraint, checked explicitly per spec)
# -----------------------------------------------------------------------
PK_TABLES = {
    "companies":"company_id","facilities":"facility_id","roles":"role_id","employees":"employee_id",
    "contractors":"contractor_id","equipment":"equipment_id","sops":"sop_id","hazards":"hazard_id",
    "controls":"control_id","maintenance_records":"maintenance_record_id","incidents":"incident_id",
    "risk_assessments":"risk_assessment_id","risk_register":"risk_register_id",
    "control_assessments":"control_assessment_id","inspections":"inspection_id",
    "audit_findings":"audit_finding_id","actions":"action_id","training_records":"training_record_id",
    "evidence":"evidence_id",
}
for table, pk in PK_TABLES.items():
    check(f"No duplicate IDs in {table}.{pk}",
          f"SELECT {pk}, COUNT(*) c FROM {table} GROUP BY {pk} HAVING c > 1;")

# -----------------------------------------------------------------------
# 3. Every incident belongs to a valid facility
# -----------------------------------------------------------------------
check("Every incident belongs to a valid facility",
      "SELECT i.incident_id FROM incidents i LEFT JOIN facilities f ON i.facility_id = f.facility_id WHERE f.facility_id IS NULL;")

# -----------------------------------------------------------------------
# 4. Every equipment-related incident references valid equipment
# -----------------------------------------------------------------------
check("Every equipment-referencing incident points to real equipment",
      "SELECT i.incident_id FROM incidents i WHERE i.equipment_id IS NOT NULL "
      "AND NOT EXISTS (SELECT 1 FROM equipment e WHERE e.equipment_id = i.equipment_id);")

# -----------------------------------------------------------------------
# 5. Every risk (assessment + register) belongs to a valid hazard
# -----------------------------------------------------------------------
check("Every risk_assessment references a valid hazard",
      "SELECT risk_assessment_id FROM risk_assessments ra WHERE NOT EXISTS "
      "(SELECT 1 FROM hazards h WHERE h.hazard_id = ra.hazard_id);")
check("Every risk_register entry references a valid hazard",
      "SELECT risk_register_id FROM risk_register rr WHERE NOT EXISTS "
      "(SELECT 1 FROM hazards h WHERE h.hazard_id = rr.hazard_id);")

# -----------------------------------------------------------------------
# 6. Every action has a valid related issue (its declared source record exists)
# -----------------------------------------------------------------------
def actions_bad_source():
    bad = []
    for r in conn.execute("SELECT * FROM actions;"):
        r = dict(r)
        st, sid = r["source_type"], None
        table_map = {"Incident":("source_incident_id","incidents","incident_id"),
                     "Audit Finding":("source_audit_finding_id","audit_findings","audit_finding_id"),
                     "Inspection":("source_inspection_id","inspections","inspection_id"),
                     "Risk Assessment":("source_risk_assessment_id","risk_assessments","risk_assessment_id")}
        col, table, pk = table_map[st]
        sid = r[col]
        if sid is None:
            bad.append({"action_id": r["action_id"], "issue": f"source_type={st} but {col} is NULL"})
            continue
        exists = conn.execute(f"SELECT 1 FROM {table} WHERE {pk} = ?", (sid,)).fetchone()
        if not exists:
            bad.append({"action_id": r["action_id"], "issue": f"{col}={sid} not found in {table}"})
    return bad
check("Every action's declared source record exists (valid related issue)", actions_bad_source)

# -----------------------------------------------------------------------
# 6b. equipment.last_maintenance_date must match a real maintenance_records row
#     for that equipment where one exists (not an independently-random fact
#     duplicated across two tables) — regression check for a bug found and
#     fixed in this pass.
# -----------------------------------------------------------------------
def equipment_maintenance_date_mismatch():
    bad = []
    for eq in conn.execute("SELECT equipment_id, last_maintenance_date FROM equipment;"):
        eq = dict(eq)
        performed = conn.execute(
            "SELECT MAX(actual_date) AS latest FROM maintenance_records WHERE equipment_id=? AND actual_date IS NOT NULL",
            (eq["equipment_id"],),
        ).fetchone()
        if performed and performed["latest"] and performed["latest"] != eq["last_maintenance_date"]:
            bad.append({"equipment_id": eq["equipment_id"], "issue":
                        f"equipment.last_maintenance_date={eq['last_maintenance_date']} but latest real "
                        f"maintenance_records.actual_date={performed['latest']}"})
    return bad
check("equipment.last_maintenance_date matches its real maintenance_records history", equipment_maintenance_date_mismatch)

def auditor_name_mismatch():
    bad = []
    for r in conn.execute(
        "SELECT af.audit_finding_id, af.auditor_name, e.first_name, e.last_name "
        "FROM audit_findings af JOIN employees e ON af.auditor_employee_id = e.employee_id"
    ):
        r = dict(r)
        expected = f"{r['first_name']} {r['last_name']} (Internal Audit)"
        if r["auditor_name"] != expected:
            bad.append({"audit_finding_id": r["audit_finding_id"], "issue":
                        f"auditor_name='{r['auditor_name']}' does not match auditor_employee_id -> '{expected}'"})
    return bad
check("audit_findings.auditor_name matches auditor_employee_id where set", auditor_name_mismatch)

# -----------------------------------------------------------------------
# 7. No impossible dates
# -----------------------------------------------------------------------
def impossible_dates():
    bad = []
    for r in conn.execute("SELECT incident_id, incident_datetime, reported_at, closed_date FROM incidents;"):
        r = dict(r)
        inc_date = r["incident_datetime"][:10]
        if inc_date > TODAY.isoformat() or inc_date < WINDOW_START.isoformat():
            bad.append({"incident_id": r["incident_id"], "issue": f"incident_datetime {inc_date} outside operating window"})
        if r["reported_at"][:10] < inc_date:
            bad.append({"incident_id": r["incident_id"], "issue": "reported_at before incident_datetime"})
        if r["closed_date"] and r["closed_date"] < inc_date:
            bad.append({"incident_id": r["incident_id"], "issue": "closed_date before incident_datetime"})
        if r["closed_date"] and r["closed_date"] > TODAY.isoformat():
            bad.append({"incident_id": r["incident_id"], "issue": "closed_date in the future"})
    for r in conn.execute("SELECT action_id, created_date, due_date, completion_date FROM actions;"):
        r = dict(r)
        if r["completion_date"] and r["completion_date"] < r["created_date"]:
            bad.append({"action_id": r["action_id"], "issue": "completion_date before created_date"})
        if r["completion_date"] and r["completion_date"] > TODAY.isoformat():
            bad.append({"action_id": r["action_id"], "issue": "completion_date in the future"})
    for r in conn.execute("SELECT equipment_id, install_date, last_maintenance_date FROM equipment WHERE last_maintenance_date IS NOT NULL;"):
        r = dict(r)
        if r["last_maintenance_date"] < r["install_date"]:
            bad.append({"equipment_id": r["equipment_id"], "issue": "last_maintenance_date before install_date"})
    for r in conn.execute("SELECT employee_id, hire_date FROM employees;"):
        r = dict(r)
        if r["hire_date"] > TODAY.isoformat():
            bad.append({"employee_id": r["employee_id"], "issue": "hire_date in the future"})
    return bad
check("No impossible dates (incidents/actions/equipment/employees)", impossible_dates)

# -----------------------------------------------------------------------
# 8. Historical events have logically consistent statuses
# -----------------------------------------------------------------------
def inconsistent_statuses():
    bad = []
    for r in conn.execute("SELECT incident_id, closure_status, investigation_status, closed_date, root_cause_category FROM incidents;"):
        r = dict(r)
        if r["closure_status"] == "Closed" and r["closed_date"] is None:
            bad.append({"incident_id": r["incident_id"], "issue": "Closed but no closed_date"})
        if r["closure_status"] == "Closed" and r["investigation_status"] != "Completed":
            bad.append({"incident_id": r["incident_id"], "issue": "Closed but investigation not Completed"})
        if r["closure_status"] == "Closed" and r["root_cause_category"] is None:
            bad.append({"incident_id": r["incident_id"], "issue": "Closed but no root_cause_category"})
        if r["investigation_status"] != "Completed" and r["root_cause_category"] is not None:
            bad.append({"incident_id": r["incident_id"], "issue": "root_cause_category set before investigation Completed"})
    for r in conn.execute("SELECT action_id, status, completion_date, due_date FROM actions;"):
        r = dict(r)
        if r["status"] == "Completed" and r["completion_date"] is None:
            bad.append({"action_id": r["action_id"], "issue": "Completed but no completion_date"})
        if r["status"] == "Overdue" and r["due_date"] >= TODAY.isoformat():
            bad.append({"action_id": r["action_id"], "issue": "Overdue but due_date is not in the past"})
        if r["status"] in ("Open","In Progress") and r["completion_date"] is not None:
            bad.append({"action_id": r["action_id"], "issue": f"{r['status']} but completion_date is set"})
    for r in conn.execute("SELECT maintenance_record_id, status, actual_date, scheduled_date FROM maintenance_records;"):
        r = dict(r)
        if r["status"] == "Completed" and r["actual_date"] is None:
            bad.append({"maintenance_record_id": r["maintenance_record_id"], "issue": "Completed but no actual_date"})
    for r in conn.execute("SELECT training_record_id, status, training_date FROM training_records;"):
        r = dict(r)
        if r["status"] == "Not Completed" and r["training_date"] is not None:
            bad.append({"training_record_id": r["training_record_id"], "issue": "Not Completed but training_date is set"})
        if r["status"] in ("Current","Expired") and r["training_date"] is None:
            bad.append({"training_record_id": r["training_record_id"], "issue": f"{r['status']} but no training_date"})
    return bad
check("Historical events have logically consistent statuses", inconsistent_statuses)

# -----------------------------------------------------------------------
# 9. Cross-checks on the three "undeclared" forward-reference columns
#    (SQLite couldn't declare these as FKs at CREATE TABLE time — see schema.sql note)
# -----------------------------------------------------------------------
check("incidents.related_risk_register_id points to a real risk_register row (where set)",
      "SELECT incident_id FROM incidents WHERE related_risk_register_id IS NOT NULL "
      "AND related_risk_register_id NOT IN (SELECT risk_register_id FROM risk_register);")
check("maintenance_records.related_incident_id points to a real incident (where set)",
      "SELECT maintenance_record_id FROM maintenance_records WHERE related_incident_id IS NOT NULL "
      "AND related_incident_id NOT IN (SELECT incident_id FROM incidents);")

# -----------------------------------------------------------------------
# 10. Row-count sanity vs. the spec's approximate volumes
# -----------------------------------------------------------------------
EXPECTED = {"facilities":3,"equipment":30,"employees":30,"contractors":20,"incidents":100,
            "risk_assessments":50,"hazards":75,"actions":100,"controls":50,"sops":30,
            "inspections":75,"maintenance_records":50,"training_records":50,"audit_findings":30}
volume_report = []
for table, expected in EXPECTED.items():
    actual = conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
    within = abs(actual - expected) <= max(3, round(expected * 0.1))
    volume_report.append((table, expected, actual, within))

# =========================================================================
# WRITE REPORT
# =========================================================================
passed_count = sum(1 for _, ok, _ in results if ok)
failed = [(n, d) for n, ok, d in results if not ok]

lines = ["# RISKON V0.1 — Database Validation Report", "",
         f"Run against `database/riskon.db`. {passed_count}/{len(results)} checks passed.", ""]
lines.append("## Consistency checks\n")
lines.append("| Check | Result | Detail |")
lines.append("|---|---|---|")
for name, ok, detail in results:
    lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")

lines.append("\n## Row-count sanity vs. spec volumes\n")
lines.append("| Table | Spec target | Actual | Within tolerance |")
lines.append("|---|---|---|---|")
for table, expected, actual, within in volume_report:
    lines.append(f"| {table} | ~{expected} | {actual} | {'yes' if within else 'NO'} |")

lines.append(f"\n## Summary\n")
if failed:
    lines.append(f"**{len(failed)} check(s) FAILED:**\n")
    for name, detail in failed:
        lines.append(f"- **{name}** — {detail}")
else:
    lines.append("All consistency checks passed. No broken foreign keys, no impossible dates, no duplicate "
                  "IDs, every action traces to a real source record, every incident has a valid facility, "
                  "every risk traces to a valid hazard, every equipment reference resolves, and status fields "
                  "are logically consistent with their dates.")

report_path = ROOT / "database" / "validation_report.md"
report_path.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
print(f"\nReport written to {report_path}")

sys.exit(1 if failed else 0)
