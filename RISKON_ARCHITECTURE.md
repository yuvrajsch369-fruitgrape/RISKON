# RISKON Architecture

How RISKON's frontend, backend, database, and Claude AI integration fit together, and why each
architectural choice was made. Companion document: [RISKON_BACKEND_SETUP.md](RISKON_BACKEND_SETUP.md) for
the practical "how do I run this" guide.

This document assumes you've read (or will read) `RISKON_FULL_PRODUCT_REVERSE_ENGINEERING.md`, which
established the state of the codebase BEFORE this pass: a static single-HTML frontend with no backend, no
live database connection, and no live AI call anywhere. Everything below describes what was added to make
those real, without rebuilding the parts that already worked.

---

## 1. High-level architecture

```
                         ┌─────────────────────────────────────────┐
                         │  BROWSER                                 │
                         │  frontend/riskon.html (unchanged UI,     │
                         │  vanilla JS, hash-routed, no framework)  │
                         └───────────────┬───────────────────────────┘
                                         │  fetch() -- same-origin, no CORS needed
                                         ▼
                         ┌─────────────────────────────────────────┐
                         │  BACKEND — FastAPI (backend/)            │
                         │  ┌─────────────────────────────────┐    │
                         │  │ routes/  (thin HTTP layer)        │    │
                         │  │  health · bootstrap · incidents   │    │
                         │  │  recommendations · actions        │    │
                         │  └───────────────┬───────────────────┘    │
                         │  ┌───────────────▼───────────────────┐    │
                         │  │ services/                          │    │
                         │  │  context_builder.py (DB -> context)│    │
                         │  │  ai/claude_service.py (THE ONE      │    │
                         │  │    place that calls Claude)         │    │
                         │  └───────────────┬───────────────────┘    │
                         └──────────────────┼─────────────────────────┘
                                            │
                        ┌───────────────────┼────────────────────────┐
                        ▼                                            ▼
          ┌───────────────────────────┐                ┌──────────────────────────┐
          │  DATABASE                  │                │  CLAUDE (Anthropic API)  │
          │  database/riskon.db        │                │  claude-sonnet-5 (default,│
          │  (SQLite — the SAME file   │                │  configurable via env)   │
          │  every existing Python     │                └──────────────────────────┘
          │  script already used)      │
          │  + risk_intelligence/      │
          │    engine.py               │
          │  + learning_engine/        │
          │    engine.py               │
          └───────────────────────────┘
```

Request path for the one fully-wired AI workflow (see §4):

```
User clicks "Generate AI Analysis"
  -> frontend: POST /api/incidents/{id}/analyze
  -> backend/routes/incidents.py: analyze_incident()
  -> backend/services/context_builder.py: build_incident_context()   [real DB reads]
  -> backend/services/ai/claude_service.py: analyze_incident()       [real Claude call]
  -> Pydantic validation (backend/models/ai_schemas.py)
  -> INSERT INTO ai_incident_analyses (real DB write)
  -> JSON response
  -> frontend: renderLiveAiAnalysis()
```

---

## 2. Why this architecture (the decision, not just the diagram)

**Backend language: Python, not Node/TypeScript.** Every piece of business logic RISKON already had —
`risk_intelligence/engine.py`, `learning_engine/engine.py`, `database/generate_database.py`,
`governance/audit_trail.py` — is Python. The only non-Python AI-related code in the repo,
`engine/pipeline.ts`, was never executed (no `package.json`, no installed dependencies, no host to run it
in — see the reverse-engineering doc §8). Building the backend in Python meant reusing
`RiskIntelligenceEngine` and `LearningEngine` directly, with zero rewrite, and meant one language across
the whole server side instead of two. Introducing Node/TypeScript/npm as a second toolchain just to run one
previously-unused file would have been exactly the kind of unnecessary new technology the brief asked to
avoid.

**Framework: FastAPI.** Chosen over Flask/Django for three concrete reasons that matter for THIS project:
built-in request/response validation via Pydantic (directly reusable for the AI response schema in §11 of
the spec), automatic `/docs` (OpenAPI) for free, and an async-friendly design that matches how the Anthropic
SDK and `httpx` work. Django would have brought an ORM, admin panel, and migrations system this
single-database, ~20-table PoC doesn't need.

