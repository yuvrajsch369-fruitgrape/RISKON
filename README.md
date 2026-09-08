# RISKON

An AI-powered industrial risk intelligence platform — incident reporting, AI-assisted investigation, risk
detection, corrective actions, and a continuous-learning loop, all backed by a real FastAPI backend and a
real database. RISKON comes pre-loaded with a complete, realistic demo environment modeled on Rex
Industrial Manufacturing, a manufacturer with 7 facilities across 5 countries (United States, United
Kingdom, Germany, India, and Australia), so every screen, workflow, and analytics view works immediately,
with no setup. Point it at a real organization's operational data and the same engine runs unchanged — the
demo dataset exists to show the product working end-to-end on day one, not to limit it.

## Running it

```bash
pip3 install -r backend/requirements.txt
python3 -m backend.main
```

That's it for local use — every setting in `backend/config.py` has a working default. The one thing worth
setting is `ANTHROPIC_API_KEY` (in a `.env` file at the repo root, or as a real environment variable), which
turns on live AI-assisted investigation; without it, RISKON runs normally and simply shows AI features as
not configured instead of erroring. The server listens on `$PORT` if set (what Railway, Render, Fly.io, and
similar platforms provide automatically) or `8743` otherwise.

## What's included

Incident reporting, AI-assisted investigation with an explicit fact/hypothesis/recommendation trail, a
Risk Register, a company-wide Risk Intelligence view, a Risk Graph (a real, traced equipment → maintenance
→ incidents → hazards → controls chain), a global facility map, corrective actions, an audit trail, a
Continuous Learning loop with a controlled human-approval pipeline before any change ships, a Command
Center for leadership, Reports, an Administration screen, a landing page, and a guided demo mode that walks
through the whole story in about 5 minutes.

---

## Project layout, in one paragraph

`frontend/` is one pre-built HTML/JS file (no separate build step). `backend/` is the FastAPI server that
serves that file and answers every `/api/...` request, including the one that calls Claude.
`database/riskon.db` is a real SQLite file, pre-loaded with a realistic, fully-populated demo dataset built
on the exact schema a live deployment would use — ready to be replaced with a real client's operational
data without touching a line of code. `risk_intelligence/` and `learning_engine/` are the two deterministic
analytics engines (pattern detection and outcome-learning) the backend calls into.
