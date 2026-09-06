import shutil
import sqlite3
from pathlib import Path

import pytest

from backend.config import ROOT, settings


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A throwaway COPY of the real database/riskon.db, so write-path tests
    (create incident, complete action, review, ...) never touch the actual
    seed dataset this repo ships with. Patches `settings.database_path` for
    the duration of the test only."""
    src = ROOT / "database" / "riskon.db"
    dst = tmp_path / "riskon_test.db"
    shutil.copyfile(src, dst)
    monkeypatch.setattr(settings, "database_path", dst)
    yield dst


@pytest.fixture
def real_db_readonly():
    """The real database, for read-only assertions only (never write here)."""
    conn = sqlite3.connect(ROOT / "database" / "riskon.db")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def app_client(temp_db):
    from fastapi.testclient import TestClient

    from backend.db import ensure_schema
    from backend.main import app

    ensure_schema()
    with TestClient(app) as c:
        yield c
