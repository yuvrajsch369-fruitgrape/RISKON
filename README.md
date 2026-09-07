# RISKON

An AI-powered industrial risk intelligence prototype for **Rex Industrial Manufacturing** (a fictional,
three-plant manufacturer) — incident reporting, AI-assisted investigation, risk detection, corrective
actions, and a continuous-learning loop, all backed by a real FastAPI backend and a real database.

Full technical detail lives in [`RISKON_ARCHITECTURE.md`](RISKON_ARCHITECTURE.md) and
[`RISKON_BACKEND_SETUP.md`](RISKON_BACKEND_SETUP.md).

---

## Project layout, in one paragraph

`frontend/` is one pre-built HTML/JS file (no separate build step). `backend/` is the FastAPI server that
serves that file and answers every `/api/...` request, including the one that calls Claude.
`database/riskon.db` is a real SQLite file, seeded with realistic-but-entirely-synthetic data — nothing
in it describes a real company. `risk_intelligence/` and `learning_engine/` are the two deterministic
analytics engines (pattern detection and outcome-learning) the backend calls into.
# RISKON.Prototype
