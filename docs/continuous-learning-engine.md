# RISKON Continuous Learning Engine

**Purpose:** make RISKON capable of learning from the outcomes of its own recommendations, without ever
letting it rewrite its own production model, prompts, safety rules, or core decision logic on its own.
Every meaningful change passes through evaluation and controlled, human approval.

> Core concept: **RISKON learns from operational outcomes and expert feedback, then improves through
> controlled, measurable, and auditable updates.** It does not self-modify.

| Artifact | Path |
|---|---|
| Data model | `database/schema.sql` Part 2 (`ai_versions`, `recommendations`, `learning_candidates`, `learning_evaluations`) |
| Synthetic data generator | [`learning_engine/generate_learning_data.py`](../learning_engine/generate_learning_data.py) |
| Computation engine | [`learning_engine/engine.py`](../learning_engine/engine.py) |
| Frontend export | `database/export_frontend_data.py` (`continuousLearning` key) |
| UI | `frontend/app.template.html` — "Continuous Learning" screen (`#learning`), plus a hook into the Executive Dashboard's risk drill-down |
| Audit integration | `governance/audit_trail.py` (recommendation decisions + learning-candidate pipeline stages) |

This module reuses the existing database, the existing Risk Intelligence Engine's evidence, the existing
Audit Trail, and the existing role system. It does not introduce a second incident store, a second
approval mechanism, or a second UI shell.

---

## 1. Architecture

```
OBSERVE  ->  ANALYZE  ->  RECOMMEND  ->  HUMAN REVIEW  ->  ACTION  ->  OUTCOME
                                                                          |
                                                                          v
IMPROVE FUTURE RECOMMENDATIONS  <-  LEARN  <-  EVALUATE  <-  FEEDBACK  <-+
```

Concretely, three layers:

1. **Data layer** (`database/schema.sql` Part 2). One row per recommendation, from generation through
   decision, implementation, and measured outcome (§2). A separate, small set of workflow tables tracks
   proposed changes to the recommendation logic itself (`learning_candidates`, `learning_evaluations`) and
   the version catalog they draw from (`ai_versions`).
2. **Computation layer** (`learning_engine/engine.py`), a `LearningEngine` class with the exact same
   discipline as `risk_intelligence/engine.py`: every statistic is a live aggregation over real rows,
   nothing is a stored, potentially-stale number. It detects recurring **learning signals**, repeated
   **expert feedback patterns**, and **multi-facility** divergence, and assembles the **Learning Graph**
   for one recommendation. It never writes back to the database.
3. **Presentation + interaction layer** (`frontend/app.template.html`). A "Continuous Learning" screen
   renders the engine's output, plus a genuinely interactive "Try It" panel where an authorized role can
   approve / reject / modify / request more information on a real pending recommendation — the actual
   human-feedback-loop step, not a static mockup of it.

Nothing here calls a live model. Recommendation text, decisions, and outcomes are synthetic (generated
once, deterministically, from the real incident/action data already in `database/riskon.db`) — the same
prototyping approach used by every other RISKON module. Every *aggregate number* the UI shows, though, is
a genuine computation over that synthetic-but-stored data, never a hand-typed statistic.

---

## 2. Database changes

Four new tables, purely additive — no existing table (`incidents`, `actions`, `risk_register`, etc.) is
altered, and `database/validate.py`'s full consistency suite still passes unchanged after this pass.

### `recommendations` — the core learning-loop record

One row per AI recommendation. Every field requested by the spec is present, and every relationship listed
(Incidents, Risks, Hazards, Controls, Corrective Actions, Facilities, Equipment, AI Investigations, Risk
Signals, Audit Trail) is a real foreign key or a documented, traceable label:

