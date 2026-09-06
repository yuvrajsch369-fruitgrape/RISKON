# RISKON Backend Setup

Practical guide to running, configuring, and testing the RISKON backend. For the architectural reasoning
behind these choices, see [RISKON_ARCHITECTURE.md](RISKON_ARCHITECTURE.md).

---

## 1. Backend architecture (summary)

Python + FastAPI, talking to the existing SQLite database (`database/riskon.db`) and, when configured, to
the Anthropic Claude API. One process serves both the API (`/api/*`) and the existing static frontend
(`/`) — no separate frontend server, no CORS configuration needed for normal use. See
RISKON_ARCHITECTURE.md §1-§2 for the full diagram and reasoning.

---

## 2. Folder structure

```
backend/
├── main.py                     FastAPI app: routes, static frontend serving, error handling, startup
├── config.py                   ALL environment variables read here, nowhere else
├── db.py                       sqlite3 connection helper + schema-ensure (Part 3 table only)
├── logging_config.py           structured logging, incl. log_ai_request() (never logs the API key)
├── requirements.txt
├── models/
│   ├── ai_schemas.py            IncidentAIAnalysis (the structured AI response contract)
│   └── api_schemas.py           request bodies for the CRUD-ish endpoints
├── services/
│   ├── context_builder.py       incident -> structured RISKON context (real, bounded DB queries)
│   ├── ids.py                    PREFIX-NNNN id generation, matching the existing convention
│   └── ai/
│       └── claude_service.py     THE ONE place that calls Claude — see RISKON_ARCHITECTURE.md §2
├── routes/
│   ├── health.py                 GET /api/health
│   ├── bootstrap.py               GET /api/bootstrap
│   ├── incidents.py                incidents CRUD + the AI analyze/review workflow
│   ├── recommendations.py           Continuous Learning feedback persistence
│   └── actions.py                   corrective-action completion
└── tests/                         pytest suite — see §9
```

Nothing outside `backend/` was restructured. `database/export_frontend_data.py` gained one refactor (its
top-level script logic became an importable `build_frontend_data()` function, verified byte-identical
output before/after) so `backend/routes/bootstrap.py` could reuse it — see RISKON_ARCHITECTURE.md §3.

---

## 3. How the backend works

Request lifecycle for any route: FastAPI receives the request → the route handler opens a `sqlite3`
connection via `backend/db.py`'s `db_session()` context manager (commits on success, rolls back and
re-raises on any exception, always closes) → runs plain parameterized SQL → returns a plain dict (FastAPI
serializes it to JSON automatically). For the AI workflow specifically, see RISKON_ARCHITECTURE.md §4.

