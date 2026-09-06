/**
 * Orchestrator for the 13-stage AI reasoning pipeline.
 *
 * Stage 1 (ingestion) is pure normalization of the submitted incident — no
 * model call. Stages 2-13 each make one Claude call, validate the response
 * against the corresponding fragment of schemas/ai-reasoning-output.schema.json,
 * and on failure retry once with the validation error appended before giving
 * up and marking that stage "failed" (the pipeline does not silently
 * substitute invented data for a failed stage).
 *
 * IMPORTANT: this module never writes to the risk register, corrective
 * actions table, or incident status. It only produces a Stage13ReviewPackage-
 * shaped draft. The API layer (see docs/ai-reasoning-engine.md, "Integration")
 * is solely responsible for persisting anything after a human approves it.
 *
 * Not yet wired to a project scaffold — this is the standalone engine module
 * to drop into your Next.js/Node API route once the app shell exists. Needs:
 *   npm install @anthropic-ai/sdk ajv uuid
 */
import Anthropic from "@anthropic-ai/sdk";
import Ajv from "ajv";
import { randomUUID } from "crypto";
import fullSchema from "../schemas/ai-reasoning-output.schema.json";
import { STAGE_PROMPT_BUILDERS, StagePromptInput } from "./prompts";
import type { AIReasoningOutput, Stage1Ingestion } from "./types";

const anthropic = new Anthropic(); // reads ANTHROPIC_API_KEY from env
const MODEL = "claude-sonnet-5";

const ajv = new Ajv({ strict: false });
const validateFull = ajv.compile(fullSchema as object);

export interface RawIncidentInput {
  incidentId: string;
  facilityId: string;
  reporterEmployeeId: string;
  rawReportText: string;
  dateSubmitted: string; // ISO datetime
  attachmentsPresent?: boolean;
}

/** Stage 1 — no model call. Pure normalization + a completeness check. */
function runStage1Ingestion(input: RawIncidentInput): Stage1Ingestion {
  const hasMinimumFields = Boolean(
    input.rawReportText?.trim() && input.facilityId && input.reporterEmployeeId
  );
  return {
    incident_id: input.incidentId,
    facility_id: input.facilityId,
    reporter_employee_id: input.reporterEmployeeId,
    raw_report_text: input.rawReportText,
    date_submitted: input.dateSubmitted,
    attachments_present: Boolean(input.attachmentsPresent),
    ingestion_status: hasMinimumFields ? "complete" : "incomplete_missing_required_fields",
  };
}

/** Extracts the JSON object from a model response, tolerating stray whitespace. */
function parseJsonResponse(text: string): unknown {
  const trimmed = text.trim();
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start === -1 || end === -1) throw new Error("No JSON object found in model response");
  return JSON.parse(trimmed.slice(start, end + 1));
}

async function callStage(
  stageKey: keyof typeof STAGE_PROMPT_BUILDERS,
  input: StagePromptInput,
  schemaFragmentKey: string
): Promise<unknown> {
  const buildPrompt = STAGE_PROMPT_BUILDERS[stageKey];
  const stageDef = (fullSchema as any).$defs[schemaFragmentKey];
  const validateStage = ajv.compile({ ...stageDef, $defs: (fullSchema as any).$defs });

  let lastError: string | null = null;

  for (let attempt = 0; attempt < 2; attempt++) {
    const { system, user } = buildPrompt(input);
    const message = await anthropic.messages.create({
      model: MODEL,
      max_tokens: 2048,
      system,
      messages: [
        { role: "user", content: attempt === 0 ? user : `${user}\n\nYour previous response failed schema validation with: ${lastError}\nReturn corrected JSON only.` },
      ],
    });
    const textBlock = message.content.find((b) => b.type === "text");
    if (!textBlock || textBlock.type !== "text") throw new Error(`Stage ${stageKey}: no text content in response`);

    try {
      const parsed = parseJsonResponse(textBlock.text);
      if (validateStage(parsed)) return parsed;
      lastError = ajv.errorsText(validateStage.errors);
    } catch (e) {
      lastError = e instanceof Error ? e.message : String(e);
    }
  }

  throw new Error(`Stage ${stageKey} failed schema validation after retry: ${lastError}`);
}

export interface ReferenceData {
  /** SOPs relevant to this facility/hazard type, e.g. loaded from the sops table. Pass only real records — never fabricate. */
  sops?: unknown;
  /** Equipment record for equipment named in the incident, if matched. */
  equipment?: unknown;
  /** Existing open risk_assessments for this facility/hazard category, if any (enables update_existing_risk in Stage 12). */
  existingRiskAssessments?: unknown;
}

/**
 * Runs the full pipeline for one incident. Throws if any stage fails
 * validation twice — callers should catch this, mark the incident
 * "ai_generation_failed", and surface it for manual handling rather than
 * showing a partial/invented draft to the reviewer.
 */
