# RISKON — Governance & Enterprise Control Layer

RISKON is a prototype for a safety-related enterprise application. This document covers the seven
governance areas required of it, and is explicit about which controls are **functional** in the running
prototype, which are **demonstrated/mocked** (the UI and logic exist and behave correctly, but aren't
backed by production-grade infrastructure), and which are **documented only** (the intended production
approach is described, but nothing is implemented — implementing it would require a real backend, which
this static, client-side prototype does not have).

**No claim of production certification or regulatory compliance is made anywhere in this document or in
the prototype.** Nothing here has been audited against OSHA, ISO 45001, SOC 2, GDPR, or any other named
standard. Where a real control (encryption, authentication, etc.) would be required for production use,
that requirement is stated plainly as *not implemented*.

| # | Area | Status |
|---|---|---|
| 1 | Human-in-the-loop | ✅ Functional (structural — see §1) |
| 2 | Audit trail | ✅ Functional (client-side/session-scoped — see §2) |
| 3 | AI explainability | ✅ Functional | 
| 4 | Data access (RBAC) | 🔶 Demonstrated (real authorization *logic*, no real authentication) |
| 5 | Data validation | ✅ Functional (client-side only — see §5 for why that matters) |
| 6 | AI safety guardrails | ✅ Functional |
| 7 | Security | 📝 Documented only (see §7 — a static prototype cannot implement most of this) |

---

## 1. Human-in-the-loop — ✅ Functional

**What the AI is allowed to do**, everywhere in this system (the per-incident reasoning engine in
`engine/`, the cross-incident Risk Intelligence Engine in `risk_intelligence/`): analyze, classify,
identify patterns, suggest causes, recommend actions, generate risk signals. **What it is never allowed to
do**: make a final safety decision, automatically close an incident, automatically declare an operation
safe, automatically approve a corrective action, or automatically change a risk classification without a
human in the loop. This is enforced in four independent places, not just stated once:

1. **Schema-level, in the AI output structure itself.** `schemas/ai-reasoning-output.schema.json` hard-locks
   several fields with JSON Schema `const`: Stage 6 (severity) `status` must equal
   `"pending_human_confirmation"`; Stage 11 (recommended actions) `requires_human_approval` must equal
   `true`; Stage 12 (risk-register impact) `write_status` must equal `"not_written_pending_approval"`. A
   pipeline response that tries to skip these fails schema validation before a human ever sees it — see
   `docs/ai-reasoning-engine.md` §1.
2. **No auto-write code path exists.** `engine/pipeline.ts` never imports a database client — it returns a
   JSON document and stops. `risk_intelligence/engine.py` is read-only (`sqlite3.connect` with no `INSERT`/
   `UPDATE` anywhere in the module). The only place either engine's output is ever written into the
   operational data is `frontend/app.template.html`'s `handleApproval()` — and that function only runs in
   response to a real button click.
3. **The approve/reject buttons are the single choke point**, and they're role-gated (see §4): a role
   without `canApprove` gets a disabled-looking review panel with an explanation, and even a direct call to
   `handleApproval()` (bypassing the UI, e.g. from the browser console) is blocked by the same server-side-
   style check inside the function itself — not just hidden by CSS.
4. **Rejection is a real, distinct outcome**, not a soft no-op: `incident.status = 'Rejected'` and nothing
   is written to the risk register or corrective actions for that incident. The Risk Intelligence Engine's
   `human_review_status` field is likewise always `"Pending"` in its own output — the engine never marks
   its own finding as reviewed.

---

## 2. Audit trail — ✅ Functional (client-side/session-scoped)

Every entry has the exact fields requested: `user`, `timestamp`, `action`, `entity_type` + `entity_id`,
`previous_value`, `new_value`, `reason`, `source` (`AI-generated` | `Human-generated`), `approval_status`.

**Two sources feed the same log**, both real:
- **Seed history** (`governance/audit_trail.py`) — reconstructed from already-stored facts in
  `database/riskon.db`: an incident's `reported_at`, an evidence row's `uploaded_date`, a corrective
  action's `completion_date`, a closed incident's `closed_date`. Nothing here is invented — where the
  schema doesn't track a fact (e.g. there's no `closed_by` column), the entry says so
  (`"System (derived)"`) rather than guessing a name. 113 seed entries as of the last export.
- **Live entries** (`logAudit()` in `frontend/app.template.html`) — appended in real time as you use the
  running app: approving/rejecting an AI recommendation, submitting a new incident, a blocked unauthorized
  action, a blocked validation failure, even a role switch. Verified live: approving incident `INC-2102`
  produced exactly the chain the spec asked for —
  `AI recommendation created → AI recommendation reviewed → Risk register entry created → Corrective action assigned ×3`
  — each with real IDs, the actual reviewer's role, and (when provided) their comment as `reason`.

