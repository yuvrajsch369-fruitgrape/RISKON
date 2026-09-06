"""GET /api/bootstrap — the SAME data shape as synthetic-data/frontend-data.json
(and therefore the same shape already baked into frontend/riskon.html as
window.RISKON_DATA), computed LIVE from the real database via the exact same
`build_frontend_data()` function the offline build script calls. This is what
makes the static build and the live backend one coherent system rather than
two data sources that can drift apart — see database/export_frontend_data.py
and RISKON_ARCHITECTURE.md."""
from fastapi import APIRouter

from database.export_frontend_data import build_frontend_data
from backend.config import settings
from backend.db import db_session

router = APIRouter()


@router.get("/api/bootstrap")
def bootstrap():
    with db_session() as conn:
        # db_path passed explicitly (rather than relying on build_frontend_data's
        # own default) so RiskIntelligenceEngine/LearningEngine — which open
        # their own internal connections — always point at the SAME file `conn`
        # above is already open against, even if DATABASE_PATH was overridden.
        return build_frontend_data(conn, db_path=settings.database_path)
