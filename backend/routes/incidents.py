"""
GET/POST endpoints for incidents, plus the flagship AI workflow:

    POST /api/incidents/{id}/analyze

which is the real, wired-up version of the frontend's existing (disabled)
"Generate AI Analysis" button — see frontend/app.template.html's
renderCondensedPipeline() and RISKON_ARCHITECTURE.md "One complete AI request,
traced" for the full before/after.
"""
import json
from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.db import db_session
from backend.logging_config import get_logger
from backend.models.api_schemas import IncidentCreate, IncidentReviewDecision
from backend.services import context_builder, ids
from backend.services.ai import claude_service
from backend.services.ai.claude_service import (
    AIProviderNotConfiguredError,
    AIRequestFailedError,
    AIResponseInvalidError,
)

logger = get_logger("riskon.routes.incidents")
router = APIRouter()

_AI_FAILURE_STATUS = {
    "timeout": 504,
    "rate_limited": 429,
    "connection_error": 502,
    "api_error": 502,
    "unexpected": 502,
}


def _row_to_dict(row):
    return dict(row) if row else None


@router.get("/api/incidents")
def list_incidents(facility_id: str | None = None, limit: int = 200):
    with db_session() as conn:
        if facility_id:
            rows = conn.execute(
                "SELECT * FROM incidents WHERE facility_id=? ORDER BY incident_datetime DESC LIMIT ?",
                (facility_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM incidents ORDER BY incident_datetime DESC LIMIT ?", (limit,)
            ).fetchall()
        return {"incidents": [dict(r) for r in rows]}


@router.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Incident {incident_id} not found.")
        return dict(row)


@router.post("/api/incidents", status_code=201)
def create_incident(body: IncidentCreate):
    with db_session() as conn:
        fac = conn.execute("SELECT facility_id FROM facilities WHERE facility_id=?",
                            (body.facility_id,)).fetchone()
        if not fac:
            raise HTTPException(400, f"Unknown facility_id: {body.facility_id}")

        reporter_id = body.reporter_employee_id
        if reporter_id:
            if not conn.execute("SELECT 1 FROM employees WHERE employee_id=?", (reporter_id,)).fetchone():
                raise HTTPException(400, f"Unknown reporter_employee_id: {reporter_id}")
        else:
            row = conn.execute(
                "SELECT employee_id FROM employees WHERE facility_id=? AND is_active=1 LIMIT 1",
                (body.facility_id,),
            ).fetchone()
            if not row:
                raise HTTPException(400, "No active employee at this facility to attribute the report to; "
                                          "pass reporter_employee_id explicitly.")
            reporter_id = row["employee_id"]

        incident_id = ids.next_id(conn, "incidents", "incident_id", "INC")
        now = datetime.utcnow()
        occurred = body.date_occurred or now.date().isoformat()
        # The incidents table has no separate `title` column (see database/schema.sql
        # -- real incidents' "title" is always derived from hazard_category+equipment
        # by database/export_frontend_data.py, never stored as its own field). Rather
        # than silently discard the submitted title, it's folded into the one text
        # field the schema actually has, so it survives a round-trip through the
        # real database instead of only existing in the request body.
        description = f"{body.title}. {body.description}" + (f" (Location: {body.location})" if body.location else "")

        conn.execute("""
            INSERT INTO incidents (
                incident_id, facility_id, location, incident_datetime, incident_type, description,
                equipment_id, hazard_id, involved_employee_id, involved_contractor_id, injury_status,
                potential_consequence, initial_severity, immediate_action, investigation_status,
                root_cause_category, related_risk_register_id, reported_by_employee_id, reported_at,
                closure_status, closed_date
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            incident_id, body.facility_id, body.location or "Not specified",
            f"{occurred} 00:00:00", "Unsafe Condition", description,
            None, None, None, None, "None reported",
            "Not yet assessed", body.severity_reported, "Not yet documented", "Not Started",
            None, None, reporter_id, now.strftime("%Y-%m-%d %H:%M:%S"),
            "Open", None,
        ))
        row = conn.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
        logger.info("incident_created incident_id=%s facility_id=%s", incident_id, body.facility_id)
        return dict(row)


@router.post("/api/incidents/{incident_id}/analyze")
def analyze_incident(incident_id: str):
    """The flagship real AI workflow: build context from the real database,
    call Claude, validate the structured response, persist it, return it.
    Never fabricates a result if Claude is unreachable or unconfigured."""
    with db_session() as conn:
        try:
            context = context_builder.build_incident_context(conn, incident_id)
        except context_builder.IncidentNotFoundError:
            raise HTTPException(404, f"Incident {incident_id} not found.")

        try:
            analysis = claude_service.analyze_incident(context, incident_id)
        except AIProviderNotConfiguredError as e:
            raise HTTPException(503, str(e))
        except AIRequestFailedError as e:
            raise HTTPException(_AI_FAILURE_STATUS.get(e.reason, 502), str(e))
        except AIResponseInvalidError as e:
            raise HTTPException(502, str(e))

        analysis_id = ids.new_uuid_id("AIAN")
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO ai_incident_analyses (
                analysis_id, incident_id, created_at, model, prompt_version_id, context_json,
                response_json, summary, confidence, requires_human_review, human_review_status
            ) VALUES (?,?,?,?,?,?,?,?,?,1,'Pending')
        """, (
            analysis_id, incident_id, created_at, settings.anthropic_model, None,
            json.dumps(context, default=str), analysis.model_dump_json(),
            analysis.summary, analysis.confidence,
        ))

        return {
            "analysis_id": analysis_id,
            "incident_id": incident_id,
            "created_at": created_at,
            "model": settings.anthropic_model,
            "analysis": analysis.model_dump(),
            "human_review_status": "Pending",
        }


@router.get("/api/incidents/{incident_id}/analyses")
def list_incident_analyses(incident_id: str):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_incident_analyses WHERE incident_id=? ORDER BY created_at DESC",
            (incident_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["analysis"] = json.loads(d.pop("response_json"))
            d.pop("context_json", None)
            out.append(d)
        return {"analyses": out}


@router.post("/api/incidents/{incident_id}/review")
def review_incident(incident_id: str, body: IncidentReviewDecision):
    """Approve/Reject gate — mirrors the existing client-side handleApproval()
    logic, now genuinely persisted. On Approved, any `recommendations` from
    the incident's most recent AI analysis (if one exists) become real,
    tracked `actions` rows. This intentionally does NOT also compute a new
    risk_register/risk_assessments entry — doing that convincingly would mean
    re-deriving likelihood/severity/control-effectiveness/trend factors the
    same way risk_intelligence/engine.py does, which is out of scope for this
    endpoint; see RISKON_BACKEND_SETUP.md "Current limitations."""
    with db_session() as conn:
        incident = conn.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
        if not incident:
            raise HTTPException(404, f"Incident {incident_id} not found.")

        latest_analysis = conn.execute(
            "SELECT * FROM ai_incident_analyses WHERE incident_id=? ORDER BY created_at DESC LIMIT 1",
            (incident_id,),
        ).fetchone()

        created_actions = []
        if body.decision == "Approved" and latest_analysis:
            analysis = json.loads(latest_analysis["response_json"])
            owner_row = conn.execute(
                "SELECT employee_id FROM employees WHERE facility_id=? AND is_active=1 LIMIT 1",
                (incident["facility_id"],),
            ).fetchone()
            owner_id = owner_row["employee_id"] if owner_row else None
            today = date.today().isoformat()
            due = date.today().isoformat()
            for rec_text in analysis.get("recommendations", []):
                if not owner_id:
                    break
                action_id = ids.next_id(conn, "actions", "action_id", "ACT")
                conn.execute("""
                    INSERT INTO actions (
                        action_id, action_type, source_type, source_incident_id, related_control_id,
                        description, facility_id, owner_employee_id, created_date, original_due_date,
                        due_date, reschedule_count, status, completion_date, verification_method
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,'Open',NULL,?)
                """, (
                    action_id, "Corrective", "Incident", incident_id, None,
                    rec_text[:500], incident["facility_id"], owner_id, today, due, due,
                    "Follow-up inspection",
                ))
                created_actions.append(action_id)

            conn.execute(
                "UPDATE ai_incident_analyses SET human_review_status='Approved', "
                "reviewed_by_employee_id=?, reviewed_at=? WHERE analysis_id=?",
                (body.reviewer_employee_id, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                 latest_analysis["analysis_id"]),
            )
        elif latest_analysis:
            conn.execute(
                "UPDATE ai_incident_analyses SET human_review_status='Rejected', "
                "reviewed_by_employee_id=?, reviewed_at=? WHERE analysis_id=?",
                (body.reviewer_employee_id, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                 latest_analysis["analysis_id"]),
            )

        conn.execute(
            "UPDATE incidents SET investigation_status='Completed' WHERE incident_id=?",
            (incident_id,),
        )

        logger.info("incident_reviewed incident_id=%s decision=%s actions_created=%s",
                    incident_id, body.decision, len(created_actions))
        return {"incident_id": incident_id, "decision": body.decision, "actions_created": created_actions}