**Why "session-scoped" is the honest label**: this is a static, single-file prototype with no backend, so
the live half of the log lives in browser memory and resets on page reload — it is not written to durable
storage, and different users/devices see independent copies. A production deployment would need an
append-only, server-side audit store (see §7).

Screen: **Audit Trail** (new nav item), filterable by source/entity type/search, with summary tiles
(pending-review count, AI vs. human split). Try it: approve or reject any incident in AI Investigation,
then open Audit Trail — the entries you just produced are at the top.

---

## 3. AI explainability — ✅ Functional

Every AI recommendation of consequence shows, together, in the UI (not just in the underlying JSON):

| Requirement | Where |
|---|---|
| Recommendation | Stage 11/12 cards in AI Investigation; `recommended_investigation` in Risk Intelligence cards |
| Evidence used | Every evidence line, tagged `FACT`/`PATTERN` (see below) |
| Reasoning summary | Stage 13 "AI Summary" callout; `possible_systemic_issue` (tagged `HYPOTHESIS`) |
| Confidence | A confidence bar per field in AI Investigation; a `Confidence: Low/Medium/High` pill on every Risk Intelligence card |
| Data sources | Explicit "Data sources:" line added to both the AI Investigation summary callout and every Risk Intelligence card |
| Human approval status | The approval banner in AI Investigation; `Human review status:` line on every Risk Intelligence card |

**No hidden chain-of-thought is ever exposed.** Both engines are designed to produce a final structured
answer with attached evidence, not a reasoning transcript — there is no "thinking" field anywhere in
`schemas/ai-reasoning-output.schema.json` or in the Risk Intelligence Engine's output. What's shown is
always the concise, user-facing "why," never an internal deliberation log.

**The fact/hypothesis distinction is a UI-visible, color-coded system**, not just a documentation
convention: every finding carries one of four tags —
<code>FACT</code> (grey), <code>PATTERN</code> (blue), <code>HYPOTHESIS</code> (amber),
<code>RECOMMENDATION</code> (green) — rendered via `evLine()`/`EV_TAG` in the frontend and defined
identically in `risk_intelligence/engine.py`'s own module docstring. See
`docs/risk-intelligence-engine.md` §1 for the full definition of each category.

---

## 4. Data access (role-based permissions) — 🔶 Demonstrated

Four roles, defined in `ROLES` (`frontend/app.template.html`):

| Role | Can approve AI recommendations | Can submit incidents | Facility scope | Visible screens |
|---|---|---|---|---|
| Employee | No | Yes | Own facility only | Dashboard, Incident Reporting |
| HSE Manager | **Yes** | Yes | Own facility only | + AI Investigation, Corrective Actions, Risk Register, Risk Intelligence, Audit Trail |
| Plant Manager | **Yes** | Yes | Own facility only | + Executive Dashboard, Management Intelligence |
| Executive | No | No | All facilities | Dashboard, Executive Dashboard, Risk Intelligence, Management Intelligence only |

The **Executive Dashboard** (§8 of `docs/risk-intelligence-engine.md`) is restricted to Plant Manager and
Executive specifically because it answers a leadership-level question ("where is risk increasing,
company-wide") that assumes visibility beyond a single facility's day-to-day queue — an HSE Manager or
Employee sees the same underlying evidence via Risk Intelligence and Incident Reporting instead, scoped to
their own facility.

This is enforced at three levels, all functional:
1. **Navigation** — `roleCanSeeNav()` filters which sidebar items render at all.
2. **Routing** — the same check runs again inside `render()` itself, so typing a hidden route's hash
   directly redirects to Dashboard. Verified: switching to Employee and forcing `location.hash =
   '#investigation'` lands back on `#dashboard`.
3. **Actions** — `handleApproval()` checks `canApprove` before touching any data, not just before showing
   the button, and logs the blocked attempt to the audit trail (`"Unauthorized action attempted"`).

A **"Viewing as (demo)"** selector in the sidebar switches roles live — this is explicitly labeled as a
demo control, not a login. For facility-scoped roles, the facility dropdown itself drops the "All
Facilities" option, and switching to such a role forces the scope onto a real single facility (fixed a bug
during this build where the dropdown *displayed* a facility as selected while the underlying filter was
still unset to "all" — the display and the actual data scope are now guaranteed to match).

