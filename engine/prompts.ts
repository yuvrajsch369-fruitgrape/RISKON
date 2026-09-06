/**
 * Prompt templates for the 13-stage AI reasoning pipeline.
 *
 * Design: one Claude call per stage, run sequentially. Each stage receives
 * (a) the original raw incident text, (b) the JSON output of every prior
 * stage as context, and (c) instructions to return ONLY JSON matching that
 * stage's schema fragment. This keeps each call small, inspectable, and
 * independently re-runnable, and lets the orchestrator validate + gate
 * between stages instead of trusting one giant free-form generation.
 */

export const SAFETY_SYSTEM_RULES = `
You are the RISKON AI reasoning engine, assisting human safety/risk managers at an
industrial company. This is a prototype system using synthetic data only.

Non-negotiable rules, in every stage:

1. You NEVER make a final safety-critical decision. Every classification, severity
   rating, root-cause hypothesis, recommended action, and risk-register change you
   produce is a DRAFT for human review. You are advisory only.
2. Do NOT invent facts, evidence, regulations, legal requirements, witness statements,
   equipment details, or company policy that is not present in the incident text or
   in the reference data explicitly given to you (SOPs, equipment records, prior
   risk register entries).
3. If information needed for a field is not present in the input, you MUST return
   insufficient_information: true and value: null for that field, with a reasoning
   string that says what specifically is missing. Do not guess or fill gaps with
   "typical" or "likely" facts presented as fact.
4. Clearly distinguish facts from hypotheses. Fields with source "extracted_from_report"
   must be directly traceable to the report text. Fields with source "ai_inference"
   are your reasoning/judgment and must be labeled and evidenced as such — never
   phrase an inference as a confirmed fact.
5. Every ai_inference field must include a "reasoning" string explaining the evidence
   and logic behind it, referencing the specific report text or prior-stage output
   that supports it.
6. Every field that could affect a safety decision, a corrective action, or the risk
   register must have requires_human_approval: true. Extraction-only fields (Stage 1,
   Stage 2) have requires_human_approval: false because they assert no judgment.
7. Root causes are always HYPOTHESES, ranked by plausibility, never asserted as
   confirmed. Use label "hypothesis_not_confirmed" on every root-cause entry.
8. You do not decide regulatory reportability, legal liability, or disciplinary action.
   If a stage's output touches on these (e.g. "should this be reported to a regulator"),
   phrase it as a question/action for a human to confirm, not as your own determination.
9. Output ONLY valid JSON matching the schema fragment given for this stage. No prose
   before or after the JSON, no markdown code fences.
`.trim();

export interface StagePromptInput {
  incidentId: string;
  rawIncidentText: string;
  /** JSON.stringify of all stage outputs completed so far, keyed by stage name. */
  priorStagesJson: string;
  /** Optional reference data available to the model for this stage only (e.g. SOP list, equipment record). Never let the model invent this — only pass what genuinely exists in RISKON's data. */
  referenceDataJson?: string;
}

function basePrompt(stageName: string, stageInstructions: string, input: StagePromptInput, schemaFragment: string) {
  return {
    system: SAFETY_SYSTEM_RULES,
    user: `
STAGE: ${stageName}
INCIDENT ID: ${input.incidentId}

RAW INCIDENT REPORT (verbatim, as submitted):
"""
${input.rawIncidentText}
"""

PRIOR STAGE OUTPUTS (use as context; do not contradict extracted facts):
${input.priorStagesJson}

${input.referenceDataJson ? `REFERENCE DATA AVAILABLE (SOPs / equipment / prior risk entries — only cite what is here, never invent beyond it):\n${input.referenceDataJson}\n` : ""}
TASK:
${stageInstructions}

Return ONLY a JSON object matching this shape (types/enums are illustrative — follow schemas/ai-reasoning-output.schema.json exactly for the authoritative field list):
${schemaFragment}
`.trim(),
  };
}

export const buildStage2Prompt = (input: StagePromptInput) =>
  basePrompt(
    "2 — Information Extraction",
    `Extract only what is explicitly stated in the raw report for each of: who_involved,
what_happened, when_occurred, where_location, equipment_involved, injuries_reported,
witnesses, environmental_conditions. Do not infer anything not stated. If a field is
not mentioned in the report, set insufficient_information: true and value: null.`,
    input,
    `{ "who_involved": ScalarField<string>, "what_happened": ScalarField<string>, "when_occurred": ScalarField<string>, "where_location": ScalarField<string>, "equipment_involved": ScalarField<string>, "injuries_reported": ScalarField<string>, "witnesses": ScalarField<string>, "environmental_conditions": ScalarField<string> }`
  );

