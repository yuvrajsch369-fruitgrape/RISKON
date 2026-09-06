# RISKON Risk Intelligence Engine

**Purpose:** move beyond storing incidents one at a time. This module analyzes the full synthetic
operational dataset (`database/riskon.db` — Rex Industrial Manufacturing, built in an earlier pass) as a
whole, across incidents, near misses, hazards, controls, control assessments, and corrective/preventive
actions, to surface **emerging risk patterns** a manager reviewing incidents one-by-one would likely miss.

| Artifact | Path |
|---|---|
| Engine | [`risk_intelligence/engine.py`](../risk_intelligence/engine.py) |
| Runner / demonstration | [`risk_intelligence/run.py`](../risk_intelligence/run.py) |
| Computed output (regenerate any time) | `risk_intelligence/output.json` |
| Frontend export | [`database/export_frontend_data.py`](../database/export_frontend_data.py) (extended — see §7) |

Run it: `python3 risk_intelligence/run.py` (deterministic — same database in, same output out, no
network call, no randomness).

**This module uses ONLY the existing synthetic dataset.** It runs no live model call and adds no new data
— every number is a SQL query or an arithmetic combination of SQL queries against `database/riskon.db`.

---

## 1. The epistemic labeling rule (read this first)

Every finding this engine produces carries exactly one of four tags, and the tag is never dropped when
the finding is displayed anywhere (JSON, terminal demonstration, or the frontend dashboard):

| Tag | What it means | Example from this dataset |
|---|---|---|
| `OBSERVED_FACT` | A direct count/value read from the database. No interpretation. | *"11 total incidents recorded under hazard category 'Heat Stress' (9 within the trailing 12 months)."* |
| `STATISTICAL_PATTERN` | A comparison/aggregation over observed facts that implies a shape. Still fully computed, not inferred. | *"Trend signal: 5 incidents in the most recent 6 months vs. 4 in the prior 6 months → Increasing."* |
| `AI_HYPOTHESIS` | A candidate explanation for a pattern. Always phrased as a possibility. | *"Pattern suggests the control(s) intended to mitigate this hazard may not be functioning as designed... Further investigation recommended."* |
| `RECOMMENDATION` | An action proposed for a human. Always "investigate/review/confirm," never a directive to act unilaterally on safety. | *"Recommended next step: the HSE/Safety Manager function... should review this cluster's incidents..."* |

**Language the engine is allowed to use:** "risk signal detected", "pattern suggests", "may indicate",
"further investigation recommended", "possible systemic issue."
**Language the engine is never allowed to use:** any claim that an accident *will* happen, *is going to*
happen, or has been *predicted* — the engine has no causal or predictive model, only descriptive
statistics over historical records. This rule is enforced structurally, not just by convention: the
`AI_HYPOTHESIS` and `RECOMMENDATION` template strings in `engine.py` are the only place hypothesis/
recommendation text is generated, and every one of them is hard-coded to the hedged phrasing above —
there is no code path that produces a certainty claim.

---

## 2. Data sources (exactly what's read, nothing more)

| Table | What it contributes |
|---|---|
| `incidents` | frequency, severity, near-miss rate, trend, root cause, facility spread — the primary evidence source |
| `hazards` | groups incidents into `hazard_category` clusters (the unit an "Emerging Risk" is built from) |
| `controls` + `control_assessments` | control-effectiveness signal, per hazard cluster and per individual control |
| `actions` | corrective/preventive action status, overdue concentration, reschedule history |
| `risk_register` / `risk_assessments` | cross-checked in the facility-profile analysis (Q4) for open High/Critical counts |
| `facilities` | facility names for readable output; facility-level rollups |

Nothing from `training_records`, `contractors`, `maintenance_records`, `evidence`, `sops`, or `audit_findings`
is used by this module in this pass — the 10 required questions don't call for them directly, and pulling
tables in "just in case" would be exactly the kind of unsupported evidence the spec prohibits. They remain
available in the database for a future extension.

---

## 3. The Risk Signal Score (prototype methodology — not a universal standard)

> Same caveat as the per-incident risk-scoring model (`docs/database-design.md` §6): this is RISKON's
> **prototype** scoring framework, transparent and inspectable, not a validated industrial-risk standard.
> A real deployment would make these weights configurable per company.

For each hazard-category cluster:

```
frequency_score       = min(1.0, incidents_trailing_12mo / 8)
severity_score         = avg_numeric_severity / 4            # Low=1..Critical=4
recurrence_score        = min(1.0, distinct_facilities / 3)
trend_score               = Increasing: 1.0 | Stable: 0.5 | Decreasing: 0.2
control_gap_score          = Ineffective: 1.0 | Partially Effective: 0.6 | Not Assessed: 0.7 | Effective: 0.2
action_overdue_score        = overdue_related_actions / total_related_actions   (0 if no related actions)

risk_signal_score (0-100) = round(100 × (
    0.25 × frequency_score  +  0.20 × severity_score   +  0.15 × recurrence_score +
    0.15 × trend_score      +  0.15 × control_gap_score +  0.10 × action_overdue_score
))

band:  Low (<30)  |  Medium (30-54)  |  High (55-79)  |  Critical (80-100)
```

