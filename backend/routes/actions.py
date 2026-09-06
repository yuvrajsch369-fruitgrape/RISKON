"""Real persistence for corrective/preventive actions — including a
"mark complete" capability that has no equivalent in the current static
frontend at all (today an action's status only ever changes via the
synthetic seed data)."""
from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from backend.db import db_session
from backend.logging_config import get_logger
from backend.models.api_schemas import ActionComplete

logger = get_logger("riskon.routes.actions")
router = APIRouter()


@router.get("/api/actions")
def list_actions(status: str | None = None, facility_id: str | None = None, limit: int = 300):
    with db_session() as conn:
        clauses, params = [], []
        if status:
            clauses.append("status=?")
            params.append(status)
        if facility_id:
            clauses.append("facility_id=?")
            params.append(facility_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(f"SELECT * FROM actions {where} ORDER BY due_date ASC LIMIT ?",
                             (*params, limit)).fetchall()
        return {"actions": [dict(r) for r in rows]}


@router.post("/api/actions/{action_id}/complete")
def complete_action(action_id: str, body: ActionComplete):
    with db_session() as conn:
        action = conn.execute("SELECT * FROM actions WHERE action_id=?", (action_id,)).fetchone()
        if not action:
            raise HTTPException(404, f"Action {action_id} not found.")
        if action["status"] == "Completed":
            raise HTTPException(400, f"Action {action_id} is already Completed.")

        completion_date = body.completion_date or date.today().isoformat()
        verification = body.verification_method or action["verification_method"]
        conn.execute(
            "UPDATE actions SET status='Completed', completion_date=?, verification_method=? WHERE action_id=?",
            (completion_date, verification, action_id),
        )
        logger.info("action_completed action_id=%s completion_date=%s", action_id, completion_date)
        row = conn.execute("SELECT * FROM actions WHERE action_id=?", (action_id,)).fetchone()
        return dict(row)