**Database: the existing SQLite file, unchanged.** `database/riskon.db` already existed, already had a real
schema, and already had every Part-1/Part-2 table this backend's routes read from. The backend adds exactly
one new table (`ai_incident_analyses`, Part 3 — see `database/schema.sql`) and touches nothing else. No
second database (Postgres/Supabase/etc.) was introduced — see §16 below for why that would have been
premature for a PoC this size.

**No ORM.** Every query in `backend/routes/*.py` is plain `sqlite3` with parameterized SQL — the same style
`risk_intelligence/engine.py` and `learning_engine/engine.py` already use. At this scale (a few thousand
rows, a handful of tables, no complex joins beyond what a few lines of SQL already express clearly), an ORM
(SQLAlchemy, etc.) would add a mapping layer and a migration system for no real benefit, and would mean
learning a second way to query the same database the rest of the codebase already queries directly.

**One Claude call per analysis, not the 13-stage pipeline.** `engine/pipeline.ts` (still present, still
undeleted, still a valid design) makes 13 sequential model calls per incident. `backend/services/ai/
claude_service.py` makes one, producing the adapted structured schema from spec §11. For a PoC's first
genuinely-wired AI feature, this is the right-sized choice: 13x the latency and cost per analysis is a real
cost that should be paid only once the simpler version has proven useful. The service is written so a
future multi-stage pipeline could reuse its context-building, error-handling, and validation patterns
without starting over — see RISKON_BACKEND_SETUP.md §13/§14.

**Frontend: unchanged, not rebuilt.** The brief was explicit: preserve existing functionality and UI. The
existing frontend is 2,500+ lines of vanilla JS across 10 screens, all of it working. Rewriting it onto a
framework, or restructuring its data model to be fetch-driven throughout, would have touched almost every
render function for no functional gain the brief asked for. Instead, exactly one structural change was made
(§3), plus targeted, additive wiring for the specific workflows the brief called out (AI analysis, incident
creation, recommendation feedback, action completion) — see §5.

---

## 3. Frontend <-> backend connection

The single structural frontend change: the main script's outer IIFE became `async`, and the line that used
to read `var DATA = window.RISKON_DATA;` now does this first:

```js
var __live = await resolveLiveData();      // tries GET /api/health, then GET /api/bootstrap
var BACKEND_REACHABLE = __live.reachable;
var AI_CONFIGURED = __live.aiConfigured;
var DATA = __live.data || window.RISKON_DATA;   // live data if reachable, else the embedded fallback
```

