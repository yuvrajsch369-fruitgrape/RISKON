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


def next_id_with_retry(conn: sqlite3.Connection, table: str, id_column: str, prefix: str, insert_fn,
                        width: int = 4, max_attempts: int = 8) -> str:
    """Computes next_id() and calls insert_fn(candidate_id) to perform the
    actual INSERT, retrying with a freshly computed id on a UNIQUE
    constraint collision.

    next_id() alone has a real race: two concurrent requests can both read
    the same "current highest" row before either has committed, compute the
    same candidate, and then both attempt to INSERT it -- confirmed under
    load (25 concurrent incident creates produced 21 `IntegrityError: UNIQUE
    constraint failed` failures). The second writer's INSERT only runs once
    it has the write lock (i.e. after the first has committed), so re-reading
    next_id() at that point sees the first writer's new row and produces a
    correct, non-colliding id -- insert_fn must let sqlite3.IntegrityError
    propagate (never swallow it) for this retry to have something to catch.

    Only retries when the collision is actually on `{table}.{id_column}`.
    insert_fn can also legitimately raise IntegrityError for an unrelated
    reason (e.g. users.py's email UNIQUE index on a duplicate signup) --
    retrying THAT with a new id would silently burn every attempt on an
    error a new id can never fix, surfacing as a confusing 500 instead of
    the real 409. SQLite's error message names the failing column, so this
    checks for it rather than assuming every IntegrityError here is "our" id
    race.
    """
    collision_marker = f"{table}.{id_column}"
    last_exc = None
    for _ in range(max_attempts):
        candidate = next_id(conn, table, id_column, prefix, width=width)
        try:
            insert_fn(candidate)
            return candidate
        except sqlite3.IntegrityError as e:
            if collision_marker not in str(e):
                raise
            last_exc = e
            continue
    raise last_exc
