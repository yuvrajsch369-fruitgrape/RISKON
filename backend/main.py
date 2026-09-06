"""
RISKON backend entry point.

Run from the repo root:
    uvicorn backend.main:app --host 0.0.0.0 --port 8743

Serves TWO things from one process, on one origin (no CORS needed for the
app's own frontend, keeping the setup as simple as `.env` + one command):
  1. The API, under /api/*  (see backend/routes/*.py)
  2. The existing static frontend (frontend/riskon.html) at /

This does not replace frontend/riskon.html as a standalone file — opening
that file directly (or via `python3 -m http.server` per .claude/launch.json's
`riskon-static` entry) still works exactly as before, with the frontend
falling back to its embedded window.RISKON_DATA when no backend is reachable.
Running it through this backend instead additionally makes /api/bootstrap,
the AI analysis workflow, and real persistence available. See
RISKON_ARCHITECTURE.md.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.config import ROOT, settings
from backend.db import DatabaseNotFoundError, ensure_database_seeded, ensure_schema
from backend.logging_config import configure_logging, get_logger
from backend.middleware import DemoAccessMiddleware
from backend.routes import actions, bootstrap, health, incidents, recommendations, users

configure_logging()
logger = get_logger("riskon.main")

FRONTEND_FILE = ROOT / "frontend" / "riskon.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_database_seeded()
        ensure_schema()
        logger.info("Database schema OK (%s). AI configured: %s. Demo gate: %s",
                    settings.database_path, settings.ai_configured, settings.demo_gate_enabled)
    except DatabaseNotFoundError as e:
        # Deliberately does not crash the process — GET /api/health will keep
        # reporting the real problem, and every DB-touching route raises a
        # clean 503 rather than a raw traceback (see the exception handler
        # below), consistent with "RISKON must not completely break."
        logger.error("Database not ready: %s", e)
    yield


app = FastAPI(title="RISKON API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Runs before CORS in request order (Starlette applies middleware in
# reverse-added order) -- doesn't matter here since the demo gate only ever
# short-circuits with a 401, never proceeds to a route that CORS would need
# to have already touched.
app.add_middleware(DemoAccessMiddleware)


@app.exception_handler(DatabaseNotFoundError)
def db_not_found_handler(request: Request, exc: DatabaseNotFoundError):
    return JSONResponse(status_code=503, content={"error": "database_not_ready", "message": str(exc)})


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    # Normalizes every raise HTTPException(...) in the route layer to the
    # same {"error", "message"} shape as the two handlers above and below,
    # so the frontend (and any other client) only ever has one error shape
    # to parse, regardless of which layer raised it.
    return JSONResponse(status_code=exc.status_code, content={"error": "request_failed", "message": exc.detail})


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception):
    # Last-resort safety net: never let a raw stack trace or exception detail
    # reach a client. The real detail is logged server-side only.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal_error",
                                                    "message": "An unexpected error occurred. Please try again."})


app.include_router(health.router)
app.include_router(bootstrap.router)
app.include_router(incidents.router)
app.include_router(recommendations.router)
app.include_router(actions.router)
app.include_router(users.router)


@app.get("/")
def serve_frontend():
    if FRONTEND_FILE.exists():
        return FileResponse(FRONTEND_FILE)
    return JSONResponse(
        status_code=500,
        content={"error": "frontend_not_built",
                 "message": "frontend/riskon.html does not exist yet — run scripts/build_frontend.py."},
    )


if __name__ == "__main__":
    # Convenience entrypoint (`python3 -m backend.main` / `python3 backend/main.py`)
    # that actually exercises settings.host/settings.port -- the Procfile and
    # Dockerfile's `uvicorn backend.main:app --port ${PORT:-8743}` both set the
    # port at the shell level instead and are the recommended way to run this
    # in production; this path exists so the same PORT-then-RISKON_PORT-then-8743 fallback in
    # backend/config.py is honored no matter how the process gets started.
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
