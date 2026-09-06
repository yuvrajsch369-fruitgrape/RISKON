"""ID generation matching the existing `PREFIX-NNNN` convention used
throughout database/generate_database.py and the frontend's own nextId()."""
import sqlite3
import uuid


def next_id(conn: sqlite3.Connection, table: str, id_column: str, prefix: str, width: int = 4) -> str:
    row = conn.execute(f"SELECT {id_column} FROM {table} ORDER BY {id_column} DESC LIMIT 1").fetchone()
    if not row or not row[0]:
        n = 1
    else:
        try:
            n = int(str(row[0]).split("-")[-1]) + 1
        except ValueError:
            n = 1
    return f"{prefix}-{str(n).zfill(width)}"


def new_uuid_id(prefix: str) -> str:
    """For tables with no natural sequential convention yet (ai_incident_analyses)."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
