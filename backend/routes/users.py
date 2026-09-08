"""
Signup profiles for RISKON's dedicated signup page — see frontend/
app.template.html's renderSignup()/handleSignup(). NOT authentication: there
is no password, no session token, and nothing anywhere checks who is "logged
in" before serving a request. A signup only ever creates a profile the
browser remembers (localStorage) and displays in the sidebar's lower-left
corner — this is deliberately not part of the app's real security posture.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.db import db_session
from backend.logging_config import get_logger
from backend.models.api_schemas import UserSignup
from backend.services import ids

logger = get_logger("riskon.routes.users")
router = APIRouter()

# Maps a signup occupation to one of the 4 existing RBAC demo roles (see
# frontend's ROLES object) so a fresh signup lands on a sensible default
# permission level instead of always defaulting to Employee. This is a
# display/demo convenience, same spirit as the rest of RISKON's client-side
# RBAC — not a real access-control decision. Anything not listed here
# (most operational job titles) defaults to 'employee'.
OCCUPATION_TO_RBAC_ROLE = {
    "Plant Manager": "plant_manager",
    "Safety Manager": "hse_manager",
    "EHS Coordinator": "hse_manager",
    "Environmental Compliance Officer": "hse_manager",
    "Executive": "executive",
}


def _rbac_role_for(occupation: str) -> str:
    return OCCUPATION_TO_RBAC_ROLE.get(occupation.strip(), "employee")


@router.post("/api/users/signup", status_code=201)
def signup(body: UserSignup):
    with db_session() as conn:
        user_id = ids.next_id(conn, "app_users", "user_id", "USR")
        rbac_role = _rbac_role_for(body.occupation)
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO app_users (user_id, name, occupation, post, rbac_role, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, body.name.strip(), body.occupation.strip(), body.post.strip(), rbac_role, created_at),
        )
        logger.info("user_signed_up user_id=%s occupation=%s rbac_role=%s", user_id, body.occupation, rbac_role)
        return {
            "user_id": user_id, "name": body.name.strip(), "occupation": body.occupation.strip(),
            "post": body.post.strip(), "rbac_role": rbac_role, "created_at": created_at,
        }


@router.get("/api/users/{user_id}")
def get_user(user_id: str):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM app_users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"User {user_id} not found.")
        return dict(row)
