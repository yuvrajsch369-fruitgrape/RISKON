# RISKON V0.1 — Database Validation Report

Run against `database/riskon.db`. 31/31 checks passed.

## Consistency checks

| Check | Result | Detail |
|---|---|---|
| SQLite PRAGMA foreign_key_check (all tables) | PASS | OK |
| No duplicate IDs in companies.company_id | PASS | OK |
| No duplicate IDs in facilities.facility_id | PASS | OK |
| No duplicate IDs in roles.role_id | PASS | OK |
| No duplicate IDs in employees.employee_id | PASS | OK |
| No duplicate IDs in contractors.contractor_id | PASS | OK |
| No duplicate IDs in equipment.equipment_id | PASS | OK |
| No duplicate IDs in sops.sop_id | PASS | OK |
| No duplicate IDs in hazards.hazard_id | PASS | OK |
| No duplicate IDs in controls.control_id | PASS | OK |
| No duplicate IDs in maintenance_records.maintenance_record_id | PASS | OK |
| No duplicate IDs in incidents.incident_id | PASS | OK |
| No duplicate IDs in risk_assessments.risk_assessment_id | PASS | OK |
| No duplicate IDs in risk_register.risk_register_id | PASS | OK |
| No duplicate IDs in control_assessments.control_assessment_id | PASS | OK |
| No duplicate IDs in inspections.inspection_id | PASS | OK |
| No duplicate IDs in audit_findings.audit_finding_id | PASS | OK |
| No duplicate IDs in actions.action_id | PASS | OK |
| No duplicate IDs in training_records.training_record_id | PASS | OK |
| No duplicate IDs in evidence.evidence_id | PASS | OK |
| Every incident belongs to a valid facility | PASS | OK |
| Every equipment-referencing incident points to real equipment | PASS | OK |
| Every risk_assessment references a valid hazard | PASS | OK |
| Every risk_register entry references a valid hazard | PASS | OK |
| Every action's declared source record exists (valid related issue) | PASS | OK |
| equipment.last_maintenance_date matches its real maintenance_records history | PASS | OK |
| audit_findings.auditor_name matches auditor_employee_id where set | PASS | OK |
| No impossible dates (incidents/actions/equipment/employees) | PASS | OK |
| Historical events have logically consistent statuses | PASS | OK |
| incidents.related_risk_register_id points to a real risk_register row (where set) | PASS | OK |
| maintenance_records.related_incident_id points to a real incident (where set) | PASS | OK |

## Row-count sanity vs. spec volumes

| Table | Spec target | Actual | Within tolerance |
|---|---|---|---|
| facilities | ~3 | 3 | yes |
| equipment | ~30 | 30 | yes |
| employees | ~30 | 30 | yes |
| contractors | ~20 | 20 | yes |
| incidents | ~100 | 100 | yes |
| risk_assessments | ~50 | 50 | yes |
| hazards | ~75 | 77 | yes |
| actions | ~100 | 100 | yes |
| controls | ~50 | 51 | yes |
| sops | ~30 | 30 | yes |
| inspections | ~75 | 75 | yes |
| maintenance_records | ~50 | 51 | yes |
| training_records | ~50 | 50 | yes |
| audit_findings | ~30 | 30 | yes |

## Summary

All consistency checks passed. No broken foreign keys, no impossible dates, no duplicate IDs, every action traces to a real source record, every incident has a valid facility, every risk traces to a valid hazard, every equipment reference resolves, and status fields are logically consistent with their dates.