Startup (`backend/main.py`'s `lifespan`): ensures the one new Part-3 table
(`ai_incident_analyses`) exists — idempotent, safe to run against the existing database every time, never
touches or regenerates any other table.

---

## 4. Database connection

The backend reads `DATABASE_PATH` (default `./database/riskon.db`) — the SAME file
`database/generate_database.py`, `risk_intelligence/engine.py`, and `learning_engine/engine.py` already
use. No second database was introduced. If the file doesn't exist yet, every DB-touching route returns a
clean `503 database_not_ready` instead of crashing — build it first:

```bash
python3 database/generate_database.py
python3 learning_engine/generate_learning_data.py
```

---

## 5. Claude integration

`backend/services/ai/claude_service.py` is the only file that imports the `anthropic` package or
constructs a prompt for Claude. It exposes exactly one function routes call: `analyze_incident(context,
incident_id)`. See RISKON_ARCHITECTURE.md §2 for why this is one call rather than the 13-stage design in
`engine/pipeline.ts` (which still exists, unexecuted, as a documented future option).

---

## 6. Environment variables

All defined in `.env.example` (copy to `.env`); every one has a safe default except the API key.

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(empty)* | Your Claude API key. Empty = AI features disabled, everything else works. |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Centralized model name — change here, not in code. |
| `ANTHROPIC_TIMEOUT_SECONDS` | `30` | Max time to wait for one Claude response. |
| `ANTHROPIC_MAX_TOKENS` | `1536` | Max tokens requested per analysis. |
| `DATABASE_PATH` | `./database/riskon.db` | Only change if you've moved the database file. |
| `RISKON_HOST` / `RISKON_PORT` | `0.0.0.0` / `8743` | What `uvicorn` binds to. |
| `CORS_ORIGINS` | `*` | Only matters if you serve the frontend from somewhere other than this backend. |
| `LOG_LEVEL` | `INFO` | Python logging level. |
| `RISKON_ENV` | `development` | Cosmetic — shown in `/api/health`. |

`.env` is read from the repo root by `backend/config.py` via `python-dotenv`. It is git-ignored (see
`.gitignore`) — never commit it. `.env.example` contains placeholders only.

---

## 7. How to add your Claude API key

```bash
cp .env.example .env     # if you haven't already — a blank .env is also already checked in for you
# open .env in any editor and set:
ANTHROPIC_API_KEY=sk-ant-...your real key...
```

That's it — no source file needs editing. Restart the backend (§8) and `GET /api/health` will show
`"ai_configured": true`.

---

## 8. How to start the application

```bash
pip3 install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8743
```

Then open `http://localhost:8743/` — this serves the exact same frontend as before, now backed by the live
API. (The old `python3 -m http.server --directory frontend` path — `.claude/launch.json`'s `riskon-static`
entry, now on port 8744 — still works too, unchanged, for offline/no-backend use.)

If the database doesn't exist yet, build it first (§4). If `frontend/riskon.html` doesn't exist yet:
`python3 scripts/build_frontend.py`.

---

## 9. How to test AI

**Without a real API key** (always possible, no cost):
```bash
pip3 install -r backend/requirements.txt
python3 -m pytest backend/tests/ -v
```
27 tests, all passing as of this writing. They verify, with a MOCKED Anthropic client: environment-variable
detection, request construction, JSON response parsing (including prose-wrapped JSON), Pydantic schema
validation (including that the model cannot set `requires_human_review: false`), and every typed failure
path (timeout, rate limit, connection error, invalid JSON, schema violation) — see
`backend/tests/test_claude_service.py`'s module docstring for the exact scope and its limits. Also verified
via a real running server with a placeholder key: a genuine HTTPS call to `https://api.anthropic.com/v1/
messages` that fails with a real 401, caught and mapped to a safe message (see the log line reproduced in
§18).

**With a real API key**: set `ANTHROPIC_API_KEY` (§7), restart, then either use the "Generate AI Analysis"
button on any incident in AI Investigation, or:
```bash
curl -X POST http://localhost:8743/api/incidents/INC-0001/analyze
```
This is the one thing that could NOT be verified during this build (no key was available) — everything
up to and including the real network call was verified; only a genuinely successful Claude response was
not observed. No successful response was fabricated or claimed.

---

## 10. API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | DB connectivity + whether AI is configured (never the key itself) |
| GET | `/api/bootstrap` | Full live dataset, same shape as the static build (see RISKON_ARCHITECTURE.md §3) |
| GET | `/api/incidents` | List incidents (`facility_id`, `limit` query params) |
| GET | `/api/incidents/{id}` | One incident |
| POST | `/api/incidents` | Create an incident (real DB insert) |
| POST | `/api/incidents/{id}/analyze` | **The flagship AI workflow** — see RISKON_ARCHITECTURE.md §4 |
| GET | `/api/incidents/{id}/analyses` | History of AI analyses for one incident |
| POST | `/api/incidents/{id}/review` | Approve/Reject — persists a decision, creates corrective actions from approved AI recommendations |
| GET | `/api/recommendations` | List Continuous Learning recommendations |
| POST | `/api/recommendations/{id}/decision` | Persist a human decision (Approved/Rejected/Modified/Request More Information) |
| GET | `/api/actions` | List corrective/preventive actions |
| POST | `/api/actions/{id}/complete` | Mark an action Completed (a capability that didn't exist in the UI before this pass) |

Every error response has the shape `{"error": "...", "message": "..."}` — never a stack trace, never a
secret.

---

## 11. Security considerations

- **`ANTHROPIC_API_KEY` never reaches the browser** — it's read server-side only
  (`backend/config.py`), never included in any API response (`Settings.as_public_dict()` deliberately
  excludes it; tested in `backend/tests/test_config.py`), and never logged (`backend/logging_config.py`'s
  `log_ai_request()` takes named fields, never a raw request/response dump).
- **`.env` is git-ignored**; `.env.example` contains only placeholders.
- **No stack trace or exception detail ever reaches a client** — a catch-all handler in `backend/main.py`
  logs the real error server-side and returns a generic `500` to the client for anything unexpected; every
  expected failure (missing record, bad input, AI unavailable) returns a specific, safe message.
- **No authentication or authorization is implemented on the backend today.** This mirrors the existing
  frontend's client-side-only role demo (`docs/governance-and-controls.md`) — the backend does not
  currently re-check who is making a request. This is the single biggest security gap before any real
  deployment; see §13.
- **CORS defaults to `*`** — acceptable because the backend also serves the frontend on the same origin for
  normal use; tighten `CORS_ORIGINS` if you ever serve the frontend from elsewhere.

---

## 12. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `GET /api/health` → `database.ok: false` | `database/riskon.db` doesn't exist yet — run §4's two commands. |
| Frontend loads but looks like the old static snapshot | Backend isn't reachable from the browser, or `frontend/riskon.html` wasn't rebuilt after a frontend change — run `python3 scripts/build_frontend.py`, and confirm `uvicorn` is actually running on the port the browser is pointed at. |
| "Generate AI Analysis" button is disabled with "No backend reachable" | The frontend's `/api/health` check failed — confirm the backend process is running and the page was loaded from `http://localhost:PORT/`, not opened as a `file://` path. |
| Button is disabled with "AI provider not configured" | `ANTHROPIC_API_KEY` is empty — see §7. |
| `POST /api/incidents/{id}/analyze` returns 502 | Claude API call failed (bad key, network issue, rate limit) — check the server log line (`riskon.ai` logger) for the specific reason; the key itself is never in that log. |
| Tests fail with a DB-locked or permission error | Another process (a running `uvicorn --reload`, an open `sqlite3` shell) may be holding the file — close it and retry. |
| A frontend edit doesn't show up | `frontend/riskon.html` is a BUILT file — edit `frontend/app.template.html` and re-run `python3 scripts/build_frontend.py`. Also hard-reload (bypass cache) if testing in a browser that already loaded the old version. |

---

## 13. Current limitations

- No live-verified successful Claude response (§9) — everything up to the real network call was tested;
  the actual model output was not observed during this build.
- No real authentication/authorization on the backend (§11) — anyone who can reach the API can call any
  endpoint.
- `POST /api/incidents/{id}/review` creates corrective actions from approved AI recommendations, but does
  NOT also create a new `risk_register`/`risk_assessments` entry — doing that convincingly would mean
  re-deriving likelihood/severity/control-effectiveness/trend factors the way
  `risk_intelligence/engine.py` does for the synthetic seed data, which is out of scope for this pass (see
  `backend/routes/incidents.py`'s docstring on that endpoint).
- The Continuous Learning pattern-level analytics (Recommendation Performance, Top Learning Signals, etc.)
  remain a load-time snapshot, not recomputed live after a feedback decision — same precedent as Risk
  Intelligence and the Executive Dashboard elsewhere in RISKON (see the reverse-engineering doc). Only the
  Learning Overview tiles and Audit Trail update live.
- `context_builder.py`'s relevance queries are simple (recency-ordered, capped) rather than a similarity
  search — fine at this dataset's size, would need revisiting at real production scale.
- No rate-limiting or request-size limiting on the API itself.
- No automated migration tool for future schema changes — `backend/db.py`'s `ensure_schema()` only ever
  adds the one new table; a future schema change would need its own careful, hand-written migration.

---

## 14. What is implemented vs. future

| Capability | Status |
|---|---|
| Backend serving the existing frontend + a real API | **Implemented** |
| Live database-backed GET endpoints (incidents, actions, recommendations, bootstrap) | **Implemented** |
| Real AI incident-analysis workflow (context → Claude → validate → persist → display) | **Implemented** (verified up to a real network call; real success unverified without a key — see §9) |
| Real persistence for incident review, recommendation decisions, action completion | **Implemented** |
| Structured, validated AI output with a locked human-review requirement | **Implemented** |
| Environment-based configuration, no hardcoded secrets | **Implemented** |
| Graceful "AI not configured" / AI-failure handling, no fabricated results | **Implemented** |
| Server-side logging of AI request metadata (never the key) | **Implemented** |
| Real authentication/authorization | **Future** |
| New risk-register entries created from a live AI analysis's approval | **Future** |
| Multi-stage (13-step) live AI pipeline | **Future** — `engine/pipeline.ts` remains as a documented design |
| Live recomputation of Risk Intelligence / Continuous Learning pattern analytics after a feedback event | **Future** |
| Rate limiting, request auditing beyond the existing audit-trail pattern | **Future** |