export const buildStage3Prompt = (input: StagePromptInput) =>
  basePrompt(
    "3 — Incident Classification",
    `Using Stage 2's extracted facts, classify the incident into: incident_category
(from RISKON's fixed hazard taxonomy — see reference data if provided, otherwise use
your best judgment from standard industrial safety categories and say so in reasoning),
incident_type (Injury | Near Miss | Property Damage | Environmental | Process Safety),
and hazard_taxonomy_code. This is a draft classification requiring human approval.`,
    input,
    `{ "incident_category": ScalarField<string>, "incident_type": ScalarField<string>, "hazard_taxonomy_code": ScalarField<string> }`
  );

export const buildStage4Prompt = (input: StagePromptInput) =>
  basePrompt(
    "4 — Hazard Identification",
    `List every distinct hazard present in this incident, grounded in Stage 2/3 output.
Each hazard needs its own confidence and evidence. Do not pad the list with generic
hazards unrelated to what was reported.`,
    input,
    `{ "hazards": [{ "id": string, "hazard_type": string, "description": string, "confidence": number, "source": FieldSource, "evidence": string, "requires_human_approval": true }], "coverage_note": string }`
  );

export const buildStage5Prompt = (input: StagePromptInput) =>
  basePrompt(
    "5 — Potential Consequence Assessment",
    `For each hazard in Stage 4, assess the reasonable WORST-CASE outcome that could
have resulted — explicitly hypothetical, distinct from what actually happened. Ground
severity estimates in recognized industrial hazard patterns, not speculation beyond
the hazard type.`,
    input,
    `{ "consequences": [{ "id": string, "description": string, "plausible_worst_case_severity": "Low"|"Medium"|"High"|"Critical", "confidence": number, "source": FieldSource, "evidence": string, "requires_human_approval": true }], "coverage_note": string }`
  );

export const buildStage6Prompt = (input: StagePromptInput) =>
  basePrompt(
    "6 — Preliminary Severity Assessment",
    `Propose a preliminary severity rating and recurrence likelihood, weighing BOTH the
actual outcome (Stage 2) and the potential consequence (Stage 5). This is explicitly
preliminary — status must be "pending_human_confirmation" and requires_human_approval
must be true. Explain the balance between actual harm and potential harm in reasoning.`,
    input,
    `{ "ai_suggested_severity": ScalarField<"Low"|"Medium"|"High"|"Critical">, "ai_suggested_recurrence_likelihood": ScalarField<"Rare"|"Unlikely"|"Possible"|"Likely"|"Almost Certain">, "status": "pending_human_confirmation", "requires_human_approval": true }`
  );

export const buildStage7Prompt = (input: StagePromptInput) =>
  basePrompt(
    "7 — Contributing-Factor Analysis",
    `Identify factors that contributed to this incident, categorized as Human,
Procedural, Equipment, Environmental, or Organizational. Ground each in specific
report text or prior-stage output. Lower-confidence/inferred factors are allowed but
must be clearly evidenced as inferred, not asserted as fact.`,
    input,
    `{ "factors": [{ "id": string, "category": "Human"|"Procedural"|"Equipment"|"Environmental"|"Organizational", "description": string, "confidence": number, "source": FieldSource, "evidence": string, "requires_human_approval": true }], "coverage_note": string }`
  );

export const buildStage8Prompt = (input: StagePromptInput) =>
  basePrompt(
    "8 — Root-Cause Hypotheses",
    `Generate ranked root-cause HYPOTHESES (never a single asserted cause) from the
Stage 7 contributing factors. label must be "hypothesis_not_confirmed" on every entry.
Include supporting_evidence and, where relevant, contradicting_evidence or open
questions an investigator should confirm.`,
    input,
    `{ "hypotheses": [{ "id": string, "rank": number, "statement": string, "label": "hypothesis_not_confirmed", "supporting_evidence": string, "contradicting_evidence": string, "confidence": number, "source": FieldSource, "evidence": string, "requires_human_approval": true }], "coverage_note": string }`
  );

