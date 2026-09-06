-- =============================================================================
-- RISKON V0.1 — Database Schema
-- Fictional company: Rex Industrial Manufacturing
-- Engine: SQLite (prototype). Written in portable SQL so it migrates to
-- PostgreSQL/Supabase with minimal changes — see docs/database-design.md
-- "Migration to PostgreSQL" section for the exact diffs needed.
--
-- Design notes (see docs/database-design.md for full rationale):
--   * All primary keys are human-readable TEXT ids (e.g. "INC-0007"), not
--     opaque integers — this keeps the dataset legible while prototyping
--     and greps easily in the AI reasoning engine's context.
--   * "Near Misses" are NOT a separate table. They are rows in `incidents`
--     with incident_type = 'Near Miss'. A near miss has the identical field
--     shape to any other incident (that's what the product spec's own
--     "each incident should contain..." field list describes), so a
--     second table would just be a duplicate schema with no real
--     difference — see docs/database-design.md, "Entity mapping decisions".
--   * "Corrective Actions" and "Preventive Actions" are NOT two tables.
--     They are rows in `actions` with action_type = 'Corrective' | 'Preventive'.
--     Same rationale: identical field shape, distinguished by one column.
--   * "Employees/Roles" is split into two tables (`roles` catalog +
--     `employees`) because a role is reusable and independently
--     referenced (SOP owners, action owners, control assessors all point
--     at a role via the employee) — this is more normalized than folding
--     role text directly onto employees.
--   * `evidence.related_entity_id` and `actions.source_*_id` are the only
--     intentionally polymorphic/optional-FK patterns; every other
--     relationship is a real enforced foreign key.
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- 1. companies
-- -----------------------------------------------------------------------------
CREATE TABLE companies (
    company_id          TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    industry            TEXT NOT NULL,
    founded_year        INTEGER NOT NULL,
    headquarters_city   TEXT NOT NULL,
    headquarters_state  TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- 2. facilities
-- -----------------------------------------------------------------------------
CREATE TABLE facilities (
    facility_id         TEXT PRIMARY KEY,
    company_id          TEXT NOT NULL REFERENCES companies(company_id),
    name                TEXT NOT NULL,
    facility_type       TEXT NOT NULL,
    city                TEXT NOT NULL,
    state               TEXT NOT NULL,
    address             TEXT NOT NULL,
    square_footage      INTEGER NOT NULL,
    year_established    INTEGER NOT NULL,
    employee_capacity   INTEGER NOT NULL
);

-- -----------------------------------------------------------------------------
-- 3a. roles  (catalog of job roles/titles — reusable, not per-employee text)
-- -----------------------------------------------------------------------------
CREATE TABLE roles (
    role_id             TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    department          TEXT NOT NULL,
    description         TEXT NOT NULL,
    is_safety_critical  INTEGER NOT NULL DEFAULT 0 CHECK (is_safety_critical IN (0,1))
);

-- -----------------------------------------------------------------------------
-- 3b. employees
-- -----------------------------------------------------------------------------
CREATE TABLE employees (
    employee_id         TEXT PRIMARY KEY,
    facility_id         TEXT NOT NULL REFERENCES facilities(facility_id),
    role_id             TEXT NOT NULL REFERENCES roles(role_id),
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    email               TEXT NOT NULL UNIQUE,
    hire_date           TEXT NOT NULL,          -- ISO 8601 date
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);

-- -----------------------------------------------------------------------------
-- 4. contractors  (individual contract workers, not employees)
-- -----------------------------------------------------------------------------
CREATE TABLE contractors (
    contractor_id               TEXT PRIMARY KEY,
    contracting_firm            TEXT NOT NULL,
    trade                       TEXT NOT NULL,
    primary_facility_id         TEXT NOT NULL REFERENCES facilities(facility_id),
    assigned_date                TEXT NOT NULL,
    safety_orientation_completed INTEGER NOT NULL DEFAULT 0 CHECK (safety_orientation_completed IN (0,1)),
    safety_orientation_date      TEXT,
    status                       TEXT NOT NULL CHECK (status IN ('Active','Inactive'))
);

-- -----------------------------------------------------------------------------
-- 5. equipment
-- -----------------------------------------------------------------------------
CREATE TABLE equipment (
    equipment_id         TEXT PRIMARY KEY,
    facility_id          TEXT NOT NULL REFERENCES facilities(facility_id),
    equipment_type       TEXT NOT NULL,
    category             TEXT NOT NULL,
    manufacturer         TEXT NOT NULL,
    model_number         TEXT NOT NULL,
    serial_number        TEXT NOT NULL,
    install_date         TEXT NOT NULL,
    last_maintenance_date TEXT,
    next_maintenance_due  TEXT,
    status               TEXT NOT NULL CHECK (status IN ('Operational','Under Maintenance','Decommissioned')),
    criticality          TEXT NOT NULL CHECK (criticality IN ('Low','Medium','High'))
);

-- -----------------------------------------------------------------------------
-- 6. sops
-- -----------------------------------------------------------------------------
CREATE TABLE sops (
    sop_id              TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    category            TEXT NOT NULL,
    version              TEXT NOT NULL,
    effective_date       TEXT NOT NULL,
    next_review_date     TEXT NOT NULL,
    owner_employee_id    TEXT NOT NULL REFERENCES employees(employee_id),
    facility_id          TEXT REFERENCES facilities(facility_id),  -- NULL = company-wide
    status                TEXT NOT NULL CHECK (status IN ('Active','Under Revision','Retired'))
);

-- -----------------------------------------------------------------------------
-- 7. hazards
-- -----------------------------------------------------------------------------
CREATE TABLE hazards (
    hazard_id            TEXT PRIMARY KEY,
    hazard_category      TEXT NOT NULL,
    description          TEXT NOT NULL,
    facility_id          TEXT REFERENCES facilities(facility_id),   -- NULL = generic/company-wide hazard
    equipment_id         TEXT REFERENCES equipment(equipment_id),
    typical_consequence  TEXT NOT NULL,
    identified_date       TEXT NOT NULL,
    identified_by_employee_id TEXT REFERENCES employees(employee_id),
    status                TEXT NOT NULL CHECK (status IN ('Active','Mitigated','Closed'))
);

-- -----------------------------------------------------------------------------
-- 8. controls
-- -----------------------------------------------------------------------------
CREATE TABLE controls (
    control_id           TEXT PRIMARY KEY,
    control_name          TEXT NOT NULL,
    control_type          TEXT NOT NULL CHECK (control_type IN ('Engineering','Administrative','PPE','Procedural')),
    hazard_id             TEXT NOT NULL REFERENCES hazards(hazard_id),
    related_sop_id         TEXT REFERENCES sops(sop_id),
    facility_id            TEXT REFERENCES facilities(facility_id),  -- NULL = company-wide
    description             TEXT NOT NULL,
    implemented_date        TEXT NOT NULL,
    status                   TEXT NOT NULL CHECK (status IN ('Active','Retired'))
);

-- -----------------------------------------------------------------------------
-- 9. maintenance_records
-- -----------------------------------------------------------------------------
CREATE TABLE maintenance_records (
    maintenance_record_id TEXT PRIMARY KEY,
    equipment_id            TEXT NOT NULL REFERENCES equipment(equipment_id),
    facility_id              TEXT NOT NULL REFERENCES facilities(facility_id),
    maintenance_type         TEXT NOT NULL CHECK (maintenance_type IN ('Preventive','Corrective','Inspection')),
    scheduled_date            TEXT NOT NULL,
    actual_date               TEXT,
    delay_days                INTEGER NOT NULL DEFAULT 0,
    performed_by_employee_id  TEXT REFERENCES employees(employee_id),
    description                TEXT NOT NULL,
    status                     TEXT NOT NULL CHECK (status IN ('Completed','Delayed','Overdue','Scheduled')),
    related_incident_id        TEXT  -- set later once incidents exist (FK added via ALTER below)
);

-- -----------------------------------------------------------------------------
-- 10. incidents  (includes near misses; see header note)
-- -----------------------------------------------------------------------------
CREATE TABLE incidents (
    incident_id            TEXT PRIMARY KEY,
    facility_id             TEXT NOT NULL REFERENCES facilities(facility_id),
    location                 TEXT NOT NULL,
    incident_datetime         TEXT NOT NULL,
    incident_type             TEXT NOT NULL CHECK (incident_type IN
                                ('Near Miss','Injury','Property Damage','Environmental',
                                 'Equipment Failure','Unsafe Condition')),
    description                TEXT NOT NULL,
    equipment_id                TEXT REFERENCES equipment(equipment_id),
    hazard_id                   TEXT REFERENCES hazards(hazard_id),
    involved_employee_id        TEXT REFERENCES employees(employee_id),
    involved_contractor_id      TEXT REFERENCES contractors(contractor_id),
    injury_status                TEXT NOT NULL,
    potential_consequence        TEXT NOT NULL,
    initial_severity              TEXT NOT NULL CHECK (initial_severity IN ('Low','Medium','High','Critical')),
    immediate_action               TEXT NOT NULL,
    investigation_status           TEXT NOT NULL CHECK (investigation_status IN ('Not Started','In Progress','Completed')),
    root_cause_category             TEXT,
    related_risk_register_id         TEXT,  -- FK added via ALTER once risk_register exists
    reported_by_employee_id          TEXT NOT NULL REFERENCES employees(employee_id),
    reported_at                       TEXT NOT NULL,
    closure_status                    TEXT NOT NULL CHECK (closure_status IN ('Open','Closed')),
    closed_date                        TEXT,
    CHECK ( NOT (involved_employee_id IS NOT NULL AND involved_contractor_id IS NOT NULL) )
);

-- -----------------------------------------------------------------------------
-- 11. risk_assessments  (point-in-time scoring events — historical trail)
-- -----------------------------------------------------------------------------
CREATE TABLE risk_assessments (
    risk_assessment_id         TEXT PRIMARY KEY,
    hazard_id                   TEXT NOT NULL REFERENCES hazards(hazard_id),
    facility_id                  TEXT NOT NULL REFERENCES facilities(facility_id),
    equipment_id                  TEXT REFERENCES equipment(equipment_id),
    source_incident_id             TEXT REFERENCES incidents(incident_id),
    assessment_date                 TEXT NOT NULL,
    assessed_by_employee_id          TEXT NOT NULL REFERENCES employees(employee_id),
    likelihood                        INTEGER NOT NULL CHECK (likelihood BETWEEN 1 AND 5),
    severity                          INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    raw_score                          INTEGER NOT NULL,        -- likelihood * severity
    control_effectiveness_rating       TEXT NOT NULL CHECK (control_effectiveness_rating IN
                                          ('Effective','Partially Effective','Ineffective','Not Assessed')),
    control_effectiveness_factor        REAL NOT NULL,
    recurrence_count_trailing_12mo       INTEGER NOT NULL,
    recurrence_factor                    REAL NOT NULL,
    trend                                 TEXT NOT NULL CHECK (trend IN ('Increasing','Stable','Decreasing')),
    trend_factor                          REAL NOT NULL,
    adjusted_score                        REAL NOT NULL,
    risk_level                             TEXT NOT NULL CHECK (risk_level IN ('Low','Medium','High','Critical')),
    methodology_notes                       TEXT NOT NULL,
    status                                  TEXT NOT NULL CHECK (status IN ('Current','Superseded'))
);

-- -----------------------------------------------------------------------------
-- 12. risk_register  (current state per hazard; one row per active risk)
-- -----------------------------------------------------------------------------
CREATE TABLE risk_register (
    risk_register_id          TEXT PRIMARY KEY,
    hazard_id                   TEXT NOT NULL REFERENCES hazards(hazard_id),
    facility_id                  TEXT NOT NULL REFERENCES facilities(facility_id),
    current_risk_assessment_id    TEXT NOT NULL REFERENCES risk_assessments(risk_assessment_id),
    title                          TEXT NOT NULL,
    current_score                   REAL NOT NULL,
    current_level                    TEXT NOT NULL CHECK (current_level IN ('Low','Medium','High','Critical')),
    owner_employee_id                 TEXT NOT NULL REFERENCES employees(employee_id),
    created_date                       TEXT NOT NULL,
    created_from                        TEXT NOT NULL CHECK (created_from IN ('Incident','Proactive Assessment','Audit Finding')),
    last_reviewed_date                   TEXT NOT NULL,
    next_review_due                       TEXT NOT NULL,
    status                                  TEXT NOT NULL CHECK (status IN ('Open','Mitigated','Closed'))
);

-- -----------------------------------------------------------------------------
-- 13. control_assessments
-- -----------------------------------------------------------------------------
CREATE TABLE control_assessments (
    control_assessment_id       TEXT PRIMARY KEY,
    control_id                    TEXT NOT NULL REFERENCES controls(control_id),
    assessment_date                 TEXT NOT NULL,
    assessed_by_employee_id          TEXT NOT NULL REFERENCES employees(employee_id),
    effectiveness_rating              TEXT NOT NULL CHECK (effectiveness_rating IN ('Effective','Partially Effective','Ineffective')),
    findings                           TEXT NOT NULL,
    related_incident_id                 TEXT REFERENCES incidents(incident_id),
    related_inspection_id                TEXT  -- FK added via ALTER once inspections exists
);

-- -----------------------------------------------------------------------------
-- 14. inspections
-- -----------------------------------------------------------------------------
CREATE TABLE inspections (
    inspection_id           TEXT PRIMARY KEY,
    facility_id                TEXT NOT NULL REFERENCES facilities(facility_id),
    inspection_type              TEXT NOT NULL,
    inspection_date                TEXT NOT NULL,
    inspector_employee_id            TEXT NOT NULL REFERENCES employees(employee_id),
    equipment_id                      TEXT REFERENCES equipment(equipment_id),
    area_location                      TEXT NOT NULL,
    findings_summary                    TEXT NOT NULL,
    deficiencies_found                   INTEGER NOT NULL DEFAULT 0,
    status                                TEXT NOT NULL CHECK (status IN ('Completed','Findings Open'))
);

-- -----------------------------------------------------------------------------
-- 15. audit_findings
-- -----------------------------------------------------------------------------
CREATE TABLE audit_findings (
    audit_finding_id         TEXT PRIMARY KEY,
    facility_id                 TEXT NOT NULL REFERENCES facilities(facility_id),
    audit_date                    TEXT NOT NULL,
    auditor_name                    TEXT NOT NULL,
    auditor_employee_id               TEXT REFERENCES employees(employee_id),  -- NULL = external auditor
    finding_category                    TEXT NOT NULL,
    description                          TEXT NOT NULL,
    severity                              TEXT NOT NULL CHECK (severity IN ('Low','Medium','High','Critical')),
    related_sop_id                         TEXT REFERENCES sops(sop_id),
    related_control_id                      TEXT REFERENCES controls(control_id),
    status                                   TEXT NOT NULL CHECK (status IN ('Open','Closed'))
);

-- -----------------------------------------------------------------------------
-- 16. actions  (corrective + preventive; see header note)
-- -----------------------------------------------------------------------------
CREATE TABLE actions (
    action_id                TEXT PRIMARY KEY,
    action_type                 TEXT NOT NULL CHECK (action_type IN ('Corrective','Preventive')),
    source_type                   TEXT NOT NULL CHECK (source_type IN
                                     ('Incident','Audit Finding','Inspection','Risk Assessment')),
    source_incident_id             TEXT REFERENCES incidents(incident_id),
    source_audit_finding_id          TEXT REFERENCES audit_findings(audit_finding_id),
    source_inspection_id              TEXT REFERENCES inspections(inspection_id),
    source_risk_assessment_id           TEXT REFERENCES risk_assessments(risk_assessment_id),
    related_control_id                    TEXT REFERENCES controls(control_id),
    description                            TEXT NOT NULL,
    facility_id                             TEXT NOT NULL REFERENCES facilities(facility_id),
    owner_employee_id                         TEXT NOT NULL REFERENCES employees(employee_id),
    created_date                               TEXT NOT NULL,
    original_due_date                            TEXT NOT NULL,
    due_date                                      TEXT NOT NULL,
    reschedule_count                                INTEGER NOT NULL DEFAULT 0,
    status                                           TEXT NOT NULL CHECK (status IN ('Open','In Progress','Completed','Overdue')),
    completion_date                                   TEXT,
    verification_method                                TEXT NOT NULL,
    CHECK (
        (source_type = 'Incident' AND source_incident_id IS NOT NULL) OR
        (source_type = 'Audit Finding' AND source_audit_finding_id IS NOT NULL) OR
        (source_type = 'Inspection' AND source_inspection_id IS NOT NULL) OR
        (source_type = 'Risk Assessment' AND source_risk_assessment_id IS NOT NULL)
    )
);

-- -----------------------------------------------------------------------------
-- 17. training_records
-- -----------------------------------------------------------------------------
CREATE TABLE training_records (
    training_record_id         TEXT PRIMARY KEY,
    employee_id                   TEXT REFERENCES employees(employee_id),
    contractor_id                   TEXT REFERENCES contractors(contractor_id),
    training_topic                    TEXT NOT NULL,
    training_date                       TEXT,
    expiry_date                          TEXT,
    status                                 TEXT NOT NULL CHECK (status IN ('Current','Expired','Not Completed')),
    conducted_by_employee_id                TEXT REFERENCES employees(employee_id),
    result                                   TEXT,
    CHECK ( (employee_id IS NOT NULL) OR (contractor_id IS NOT NULL) ),
    CHECK ( NOT (employee_id IS NOT NULL AND contractor_id IS NOT NULL) )
);

-- -----------------------------------------------------------------------------
-- 18. evidence  (polymorphic attachment record — see header note)
-- -----------------------------------------------------------------------------
CREATE TABLE evidence (
    evidence_id               TEXT PRIMARY KEY,
    related_entity_type          TEXT NOT NULL CHECK (related_entity_type IN
                                    ('Incident','Inspection','Audit Finding','Action','Training Record','Maintenance Record')),
    related_entity_id              TEXT NOT NULL,  -- polymorphic: id within the table named by related_entity_type
    file_name                        TEXT NOT NULL,
    file_type                          TEXT NOT NULL,
    description                          TEXT NOT NULL,
    uploaded_by_employee_id                TEXT REFERENCES employees(employee_id),
    uploaded_date                            TEXT NOT NULL
);

-- =============================================================================
-- PART 2 — CONTINUOUS LEARNING ENGINE (added in a later pass; see
-- docs/continuous-learning-engine.md for the full design rationale).
-- Purely additive: no existing table above is altered, and every FK here
-- points at rows that already exist from Part 1 above. Populated by
-- learning_engine/generate_learning_data.py against the already-built
-- database — it does not touch or regenerate any Part 1 table.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 19. ai_versions  (catalog of prompt / recommendation-logic / risk-scoring /
-- learning-configuration versions. Every recommendation records which
-- versions generated it -- see `recommendations` below.)
-- -----------------------------------------------------------------------------
CREATE TABLE ai_versions (
    version_id           TEXT PRIMARY KEY,
    version_type         TEXT NOT NULL CHECK (version_type IN
                            ('Prompt','Recommendation Logic','Risk Scoring','Learning Configuration')),
    label                TEXT NOT NULL,
    status               TEXT NOT NULL CHECK (status IN ('Active','Candidate','Deprecated','Rejected')),
    description          TEXT NOT NULL,
    parent_version_id    TEXT REFERENCES ai_versions(version_id),
    created_date         TEXT NOT NULL,
    activated_date       TEXT,
    created_by           TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- 20. recommendations  (the core learning-loop record: one row per AI
-- recommendation, from generation through human decision, implementation,
-- and measured outcome. See docs/continuous-learning-engine.md §2 for the
-- full field-by-field rationale.)
-- -----------------------------------------------------------------------------
CREATE TABLE recommendations (
    recommendation_id       TEXT PRIMARY KEY,
    source_type              TEXT NOT NULL CHECK (source_type IN ('AI Investigation','Emerging Risk')),
    incident_id               TEXT REFERENCES incidents(incident_id),
    risk_register_id           TEXT REFERENCES risk_register(risk_register_id),
    risk_signal_id              TEXT,  -- snapshot of an ERISK-xxx id at generation time; emerging risks
                                        -- are computed on demand (risk_intelligence/engine.py), not stored,
                                        -- so this is a label for traceability, not an enforced FK.
    hazard_id                    TEXT REFERENCES hazards(hazard_id),
    facility_id                   TEXT NOT NULL REFERENCES facilities(facility_id),
    equipment_id                   TEXT REFERENCES equipment(equipment_id),
    related_control_id              TEXT REFERENCES controls(control_id),
    recommendation_type              TEXT NOT NULL,
    recommendation_text               TEXT NOT NULL,
    evidence_used                      TEXT NOT NULL,
    ai_confidence                       REAL,
    prompt_version_id                    TEXT REFERENCES ai_versions(version_id),
    logic_version_id                      TEXT REFERENCES ai_versions(version_id),
    human_decision                         TEXT NOT NULL CHECK (human_decision IN
                                              ('Approved','Rejected','Modified','Request More Information','Pending')),
    human_modification_text                 TEXT,
    decision_reason                          TEXT,
    decision_by_employee_id                   TEXT REFERENCES employees(employee_id),
    decision_date                              TEXT,
    assigned_action_id                          TEXT REFERENCES actions(action_id),
    action_status                                TEXT NOT NULL CHECK (action_status IN
                                                    ('Not Assigned','Assigned','Completed')),
    action_completion_date                        TEXT,
    followup_period_days                           INTEGER,
    baseline_incident_count                         INTEGER,
    followup_incident_count                          INTEGER,
    followup_incident_ids                             TEXT,  -- JSON array of incident_id
    outcome_measurement                                TEXT,  -- hedged narrative, never a causal claim
    effectiveness_rating                                TEXT CHECK (effectiveness_rating IN
                                                            ('High','Medium','Low','Uncertain','Not Yet Measured')),
    user_feedback                                        TEXT,
    learning_signal                                       TEXT CHECK (learning_signal IN
                                                             ('Positive','Negative','Modification','Insufficient Data','Not Yet Determined')),
    evaluation_status                                      TEXT NOT NULL CHECK (evaluation_status IN
                                                              ('Not Evaluated','Insufficient Data','Evaluated')),
    created_at                                              TEXT NOT NULL,
    updated_at                                               TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- 21. learning_candidates  (a proposed, human-reviewable change to a prompt /
-- recommendation-logic / risk-scoring / learning-configuration version,
-- triggered by a learning signal. Never auto-applied -- see `status`.)
-- -----------------------------------------------------------------------------
CREATE TABLE learning_candidates (
    candidate_id                TEXT PRIMARY KEY,
    candidate_type                TEXT NOT NULL CHECK (candidate_type IN
                                     ('Prompt','Recommendation Logic','Risk Scoring','Learning Configuration')),
    title                          TEXT NOT NULL,
    description                     TEXT NOT NULL,
    source_signal_summary            TEXT NOT NULL,  -- text snapshot of the learning signal that triggered
                                                       -- this candidate (signals are detected live from
                                                       -- `recommendations`, not stored as their own table --
                                                       -- see docs/continuous-learning-engine.md).
    source_recommendation_ids          TEXT NOT NULL, -- JSON array: the actual recommendation_id rows used
                                                        -- as evidence for the signal, so the trigger is
                                                        -- traceable, not asserted.
    proposed_change                     TEXT NOT NULL,
    baseline_version_id                  TEXT NOT NULL REFERENCES ai_versions(version_id),
    candidate_version_id                  TEXT NOT NULL REFERENCES ai_versions(version_id),
    status                                  TEXT NOT NULL CHECK (status IN
                                              ('Proposed','Sandbox Testing','Evaluated','Approved','Rejected','Deployed')),
    created_date                            TEXT NOT NULL,
    created_by                               TEXT NOT NULL,
    reviewed_by_employee_id                   TEXT REFERENCES employees(employee_id),
    review_decision                            TEXT,
    review_reason                               TEXT,
    review_date                                  TEXT
);

-- -----------------------------------------------------------------------------
-- 22. learning_evaluations  (before-vs-after comparison of a learning
-- candidate against the version it would replace, using configurable
-- thresholds. A candidate may only be promoted to Active after this passes
-- AND a human approves -- see learning_candidates.status/review_decision.)
-- -----------------------------------------------------------------------------
CREATE TABLE learning_evaluations (
    evaluation_id                  TEXT PRIMARY KEY,
    candidate_id                     TEXT NOT NULL REFERENCES learning_candidates(candidate_id),
    baseline_version_id               TEXT NOT NULL REFERENCES ai_versions(version_id),
    candidate_version_id               TEXT NOT NULL REFERENCES ai_versions(version_id),
    baseline_sample_size                INTEGER NOT NULL,
    candidate_sample_size                INTEGER NOT NULL,
    baseline_modification_rate            REAL,
    candidate_modification_rate            REAL,
    baseline_acceptance_rate                REAL,
    candidate_acceptance_rate                REAL,
    baseline_effectiveness_rate               REAL,
    candidate_effectiveness_rate               REAL,
    thresholds_json                             TEXT NOT NULL,
    passed_thresholds                            INTEGER NOT NULL CHECK (passed_thresholds IN (0,1)),
    recommendation                                TEXT NOT NULL CHECK (recommendation IN
                                                     ('Promote','Do Not Promote','Insufficient Data')),
    method_note                                    TEXT NOT NULL,  -- discloses how candidate-side metrics
                                                                     -- were derived (retrospective backtest
                                                                     -- against real historical decisions, not
                                                                     -- a live production A/B test)
    evaluated_date                                  TEXT NOT NULL
);

CREATE INDEX idx_recommendations_incident   ON recommendations(incident_id);
CREATE INDEX idx_recommendations_facility   ON recommendations(facility_id);
CREATE INDEX idx_recommendations_hazard     ON recommendations(hazard_id);
CREATE INDEX idx_recommendations_decision   ON recommendations(human_decision);
CREATE INDEX idx_recommendations_action     ON recommendations(assigned_action_id);
CREATE INDEX idx_learning_candidates_status ON learning_candidates(status);
CREATE INDEX idx_learning_evaluations_candidate ON learning_evaluations(candidate_id);
-- END PART 2

-- =============================================================================
-- PART 3 — LIVE BACKEND (added when the FastAPI backend + Claude AI service
-- were introduced; see RISKON_ARCHITECTURE.md and RISKON_BACKEND_SETUP.md).
-- One new table: a real, server-persisted record of every live AI incident
-- analysis, distinct from the synthetic `recommendations` table Part 2 seeds
-- (those were never reviewed by a real person or produced by a real model
-- call — see docs/continuous-learning-engine.md). Rows here are only ever
-- inserted by backend/routes/incidents.py after a genuine Claude API call
-- succeeds and its response passes Pydantic validation. Created idempotently
-- at backend startup by backend/db.py's ensure_schema() — never by re-running
-- the Part 1/2 generators, so it never disturbs the synthetic seed data.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 23. ai_incident_analyses  (persisted result of a live POST /api/incidents/
-- {id}/analyze call — see backend/services/ai/claude_service.py)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_incident_analyses (
    analysis_id           TEXT PRIMARY KEY,
    incident_id             TEXT NOT NULL REFERENCES incidents(incident_id),
    created_at               TEXT NOT NULL,
    model                     TEXT NOT NULL,
    prompt_version_id          TEXT REFERENCES ai_versions(version_id),
    context_json                TEXT NOT NULL,   -- the exact structured context sent to Claude (audit/debug)
    response_json                TEXT NOT NULL,  -- the full validated IncidentAIAnalysis, verbatim
    summary                       TEXT NOT NULL, -- denormalized from response_json for quick list display
    confidence                     REAL,
    requires_human_review           INTEGER NOT NULL DEFAULT 1 CHECK (requires_human_review IN (0,1)),
    human_review_status              TEXT NOT NULL DEFAULT 'Pending' CHECK (human_review_status IN
                                        ('Pending','Approved','Rejected')),
    reviewed_by_employee_id            TEXT REFERENCES employees(employee_id),
    reviewed_at                          TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_incident_analyses_incident ON ai_incident_analyses(incident_id);
-- END PART 3

-- =============================================================================
-- PART 4 — SIGNUP / PROFILE (added with the dedicated RISKON signup page).
-- A lightweight, real, server-persisted profile: name + occupation + post
-- (facility/site), plus the RBAC demo role that occupation maps onto. This is
-- NOT authentication — there is no password, no session token, no login
-- check anywhere in the backend (see RISKON_BACKEND_SETUP.md §11/§13, which
-- already documents that gap for the rest of the API). Signing up only ever
-- creates a profile a browser can remember (localStorage) and display; it
-- never gates access to any endpoint or screen. Created idempotently at
-- backend startup by backend/db.py's ensure_schema().
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 24. app_users  (signup profiles — see backend/routes/users.py)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_users (
    user_id        TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    occupation        TEXT NOT NULL,
    post               TEXT NOT NULL,
    rbac_role           TEXT NOT NULL CHECK (rbac_role IN ('employee','hse_manager','plant_manager','executive')),
    created_at            TEXT NOT NULL
);
-- END PART 4

-- -----------------------------------------------------------------------------
-- Indexes (facility/date/status lookups are the hot paths for the
-- dashboard, filters, and the AI engine's reference-data queries)
-- -----------------------------------------------------------------------------
CREATE INDEX idx_incidents_facility   ON incidents(facility_id);
CREATE INDEX idx_incidents_hazard     ON incidents(hazard_id);
CREATE INDEX idx_incidents_equipment  ON incidents(equipment_id);
CREATE INDEX idx_incidents_datetime   ON incidents(incident_datetime);
CREATE INDEX idx_incidents_contractor ON incidents(involved_contractor_id);
CREATE INDEX idx_risk_assessments_hazard   ON risk_assessments(hazard_id);
CREATE INDEX idx_risk_register_hazard      ON risk_register(hazard_id);
CREATE INDEX idx_actions_status            ON actions(status);
CREATE INDEX idx_actions_owner             ON actions(owner_employee_id);
CREATE INDEX idx_actions_control           ON actions(related_control_id);
CREATE INDEX idx_maintenance_equipment     ON maintenance_records(equipment_id);
CREATE INDEX idx_maintenance_status        ON maintenance_records(status);
CREATE INDEX idx_training_employee         ON training_records(employee_id);
CREATE INDEX idx_training_contractor       ON training_records(contractor_id);
CREATE INDEX idx_control_assessments_control ON control_assessments(control_id);
CREATE INDEX idx_evidence_entity           ON evidence(related_entity_type, related_entity_id);

-- -----------------------------------------------------------------------------
-- Deferred FKs: these three columns reference tables created later in the
-- file than the table they live on (a chicken/egg the CREATE TABLE order
-- can't avoid — incidents <-> maintenance_records <-> risk_register all
-- point at each other). SQLite enforces FKs on INSERT regardless of when
-- the constraint was declared textually, so this is a documentation-only
-- comment for the two forward-reference columns SQLite's ALTER TABLE
-- can't add after the fact (it does not support ADD CONSTRAINT):
--   incidents.related_risk_register_id   -> risk_register.risk_register_id
--   maintenance_records.related_incident_id -> incidents.incident_id
--   control_assessments.related_inspection_id -> inspections.inspection_id
-- The build script validates these three relationships explicitly in its
-- consistency-check pass (see database/validate.py) since SQLite cannot
-- declare the constraint without a table rebuild. On Postgres these would
-- simply be declared inline with no special handling.
-- =============================================================================