Notes on the design choices, each made explicit rather than buried:
- **`Not Assessed` scores 0.7, not 0** — absence of a control assessment is never treated as evidence the
  control is fine. This mirrors the same rule used in the per-incident risk-scoring model.
- **Recurrence saturates at 3 facilities** because this dataset has exactly 3 facilities — a hazard
  present at all of them is maximally "spread," by definition.
- **Frequency saturates at 8 incidents/12mo** — a round, documented cutoff, not derived from any external
  benchmark. Configurable.
- Weights sum to 1.0. Every individual factor plus its raw input value is retained in the output's
  `score_breakdown` field so a reviewer can re-derive the score by hand — same transparency rule as the
  per-incident engine's `methodology_notes`.

**Confidence** is a separate, simpler signal: `Low` (<3 incidents trailing 12mo), `Medium` (3-5), `High`
(6+). This is a sample-size heuristic, not a statistical confidence interval — labeled as such everywhere
it appears.

---

## 4. The "Emerging Risk" object

```json
{
  "risk_id": "ERISK-011",
  "risk_name": "Forklift/Pedestrian Interaction",
  "hazard_category": "Forklift / Vehicle Incident",
  "facility": "Multiple",
  "facilities": ["Rex North Plant", "Rex Central Plant", "Rex South Plant"],
  "risk_signal_score": 60.5,
  "risk_band": "High",
  "signal": "Decreasing",
  "score_breakdown": { "...": "one entry per factor above, with its raw value, 0-1 score, and weight" },
  "evidence": [ { "type": "OBSERVED_FACT | STATISTICAL_PATTERN", "statement": "...", "refs": ["INC-...", "..."] } ],
  "related_incidents": ["INC-0001", "..."],
  "related_hazards": ["HAZ-0001", "HAZ-0002"],
  "related_controls": ["CTL-0002", "CTL-0003"],
  "related_actions": ["ACT-...", "..."],
  "related_actions_overdue": ["ACT-...", "..."],
  "confidence": "High",
  "possible_systemic_issue": { "type": "AI_HYPOTHESIS", "statement": "..." },
  "recommended_investigation": { "type": "RECOMMENDATION", "statement": "..." },
  "human_review_status": "Pending"
}
```

`related_*` arrays are always real IDs pulled from the query results that produced the score — nothing in
`evidence`, `related_incidents`, `related_hazards`, or `related_controls` is invented; if a category has
no incidents, no controls, or no actions, that array is simply empty rather than backfilled.

`human_review_status` is always `"Pending"` in this engine's output — the engine never marks its own
findings as reviewed. That's a human action, tracked the same way incident approvals are tracked in the
per-incident reasoning engine (`docs/ai-reasoning-engine.md`).

---

## 5. The 10 required questions — how each is answered

| # | Question | Method | Grounded in |
|---|---|---|---|
| 1 | Top 5 emerging risks | `q1_top_emerging_risks()` | All 19 hazard-category clusters, ranked by risk_signal_score, top 5 |
| 2 | Which risks are increasing | `q2_increasing_risks()` | Clusters where `signal == "Increasing"` (recent 6mo > prior 6mo) |
| 3 | Which risks are recurring | `q3_recurring_risks()` | Clusters with ≥3 incidents trailing 12mo OR spread across ≥2 facilities |
| 4 | Which facilities have unusual patterns | `q4_unusual_facility_patterns()` | Per-facility overdue-action and open-High/Critical-risk counts, flagged when ≥1.8× the cross-facility average |
| 5 | Which actions are repeatedly overdue | `q5_repeatedly_overdue_actions()` | `actions.reschedule_count >= 2`, grouped by control / facility / owner to surface concentration |
| 6 | Which controls appear ineffective | `q6_ineffective_controls()` | Latest `control_assessments.effectiveness_rating` per control = Ineffective, or never once rated Effective across 2+ assessments |
| 7 | Which hazards span multiple facilities | `q7_cross_facility_hazards()` | `hazard_category` → distinct facility count from real incidents, ≥2 |
| 8 | Which incidents suggest a systemic problem | `q8_systemic_problem_incidents()` | Incidents belonging to a High/Critical-band cluster — flagged as a hypothesis about the *cluster*, never a claim about any single incident |
| 9 | What evidence supports each conclusion | `q9_evidence_for(risk_id)` | Returns that risk's own `evidence` array — no separate computation, this is a lookup by design so evidence is never re-derived differently for display vs. scoring |
| 10 | What should management investigate | `q10_recommended_investigations()` | The `recommended_investigation` from the top emerging risks, plus a standing recommendation on overdue-action follow-through from Q5 |

