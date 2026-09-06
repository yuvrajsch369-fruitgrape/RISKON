"""
Assembles the RISKON context for one incident-analysis AI request — real
database queries only, never the whole database. This is the Python,
actually-executed counterpart to the `ReferenceData` concept already sketched
(but never wired up) in engine/pipeline.ts: pull only what's relevant to the
one incident being analyzed, and pass Claude nothing it wasn't given.

Every list below is capped (5-10 rows) — not because more data exists, but
because a well-scoped context produces a more focused analysis than "every
row that could possibly relate," and keeps the prompt (and therefore cost and
latency) bounded regardless of how large this dataset grows. Each cap is
called out at the query itself.
"""
import json
import sqlite3


class IncidentNotFoundError(LookupError):
    pass


def _rows(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params)]


def _one(conn: sqlite3.Connection, sql: str, params=()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def build_incident_context(conn: sqlite3.Connection, incident_id: str) -> dict:
    """Returns a JSON-serializable dict — the exact object sent to Claude
    (and also persisted verbatim in ai_incident_analyses.context_json for
    audit/debugging). Raises IncidentNotFoundError if the id doesn't exist."""
    incident = _one(conn, "SELECT * FROM incidents WHERE incident_id=?", (incident_id,))
    if not incident:
        raise IncidentNotFoundError(incident_id)

    facility = _one(conn, "SELECT facility_id, name, facility_type, city, state FROM facilities WHERE facility_id=?",
                     (incident["facility_id"],))

    equipment = None
    if incident["equipment_id"]:
        equipment = _one(conn, """SELECT equipment_id, equipment_type, category, manufacturer, model_number,
                                          status, criticality, last_maintenance_date
                                   FROM equipment WHERE equipment_id=?""", (incident["equipment_id"],))

    hazard = None
    if incident["hazard_id"]:
        hazard = _one(conn, """SELECT hazard_id, hazard_category, description, typical_consequence, status
                                FROM hazards WHERE hazard_id=?""", (incident["hazard_id"],))

    # Related past incidents/near-misses — same facility + hazard, most recent
    # 8, excluding this one. This is the single most important piece of
    # cross-record context: it's what lets Claude reason about recurrence
    # rather than this one event in isolation.
    related_incidents = []
    if incident["hazard_id"]:
        related_incidents = _rows(conn, """
            SELECT incident_id, incident_type, initial_severity, incident_datetime, description
            FROM incidents
            WHERE hazard_id=? AND facility_id=? AND incident_id != ?
            ORDER BY incident_datetime DESC LIMIT 8
        """, (incident["hazard_id"], incident["facility_id"], incident_id))

    # Controls for this hazard + each one's most recent effectiveness rating.
    controls = []
    if incident["hazard_id"]:
        ctl_rows = _rows(conn, """SELECT control_id, control_name, control_type, status
                                   FROM controls WHERE hazard_id=? LIMIT 10""", (incident["hazard_id"],))
        for c in ctl_rows:
            latest = _one(conn, """SELECT effectiveness_rating, assessment_date FROM control_assessments
                                    WHERE control_id=? ORDER BY assessment_date DESC LIMIT 1""", (c["control_id"],))
            c["latest_effectiveness_rating"] = latest["effectiveness_rating"] if latest else "Not Assessed"
            c["latest_assessment_date"] = latest["assessment_date"] if latest else None
            controls.append(c)

    # Recent maintenance history for the involved equipment, if any — most recent 5.
    maintenance = []
    if incident["equipment_id"]:
        maintenance = _rows(conn, """
            SELECT maintenance_type, scheduled_date, actual_date, delay_days, status, description
            FROM maintenance_records WHERE equipment_id=? ORDER BY scheduled_date DESC LIMIT 5
        """, (incident["equipment_id"],))

    # Training relevant to the involved person, if any (employee OR contractor,
    # per the schema's mutual-exclusion constraint on incidents) — most recent 5.
    training = []
    person_col = "involved_employee_id" if incident["involved_employee_id"] else (
        "involved_contractor_id" if incident["involved_contractor_id"] else None)
    if person_col == "involved_employee_id":
        training = _rows(conn, """SELECT training_topic, training_date, expiry_date, status, result
                                   FROM training_records WHERE employee_id=? ORDER BY training_date DESC LIMIT 5""",
                          (incident["involved_employee_id"],))
    elif person_col == "involved_contractor_id":
        training = _rows(conn, """SELECT training_topic, training_date, expiry_date, status, result
                                   FROM training_records WHERE contractor_id=? ORDER BY training_date DESC LIMIT 5""",
                          (incident["involved_contractor_id"],))

    # Open risk-register entries for this hazard (existing risk assessments RISKON already has on file).
    open_risks = []
    if incident["hazard_id"]:
        open_risks = _rows(conn, """
            SELECT risk_register_id, title, current_score, current_level, status, last_reviewed_date
            FROM risk_register WHERE hazard_id=? AND status != 'Closed' LIMIT 5
        """, (incident["hazard_id"],))

    # Existing corrective/preventive actions tied to this hazard's controls or facility — open ones, most recent 8.
    existing_actions = []
    if incident["hazard_id"]:
        ctl_ids = [c["control_id"] for c in controls]
        placeholders = ",".join("?" for _ in ctl_ids) if ctl_ids else "NULL"
        existing_actions = _rows(conn, f"""
            SELECT action_id, action_type, description, status, due_date, reschedule_count
            FROM actions
            WHERE facility_id=? AND status != 'Completed'
              AND (related_control_id IN ({placeholders}) OR source_incident_id=?)
            ORDER BY due_date ASC LIMIT 8
        """, (incident["facility_id"], *ctl_ids, incident_id))

    return {
        "incident": {
            "incident_id": incident["incident_id"],
            "incident_type": incident["incident_type"],
            "initial_severity": incident["initial_severity"],
            "description": incident["description"],
            "location": incident["location"],
            "incident_datetime": incident["incident_datetime"],
            "injury_status": incident["injury_status"],
            "potential_consequence": incident["potential_consequence"],
            "immediate_action": incident["immediate_action"],
            "investigation_status": incident["investigation_status"],
            "root_cause_category": incident["root_cause_category"],
        },
        "facility": facility,
        "equipment": equipment,
        "hazard": hazard,
        "related_incidents": related_incidents,
        "controls": controls,
        "recent_maintenance": maintenance,
        "relevant_training": training,
        "open_risk_register_entries": open_risks,
        "existing_corrective_actions": existing_actions,
    }


def context_to_prompt_json(context: dict) -> str:
    return json.dumps(context, indent=2, default=str)