| Field | Notes |
|---|---|
| `recommendation_id` | PK |
| `source_type` | `AI Investigation` (from a single incident) or `Emerging Risk` (from a cross-incident cluster computed by `risk_intelligence/engine.py`) |
| `incident_id`, `hazard_id`, `facility_id`, `equipment_id`, `related_control_id`, `risk_register_id` | real FKs into Part-1 tables |
| `risk_signal_id` | a label (e.g. `ERISK-012`), not an enforced FK — emerging risks are computed on demand, never stored, so there is no row to reference |
| `recommendation_type`, `recommendation_text`, `evidence_used`, `ai_confidence` | what the AI produced |
| `prompt_version_id`, `logic_version_id` | which `ai_versions` rows generated this recommendation — see §5 |
| `human_decision`, `human_modification_text`, `decision_reason`, `decision_by_employee_id`, `decision_date` | the human feedback loop (§3) |
| `assigned_action_id`, `action_status`, `action_completion_date` | links to the real `actions` row, when approved |
| `followup_period_days`, `baseline_incident_count`, `followup_incident_count`, `followup_incident_ids`, `outcome_measurement`, `effectiveness_rating` | outcome tracking (§4) |
| `user_feedback` | free-text, populated by the live "Try It" interaction if a user adds a comment |
| `learning_signal` | this row's own signal (`Positive` / `Negative` / `Modification` / `Insufficient Data` / `Not Yet Determined`) — distinct from the cross-recommendation *pattern*-level signals computed by `detect_signals()`, see §6 |
| `evaluation_status` | `Not Evaluated` / `Insufficient Data` / `Evaluated` |
| `created_at`, `updated_at` | |

### `ai_versions`, `learning_candidates`, `learning_evaluations`

See §5 (versioning) and §6 (evaluation) below — these three implement the controlled improvement pipeline.

### Why signals aren't their own table

