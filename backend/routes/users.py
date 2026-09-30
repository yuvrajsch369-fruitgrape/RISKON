"""
Real per-user accounts for RISKON — see frontend/app.template.html's
renderSignup()/handleSignup()/handleLogin()/handleLogout(). Signing up
creates a genuine account (hashed password, real server-side session); this
is now real authentication in the sense that a password is checked and a
session can be revoked by logging out. It is NOT, by itself, an access-
control gate: unauthenticated requests are still allowed everywhere unless
AUTH_REQUIRED is explicitly enabled (see backend/middleware.py,
backend/services/auth.py) — by default RISKON's existing open, frictionless
demo experience (including the free "Viewing as (demo)" role switcher) is
completely unaffected by any of this.
"""
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response

from backend.db import db_session
from backend.logging_config import get_logger
from backend.models.api_schemas import UserLogin, UserSignup
from backend.services import auth, ids

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
def signup(body: UserSignup, response: Response):
    with db_session() as conn:
        dupe = conn.execute("SELECT 1 FROM app_users WHERE email = ? COLLATE NOCASE", (body.email,)).fetchone()
        if dupe:
            raise HTTPException(409, "An account with this email already exists.")
        try:
            password_hash = auth.hash_password(body.password)
        except ValueError as e:
            raise HTTPException(422, str(e))
        user_id = ids.next_id(conn, "app_users", "user_id", "USR")
        rbac_role = _rbac_role_for(body.occupation)
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO app_users (user_id, name, occupation, post, rbac_role, created_at, email, password_hash) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, body.name.strip(), body.occupation.strip(), body.post.strip(), rbac_role, created_at,
             body.email, password_hash),
        )
        token = auth.create_session(conn, user_id)
        logger.info("user_signed_up user_id=%s occupation=%s rbac_role=%s", user_id, body.occupation, rbac_role)
        result = {
            "user_id": user_id, "name": body.name.strip(), "occupation": body.occupation.strip(),
            "post": body.post.strip(), "rbac_role": rbac_role, "created_at": created_at, "email": body.email,
        }
    auth.set_session_cookie(response, token)
    return result


@router.post("/api/users/login")
def login(body: UserLogin, response: Response):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM app_users WHERE email = ? COLLATE NOCASE", (body.email,)).fetchone()
        # Deliberately generic message either way -- don't reveal whether the
        # email or the password was the wrong part.
        if not row or not auth.verify_password(body.password, row["password_hash"]):
            raise HTTPException(401, "Invalid email or password.")
        token = auth.create_session(conn, row["user_id"])
        user = dict(row)
        user.pop("password_hash", None)
    auth.set_session_cookie(response, token)
    logger.info("user_logged_in user_id=%s", user["user_id"])
    return user


@router.post("/api/users/logout", status_code=204)
def logout(response: Response, session_token: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE_NAME)):
    if session_token:
        with db_session() as conn:
            conn.execute("DELETE FROM sessions WHERE session_token = ?", (session_token,))
    auth.clear_session_cookie(response)


@router.get("/api/users/me")
def me(user: dict | None = Depends(auth.get_current_user_optional)):
    return {"user": user}


@router.get("/api/users/{user_id}")
def get_user(user_id: str):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM app_users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"User {user_id} not found.")
        user = dict(row)
        user.pop("password_hash", None)
        return user