---

## 6. Worked example, run against the real database

Output of `python3 risk_intelligence/run.py` for the pattern named in the spec (this is real engine
output, not hand-written — see `risk_intelligence/output.json` for the complete machine-readable record):

```
EMERGING RISK:
Forklift/Pedestrian Interaction

FACILITY:
Multiple (Rex North Plant, Rex Central Plant, Rex South Plant)

RISK SIGNAL SCORE:
60.5 / 100  (High)  — confidence: High

SIGNAL:
Decreasing

EVIDENCE:
* [OBSERVED_FACT] 12 total incidents recorded under hazard category 'Forklift / Vehicle Incident'
  (7 within the trailing 12 months).
* [OBSERVED_FACT] 10 of these were near misses (no injury/damage occurred).
* [OBSERVED_FACT] Incidents recorded at 3 separate facilities: Rex North Plant, Rex Central Plant,
  Rex South Plant.
* [STATISTICAL_PATTERN] Trend signal: 3 incidents in the most recent 6 months vs. 4 in the prior
  6 months -> Decreasing.
* [OBSERVED_FACT] Most recent control assessment for the related control(s) rated effectiveness as
  'Partially Effective'.
* [OBSERVED_FACT] 2 of 10 related corrective/preventive actions are currently Overdue.
* [STATISTICAL_PATTERN] Root-cause category 'Procedural Non-Compliance' recorded on 3 of 10
  investigated incidents in this cluster.

POSSIBLE SYSTEMIC ISSUE:
[AI_HYPOTHESIS] Pattern suggests the control(s) intended to mitigate 'Forklift / Vehicle Incident' may
not be functioning as designed; and the issue may not be site-specific, which would point toward a
shared procedural or design gap rather than a local one; and a recurring 'procedural non-compliance'
factor may be a common thread across these incidents. Further investigation recommended before drawing
a conclusion.

RECOMMENDED NEXT STEP:
[RECOMMENDATION] Recommended next step: the HSE/Safety Manager function across the affected facilities
should review this cluster's incidents and the related control(s) and confirm whether the 2 overdue
action(s) address the root cause.

HUMAN REVIEW STATUS: Pending
```

Note the score (60.5, High) — even though the *signal* here is Decreasing, the risk still ranks High
because frequency, cross-facility spread, and a "Partially Effective" control rating outweigh the
short-term dip. This is deliberate: **a decreasing recent trend does not by itself clear a risk**, exactly
the same principle documented for the per-incident scoring model. The engine's #1-ranked risk in this
dataset is actually **Heat Stress** (score 83.8, Critical, Increasing) — the demonstration surfaces the
real top 5 by score, not a pre-selected "expected answer," specifically so this document doesn't quietly
cherry-pick the example that looks best. Full top-5 and all Q&A output: `risk_intelligence/output.json`.

---

## 7. Integration into the RISKON dashboard

`database/export_frontend_data.py` was extended with a `build_risk_intelligence()` step that imports
`risk_intelligence/engine.py` directly (no subprocess, no intermediate file needed at build time) and adds
one new key, `riskIntelligence`, to `synthetic-data/frontend-data.json`:

```json
"riskIntelligence": {
  "generatedAt": "2026-09-03",
  "topRisks": [ /* top 5 Emerging Risk objects, same shape as §4 */ ],
  "qa": { /* the 10-question answers, same shape as engine.answer_all() */ }
}
```

The Dashboard screen (`frontend/app.template.html`) renders a new **"Risk Intelligence"** card above the
existing risk matrix: the top 3 emerging risks as compact cards (risk name, score/band pill, signal-trend
pill, a 2-3 line evidence excerpt, and the hypothesis/recommendation, each still carrying its
`OBSERVED_FACT`/`AI_HYPOTHESIS`/`RECOMMENDATION` label so the same fact-vs-hypothesis discipline holds in
the UI, not just in the JSON) with a "View all emerging risks" link into a full **Risk Intelligence**
screen listing all computed clusters and the 10-question answers, filterable by facility like every other
screen. See the running app for the live version — this is additive; none of the existing 6 screens'
behavior changed.

---

## 8. Executive Dashboard — enterprise rollups and the historical trend

A separate screen (`#executive` in the frontend, gated to the Plant Manager and Executive roles) answers
one question only: *"Where is our industrial risk increasing, why, and what should management
investigate?"* It does not introduce a second scoring system — every number on it is either a direct
rollup of the Emerging Risk objects described above, or a genuine historical re-run of the exact same
`build_emerging_risk()` formula. The new engine methods, all in `risk_intelligence/engine.py`:

