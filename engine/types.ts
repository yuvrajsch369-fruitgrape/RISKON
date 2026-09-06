/**
 * TypeScript types mirroring schemas/ai-reasoning-output.schema.json.
 * Keep these two files in sync manually — the JSON Schema is the source of
 * truth (used for runtime validation); this file is for editor/compile-time
 * safety in the pipeline and API layer.
 */

export type FieldSource =
  | "extracted_from_report"
  | "ai_inference"
  | "derived_from_prior_stage"
  | "human_input"
  | "system_reference";

/** Envelope for a single expected fact or judgment (Stage 2, 3, 6, 12 scalar fields). */
export interface ScalarField<T> {
  value: T | null;
  insufficient_information: boolean;
  source: FieldSource;
  confidence: number | null;
  reasoning: string;
  requires_human_approval: boolean;
}

/** Base shape shared by every item in a list-type stage (hazards, factors, hypotheses, etc). */
export interface ListItemBase {
  id: string;
  confidence: number;
  source: FieldSource;
  evidence: string;
  requires_human_approval: boolean;
}

export interface Stage1Ingestion {
  incident_id: string;
  facility_id: string;
  reporter_employee_id: string;
  raw_report_text: string;
  date_submitted: string;
  attachments_present: boolean;
  ingestion_status: "complete" | "incomplete_missing_required_fields";
}

export interface Stage2Extraction {
  who_involved: ScalarField<string>;
  what_happened: ScalarField<string>;
  when_occurred: ScalarField<string>;
  where_location: ScalarField<string>;
  equipment_involved: ScalarField<string>;
  injuries_reported: ScalarField<string>;
  witnesses: ScalarField<string>;
  environmental_conditions: ScalarField<string>;
}

export interface Stage3Classification {
  incident_category: ScalarField<string>;
  incident_type: ScalarField<string>;
  hazard_taxonomy_code: ScalarField<string>;
}

export interface HazardItem extends ListItemBase {
  hazard_type: string;
  description: string;
}
export interface Stage4Hazards {
  hazards: HazardItem[];
  coverage_note: string;
}

export interface ConsequenceItem extends ListItemBase {
  description: string;
  plausible_worst_case_severity: "Low" | "Medium" | "High" | "Critical";
}
export interface Stage5Consequences {
  consequences: ConsequenceItem[];
  coverage_note: string;
}

export interface Stage6Severity {
  ai_suggested_severity: ScalarField<"Low" | "Medium" | "High" | "Critical">;
  ai_suggested_recurrence_likelihood: ScalarField<
    "Rare" | "Unlikely" | "Possible" | "Likely" | "Almost Certain"
  >;
  status: "pending_human_confirmation";
  requires_human_approval: true;
}

export interface ContributingFactorItem extends ListItemBase {
  category: "Human" | "Procedural" | "Equipment" | "Environmental" | "Organizational";
  description: string;
}
export interface Stage7ContributingFactors {
  factors: ContributingFactorItem[];
  coverage_note: string;
}

export interface RootCauseHypothesisItem extends ListItemBase {
  rank: number;
  statement: string;
  label: "hypothesis_not_confirmed";
  supporting_evidence: string;
  contradicting_evidence?: string;
}
export interface Stage8RootCause {
  hypotheses: RootCauseHypothesisItem[];
  coverage_note: string;
}

export interface ExistingControlItem extends ListItemBase {
  control_description: string;
  control_type: "Engineering" | "Administrative" | "PPE" | "Procedural";
  status: "present" | "absent" | "unknown_insufficient_information";
  related_sop_id: string | null;
}
export interface Stage9ExistingControls {
  controls: ExistingControlItem[];
  coverage_note: string;
}

export interface ControlGapItem extends ListItemBase {
  related_control_id: string | null;
  gap_description: string;
  required_by_sop_id: string | null;
}
export interface Stage10ControlGaps {
  gaps: ControlGapItem[];
  coverage_note: string;
}

export interface RecommendedActionItem extends ListItemBase {
  action_type: "Corrective" | "Preventive";
  description: string;
  priority: "Low" | "Medium" | "High" | "Critical";
  suggested_owner_role: string;
  suggested_timeframe_days: number;
  addresses_gap_ids: string[];
  requires_human_approval: true;
}
export interface Stage11Actions {
  actions: RecommendedActionItem[];
  coverage_note: string;
}

export interface Stage12RiskImpact {
  proposed_action: "create_new_risk" | "update_existing_risk";
  hazard_category: string;
  likelihood: ScalarField<number>;
  impact: ScalarField<number>;
  risk_score: ScalarField<number>;
  risk_level: ScalarField<"Low" | "Medium" | "High" | "Critical">;
  existing_risk_assessment_id: string | null;
  reasoning: string;
  requires_human_approval: true;
  write_status: "not_written_pending_approval";
}

export interface Stage13ReviewPackage {
  package_id: string;
  incident_id: string;
  summary_for_reviewer: string;
  stages_requiring_approval: string[];
  approval: {
    decision: "pending" | "approved" | "approved_with_edits" | "rejected";
    reviewer_employee_id: string | null;
    reviewed_at: string | null;
    comments: string | null;
    edited_fields: { field_path: string; ai_value: unknown; human_value: unknown }[];
  };
}

export interface AIReasoningOutput {
  incident_id: string;
  schema_version: "1.0.0";
  pipeline_run_id: string;
  generated_at: string;
  model: string;
  stage_1_ingestion: Stage1Ingestion;
  stage_2_information_extraction: Stage2Extraction;
  stage_3_classification: Stage3Classification;
  stage_4_hazard_identification: Stage4Hazards;
  stage_5_potential_consequences: Stage5Consequences;
  stage_6_preliminary_severity_assessment: Stage6Severity;
  stage_7_contributing_factors: Stage7ContributingFactors;
  stage_8_root_cause_hypotheses: Stage8RootCause;
  stage_9_existing_controls: Stage9ExistingControls;
  stage_10_control_gaps: Stage10ControlGaps;
  stage_11_recommended_actions: Stage11Actions;
  stage_12_risk_register_impact: Stage12RiskImpact;
  stage_13_human_review_package: Stage13ReviewPackage;
}