export async function runReasoningPipeline(
  rawIncident: RawIncidentInput,
  referenceData: ReferenceData = {}
): Promise<AIReasoningOutput> {
  const stage_1_ingestion = runStage1Ingestion(rawIncident);

  const priorStages: Record<string, unknown> = { stage_1_ingestion };
  const baseInput = (): StagePromptInput => ({
    incidentId: rawIncident.incidentId,
    rawIncidentText: rawIncident.rawReportText,
    priorStagesJson: JSON.stringify(priorStages, null, 2),
    referenceDataJson: Object.keys(referenceData).length ? JSON.stringify(referenceData, null, 2) : undefined,
  });

  const stage_2_information_extraction = await callStage("stage_2_information_extraction", baseInput(), "stage2Extraction");
  priorStages.stage_2_information_extraction = stage_2_information_extraction;

  const stage_3_classification = await callStage("stage_3_classification", baseInput(), "stage3Classification");
  priorStages.stage_3_classification = stage_3_classification;

  const stage_4_hazard_identification = await callStage("stage_4_hazard_identification", baseInput(), "stage4Hazards");
  priorStages.stage_4_hazard_identification = stage_4_hazard_identification;

  const stage_5_potential_consequences = await callStage("stage_5_potential_consequences", baseInput(), "stage5Consequences");
  priorStages.stage_5_potential_consequences = stage_5_potential_consequences;

  const stage_6_preliminary_severity_assessment = await callStage("stage_6_preliminary_severity_assessment", baseInput(), "stage6Severity");
  priorStages.stage_6_preliminary_severity_assessment = stage_6_preliminary_severity_assessment;

  const stage_7_contributing_factors = await callStage("stage_7_contributing_factors", baseInput(), "stage7ContributingFactors");
  priorStages.stage_7_contributing_factors = stage_7_contributing_factors;

  const stage_8_root_cause_hypotheses = await callStage("stage_8_root_cause_hypotheses", baseInput(), "stage8RootCause");
  priorStages.stage_8_root_cause_hypotheses = stage_8_root_cause_hypotheses;

  const stage_9_existing_controls = await callStage("stage_9_existing_controls", baseInput(), "stage9ExistingControls");
  priorStages.stage_9_existing_controls = stage_9_existing_controls;

  const stage_10_control_gaps = await callStage("stage_10_control_gaps", baseInput(), "stage10ControlGaps");
  priorStages.stage_10_control_gaps = stage_10_control_gaps;

  const stage_11_recommended_actions = await callStage("stage_11_recommended_actions", baseInput(), "stage11Actions");
  priorStages.stage_11_recommended_actions = stage_11_recommended_actions;

  const stage_12_risk_register_impact = await callStage("stage_12_risk_register_impact", baseInput(), "stage12RiskImpact");
  priorStages.stage_12_risk_register_impact = stage_12_risk_register_impact;

  const stage_13_human_review_package = await callStage("stage_13_human_review_package", baseInput(), "stage13ReviewPackage");

  const output: AIReasoningOutput = {
    incident_id: rawIncident.incidentId,
    schema_version: "1.0.0",
    pipeline_run_id: randomUUID(),
    generated_at: new Date().toISOString(),
    model: MODEL,
    stage_1_ingestion,
    stage_2_information_extraction: stage_2_information_extraction as AIReasoningOutput["stage_2_information_extraction"],
    stage_3_classification: stage_3_classification as AIReasoningOutput["stage_3_classification"],
    stage_4_hazard_identification: stage_4_hazard_identification as AIReasoningOutput["stage_4_hazard_identification"],
    stage_5_potential_consequences: stage_5_potential_consequences as AIReasoningOutput["stage_5_potential_consequences"],
    stage_6_preliminary_severity_assessment: stage_6_preliminary_severity_assessment as AIReasoningOutput["stage_6_preliminary_severity_assessment"],
    stage_7_contributing_factors: stage_7_contributing_factors as AIReasoningOutput["stage_7_contributing_factors"],
    stage_8_root_cause_hypotheses: stage_8_root_cause_hypotheses as AIReasoningOutput["stage_8_root_cause_hypotheses"],
    stage_9_existing_controls: stage_9_existing_controls as AIReasoningOutput["stage_9_existing_controls"],
    stage_10_control_gaps: stage_10_control_gaps as AIReasoningOutput["stage_10_control_gaps"],
    stage_11_recommended_actions: stage_11_recommended_actions as AIReasoningOutput["stage_11_recommended_actions"],
    stage_12_risk_register_impact: stage_12_risk_register_impact as AIReasoningOutput["stage_12_risk_register_impact"],
    stage_13_human_review_package: stage_13_human_review_package as AIReasoningOutput["stage_13_human_review_package"],
  };

  // Final full-document validation as a last safety net before returning to the API layer.
  if (!validateFull(output)) {
    throw new Error(`Final pipeline output failed full-schema validation: ${ajv.errorsText(validateFull.errors)}`);
  }

  return output;
}
