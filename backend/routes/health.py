"""GET /api/health — used by the setup docs, by automated checks, and by the
frontend's own bootstrap logic to decide whether a backend is even reachable
before it tries anything fancier."""
from fastapi import APIRouter

from backend.config import settings
from backend.db import check_health

router = APIRouter()


@router.get("/api/health")
def health():
    db = check_health()
    return {
        "status": "ok" if db["ok"] else "degraded",
        "database": db,
        **settings.as_public_dict(),
    }
