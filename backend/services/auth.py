"""
Real per-user auth: password hashing + server-side sessions. This is
deliberately a separate concern from two other things in this repo that
sound similar but aren't:
  - backend/middleware.py's DemoAccessMiddleware: one shared HTTP Basic Auth
    password for a whole public demo deployment, not per-user identity.
  - frontend/app.template.html's "Viewing as (demo)" role switcher: a
    100%-client-side demo affordance for showing all 4 RBAC roles instantly.
    It is untouched by this module and keeps working exactly as before.

Sessions are opaque random tokens looked up in the `sessions` table on every
request -- not a signed/stateless JWT-style cookie -- so logout can revoke
access immediately, server-side, with no signing secret to generate or
rotate.
"""
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Response

from backend.config import settings
from backend.db import db_session

SESSION_COOKIE_NAME = "riskon_session"
SESSION_TTL_HOURS = 24 * 14  # 14 days
_TS_FMT = "%Y-%m-%d %H:%M:%S"


def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        raise ValueError("Password must be 72 bytes or fewer.")
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    """False for a legacy row with no password set, or an unknown user --
    never calls bcrypt on None/empty (it would raise), and fails closed on
    any malformed/foreign hash rather than 500ing."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_session(conn: sqlite3.Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=SESSION_TTL_HOURS)
    conn.execute(
        "INSERT INTO sessions (session_token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (token, user_id, now.strftime(_TS_FMT), expires.strftime(_TS_FMT)),
    )
    return token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def _lookup_session(conn: sqlite3.Connection, token: str) -> dict | None:
    # Alias s.expires_at so it doesn't collide with u.* -- SELECT u.* keeps
    # exactly one copy of every app_users column (including its own
    # created_at), with the session's own expiry available under a distinct
    # name for the check below.
    row = conn.execute(
        "SELECT u.*, s.expires_at AS session_expires_at FROM sessions s "
        "JOIN app_users u ON u.user_id = s.user_id WHERE s.session_token = ?",
        (token,),
    ).fetchone()
    if not row:
        return None
    if row["session_expires_at"] < datetime.utcnow().strftime(_TS_FMT):
        return None
    user = dict(row)
    user.pop("session_expires_at", None)
    user.pop("password_hash", None)
    return user


def get_current_user_optional(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict | None:
    """FastAPI dependency: the logged-in user, or None. Never raises --
    routes/middleware that need to distinguish "not logged in" decide that
    for themselves."""
    if not session_token:
        return None
    with db_session() as conn:
        return _lookup_session(conn, session_token)


def require_current_user(user: dict | None = Depends(get_current_user_optional)) -> dict:
    """FastAPI dependency: the logged-in user, or a 401."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user
