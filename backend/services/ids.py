"""ID generation matching the existing `PREFIX-NNNN` convention used
throughout database/generate_database.py and the frontend's own nextId()."""
import sqlite3
import uuid


def next_id(conn: sqlite3.Connection, table: str, id_column: str, prefix: str, width: int = 4) -> str:
    # Ordering by CAST(...AS INTEGER) rather than the raw TEXT column: a plain
    # `ORDER BY {id_column} DESC` sorts lexicographically, which only agrees
    # with numeric order while every id has the same zero-padded width. Past
    # 9999 (e.g. "INC-10000" vs "INC-9999"), TEXT order would pick "INC-9999"
    # as "highest" and hand out a duplicate id. Casting sidesteps that at any
    # row count instead of relying on width never being exceeded.
    row = conn.execute(
        f"SELECT {id_column} FROM {table} "
        f"ORDER BY CAST(SUBSTR({id_column}, LENGTH('{prefix}-') + 1) AS INTEGER) DESC LIMIT 1"
    ).fetchone()
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
