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
from starlette.responses import Response

from backend.config import settings

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
