"""
A single, optional shared-password gate for a public demo deployment — NOT
real authentication (there is still no concept of an individual user account
anywhere in the backend; see backend/routes/users.py's module docstring).
This exists purely to keep a demo URL from being wide open to the entire
internet before real per-client accounts are built.

Disabled by default (empty DEMO_ACCESS_PASSWORD) so local development and
the existing test suite are completely unaffected. When enabled, it protects
EVERY route -- the frontend page at "/" included -- except GET /api/health,
which is deliberately left open so hosting-platform health checks (which
never send credentials) don't mistake a healthy app for a dead one.
"""
import base64
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.config import settings
from backend.db import db_session
from backend.services.auth import SESSION_COOKIE_NAME, _lookup_session

_UNPROTECTED_PATHS = {"/api/health"}


def _credentials_match(username: str, password: str) -> bool:
    # constant-time comparisons -- a naive `==` would leak timing information
    # about how many leading characters matched, which is exactly the kind
    # of small mistake this module exists to avoid making.
    return (
        secrets.compare_digest(username, settings.demo_access_username)
        and secrets.compare_digest(password, settings.demo_access_password)
    )


def _parse_basic_auth(header_value: str | None) -> tuple[str, str] | None:
    if not header_value or not header_value.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(header_value[len("Basic "):]).decode("utf-8")
    except Exception:
        return None
    username, sep, password = decoded.partition(":")
    return (username, password) if sep else None


class DemoAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.demo_gate_enabled or request.url.path in _UNPROTECTED_PATHS:
            return await call_next(request)

        creds = _parse_basic_auth(request.headers.get("Authorization"))
        if creds and _credentials_match(*creds):
            return await call_next(request)

        return Response(
            status_code=401,
            content="Authentication required.",
            headers={"WWW-Authenticate": 'Basic realm="RISKON Demo"'},
        )


# -----------------------------------------------------------------------------
# Real per-user login enforcement — a SEPARATE, independent gate from the one
# above. DemoAccessMiddleware is one shared password for the whole public
# demo; this is per-account, backed by backend/services/auth.py's real
# sessions. Off by default (AUTH_REQUIRED unset) so nothing about today's
# open, frictionless demo changes unless a real access-controlled pilot
# deployment explicitly turns it on. Both gates can run at once.
# -----------------------------------------------------------------------------
_AUTH_EXEMPT_PATHS = {"/api/health", "/api/users/signup", "/api/users/login", "/api/users/logout", "/api/users/me"}
# Only these exact paths stay reachable when enforcement is on: signup/login/
# logout are how you'd ever get (or end) a session in the first place, and
# GET /api/users/me must be answerable with NO session (it's exactly how the
# frontend learns "you are not logged in"). Every other /api/* route --
# GET /api/users/{id} included -- requires a real session.
#
# Deliberately exact-path, not prefix, matching. Confirmed real gap with the
# previous "/api/users/" PREFIX exemption: it also covered GET
# /api/users/{user_id}, an arbitrary-id lookup with no legitimate pre-auth
# use case (the frontend never calls it) -- meaning a real locked-down
# deployment with AUTH_REQUIRED on still let anyone enumerate every real
# user's name/email/role/facility with zero session, just by incrementing
# the (sequential, predictable) USR-nnnn id. The frontend itself ("/") is
# never blocked by path (see the check below) -- an unauthenticated visitor
# must still be able to load the page in order to see a real login form,
# rather than getting a dead, unstyled 401 response.


class AuthRequiredMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.auth_required:
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/") or path in _AUTH_EXEMPT_PATHS:
            return await call_next(request)

        token = request.cookies.get(SESSION_COOKIE_NAME)
        user = None
        if token:
            with db_session() as conn:
                user = _lookup_session(conn, token)
        if user is None:
            return JSONResponse(
                status_code=401,
                content={"error": "authentication_required", "message": "Sign in required."},
            )
        return await call_next(request)


# -----------------------------------------------------------------------------
# Request body size cap. Confirmed by direct test: with no limit at all, a
# single request could carry an arbitrarily large body -- Pydantic's
# max_length constraints (e.g. IncidentCreate.description) only reject AFTER
# FastAPI has already buffered and JSON-parsed the whole thing into memory, so
# they're not actually a defense against a large-body resource-exhaustion
# attempt, just a correctness check on an already-paid-for allocation. 20
# concurrent 20MB bodies didn't visibly strain this dev machine, but nothing
# stopped them from being much bigger, and production hosts (e.g. Railway's
# smaller tiers) have far less headroom. Checking Content-Length and
# rejecting BEFORE any body read/parse closes that -- the real legitimate
# max across every request body in this API is a few KB (IncidentCreate's
# largest field, description, caps at 5000 chars).
# -----------------------------------------------------------------------------
class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = None
            if size is not None and size > settings.max_request_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"error": "payload_too_large",
                             "message": "Request body exceeds the maximum allowed size."},
                )
        return await call_next(request)