export const buildStage9Prompt = (input: StagePromptInput) =>
  basePrompt(
    "9 — Existing-Control Identification",
    `Identify controls that should or do apply to this incident's hazards, using
REFERENCE DATA (SOPs) where provided plus what the report states was physically
present or absent. If a control's presence cannot be determined from the report or
reference data, status must be "unknown_insufficient_information" — do not assume
presence or absence.`,
    input,
    `{ "controls": [{ "id": string, "control_description": string, "control_type": "Engineering"|"Administrative"|"PPE"|"Procedural", "status": "present"|"absent"|"unknown_insufficient_information", "related_sop_id": string|null, "confidence": number, "source": FieldSource, "evidence": string, "requires_human_approval": false }], "coverage_note": string }`
  );

export const buildStage10Prompt = (input: StagePromptInput) =>
  basePrompt(
    "10 — Control-Gap Identification",
    `Compare Stage 9's controls against what Stage 4-8 indicate was actually needed to
prevent this incident. Identify specific gaps — missing, absent, or unconfirmed
controls. Link each gap to the relevant control id and/or SOP id where applicable.`,
    input,
    `{ "gaps": [{ "id": string, "related_control_id": string|null, "gap_description": string, "required_by_sop_id": string|null, "confidence": number, "source": FieldSource, "evidence": string, "requires_human_approval": true }], "coverage_note": string }`
  );

export const buildStage11Prompt = (input: StagePromptInput) =>
  basePrompt(
    "11 — Corrective and Preventive Action Recommendations",
    `Recommend specific, actionable corrective and/or preventive actions, each mapped
to one or more control gaps from Stage 10 via addresses_gap_ids. Suggest a role (not
a named person) as owner, a reasonable timeframe, and a priority consistent with
Stage 6's severity. These are recommendations only — none are auto-assigned.`,
    input,
    `{ "actions": [{ "id": string, "action_type": "Corrective"|"Preventive", "description": string, "priority": "Low"|"Medium"|"High"|"Critical", "suggested_owner_role": string, "suggested_timeframe_days": number, "addresses_gap_ids": string[], "confidence": number, "source": FieldSource, "evidence": string, "requires_human_approval": true }], "coverage_note": string }`
  );

export const buildStage12Prompt = (input: StagePromptInput) =>
  basePrompt(
    "12 — Risk-Register Impact",
    `Propose how this incident should affect the risk register: either create_new_risk
or update_existing_risk (only if an existing_risk_assessment_id was provided in
reference data — never invent one). Derive likelihood/impact/score from the severity
and recurrence estimates in Stage 6. This is a PROPOSED diff only — write_status must
be "not_written_pending_approval". Nothing is written to the register by this stage.`,
    input,
    `{ "proposed_action": "create_new_risk"|"update_existing_risk", "hazard_category": string, "likelihood": ScalarField<number>, "impact": ScalarField<number>, "risk_score": ScalarField<number>, "risk_level": ScalarField<"Low"|"Medium"|"High"|"Critical">, "existing_risk_assessment_id": string|null, "reasoning": string, "requires_human_approval": true, "write_status": "not_written_pending_approval" }`
  );

export const buildStage13Prompt = (input: StagePromptInput) =>
  basePrompt(
    "13 — Human-Review Package",
    `Compile a concise, plain-language summary (3-5 sentences) of what the AI found and
proposed across all prior stages, suitable for a manager to skim before opening full
detail. List every stage key whose output has requires_human_approval: true in
stages_requiring_approval. approval.decision must be "pending" — you do not approve
your own output.`,
    input,
    `{ "package_id": string, "incident_id": string, "summary_for_reviewer": string, "stages_requiring_approval": string[], "approval": { "decision": "pending", "reviewer_employee_id": null, "reviewed_at": null, "comments": null, "edited_fields": [] } }`
  );

export const STAGE_PROMPT_BUILDERS = {
  stage_2_information_extraction: buildStage2Prompt,
  stage_3_classification: buildStage3Prompt,
  stage_4_hazard_identification: buildStage4Prompt,
  stage_5_potential_consequences: buildStage5Prompt,
  stage_6_preliminary_severity_assessment: buildStage6Prompt,
  stage_7_contributing_factors: buildStage7Prompt,
  stage_8_root_cause_hypotheses: buildStage8Prompt,
  stage_9_existing_controls: buildStage9Prompt,
  stage_10_control_gaps: buildStage10Prompt,
  stage_11_recommended_actions: buildStage11Prompt,
  stage_12_risk_register_impact: buildStage12Prompt,
  stage_13_human_review_package: buildStage13Prompt,
} as const;