`GET /api/bootstrap` calls the exact same `build_frontend_data()` function `database/
export_frontend_data.py` already used to produce the JSON baked into `frontend/riskon.html` at build time
(see that file's docstring) — refactored out of that script into an importable function so there is ONE
data-shaping code path, not two that could quietly drift apart. This means:

- **With no backend running** (opening `frontend/riskon.html` directly, or via the old
  `python3 -m http.server` per `.claude/launch.json`'s `riskon-static` entry): the fetches fail fast, and the
  app runs exactly as it did before this pass, off the embedded snapshot.
- **With the backend running** (`uvicorn backend.main:app`, which also serves this same file at `/` — see
  §22 of the setup doc): the app loads real, current database state instead of a build-time snapshot, with
  every existing render function completely unaware of the difference (they only ever read `DATA.*`, never
  care where it came from).

Everything else added to the frontend is targeted, per-workflow wiring, not a data-layer rewrite:

| Workflow | Frontend change | Falls back to (no backend) |
|---|---|---|
| AI incident analysis | `renderAiAnalysisButton()` shows one of 3 honest states (no backend / no key / real button); `handleGenerateAiAnalysis()` calls `POST /api/incidents/{id}/analyze` for real | existing disabled-button behavior, unchanged |
| Incident review (Approve/Reject) | `handleApproval()` checks for a live analysis first and, if present, calls `POST /api/incidents/{id}/review` instead of the old client-only logic | old client-only risk-register mutation, unchanged |
| Submit incident | `submitNewIncident()` tries `POST /api/incidents` first; on failure or no backend, falls back to the old local-only insert | old local-only insert, unchanged |
| Continuous Learning feedback | `handleRecommendationFeedback()` mutates local state (as before) AND best-effort syncs via `POST /api/recommendations/{id}/decision` | local-only mutation, unchanged |
| Mark corrective action complete | New button, `POST /api/actions/{id}/complete` — a capability that didn't exist in the UI at all before this pass | button is disabled with a tooltip explaining no backend is reachable |

---

## 4. The flagship AI workflow, in detail

This is the literal example from the brief (§10): "User opens Incident → clicks Analyze with AI → ... →
Frontend displays analysis."

1. **Frontend sends only the incident ID** — `POST /api/incidents/{id}/analyze`, no body.
2. **Backend retrieves relevant RISKON records** — `backend/services/context_builder.py`'s
   `build_incident_context()` runs real, targeted SQL: the incident itself; its facility; its equipment (if
   any); its hazard; up to 8 related past incidents/near-misses at the same facility+hazard; up to 10
   controls for that hazard plus each one's latest effectiveness rating; up to 5 recent maintenance records
   for the equipment; up to 5 relevant training records for the involved person; up to 5 open risk-register
   entries for the hazard; up to 8 existing open corrective actions. Every cap is a deliberate scope
   decision (documented in that file), not an accident — the whole database is never dumped into a prompt.
3. **Backend builds structured context** — a plain JSON-serializable dict, the same shape that's persisted
   to `ai_incident_analyses.context_json` for audit/debugging.
4. **Backend calls Claude** — `backend/services/ai/claude_service.py`'s `analyze_incident()`, with a system
   prompt that hard-codes the FACT/HYPOTHESIS/RECOMMENDATION distinction, forbids inventing evidence, and
   requires the exact JSON shape below.
5. **Claude analyzes context** and returns JSON matching:
   ```json
   {
     "summary": "...", "observed_facts": [], "ai_hypotheses": [], "related_risk_signals": [],
     "evidence": [], "recommendations": [], "confidence": 0.0, "uncertainties": [],
     "requires_human_review": true
   }
   ```
6. **Backend validates the response** — `backend/models/ai_schemas.py`'s `IncidentAIAnalysis` (Pydantic).
   `requires_human_review` is typed `Literal[True]`: Pydantic rejects a response where the model returns
   `false`, so the human-in-the-loop guarantee is structural, not just prompted for.
7. **Backend stores the AI result** — one row in `ai_incident_analyses` (Part 3 of the schema): the full
   context, the full validated response, and a `human_review_status` starting at `'Pending'`.
8. **Frontend displays the analysis** — `renderLiveAiAnalysis()`, using the exact same FACT/PATTERN/
   HYPOTHESIS/RECOMMENDATION tag components (`evLine()`/`EV_TAG`) already used by Risk Intelligence and
   Continuous Learning, so a new AI surface doesn't introduce a new visual vocabulary.

Every failure mode in that chain is handled explicitly and safely (never a fabricated result — see
RISKON_BACKEND_SETUP.md §18/§19 for the full table of what happens on each failure).

---

## 5. What was deliberately NOT built (avoiding overengineering)

- **No microservices** — one FastAPI process serves both the API and the static frontend file.
- **No message queue** — the one AI call per request is synchronous; there's no background job system
  because there's nothing yet that needs one (an AI call takes seconds, not minutes).
- **No second database** — see §16 above.
- **No new frontend framework/bundler** — see §2.
- **No full data-layer rewrite** — see §3; only the specific workflows the brief named were wired for real
  persistence.
- **No multi-stage AI pipeline (yet)** — see §2's "one Claude call" decision.
- **No real authentication** — out of scope for this pass; the existing client-side role demo is unchanged
  (still clearly documented as a demo, not real auth, in `docs/governance-and-controls.md`). Backend routes
  do not currently enforce authorization beyond input validation — see RISKON_BACKEND_SETUP.md §11 and §13
  for exactly what this means and what would need to change before any real deployment.

---

## 6. Where this leaves RISKON

Frontend, backend, database, and Claude are now genuinely connected in one direction that matters most for
a PoC demo: a user can trigger a real AI analysis of a real incident, using real database context, through
a real (if simple) API, with a real, typed, validated response — or, with no API key configured, see an
honest message explaining why not, never a fabricated one. See RISKON_BACKEND_SETUP.md for how to run it,
test it, and what's still missing before this would be production-ready.
