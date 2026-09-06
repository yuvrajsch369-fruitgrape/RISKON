"""Persists a real human decision on a Continuous Learning `recommendations`
row — the server-side counterpart to the frontend's existing (session-only)
handleRecommendationFeedback(). See docs/continuous-learning-engine.md."""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.db import db_session
from backend.logging_config import get_logger
from backend.models.api_schemas import RecommendationDecision

logger = get_logger("riskon.routes.recommendations")
router = APIRouter()


@router.get("/api/recommendations")
def list_recommendations(human_decision: str | None = None, limit: int = 200):
    with db_session() as conn:
        if human_decision:
            rows = conn.execute(
                "SELECT * FROM recommendations WHERE human_decision=? ORDER BY created_at DESC LIMIT ?",
                (human_decision, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM recommendations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return {"recommendations": [dict(r) for r in rows]}


@router.post("/api/recommendations/{recommendation_id}/decision")
def decide_recommendation(recommendation_id: str, body: RecommendationDecision):
    with db_session() as conn:
        rec = conn.execute("SELECT * FROM recommendations WHERE recommendation_id=?",
                            (recommendation_id,)).fetchone()
        if not rec:
            raise HTTPException(404, f"Recommendation {recommendation_id} not found.")
        if body.decision != "Approved" and not (body.reason or body.modification_text):
            raise HTTPException(400, "A reason (or modification_text) is required for anything but Approved.")

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        learning_signal = "Modification" if body.decision == "Modified" else "Not Yet Determined"
        conn.execute("""
            UPDATE recommendations
            SET human_decision=?, human_modification_text=?, decision_reason=?,
                decision_by_employee_id=?, decision_date=?, updated_at=?,
                learning_signal=?, evaluation_status='Not Evaluated'
            WHERE recommendation_id=?
        """, (
            body.decision,
            body.modification_text if body.decision == "Modified" else None,
            body.reason, body.decided_by_employee_id, now, now, learning_signal, recommendation_id,
        ))
        logger.info("recommendation_decided recommendation_id=%s decision=%s", recommendation_id, body.decision)
        row = conn.execute("SELECT * FROM recommendations WHERE recommendation_id=?",
                            (recommendation_id,)).fetchone()
        return dict(row)
