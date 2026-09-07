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

## 7. API endpoints

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

## 8. Security considerations

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

## 9. Troubleshooting

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

## 10. What is implemented vs. future

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
