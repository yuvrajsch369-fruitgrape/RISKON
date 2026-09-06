"""
SQLite access for the RISKON backend — the SAME database file every offline
Python script in this repo already uses (database/riskon.db). Plain
`sqlite3`, no ORM: the dataset and query patterns are simple enough that an
ORM would be extra machinery for no real benefit at this scale (see
RISKON_ARCHITECTURE.md, "Why no ORM").

`ensure_schema()` is idempotent and only ever creates the Part-3/Part-4
tables (`ai_incident_analyses`, `app_users`) this backend introduces — it
never touches or recreates any Part 1/2 table, and never regenerates
synthetic seed data.
"""
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from backend.config import ROOT, settings

# The database this repo ships with, seeded once by database/generate_database.py
# + learning_engine/generate_learning_data.py and committed to git (it's the
# synthetic Rex Industrial Manufacturing demo dataset, not real or sensitive
# data — see RISKON_DEPLOYMENT_RUNBOOK.md Phase 3 for why committing it is
# the right call here). On a host with a persistent volume mounted at a
# DIFFERENT path than the git checkout (Railway/Fly/Render volumes all work
# this way), the volume starts out empty on first deploy — ensure_database_
# seeded() copies this repo copy there once, so first boot doesn't require
# an extra manual step, while every real write after that (new incidents,
# signups, AI analyses) lands on the persistent copy and survives redeploys.
_REPO_SEED_DB = ROOT / "database" / "riskon.db"

_PART3_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_incident_analyses (
    analysis_id           TEXT PRIMARY KEY,
    incident_id             TEXT NOT NULL REFERENCES incidents(incident_id),
    created_at               TEXT NOT NULL,
    model                     TEXT NOT NULL,
    prompt_version_id          TEXT REFERENCES ai_versions(version_id),
    context_json                TEXT NOT NULL,
    response_json                TEXT NOT NULL,
    summary                       TEXT NOT NULL,
    confidence                     REAL,
    requires_human_review           INTEGER NOT NULL DEFAULT 1 CHECK (requires_human_review IN (0,1)),
    human_review_status              TEXT NOT NULL DEFAULT 'Pending' CHECK (human_review_status IN
                                        ('Pending','Approved','Rejected')),
    reviewed_by_employee_id            TEXT REFERENCES employees(employee_id),
    reviewed_at                          TEXT
);
CREATE INDEX IF NOT EXISTS idx_ai_incident_analyses_incident ON ai_incident_analyses(incident_id);
"""

_PART4_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_users (
    user_id      TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    occupation      TEXT NOT NULL,
    post             TEXT NOT NULL,
    rbac_role         TEXT NOT NULL CHECK (rbac_role IN ('employee','hse_manager','plant_manager','executive')),
    created_at          TEXT NOT NULL
);
"""


class DatabaseNotFoundError(RuntimeError):
    pass


def ensure_database_seeded() -> None:
    """If DATABASE_PATH doesn't exist yet but the repo's own seed copy does
    (and they're not the same file), copy the seed there. A no-op on a normal
    local dev setup, where DATABASE_PATH already points straight at the repo
    copy. Never overwrites an existing file at DATABASE_PATH — a persistent
    volume that already has real data in it is left alone."""
    target = Path(settings.database_path)
    if target.exists():
        return
    if not _REPO_SEED_DB.exists():
        return  # nothing to seed from; get_connection() will raise its own clear error
    if target.resolve() == _REPO_SEED_DB.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_REPO_SEED_DB, target)


def get_connection() -> sqlite3.Connection:
    db_path = Path(settings.database_path)
    if not db_path.exists():
        raise DatabaseNotFoundError(
            f"database not found at {db_path}. Run `python3 database/generate_database.py` "
            f"(and `python3 learning_engine/generate_learning_data.py`) first to build it."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    """`with db_session() as conn:` — commits on clean exit, rolls back and
    re-raises on any exception, always closes the connection."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_schema() -> None:
    """Creates the Part-3/Part-4 tables if missing. Safe to call every startup."""
    conn = get_connection()
    try:
        conn.executescript(_PART3_SCHEMA)
        conn.executescript(_PART4_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def check_health() -> dict:
    """Used by GET /api/health — a real query, not just 'file exists'."""
    try:
        conn = get_connection()
        try:
            n = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            return {"ok": True, "incident_count": n}
        finally:
            conn.close()
    except Exception as e:
        return {"ok": False, "error": str(e)}
