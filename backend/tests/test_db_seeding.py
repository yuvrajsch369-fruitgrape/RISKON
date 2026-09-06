"""ensure_database_seeded() is what makes a fresh, empty persistent volume
usable on first deploy without an extra manual step — see its docstring in
backend/db.py."""
from backend.config import settings
from backend.db import ensure_database_seeded


def test_seeds_an_empty_target_path(tmp_path, monkeypatch):
    target = tmp_path / "fresh_volume" / "riskon.db"
    monkeypatch.setattr(settings, "database_path", target)

    assert not target.exists()
    ensure_database_seeded()
    assert target.exists()
    assert target.stat().st_size > 0


def test_never_overwrites_an_existing_target(tmp_path, monkeypatch):
    target = tmp_path / "riskon.db"
    target.write_bytes(b"already has real demo data, do not touch")
    monkeypatch.setattr(settings, "database_path", target)

    ensure_database_seeded()
    assert target.read_bytes() == b"already has real demo data, do not touch"


def test_noop_when_target_already_is_the_repo_seed(monkeypatch):
    from backend.config import ROOT
    monkeypatch.setattr(settings, "database_path", ROOT / "database" / "riskon.db")
    ensure_database_seeded()  # must not raise, must not touch the real seed file's mtime meaningfully
