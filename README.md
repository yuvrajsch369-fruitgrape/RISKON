# RISKON

An AI-powered industrial risk intelligence prototype for **Rex Industrial Manufacturing** (a fictional,
three-plant manufacturer) — incident reporting, AI-assisted investigation, risk detection, corrective
actions, and a continuous-learning loop, all backed by a real FastAPI backend and a real database.

Full technical detail lives in [`RISKON_ARCHITECTURE.md`](RISKON_ARCHITECTURE.md),
[`RISKON_BACKEND_SETUP.md`](RISKON_BACKEND_SETUP.md), and
[`RISKON_DEPLOYMENT_RUNBOOK.md`](RISKON_DEPLOYMENT_RUNBOOK.md) — this file is just the fastest path to
running it.

---

## Quick Start

```bash
# 1. Install dependencies
pip3 install -r backend/requirements.txt

# 2. Set up your environment file
cp .env.example .env      # skip this if .env already exists
# open .env and paste your key on this line:
#   ANTHROPIC_API_KEY=sk-ant-...

# 3. Run it
uvicorn backend.main:app --reload --port 8743
```

Then open **http://localhost:8743/** in a browser. That's it — RISKON serves its own frontend and API from
that one address.

- **No key yet?** RISKON still runs and every screen still works — AI analysis just shows an honest
  "AI provider not configured" message instead of pretending to work. Paste a key into `.env` and restart
  any time to turn it on.
- **Get a key** at [console.anthropic.com](https://console.anthropic.com/).
- **Never commit your real `.env`.** It's already excluded by `.gitignore` — only the blank
  `.env.example` template is meant to be shared or pushed to GitHub.

## Running the tests

```bash
python3 -m pytest backend/tests/ -v
```

## Project layout, in one paragraph

`frontend/` is one pre-built HTML/JS file (no separate build step). `backend/` is the FastAPI server that
serves that file and answers every `/api/...` request, including the one that calls Claude.
`database/riskon.db` is a real SQLite file, seeded with realistic-but-entirely-synthetic data — nothing
in it describes a real company. `risk_intelligence/` and `learning_engine/` are the two deterministic
analytics engines (pattern detection and outcome-learning) the backend calls into.

## Pushing this to GitHub

```bash
git remote add origin <your-empty-GitHub-repo-URL>
git push -u origin main
```

(A local git repository and first commit are already set up — see below.)
