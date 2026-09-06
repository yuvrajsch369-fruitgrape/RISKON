# RISKON AI Reasoning Engine — Design & Field Dictionary

Status: **prototype / PoC**. Synthetic data only. AI never makes a final safety-critical
decision — every output below is a draft that a human must review before it affects the
risk register or triggers corrective action.

Related files:
- Schema: [`schemas/ai-reasoning-output.schema.json`](../schemas/ai-reasoning-output.schema.json)
- Prompt templates: [`engine/prompts.ts`](../engine/prompts.ts)
- Orchestrator: [`engine/pipeline.ts`](../engine/pipeline.ts)
- TypeScript types: [`engine/types.ts`](../engine/types.ts)
- 5 worked examples: [`examples/`](../examples/)

---

## 1. Design principles (how the safety rules are enforced structurally)

Rather than relying only on prompt instructions to "be careful," the schema itself
makes the required distinctions structurally unavoidable:

1. **Every AI-derived value is wrapped in a provenance envelope.** No field is a bare
   string/number — it's always `{ value, source, confidence, reasoning, requires_human_approval, insufficient_information }`. A developer building the review UI cannot
   accidentally render an AI hypothesis as if it were a fact, because the envelope forces
   the UI to read `source` before deciding how to display it.
2. **`source` has exactly 5 allowed values** — `extracted_from_report`,
   `ai_inference`, `derived_from_prior_stage`, `human_input`, `system_reference`.
   Extraction stages (1-2) only ever use the first; reasoning stages (3-12) are
   `ai_inference`; computed numbers (risk score) are `derived_from_prior_stage`.
3. **Missing information is a typed state, not a guess.** `insufficient_information: true`
   + `value: null` is a valid, expected output. The prompts (`SAFETY_SYSTEM_RULES` in
   `prompts.ts`) explicitly instruct the model to prefer this over inventing a plausible
   answer, and the schema makes null a legal value so there's no pressure to fill it.
4. **Root causes are never singular or asserted.** Stage 8 always returns a *ranked list*
   of hypotheses, each hard-locked to `label: "hypothesis_not_confirmed"` via a JSON
   Schema `const`. There is no field anywhere in the schema called `root_cause` (singular) —
   that would imply certainty the pipeline cannot have.
5. **Severity, risk-register changes, and recommended actions cannot be silently final.**
   Stage 6 (`status`), Stage 11 (`requires_human_approval`), and Stage 12
   (`write_status`) all use JSON Schema `const` to hard-code `"pending_human_confirmation"`,
   `true`, and `"not_written_pending_approval"` respectively. This isn't just convention —
   a pipeline output that omits or changes these values fails schema validation and is
   rejected by the orchestrator before it ever reaches a human reviewer.
6. **The pipeline itself never writes to the database.** `runReasoningPipeline()` in
   `pipeline.ts` returns a JSON document. Nothing in `engine/` imports a database client.
   Persistence only happens in the API layer, and only for the parts of that document a
   human has approved (see §3, Integration).

---

## 2. Field dictionary, by stage

Legend for the repeated envelope columns:
- **Source** = allowed value(s) of `source` for this field
- **Confidence** = whether/how `confidence` (0-1) is populated
- **Approval** = `requires_human_approval`

### Stage 1 — Incident Ingestion
No model call. Pure normalization of the submitted form; asserts no judgment, so nothing here requires approval.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `incident_id` | string | FK to `incidents.incident_id` | human_input | n/a | No |
| `facility_id` | string | FK to `facilities.facility_id` | human_input | n/a | No |
| `reporter_employee_id` | string | FK to `employees.employee_id` | human_input | n/a | No |
| `raw_report_text` | string | Verbatim submitted text | human_input | n/a | No |
| `date_submitted` | datetime | Submission timestamp | human_input | n/a | No |
| `attachments_present` | boolean | Whether files were attached | human_input | n/a | No |
| `ingestion_status` | enum | `complete` \| `incomplete_missing_required_fields` | system_reference | n/a | No |

