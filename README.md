# RISKON

An AI-powered industrial risk intelligence platform — incident reporting, AI-assisted investigation, risk
detection, corrective actions, and a continuous-learning loop, all backed by a real FastAPI backend and a
real database. RISKON comes pre-loaded with a complete, realistic demo environment modeled on Rex
Industrial Manufacturing, a three-plant manufacturing operation, so every screen, workflow, and analytics
view works immediately, with no setup. Point it at a real organization's operational data and the same
engine runs unchanged — the demo dataset exists to show the product working end-to-end on day one, not to
limit it.

Full technical detail lives in [`RISKON_ARCHITECTURE.md`](RISKON_ARCHITECTURE.md) and
[`RISKON_BACKEND_SETUP.md`](RISKON_BACKEND_SETUP.md).

---

## Project layout, in one paragraph

`frontend/` is one pre-built HTML/JS file (no separate build step). `backend/` is the FastAPI server that
serves that file and answers every `/api/...` request, including the one that calls Claude.
`database/riskon.db` is a real SQLite file, pre-loaded with a realistic, dataset built
on the exact schema a live deployment would use, ready to be replaced with a real client's operational
data without touching a line of code. `risk_intelligence/` and `learning_engine/` are the two deterministic
analytics engines (pattern detection and outcome-learning) the backend calls into.