The spec's "learning signal" concept operates at two levels: a single recommendation's own outcome
(stored, above), and a *recurring pattern across many recommendations* ("HSE managers repeatedly modify
this recommendation the same way"). The second kind is computed live by `LearningEngine.detect_signals()`
every time it's asked, the same way `risk_intelligence/engine.py` computes "Emerging Risks" live rather
than storing them — this avoids a second copy of the truth that could silently drift from the underlying
`recommendations` rows as new decisions come in.

---

## 3. Learning workflow

### Human feedback loop (spec §2)

Every recommendation carries `human_decision` in `{Approved, Rejected, Modified, Request More Information,
Pending}`. The frontend's "Try It" panel (Continuous Learning screen, section 7) lets an authorized role
(HSE Manager or Plant Manager — the roles with `canApprove: true`) act on a real pending recommendation:
picking Modify, Reject, or Request More Information requires a typed reason/modification first. The
decision is written onto the recommendation row, logged to the Audit Trail immediately
(`entity_type: "Recommendation"`), and reflected in the Learning Overview tiles on the same page load. It
is never applied automatically to any other recommendation.

### Outcome tracking (spec §3)

For a recommendation whose action reached `Completed`, `learning_engine/generate_learning_data.py` compares
real incident counts in the same hazard category and facility for an equal-length window before and after
the action's `completion_date` (default 90 days, `FOLLOWUP_PERIOD_DAYS`). No follow-up incident is
invented — the count comes directly from `incidents.incident_datetime`. Language is deliberately hedged:
*"Observed improvement following implementation... not established as causal; other factors may have
contributed."* — never *"this intervention caused the reduction."* If fewer than 30 days have elapsed since
completion, or if there are fewer than 2 total incidents in the compared windows, the outcome is marked
`Not Evaluated` / `Insufficient Data` rather than forced into a direction.

### Learning from human expertise (spec §6)

`LearningEngine.expert_feedback_patterns()` groups `Rejected`/`Modified` recommendations by
`(hazard_category, decision_reason)` and flags any reasoning that recurs 2+ times as an *"Expert feedback
pattern detected"* — real, computed, never a single anecdote inflated into a pattern.

---

## 4. Safety controls

The engine is structurally prevented — not just instructed — from:

| Never does | How it's prevented |
|---|---|
| Auto-override a human safety decision | `handleRecommendationFeedback()` only runs for `role.canApprove === true`; a blocked attempt is itself audit-logged (`"Unauthorized action attempted"`), same pattern as the existing incident-approval guardrail |
| Auto-close an incident / declare a facility safe | Nothing in this module writes to `incidents.closure_status` or any facility-level status field — it only ever writes to `recommendations` |
| Auto-change a risk rating | Nothing in this module writes to `risk_register` or `risk_assessments` |
| Auto-deploy an untested learning change | `learning_candidates.status` only reaches `Deployed` after a stored `review_decision = "Approved"` from a named human reviewer — see §6 |
| Invent evidence or outcomes | Every `evidence_used`/`outcome_measurement` string traces to a real query (§2, §3); a candidate's *future* effectiveness is explicitly left `NULL` rather than guessed (§6) |
| Treat correlation as causation | Hedged language is hard-coded into the only two places outcome narratives are generated (`compute_outcome()` in the generator, `renderFeedbackCard`/`renderSignalCard` in the frontend) |
| Treat AI confidence as proof | `ai_confidence` is displayed as a labeled number, never used to auto-approve anything |
| Remove human approval requirements | Approving a recommendation in the live demo does **not** auto-create a corrective action — the UI says so explicitly; a real action is only ever created through the existing, human-gated Corrective Actions workflow |

If evidence is insufficient, the engine says exactly that (`evaluation_status: "Insufficient Data"`,
signal type `Insufficient Data`) rather than forcing a positive or negative conclusion.

---

## 5. Versioning approach

`ai_versions` tracks four independent version types — `Prompt`, `Recommendation Logic`, `Risk Scoring`,
`Learning Configuration` — each with a `status` of `Active`, `Candidate`, `Deprecated`, or `Rejected`, and
a `parent_version_id` linking a candidate back to what it would replace.

Every recommendation records `prompt_version_id` and `logic_version_id` — so RISKON can always answer
*"which version generated this recommendation?"* by a direct lookup, not a guess. In this dataset,
`LOGIC-001` (v1.0) generated all "AI Investigation" recommendations; `LOGIC-002` (v1.1, the deployed
Forklift/Pedestrian segregation candidate — see §7) generated the one demo "Pending" recommendation
(`REC-DEMO-001`), and would generate any future Forklift/Vehicle Incident recommendation in this prototype
going forward. All other hazard categories are unaffected by that deployment.

---

## 6. Evaluation methodology (before vs. after, §9 of the spec)

A candidate change is only ever proposed in response to a real, computed **learning signal** — never
speculatively. The one candidate in this dataset, `LCAND-001`, walks the full pipeline:

```
Learning Signal -> Learning Candidate -> Evaluation -> Sandbox/Test -> Performance Comparison
   -> Human/Engineering Approval -> Controlled Version Update -> Monitoring
```

(rendered as a stepper on the Continuous Learning screen, driven by `learning_candidates.status`).

**Trigger:** 4 of 10 decided `Forklift / Vehicle Incident` recommendations were `Modified`, and all 4
modifications were the same real edit ("add a physical barrier"), across 2 facilities — a genuine
`Modification` signal from `detect_signals()`, not asserted.

**Evaluation is an honest retrospective backtest, not a fabricated future result.** `learning_evaluations`
compares:

| Metric | Baseline (v1.0) | Candidate (v1.1) |
|---|---|---|
| Sample size | real count of decided Forklift recommendations | same population, re-scored |
| Modification rate | real | recomputed *assuming* a Modified recommendation whose edit was exactly the now-included addendum would not have needed modification under v1.1 — every other historical decision is assumed unchanged |
| Acceptance rate | real | same assumption |
| Effectiveness rate | real (from measured outcomes) | **left `NULL`** — no historical case was ever generated under v1.1, so a candidate effectiveness number cannot be computed without inventing one. This is disclosed in `method_note`, not hidden. |

**Configurable thresholds** (prototype values, not an industry standard — `learning_evaluations.thresholds_json`):
minimum sample size 5, candidate modification rate ≤ 15%, candidate acceptance rate ≥ 85%. The evaluation
only recommends `Promote` when the *real, computed* candidate-side numbers clear these thresholds.

**A passing evaluation is necessary but not sufficient.** `LCAND-001` only reached `status: "Deployed"`
after a named human reviewer (`review_decision: "Approved"`, with a stored `review_reason`) signed off —
see `learning_candidates.reviewed_by_employee_id`/`review_date`. No code path in this prototype moves a
candidate to `Deployed` without that field being set.

---

## 7. Demo scenario

The spec's illustrative scenario ("RISKON processes 50 historical forklift-related cases") is adapted to
this dataset's real size rather than inflated to match — this dataset has **12** real
`Forklift / Vehicle Incident` incidents, of which 10 had a completed investigation and therefore a
recommendation. Using the real count, not a round illustrative number, is the same discipline every other
RISKON module follows (e.g. Risk Intelligence's worked example is the dataset's actual #1 risk, not a
cherry-picked one).

Walkthrough (also rendered as a clickable "5-Minute Guided Demo" panel at the bottom of the Continuous
Learning screen):

1. **Incident** — a real Forklift/Vehicle Incident near miss (Incident Reporting / AI Investigation).
2. **AI Investigation** — the reasoning trace and its recommended action.
3. **Related Events / Emerging Risk** — the Forklift/Pedestrian Interaction cluster in Risk Intelligence.
4. **Recommendation + Human Approval** — "Try It" on the Continuous Learning screen: approve, modify,
   reject, or request more information on `REC-DEMO-001`, the one live "Pending" recommendation seeded for
   this purpose.
5. **Action -> Outcome -> Learning Signal** — Recommendation Performance and a completed, evaluated
   recommendation's real before/after counts.
6. **Evaluation -> Improved Future Recommendation** — the Controlled Improvement Pipeline section: the
   real trigger, the honest backtest evaluation, the human approval, and `REC-DEMO-001` itself — generated
   under the now-deployed v1.1 logic, its text visibly carries the "Based on similar historical cases..."
   addendum, sourced and hedged, exactly as specified.

All data is synthetic, generated once and deterministically from the real underlying incident/action
history in `database/riskon.db`. Nothing in this walkthrough is presented as, or should be read as,
real-world safety performance.

---

## 8. Known limitations

- **No live model call anywhere in this module.** Recommendation text, decisions, and the one candidate's
  proposed change are template-generated, exactly like the rest of RISKON's "AI" output in this prototype.
- **The live "Try It" interaction only mutates in-memory browser state** (same as every other interactive
  demo in this app) — it does not persist to `database/riskon.db`, and a page reload resets it. The Audit
  Trail entry it creates is real for the session but not written back to the seed database.
- **The pattern-level sections (Recommendation Performance, Top Learning Signals, Expert Feedback,
  Multi-Facility Learning) are a load-time snapshot**, not recomputed live after a "Try It" decision — the
  same precedent as Risk Intelligence and the Executive Dashboard elsewhere in RISKON, which are also
  computed once at export time. Only the Learning Overview tiles and the Audit Trail update live, because
  those are simple client-side filters over the (now-mutated) `recommendations` array.
- **Outcome measurement uses each control's/action's CURRENT status even for past `as_of` comparisons** —
  there is no state-history table recording what a status "was" on a past date (same disclosed
  simplification as the Executive Dashboard's Risk Trend backtest).
- **The candidate evaluation is a retrospective backtest against historical decisions, not a live A/B
  test** — there is no way, in a static prototype with no live traffic, to measure how humans would
  actually have responded to text that was never shown to them. This is disclosed in
  `learning_evaluations.method_note`, not hidden.
- **Sandbox/Test is a conceptual pipeline stage**, not a separately instrumented execution environment in
  this prototype — the "evaluation" step *is* the sandbox test here (a backtest against real historical
  data, computed before deployment, with no effect on production data). A production system would run this
  as a genuinely isolated shadow-mode evaluation against live traffic before touching what users see.
- **Confidence and signal thresholds are fixed prototype constants** (`POSITIVE_RATE_THRESHOLD`,
  `MODIFICATION_RATE_THRESHOLD`, etc. in `learning_engine/engine.py`), not tuned against any validated
  standard, and not yet configurable through the UI despite being called "Learning Configuration" in the
  version catalog.

---

## 9. What would need to change before production deployment

1. **Real authentication and server-side authorization** for the feedback loop and candidate
   approval — today's RBAC is the same client-side demo pattern as the rest of RISKON
   (`docs/governance-and-controls.md` §4), not a real access-control boundary.
2. **Persistence for live decisions.** "Try It" feedback and any real candidate review must be written to
   a real backend (this database, or its production equivalent), not held in browser memory.
3. **A genuine shadow-mode / canary evaluation environment** for candidates — running the candidate logic
   against real (or held-out) live traffic before deployment, rather than a retrospective backtest against
   historical decisions.
4. **A state-history table** for control ratings, action status, and risk levels, so historical
   backtests (both this module's outcome tracking and the Executive Dashboard's Risk Trend) stop relying
   on current/final values as a stand-in for past state.
5. **Configurable, reviewable thresholds** — `learning_evaluations.thresholds_json` and the detection
   constants in `learning_engine/engine.py` should become an editable, audited configuration object (a
   real `Learning Configuration` version), not a hardcoded constant.
6. **A statistically defensible outcome methodology**, reviewed by someone with EHS/safety statistics
   expertise — before/after incident counts over a fixed window is a reasonable prototype heuristic, not a
   validated causal-inference method, and should not be presented to a real safety organization as one
   without that review.
7. **Human sign-off requirements should be enforced server-side**, including a documented escalation path
   (e.g. a second approver for a candidate that touches a Critical-band hazard category), not just a
   client-side `canApprove` check.
8. **Monitoring after deployment** — the pipeline's final "Monitoring" stage is currently a status label,
   not an active process; production would need real post-deployment tracking of the deployed version's
   own acceptance/effectiveness rates, feeding back into the next learning-signal detection cycle.