**Why this is "Demonstrated" and not "Functional" in the full sense**: there is no login, no password, no
session, and nothing stops a user from picking "Executive" from the dropdown to see the Executive view —
the *authorization logic* (what each role can see/do once you're in that role) is real and enforced; the
*authentication* (proving who you are) does not exist in this prototype. Production would sit real
authentication (§7) in front of this same role logic.

---

## 5. Data validation — ✅ Functional (client-side only)

`Validators` (`frontend/app.template.html`) is called at every state-changing action, and a failed
validation genuinely blocks the write — it doesn't just show a warning after the fact:

| Prevented | How | Where checked |
|---|---|---|
| Missing required fields | `Validators.requiredFields()` | New Incident submission (title, description, facility) |
| Invalid dates | `Validators.notFutureDate()` | New Incident's "date/time occurred" field can't be in the future |
| Invalid risk scores | `Validators.riskScore()` | Before every risk-register write in `handleApproval()` — likelihood/impact must be 1-5, score 1-25; a failure blocks the write and logs it |
| Duplicate incident IDs | `Validators.noDuplicateId()` + `nextId()` | `nextId()` prevents collisions by construction (always past the current max); the validator re-checks explicitly as a second, independent guard before every new incident/risk row is pushed |
| Unauthorized status changes | RBAC check in `handleApproval()` (§4) | Same function, same guardrail |

**Why "client-side only" is the honest label, and matters**: every one of these checks runs in the
visitor's own browser. Nothing stops a user from opening the browser console and pushing an invalid row
into `DATA.incidents` directly, bypassing every check above — client-side validation is a UX/data-quality
aid, never a security boundary. A production system must re-run every one of these checks server-side, on
the data actually being persisted, regardless of what the client claims to have already validated.

---

## 6. AI safety guardrails — ✅ Functional

**"Insufficient information — human investigation required."** appears verbatim, exactly as specified, in
two places a reader will actually encounter it:
- Any AI-extracted field the model couldn't determine (`fieldRow()` in AI Investigation).
- The full "AI Analysis: Not yet generated for this incident" panel shown for the ~100 incidents in this
  dataset that have no AI pipeline output at all.

It's also the operating instruction baked into the AI reasoning engine's own prompts: `SAFETY_SYSTEM_RULES`
in `engine/prompts.ts` explicitly requires `insufficient_information: true` + `value: null` over guessing,
and the JSON Schema (`schemas/ai-reasoning-output.schema.json`) makes `null` a legal, expected value for
exactly this reason — there is no schema pressure to fill a field with a plausible-sounding invention.

**Never invent facts, regulations, evidence, or incident details** — enforced the same structural way as
human-in-the-loop (§1): every field in the reasoning engine's schema carries a `source` tag
(`extracted_from_report` / `ai_inference` / `derived_from_prior_stage` / `system_reference`), so an
invented fact would have nowhere honest to be tagged. The Risk Intelligence Engine goes further — it has
*no generative step at all*; every `FACT`/`PATTERN` finding is a direct SQL query result or arithmetic over
one, and `HYPOTHESIS`/`RECOMMENDATION` text is built from fixed, hedged templates
(`"Pattern suggests ... Further investigation recommended before drawing a conclusion."`), never freely
generated. See `docs/risk-intelligence-engine.md` §1 for the exact hedge-language rules, which this
prototype has never violated in its own generated demonstration output (spot-checked in that document).

---

## 7. Security — 📝 Documented only

This is a static, single-HTML-file prototype with **no server, no database connection from the browser,
and no live model calls in the shipped artifact** (the AI reasoning engine's prompts/pipeline code exists
and is real, but nothing in this repository currently executes it against a live Claude API — the 5
AI-pipeline example incidents are pre-generated, checked-in JSON). That constrains what can honestly be
called "implemented" here to almost nothing in this section; what follows is the intended production
approach, clearly flagged as not built.

| Area | Prototype reality | Production approach (not implemented here) |
|---|---|---|
| **Authentication** | None. The role selector (§4) is a UI convenience, not a login. | SSO/OIDC against the company's identity provider; MFA for HSE Manager/Plant Manager roles given their approval authority. |
| **Authorization** | Real client-side logic (§4), trivially bypassable via devtools. | The same role model, re-implemented server-side as the actual access-control layer, with every API call checked against the caller's real, server-verified role — never trusting a client-supplied role. |
| **Encryption** | None — this is static HTML with embedded JSON, served however the artifact host serves it. | TLS in transit (non-negotiable); encryption at rest for the database (SQLite today, would move to Postgres per `docs/database-design.md` §11 — see that section for the migration path); field-level encryption for anything classified as personal data. |
| **API key protection** | The reasoning engine's design already keeps this correct even though it isn't running live: `docs/ai-reasoning-engine.md` §3 states the model API key stays server-side only, in an API route the browser calls, never shipped to or readable from the client. | Same principle, actually deployed: key in a server-side secret store (not `.env` committed to a repo), rotated, scoped to the minimum needed API. |
| **Data isolation** | Single-tenant by construction — one fictional company (Rex Industrial Manufacturing), no multi-tenant code path exists to isolate. | If ever multi-tenant: row-level security or per-tenant database/schema isolation, never a shared table trusting an application-layer `WHERE company_id = ?` alone. |
| **Logging** | The audit trail (§2) is the closest thing to security logging here, and it's business-event logging (who approved what), not security/access logging (who logged in from where). | Separate security event log (auth attempts, permission denials, admin actions) from the business audit trail; centralized, tamper-evident (append-only or hash-chained), retained per policy. |
| **Backup strategy** | None — `database/riskon.db` is a single local file with no automated backup; regenerating it from `database/generate_database.py` reproduces the *synthetic seed data* deterministically, but would not recover any real operational data (there is none in this prototype). | Automated, tested backups with a defined RPO/RTO; point-in-time recovery; backups encrypted and access-controlled same as production data. |

**Nothing in this table should be read as a claim that RISKON meets any of these production requirements
today.** It's an explicit list of what a real deployment would need to add, written now so the gap is
visible rather than discovered later.

---

## 8. Continuous Learning guardrails — ✅ Functional / 🔶 Demonstrated

The Continuous Learning Engine (`learning_engine/`, screen `#learning`) extends this same governance model
to a new kind of state change — a proposed edit to RISKON's own recommendation logic — rather than
introducing a separate one. Full design in
[`docs/continuous-learning-engine.md`](continuous-learning-engine.md) §4; the summary against this
document's own §1-§6 framework:

- **Human-in-the-loop (§1):** a learning candidate can only reach `status: "Deployed"` after a stored,
  named human `review_decision: "Approved"` — there is no code path that promotes a candidate on evaluation
  results alone. Recording feedback on a live recommendation (`handleRecommendationFeedback()`) uses the
  exact same `canApprove` gate and blocked-attempt logging as `handleApproval()` does for incidents.
- **Audit trail (§2):** every recommendation decision and every learning-candidate pipeline stage
  (Proposed / Evaluated / Reviewed / Deployed) is a real, timestamped `governance/audit_trail.py` entry —
  new `entity_type` values `Recommendation`, `LearningCandidate`, and `AIVersion`, filterable on the same
  Audit Trail screen as everything else.
- **Data access (§4):** the Continuous Learning screen and its feedback controls follow the same role
  table as the rest of RISKON (HSE Manager / Plant Manager can act, Executive can view only, Employee has
  no access) — see `docs/database-design.md` §12 / `docs/continuous-learning-engine.md` for why Executive
  and Plant Manager also get an Executive Dashboard hook into it.
- **AI safety guardrails (§6):** outcome language is hedged the same way (`"Observed improvement following
  implementation"`, never `"caused"`), and a candidate's *future* effectiveness is left unmeasured rather
  than invented — see `docs/continuous-learning-engine.md` §4 for the full list of things this module is
  structurally prevented from doing (auto-closing an incident, auto-changing a risk rating, auto-deploying
  an untested change, among others).

This section is marked both Functional and Demonstrated because the governance *logic* (the approval gate,
the audit logging, the role checks) is real and enforced, exactly like the rest of this document's
Functional items — but, like the "Try It" feedback panel itself, a live decision only persists for the
current browser session (§8 of `docs/continuous-learning-engine.md`, "Known limitations"), not to
`database/riskon.db`.

---

## Summary — what to demonstrate, and how

1. Open **AI Investigation**, pick an incident with a "Full AI Trace" tag, and try to approve it as
   **Employee** (switch role first) — the approval panel explains why you can't, and no data changes.
2. Switch to **HSE Manager**, approve the same incident, add a review comment — watch the risk register
   and corrective actions populate.
3. Open **Audit Trail** — the exact chain you just produced is at the top, tagged `Human-generated`, with
   your comment as the `reason`.
4. Open **Risk Intelligence** — every finding is tagged `FACT`/`PATTERN`/`HYPOTHESIS`/`RECOMMENDATION`;
   none claims certainty about a future event.
5. Try submitting a new incident with no title — validation blocks it before it's added.
6. Open **Continuous Learning**, use "Try It" to modify the one pending recommendation with a reason — the
   Learning Overview tiles and Audit Trail update immediately. Scroll to the Controlled Improvement
   Pipeline to see a real signal-to-deployment chain, including the human approval that gated it.