| Method | Produces |
|---|---|
| `enterprise_risk_signal(as_of=None)` | A single 0-100 number: the average `risk_signal_score` across the top 5 emerging risks as of a given date (defaults to today). This is what "Overall Enterprise Risk Signal" shows — intentionally the average of the risks material enough to already be on management's radar, not diluted across every minor category. |
| `enterprise_risk_trend(months=6)` | A list of `{date, signal_score, band}` — `enterprise_risk_signal()` re-run at each of the last 6 month-end checkpoints. This is what the Risk Trend chart plots. |
| `enterprise_overview(as_of=None)` | The 7 headline counts for the Enterprise Risk Overview tiles (open high-risk issues, emerging-risk count, open/overdue corrective actions, trailing-12mo incidents/near-misses). |
| `facility_comparison()` | Per-facility risk exposure ranking, recurring cross-facility hazards, and control failures (reuses Q4/Q6/Q7 under the hood). |
| `corrective_action_intelligence()` | Open / overdue / recently-closed (30d) / repeatedly-overdue / high-priority action rollups, plus the individual action lists the tables render. |
| `management_brief()` | The template-generated AI Management Brief text. |

### 8.1 How the historical trend avoids lookahead bias

`build_emerging_risk(category, risk_id, as_of=None)` was extended to accept an `as_of` date. When set:

- Only incidents with `incident_datetime <= as_of` are included at all — an incident that hadn't happened
  yet by that checkpoint cannot inflate a past score.
- `trend_of()` and `trailing_12mo()` compute their 6-month/12-month windows relative to `as_of`, not today.
- `latest_control_rating()` only considers control assessments dated on or before `as_of`.
- `related_actions_for()` only considers actions with `created_date <= as_of`.

**Two disclosed simplifications** (not hidden — stated here and in the code's own docstrings): the control
rating and action-overdue status used for a historical checkpoint are each control/action's **current
(final) value**, not a reconstructed point-in-time value. This dataset has no state-history table that
records what an assessment rating or an action's status *was* on an arbitrary past date, only what it is
now plus its `created_date`/`assessment_date`. Reconstructing true historical state would require adding
that table — a real deployment tracking this rollup over time would log state transitions and should. The
trend line this produces is therefore a genuine backtest of *incident timing* combined with *current*
knowledge of controls and actions — not a claim that the control rating itself was already known at that
lower value back then. This is the same honesty standard applied to every other scoring choice in this
document.

### 8.2 Facility risk exposure — why it isn't just "biggest score touching this site"

A naive per-facility ranking (take the highest `risk_signal_score` among risks touching that facility)
produces ties whenever a risk spans all 3 facilities equally — which several of this dataset's Critical/
High risks do. `facility_comparison()` instead computes a **risk exposure score**: each risk's signal score
is divided evenly across the facilities it touches (a risk at all 3 plants contributes 1/3 of its score to
each; a single-facility risk contributes its full score to that one facility) and summed per facility. This
is a ranking aid, not a second 0-100 scale — it is displayed as a normalized bar, never as a score a viewer
might compare directly to the 0-100 Risk Signal Score.

### 8.3 Corrective-action priority — a derived field, not a database column

`actions` has no `priority` column in the schema (see `docs/database-design.md`). `action_priority(a)`
derives one from the severity of the action's linked incident (`Critical`/`High` severity → `High`
priority, `Medium` → `Medium`, otherwise `Low`; an action with no linked incident defaults to `Medium`).
This is used only for the Executive Dashboard's "High-Priority Open" count and table — it is never written
back to the database, and the derivation rule is stated here rather than presented as if `actions` tracked
priority natively.

### 8.4 The AI Management Brief

`management_brief()` is a **template**, not a live model call: it inspects the top 5 emerging risks,
counts how many are `Increasing`, and if any are, names the single strongest one along with its evidence
counts (recorded incidents, facilities, overdue actions) and its existing `recommended_investigation`
statement — every clause traces to a number computed elsewhere in this module. It closes with the
company-wide overdue-action count when nonzero. The frontend renders its output under the literal,
un-editable label **"AI-generated management summary — human review recommended"** and shows
`human_review_status: "Pending"` next to it — this label is not a suggestion the UI happens to add, it is
the field the engine itself returns.

### 8.5 Drill-down

Clicking a risk on the Executive Dashboard expands the same evidence already in that risk's `evidence`
array, plus five additional views assembled entirely from `related_*` IDs already on the object (no new
computation): the actual incident rows (`related_incidents`), the control rows and their latest rating
(`related_controls` + `score_breakdown.control_gap`), the corrective-action rows with owner and status
(`related_actions`, looked up against `correctiveActions` in the frontend export), and a same-data rollup
of distinct owners. Nothing in the drill-down is computed differently than what produced the score —
consistent with the same principle behind `q9_evidence_for()` in §5.