### Stage 2 — Information Extraction
Deterministic-style extraction. Every field uses the scalar envelope. `confidence` here reflects *extraction* confidence (did the model correctly read what's there), not judgment confidence.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `who_involved` | string\|null | People named or role-referenced in the report | extracted_from_report | 0-1 | No |
| `what_happened` | string\|null | Narrative of the event, restated from the report | extracted_from_report | 0-1 | No |
| `when_occurred` | string\|null | Date/time as stated | extracted_from_report | 0-1 | No |
| `where_location` | string\|null | Location as stated | extracted_from_report | 0-1 | No |
| `equipment_involved` | string\|null | Equipment named or implied | extracted_from_report | 0-1 | No |
| `injuries_reported` | string\|null | Injury/no-injury statement | extracted_from_report | 0-1 | No |
| `witnesses` | string\|null | Named/referenced witnesses | extracted_from_report | 0-1 | No |
| `environmental_conditions` | string\|null | Lighting, weather, noise, etc. if stated | extracted_from_report | 0-1 | No |

Extraction fields still get `requires_human_approval: false` — they're facts, not decisions — but a reviewer should still be able to see and correct a bad extraction; see §3 for how the review UI surfaces this.

### Stage 3 — Incident Classification
First stage where the model makes a judgment call. Always requires approval.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `incident_category` | string\|null | One of the fixed hazard categories (matches the synthetic dataset's `hazard_category` taxonomy) | ai_inference | 0-1 | **Yes** |
| `incident_type` | string\|null | `Injury` \| `Near Miss` \| `Property Damage` \| `Environmental` \| `Process Safety` | ai_inference | 0-1 | **Yes** |
| `hazard_taxonomy_code` | string\|null | Internal taxonomy code for downstream filtering/reporting | ai_inference | 0-1 | **Yes** |

### Stage 4 — Hazard Identification
List; each item independently evidenced.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `hazards[].hazard_type` | string | Hazard category label | ai_inference | 0-1 per item | **Yes** |
| `hazards[].description` | string | Specific description of this hazard in this incident | ai_inference | 0-1 per item | **Yes** |
| `hazards[].evidence` | string | What in Stage 2/3 supports flagging this hazard | ai_inference | — | **Yes** |
| `coverage_note` | string | Whether the list is believed complete, or limited by report detail | ai_inference | — | No (meta-note) |

### Stage 5 — Potential Consequence Assessment
Explicitly hypothetical worst case, kept separate from what actually happened.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `consequences[].description` | string | Reasonable worst-case outcome | ai_inference | 0-1 per item | **Yes** |
| `consequences[].plausible_worst_case_severity` | enum | Low/Medium/High/Critical | ai_inference | 0-1 per item | **Yes** |
| `consequences[].evidence` | string | Why this worst case is plausible for this hazard | ai_inference | — | **Yes** |

### Stage 6 — Preliminary Severity Assessment
The single most safety-sensitive field in the pipeline — locked to pending status.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `ai_suggested_severity` | enum\|null | Low/Medium/High/Critical | ai_inference | 0-1 | **Yes (always)** |
| `ai_suggested_recurrence_likelihood` | enum\|null | Rare…Almost Certain | ai_inference | 0-1 | **Yes (always)** |
| `status` | const | Always `"pending_human_confirmation"` | system_reference | n/a | — |
| `requires_human_approval` | const `true` | Hard-locked at the schema level | — | — | **Yes** |

### Stage 7 — Contributing-Factor Analysis

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `factors[].category` | enum | Human / Procedural / Equipment / Environmental / Organizational | ai_inference | 0-1 per item | **Yes** |
| `factors[].description` | string | The specific factor | ai_inference | 0-1 per item | **Yes** |
| `factors[].evidence` | string | Grounding in report text or prior stages | ai_inference | — | **Yes** |

### Stage 8 — Root-Cause Hypotheses
Never a single confirmed cause — always a ranked, labeled hypothesis list.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `hypotheses[].rank` | integer | Plausibility rank, 1 = most likely | ai_inference | — | **Yes** |
| `hypotheses[].statement` | string | The hypothesis itself | ai_inference | 0-1 per item | **Yes** |
| `hypotheses[].label` | const | Always `"hypothesis_not_confirmed"` | — | — | **Yes** |
| `hypotheses[].supporting_evidence` | string | What supports it | ai_inference | — | **Yes** |
| `hypotheses[].contradicting_evidence` | string (optional) | What's unconfirmed or cuts against it | ai_inference | — | **Yes** |

### Stage 9 — Existing-Control Identification
Mixed source: what SOPs say (system_reference) vs. what the report confirms was physically present (extracted_from_report). Does **not** require approval by itself — it's evidence-gathering — but feeds Stage 10, which does.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `controls[].control_description` | string | The control (SOP, guard, PPE, permit, etc.) | system_reference \| extracted_from_report | 0-1 per item | No |
| `controls[].control_type` | enum | Engineering / Administrative / PPE / Procedural | system_reference | — | No |
| `controls[].status` | enum | `present` \| `absent` \| `unknown_insufficient_information` | ai_inference | 0-1 per item | No |
| `controls[].related_sop_id` | string\|null | FK to `sops.sop_id` if matched | system_reference | — | No |

### Stage 10 — Control-Gap Identification

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `gaps[].gap_description` | string | The specific control gap | ai_inference | 0-1 per item | **Yes** |
| `gaps[].related_control_id` | string\|null | Links back to Stage 9 item | derived_from_prior_stage | — | **Yes** |
| `gaps[].required_by_sop_id` | string\|null | FK to `sops.sop_id` if the gap is against a specific SOP | system_reference | — | **Yes** |

### Stage 11 — Corrective and Preventive Action Recommendations
Recommendations only — never auto-assigned or auto-scheduled.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `actions[].action_type` | enum | `Corrective` \| `Preventive` | ai_inference | — | **Yes (always)** |
| `actions[].description` | string | The recommended action | ai_inference | 0-1 per item | **Yes** |
| `actions[].priority` | enum | Low/Medium/High/Critical | ai_inference | — | **Yes** |
| `actions[].suggested_owner_role` | string | A *role*, never a named person | ai_inference | — | **Yes** |
| `actions[].suggested_timeframe_days` | integer | Suggested due-by window | ai_inference | — | **Yes** |
| `actions[].addresses_gap_ids` | string[] | Links to Stage 10 gaps | derived_from_prior_stage | — | **Yes** |

### Stage 12 — Risk-Register Impact
A proposed diff only. `write_status` is hard-locked so the pipeline cannot claim it already wrote anything.

| Field | Type | Description | Source | Confidence | Approval |
|---|---|---|---|---|---|
| `proposed_action` | enum | `create_new_risk` \| `update_existing_risk` | ai_inference | — | **Yes (always)** |
| `likelihood` | integer 1-5 \|null | Derived from Stage 6 recurrence estimate | ai_inference | 0-1 | **Yes** |
| `impact` | integer 1-5 \|null | Derived from Stage 5/6 severity | ai_inference | 0-1 | **Yes** |
| `risk_score` | integer\|null | `likelihood × impact` | derived_from_prior_stage | n/a | **Yes** |
| `risk_level` | enum\|null | Banded from `risk_score` | derived_from_prior_stage | n/a | **Yes** |
| `existing_risk_assessment_id` | string\|null | Only populated if `update_existing_risk` and a real record was passed in as reference data | system_reference | — | **Yes** |
| `write_status` | const | Always `"not_written_pending_approval"` | — | — | **Yes** |

### Stage 13 — Human-Review Package
The compiled artifact shown on the Incident Review screen. Not itself an AI judgment — it's an aggregation — but its `approval` object is the actual gate.

| Field | Type | Description | Source | Approval |
|---|---|---|---|---|
| `summary_for_reviewer` | string | Plain-language 3-5 sentence summary | ai_inference | — |
| `stages_requiring_approval` | string[] | Which stage keys need a human decision | derived_from_prior_stage | — |
| `approval.decision` | enum | `pending` \| `approved` \| `approved_with_edits` \| `rejected` — **starts and stays `pending` until a human API call changes it** | human_input | **This is the gate itself** |
| `approval.edited_fields` | array | Records every field a reviewer changed, `{field_path, ai_value, human_value}` — this is your AI-accuracy audit trail | human_input | — |

---

## 3. How this connects to the rest of RISKON

This maps directly onto the MVP architecture and DB schema already defined for RISKON (see prior design conversation) and reuses ID conventions from the seeded synthetic dataset (`FAC-`, `EMP-`, `EQ-`, `SOP-`, `INC-`, `RISK-`, `CA-`).

**1. Trigger point.** On the Incident Detail screen, the "Generate AI Analysis" button
calls `POST /api/incidents/:id/generate-ai-draft`. That route:
- Loads the incident row + any matched `equipment`/`sops`/open `risk_assessments` for
  that facility/hazard area, to pass as `ReferenceData` (never let the model invent
  SOP IDs or equipment specs it wasn't given).
- Calls `runReasoningPipeline(rawIncident, referenceData)` from `engine/pipeline.ts`.
- On success, stores the full `AIReasoningOutput` JSON verbatim in
  `ai_drafts.raw_model_response`, and also flattens the commonly-displayed fields
  (`category`, `severity_ai`, `investigation_text`, `root_cause_text`,
  `corrective_actions_text`) into `ai_drafts`' typed columns for simple querying —
  the raw JSON stays the source of truth for anything needing full provenance.
- On failure (schema validation fails twice, or the API call errors), the route
  returns an error status and the incident stays in `new`/`in_review` with no draft —
  it does **not** fall back to a partial or guessed draft.

**2. Review screen rendering.** The Incident Detail screen renders `stage_13...summary_for_reviewer` at the top, then each stage below it. The UI uses each field's `source` to
style it distinctly — e.g. extracted facts in plain text, `ai_inference` fields with a
visible "AI-suggested" badge and an expandable "why" showing `reasoning`/`evidence`, and
anything with `insufficient_information: true` rendered as a visible gap ("Not stated in
report") rather than blank. Every field with `requires_human_approval: true` is
editable inline, consistent with the MVP's single-gate review model.

**3. The approval action.** `POST /api/incidents/:id/review` accepts the manager's
decision plus any `edited_fields`. This route, not the AI pipeline, is what:
- Writes a `reviews` row (per the MVP schema) capturing the original AI draft
  reference, the decision, and every edit made.
- Sets `stage_13...approval.decision` and re-saves the package for audit history.
- **Only if `decision` is `approved` or `approved_with_edits`:**
  - Upserts a `risks` row using Stage 12's (possibly edited) `likelihood`/`impact`/
    `risk_score`, sourced from `proposed_action`/`existing_risk_assessment_id`.
  - Inserts one `corrective_actions` row per Stage 11 action (possibly edited),
    with `owner_employee_id` resolved from `suggested_owner_role` (the manager picks
    an actual person for that role — the AI never assigns a specific employee).
  - Sets `incidents.status = 'approved'`.
- If `decision` is `rejected`, none of the above writes happen; `incidents.status = 'rejected'` with the reviewer's comment retained for reference.

**4. Regeneration.** A "Regenerate" action re-runs `runReasoningPipeline` and inserts a
new `ai_drafts` row (old ones are kept, not overwritten) — this preserves a full
history of AI output versions per incident, independent of whether any version was
ever approved.

**5. Management Intelligence dashboard.** Reads only from `risks` and
`corrective_actions` — i.e., only from data that passed through a human approval. The
dashboard never queries `ai_drafts` directly, which structurally guarantees that
nothing AI-generated-but-unapproved can appear in management reporting.

**6. What is intentionally NOT built yet (v2):**
- Per-stage/per-field granular approval (today it's one approval covering the whole
  package, consistent with the MVP's single-gate decision).
- Automatic regulatory-reportability determination (Stage 12/13 explicitly punt this
  to a human, per the "do not invent legal requirements" rule).
- Any auto-write path that skips `reviews` — there isn't one; `pipeline.ts` has no
  database import by design, so this can't regress silently.
