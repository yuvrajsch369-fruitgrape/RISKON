#!/usr/bin/env python3
"""Builds the 5 worked AI-reasoning-pipeline examples and validates each
against schemas/ai-reasoning-output.schema.json before writing to examples/.
"""
import json
import uuid
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.load(open(ROOT / "schemas" / "ai-reasoning-output.schema.json"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)


def scalar(value, source, confidence, reasoning, requires_approval, insufficient=False):
    return {
        "value": None if insufficient else value,
        "insufficient_information": insufficient,
        "source": source,
        "confidence": None if insufficient else confidence,
        "reasoning": reasoning,
        "requires_human_approval": requires_approval,
    }


def item(id_, confidence, source, evidence, requires_approval, **extra):
    d = {"id": id_, "confidence": confidence, "source": source, "evidence": evidence,
         "requires_human_approval": requires_approval}
    d.update(extra)
    return d


def ingestion(incident_id, facility_id, reporter_id, raw_text, submitted_at, attachments=False, status="complete"):
    return {
        "incident_id": incident_id, "facility_id": facility_id, "reporter_employee_id": reporter_id,
        "raw_report_text": raw_text, "date_submitted": submitted_at,
        "attachments_present": attachments, "ingestion_status": status,
    }


def review_package(incident_id, summary, stages):
    return {
        "package_id": f"RVW-{uuid.uuid4().hex[:8]}",
        "incident_id": incident_id,
        "summary_for_reviewer": summary,
        "stages_requiring_approval": stages,
        "approval": {
            "decision": "pending", "reviewer_employee_id": None, "reviewed_at": None,
            "comments": None, "edited_fields": [],
        },
    }


APPROVAL_STAGES = [
    "stage_3_classification", "stage_4_hazard_identification", "stage_5_potential_consequences",
    "stage_6_preliminary_severity_assessment", "stage_7_contributing_factors",
    "stage_8_root_cause_hypotheses", "stage_10_control_gaps", "stage_11_recommended_actions",
    "stage_12_risk_register_impact",
]


def wrap(incident_id, run_suffix, stages: dict):
    out = {
        "incident_id": incident_id,
        "schema_version": "1.0.0",
        "pipeline_run_id": f"RUN-{incident_id}-{run_suffix}",
        "generated_at": "2026-09-03T14:32:00Z",
        "model": "claude-sonnet-5",
    }
    out.update(stages)
    return out


examples = []

# ===========================================================================
# EXAMPLE 1 — Forklift / pedestrian near miss
# ===========================================================================
inc_id = "INC-2101"
raw = (
    "While walking through the main aisle near the electric forklift charging station in the "
    "warehouse, I had to jump back when a forklift carrying a pallet turned the corner without "
    "sounding its horn. No contact was made. The operator said the pallet was blocking their view "
    "around the corner. This happened around 2:15pm on day shift. No injuries."
)
stages = {
    "stage_1_ingestion": ingestion(inc_id, "FAC-002", "EMP-0014", raw, "2026-08-14T15:05:00Z"),
    "stage_2_information_extraction": {
        "who_involved": scalar("Reporting pedestrian (warehouse associate); forklift operator (unnamed in report)",
                                "extracted_from_report", 0.9, "Reporter self-identifies as pedestrian; operator is referenced but not named in the text.", False),
        "what_happened": scalar("Forklift carrying a pallet turned a blind corner without sounding its horn; pedestrian stepped back to avoid contact; no contact occurred.",
                                 "extracted_from_report", 0.95, "Directly stated in report body.", False),
        "when_occurred": scalar("Approx. 2:15pm, day shift, 2026-08-14", "extracted_from_report", 0.85, "Reporter states 'around 2:15pm on day shift'; exact minute not confirmed.", False),
        "where_location": scalar("Main warehouse aisle near electric forklift charging station", "extracted_from_report", 0.9, "Directly stated.", False),
        "equipment_involved": scalar("Electric forklift (EQ-0031)", "extracted_from_report", 0.7, "Report identifies 'forklift'; specific unit matched via facility equipment log for the charging-station area.", False),
        "injuries_reported": scalar("None", "extracted_from_report", 0.95, "Reporter explicitly states 'No injuries'.", False),
        "witnesses": scalar(None, "extracted_from_report", None, "Report does not name any witnesses beyond the two involved parties.", False, insufficient=True),
        "environmental_conditions": scalar(None, "extracted_from_report", None, "Lighting, floor condition, and noise levels at the corner are not described in the report.", False, insufficient=True),
    },
    "stage_3_classification": {
        "incident_category": scalar("Forklift / Vehicle Incident", "ai_inference", 0.93, "Event centers on a powered industrial truck interacting with a pedestrian; matches this category's definition directly.", True),
        "incident_type": scalar("Near Miss", "ai_inference", 0.97, "No contact and no injury occurred, but potential for harm was present.", True),
        "hazard_taxonomy_code": scalar("VEH-PED-01", "ai_inference", 0.9, "Maps to the pedestrian/vehicle interaction subcategory of the vehicle-incident taxonomy.", True),
    },
    "stage_4_hazard_identification": {
        "hazards": [
            item("HAZ-1", 0.9, "ai_inference", "Blind corner combined with a load-obstructed operator view creates a pedestrian strike hazard.",
                 True, hazard_type="Forklift / Vehicle Incident", description="Pedestrian-forklift interaction at a blind aisle corner with obstructed operator sightline."),
            item("HAZ-2", 0.75, "ai_inference", "Report states the horn was not sounded at the corner, a control specifically meant to mitigate this hazard.",
                 True, hazard_type="Forklift / Vehicle Incident", description="Non-use of audible warning (horn) at a blind intersection."),
        ],
        "coverage_note": "No hazards beyond the vehicle/pedestrian interaction were identified from the report text.",
    },
    "stage_5_potential_consequences": {
        "consequences": [
            item("CONS-1", 0.85, "ai_inference", "Forklift-pedestrian strikes at blind corners are a recognized high-severity industrial hazard pattern; the pallet load and lack of horn increase strike likelihood in a repeat scenario.",
                 True, description="Pedestrian struck by forklift, resulting in crush injury or fatality.", plausible_worst_case_severity="Critical"),
        ],
        "coverage_note": "Assessment reflects reasonable worst case for this hazard type, not what occurred.",
    },
    "stage_6_preliminary_severity_assessment": {
        "ai_suggested_severity": scalar("Medium", "ai_inference", 0.7,
            "Actual outcome was no-harm (near miss), but the potential consequence (Stage 5) is Critical and the hazard pattern (blind corner, load-obstructed view, no horn) appears likely to recur without controls. Preliminary rating balances actual-harm-none against high recurrence-weighted potential.", True),
        "ai_suggested_recurrence_likelihood": scalar("Likely", "ai_inference", 0.65,
            "No engineering or procedural gap identified in Stage 4/7 appears to have been corrected between incidents; corner geometry and traffic pattern are structural, not one-off.", True),
        "status": "pending_human_confirmation",
        "requires_human_approval": True,
    },
    "stage_7_contributing_factors": {
        "factors": [
            item("CF-1", 0.85, "ai_inference", "Report states pallet load blocked operator's forward view around the corner.", True,
                 category="Equipment", description="Load size/placement obstructed operator sightline."),
            item("CF-2", 0.7, "ai_inference", "Report states horn was not sounded before the turn.", True,
                 category="Human", description="Operator did not sound horn at blind intersection per expected practice."),
            item("CF-3", 0.55, "ai_inference", "No mirror, signage, or pedestrian lane markings are mentioned as present at this corner; typically inferred as absent when a report describes an unmitigated blind-corner event and none are referenced.", True,
                 category="Environmental", description="Aisle corner design lacks visibility aids (unconfirmed - see Stage 9)."),
        ],
        "coverage_note": "Factors limited to what can be inferred from the report; facility layout was not independently inspected.",
    },
    "stage_8_root_cause_hypotheses": {
        "hypotheses": [
            item("RC-1", 0.75, "ai_inference", "Direct combination of Stage 7 factors CF-1 and CF-2 in a location with no cited visibility aid.", True,
                 rank=1, statement="Absence of an engineering control (e.g. convex mirror) at a known blind corner, combined with inconsistent horn-use practice, allowed a load-obstructed forklift to enter a shared pedestrian path undetected.",
                 label="hypothesis_not_confirmed", supporting_evidence="Report confirms blocked view and no horn sounded; corner is on a route pedestrians and forklifts both use."),
            item("RC-2", 0.4, "ai_inference", "Plausible secondary contributor but not directly evidenced in the report text.", True,
                 rank=2, statement="Operator training on horn-use-at-intersections may not be consistently reinforced.",
                 label="hypothesis_not_confirmed", supporting_evidence="General pattern in similar near-miss reports; not confirmed for this specific operator.",
                 contradicting_evidence="No training record was reviewed as part of this report; SOP-0005 (forklift operation) is Active per facility records."),
        ],
        "coverage_note": "Hypotheses are ranked by evidentiary support from the report text alone; a full investigation may surface additional causes.",
    },
    "stage_9_existing_controls": {
        "controls": [
            item("CTRL-1", 0.9, "system_reference", "SOP-0005 governs powered industrial truck operation for this facility and is currently Active.", False,
                 control_description="Powered Industrial Truck (Forklift) Operation SOP, including horn-at-intersection requirement.",
                 control_type="Procedural", status="present", related_sop_id="SOP-0005"),
            item("CTRL-2", 0.3, "extracted_from_report", "Report does not mention a mirror, signage, or marked pedestrian lane at this corner.", False,
                 control_description="Visual aid (convex mirror) or marked pedestrian lane at blind corner.",
                 control_type="Engineering", status="unknown_insufficient_information", related_sop_id=None),
        ],
        "coverage_note": "Control presence for CTRL-1 confirmed against facility SOP register; CTRL-2 status could not be confirmed from the report alone and should be verified by facility walk-down.",
    },
    "stage_10_control_gaps": {
        "gaps": [
            item("GAP-1", 0.75, "ai_inference", "No engineering control (mirror/marking) is confirmed present at a corner where a near miss of this type occurred; SOP-0005 alone did not prevent the event.", True,
                 related_control_id="CTRL-2", gap_description="No confirmed engineering control (mirror or marked pedestrian lane) at the blind corner where the near miss occurred.",
                 required_by_sop_id=None),
            item("GAP-2", 0.6, "ai_inference", "SOP-0005 requires horn use at intersections; report indicates this was not followed on this occasion.", True,
                 related_control_id="CTRL-1", gap_description="Procedural compliance gap: horn-at-intersection requirement in SOP-0005 not followed in this instance.",
                 required_by_sop_id="SOP-0005"),
        ],
        "coverage_note": "Gaps reflect what the report evidences; confirmation requires facility walk-down and operator interview.",
    },
    "stage_11_recommended_actions": {
        "actions": [
            item("ACT-1", 0.8, "ai_inference", "Directly addresses GAP-1; convex mirrors are a standard engineering control for blind warehouse corners.", True,
                 action_type="Preventive", description="Install a convex mirror and repaint/mark a pedestrian lane at the aisle corner near the forklift charging station.",
                 priority="High", suggested_owner_role="Maintenance Technician", suggested_timeframe_days=30,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
            item("ACT-2", 0.7, "ai_inference", "Directly addresses GAP-2; refresher training is the standard corrective response to a procedural compliance gap.", True,
                 action_type="Corrective", description="Refresher training for forklift operators on SOP-0005 horn-at-intersection requirement, with signed acknowledgment.",
                 priority="Medium", suggested_owner_role="Safety Manager", suggested_timeframe_days=14,
                 addresses_gap_ids=["GAP-2"], requires_human_approval=True),
        ],
        "coverage_note": "Two actions proposed, mapped 1:1 to the two identified control gaps.",
    },
    "stage_12_risk_register_impact": {
        "proposed_action": "create_new_risk", "hazard_category": "Forklift / Vehicle Incident",
        "likelihood": scalar(4, "ai_inference", 0.65, "Blind-corner pedestrian/forklift routes with no confirmed engineering control tend to recur; rated Likely per Stage 6.", True),
        "impact": scalar(4, "ai_inference", 0.75, "Stage 5 worst-case consequence is Critical (struck-by, potential fatality); impact rated High-to-Critical band.", True),
        "risk_score": scalar(16, "derived_from_prior_stage", None, "likelihood (4) x impact (4) = 16.", True),
        "risk_level": scalar("High", "derived_from_prior_stage", None, "Score of 16 falls in the High band (12-19) per facility risk matrix.", True),
        "existing_risk_assessment_id": None,
        "reasoning": "No existing risk register entry covers this specific blind-corner pedestrian/vehicle interaction; proposing a new entry.",
        "requires_human_approval": True, "write_status": "not_written_pending_approval",
    },
    "stage_13_human_review_package": review_package(
        inc_id,
        "Near-miss forklift/pedestrian event at a blind warehouse corner. No injury occurred. AI identifies a likely engineering-control gap (no mirror/marking) plus a procedural compliance gap (horn not sounded), and proposes a new High risk-register entry pending your review.",
        APPROVAL_STAGES,
    ),
}
examples.append(("incident-01-forklift-pedestrian-near-miss.json", wrap(inc_id, "A1", stages)))

# ===========================================================================
# EXAMPLE 2 — Machine-guarding incident
# ===========================================================================
inc_id = "INC-2102"
raw = (
    "Operator was clearing a jam on the punch press when their glove got caught between the die "
    "and the guard, which was found propped open with a wood block. Operator pulled hand back "
    "before the press cycled again. Minor cut to the back of the hand, treated with first aid on "
    "site. Machine was locked out after the incident. This occurred on night shift around 11pm."
)
stages = {
    "stage_1_ingestion": ingestion(inc_id, "FAC-001", "EMP-0022", raw, "2026-07-02T23:40:00Z"),
    "stage_2_information_extraction": {
        "who_involved": scalar("Punch press operator (reporter)", "extracted_from_report", 0.9, "Reporter is the operator involved.", False),
        "what_happened": scalar("Operator's glove was caught between die and guard while clearing a jam; guard was found propped open with a wood block; operator withdrew hand before next cycle; minor hand laceration.", "extracted_from_report", 0.95, "Directly stated.", False),
        "when_occurred": scalar("Approx. 11:00pm, night shift, 2026-07-02", "extracted_from_report", 0.8, "Reporter states 'around 11pm' on night shift.", False),
        "where_location": scalar("Punch press station (production floor)", "extracted_from_report", 0.85, "Inferred from equipment context; specific bay not named.", False),
        "equipment_involved": scalar("Punch Press (EQ-0009)", "extracted_from_report", 0.75, "Report identifies 'punch press'; matched to facility equipment log.", False),
        "injuries_reported": scalar("Minor laceration to back of hand, treated with on-site first aid", "extracted_from_report", 0.9, "Directly stated.", False),
        "witnesses": scalar(None, "extracted_from_report", None, "No witnesses named in report.", False, insufficient=True),
        "environmental_conditions": scalar("Night shift", "extracted_from_report", 0.6, "Only shift timing given; lighting/staffing levels not described.", False),
    },
    "stage_3_classification": {
        "incident_category": scalar("Machine Guarding Failure", "ai_inference", 0.95, "A guard was defeated (propped open) and directly implicated in exposure to a pinch point.", True),
        "incident_type": scalar("Injury", "ai_inference", 0.95, "First-aid-level injury was sustained.", True),
        "hazard_taxonomy_code": scalar("MACH-GRD-02", "ai_inference", 0.9, "Maps to defeated/bypassed machine guard subcategory.", True),
    },
    "stage_4_hazard_identification": {
        "hazards": [
            item("HAZ-1", 0.95, "ai_inference", "Guard explicitly found propped open with a wood block, exposing the die pinch point during jam-clearing.", True,
                 hazard_type="Machine Guarding Failure", description="Guard defeated (propped open), exposing operator to die pinch point."),
            item("HAZ-2", 0.6, "ai_inference", "Clearing a jam by hand while the machine is not confirmed de-energized is a recognized caught-in hazard, consistent with this event.", True,
                 hazard_type="Caught-In / Caught-Between", description="Manual jam-clearing without confirmed lockout/tagout of the press."),
        ],
        "coverage_note": "Two related hazards identified: the defeated guard itself, and the jam-clearing practice that placed a hand in the point of operation.",
    },
    "stage_5_potential_consequences": {
        "consequences": [
            item("CONS-1", 0.9, "ai_inference", "Point-of-operation press hazards with a defeated guard and no confirmed lockout are associated with amputation-level injuries in similar incidents.", True,
                 description="Amputation or crush injury to hand/fingers if press cycled while hand was in the die area.", plausible_worst_case_severity="Critical"),
        ],
        "coverage_note": "Reflects worst-case for this hazard pattern, not what occurred (actual injury was a minor laceration).",
    },
    "stage_6_preliminary_severity_assessment": {
        "ai_suggested_severity": scalar("High", "ai_inference", 0.8,
            "Actual injury was minor, but a defeated guard plus unlocked point-of-operation access during jam-clearing is a high-severity hazard pattern with narrowly avoided amputation potential (Stage 5). Rated above actual-harm level due to control failure severity.", True),
        "ai_suggested_recurrence_likelihood": scalar("Possible", "ai_inference", 0.55,
            "Machine was locked out after this event, which may reduce near-term recurrence, but the underlying practice of propping guards during jam-clearing is not confirmed as corrected.", True),
        "status": "pending_human_confirmation",
        "requires_human_approval": True,
    },
    "stage_7_contributing_factors": {
        "factors": [
            item("CF-1", 0.9, "ai_inference", "Report explicitly states the guard was propped open with a wood block.", True,
                 category="Procedural", description="Guard intentionally defeated to facilitate jam-clearing access."),
            item("CF-2", 0.6, "ai_inference", "Report does not state the press was locked out before jam-clearing began (only that it was locked out after the incident).", True,
                 category="Procedural", description="Jam likely cleared without confirmed prior lockout/tagout of the press."),
            item("CF-3", 0.4, "ai_inference", "Night shift context with unconfirmed staffing/supervision levels is a commonly associated factor in guard-defeat incidents, though not directly evidenced here.", True,
                 category="Organizational", description="Reduced night-shift oversight of guarding practices (unconfirmed)."),
        ],
        "coverage_note": "CF-1 is directly evidenced; CF-2 and CF-3 are inferred and should be confirmed by investigation.",
    },
    "stage_8_root_cause_hypotheses": {
        "hypotheses": [
            item("RC-1", 0.8, "ai_inference", "Guard defeat is a known workaround when jam-clearing is frequent and guard design impedes quick access; consistent with a wood block being readily used.", True,
                 rank=1, statement="Frequent jams on this press create pressure to bypass the guard for faster clearing, and no safe/quick jam-clearing procedure with guard intact is in place or followed.",
                 label="hypothesis_not_confirmed", supporting_evidence="Guard found propped open specifically to allow jam access; suggests a recurring workaround rather than a one-off."),
            item("RC-2", 0.5, "ai_inference", "LOTO omission before manual intervention is a common contributor to point-of-operation injuries.", True,
                 rank=2, statement="LOTO was not applied before manual jam-clearing began, removing the last-line control once the guard was already defeated.",
                 label="hypothesis_not_confirmed", supporting_evidence="Report only confirms lockout occurred after the incident, not before jam-clearing.",
                 contradicting_evidence="SOP-0001 (LOTO) is Active for this facility; whether it was followed for jam-clearing specifically is unconfirmed."),
        ],
        "coverage_note": "Frequency-of-jams data was not available in the report; recommend maintenance log review to confirm RC-1.",
    },
    "stage_9_existing_controls": {
        "controls": [
            item("CTRL-1", 0.9, "system_reference", "SOP-0001 (LOTO) is Active for this facility and applies to maintenance/jam-clearing on production equipment.", False,
                 control_description="Lockout/Tagout Procedure covering press jam-clearing.", control_type="Procedural", status="present", related_sop_id="SOP-0001"),
            item("CTRL-2", 0.9, "extracted_from_report", "Physical guard exists on the press (it was propped open, implying it is normally closed/functional).", False,
                 control_description="Fixed/interlocked guard over die point of operation.", control_type="Engineering", status="present", related_sop_id=None),
            item("CTRL-3", 0.3, "extracted_from_report", "Report does not mention a documented safe jam-clearing procedure distinct from general LOTO.", False,
                 control_description="Specific jam-clearing work instruction for this press.", control_type="Procedural", status="unknown_insufficient_information", related_sop_id=None),
        ],
        "coverage_note": "CTRL-1 and CTRL-2 confirmed present; CTRL-3 (jam-specific procedure) could not be confirmed from the report.",
    },
    "stage_10_control_gaps": {
        "gaps": [
            item("GAP-1", 0.85, "ai_inference", "Guard was defeated and LOTO does not appear to have been applied before manual access, meaning both the engineering control and the procedural control failed simultaneously.", True,
                 related_control_id="CTRL-2", gap_description="Guard was defeatable/defeated with a simple physical object (wood block) rather than requiring a controlled, logged override.",
                 required_by_sop_id=None),
            item("GAP-2", 0.6, "ai_inference", "No confirmed jam-specific safe-clearing procedure, which may be why operators default to propping the guard.", True,
                 related_control_id="CTRL-3", gap_description="No confirmed documented procedure for safely clearing jams on this press without defeating the guard.",
                 required_by_sop_id=None),
        ],
        "coverage_note": "Gaps target both the physical guard defeat and the likely underlying workflow pressure causing it.",
    },
    "stage_11_recommended_actions": {
        "actions": [
            item("ACT-1", 0.85, "ai_inference", "Directly addresses GAP-1; interlocked guards that cannot be propped open are a standard engineering fix for this exact failure mode.", True,
                 action_type="Corrective", description="Replace or retrofit the punch press guard with an interlocked guard that stops the press when opened, and remove ability to prop it open.",
                 priority="Critical", suggested_owner_role="Mechanical Engineer", suggested_timeframe_days=30,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
            item("ACT-2", 0.7, "ai_inference", "Directly addresses GAP-2; a documented safe jam-clearing procedure with mandatory LOTO removes the incentive to bypass the guard.", True,
                 action_type="Preventive", description="Develop and train a documented jam-clearing work instruction for the punch press that mandates LOTO before any manual access.",
                 priority="High", suggested_owner_role="Safety Manager", suggested_timeframe_days=21,
                 addresses_gap_ids=["GAP-2"], requires_human_approval=True),
            item("ACT-3", 0.6, "ai_inference", "Immediate containment action independent of root-cause fix, appropriate given the severity of the near-amputation exposure.", True,
                 action_type="Corrective", description="Retrain all punch press operators on the requirement to never defeat machine guards, with signed acknowledgment.",
                 priority="High", suggested_owner_role="Shift Supervisor", suggested_timeframe_days=7,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
        ],
        "coverage_note": "Three actions: one engineering fix, one procedural fix, one immediate behavioral reinforcement.",
    },
    "stage_12_risk_register_impact": {
        "proposed_action": "create_new_risk", "hazard_category": "Machine Guarding Failure",
        "likelihood": scalar(3, "ai_inference", 0.6, "Guard-defeat workarounds tend to recur until the underlying jam-frequency/procedure issue is fixed; rated Possible per Stage 6.", True),
        "impact": scalar(5, "ai_inference", 0.85, "Stage 5 worst case is amputation/crush injury; impact rated at the top of the scale for point-of-operation press hazards.", True),
        "risk_score": scalar(15, "derived_from_prior_stage", None, "likelihood (3) x impact (5) = 15.", True),
        "risk_level": scalar("High", "derived_from_prior_stage", None, "Score of 15 falls in the High band (12-19) per facility risk matrix.", True),
        "existing_risk_assessment_id": None,
        "reasoning": "No existing risk register entry specifically covers guard-defeat on this press; proposing a new entry given the severity of the exposure.",
        "requires_human_approval": True, "write_status": "not_written_pending_approval",
    },
    "stage_13_human_review_package": review_package(
        inc_id,
        "Operator sustained a minor hand laceration after a defeated punch-press guard (propped open) exposed the die pinch point during jam-clearing. AI flags this as a High-severity near-amputation exposure despite the minor actual injury, identifies a likely LOTO-before-jam-clearing gap, and proposes three actions plus a new High risk-register entry.",
        APPROVAL_STAGES,
    ),
}
examples.append(("incident-02-machine-guarding.json", wrap(inc_id, "A2", stages)))

# ===========================================================================
# EXAMPLE 3 — Chemical spill
# ===========================================================================
inc_id = "INC-2103"
raw = (
    "A 5-gallon container of degreasing solvent was being transferred at the parts-cleaning "
    "station when the hose connector failed, spilling an estimated 2-3 gallons onto the floor. "
    "The spill reached a nearby floor drain before the area could be contained. Two employees "
    "in the area evacuated per procedure; no injuries or skin contact reported. Spill kit was "
    "used to contain the remainder. EHS was notified. Occurred on day shift."
)
stages = {
    "stage_1_ingestion": ingestion(inc_id, "FAC-003", "EMP-0027", raw, "2026-05-19T10:12:00Z"),
    "stage_2_information_extraction": {
        "who_involved": scalar("Two employees in the parts-cleaning area at time of spill (not individually named)", "extracted_from_report", 0.8, "Report references 'two employees' without names.", False),
        "what_happened": scalar("Hose connector failure during solvent transfer released an estimated 2-3 gallons of degreasing solvent; spill reached a floor drain before containment; spill kit used; EHS notified.", "extracted_from_report", 0.92, "Directly stated.", False),
        "when_occurred": scalar("Day shift, 2026-05-19 (exact time not given)", "extracted_from_report", 0.6, "Only shift is specified, not a clock time.", False),
        "where_location": scalar("Parts-cleaning station", "extracted_from_report", 0.9, "Directly stated.", False),
        "equipment_involved": scalar("Solvent transfer hose/connector at parts-cleaning station", "extracted_from_report", 0.65, "Report identifies the hose connector as the failure point; not matched to a specific facility equipment ID.", False),
        "injuries_reported": scalar("None; no skin contact reported", "extracted_from_report", 0.9, "Directly stated.", False),
        "witnesses": scalar("Two employees present in the area (unnamed)", "extracted_from_report", 0.5, "Referenced generically, not individually identified.", False),
        "environmental_conditions": scalar(None, "extracted_from_report", None, "Ventilation status and containment/berm condition at the station are not described.", False, insufficient=True),
    },
    "stage_3_classification": {
        "incident_category": scalar("Environmental Spill / Release", "ai_inference", 0.9, "Event is a chemical release reaching a floor drain, matching this category.", True),
        "incident_type": scalar("Environmental", "ai_inference", 0.85, "No injury occurred; primary exposure is environmental release risk via the floor drain.", True),
        "hazard_taxonomy_code": scalar("ENV-SPILL-03", "ai_inference", 0.85, "Maps to chemical spill with potential drain/waterway pathway.", True),
    },
    "stage_4_hazard_identification": {
        "hazards": [
            item("HAZ-1", 0.9, "ai_inference", "Spill explicitly reached a floor drain before containment, per report.", True,
                 hazard_type="Environmental Spill / Release", description="Solvent release reaching a floor drain with potential discharge to the sewer/environment."),
            item("HAZ-2", 0.5, "ai_inference", "Solvent spills of this volume in an enclosed area commonly carry inhalation exposure risk; not directly evidenced but a standard associated hazard for this chemical/quantity.", True,
                 hazard_type="Chemical Exposure", description="Potential inhalation exposure to solvent vapors during the spill/evacuation window."),
        ],
        "coverage_note": "Primary hazard (drain pathway) is directly evidenced; secondary vapor-exposure hazard is inferred from chemical/volume, not confirmed by air monitoring data in the report.",
    },
    "stage_5_potential_consequences": {
        "consequences": [
            item("CONS-1", 0.75, "ai_inference", "Uncontained solvent reaching a floor drain is a recognized pathway to reportable environmental discharge.", True,
                 description="Environmental discharge requiring regulatory notification if drain connects to sewer/waterway.", plausible_worst_case_severity="High"),
            item("CONS-2", 0.4, "ai_inference", "If ventilation was inadequate, prolonged exposure before evacuation could plausibly cause respiratory irritation.", True,
                 description="Respiratory irritation or exposure symptoms in employees present before evacuation.", plausible_worst_case_severity="Medium"),
        ],
        "coverage_note": "CONS-1 reflects the directly evidenced drain pathway; CONS-2 is a lower-confidence secondary hypothesis.",
    },
    "stage_6_preliminary_severity_assessment": {
        "ai_suggested_severity": scalar("Medium", "ai_inference", 0.65,
            "No injury or confirmed environmental discharge occurred and evacuation/containment procedure was followed, but the drain pathway (Stage 5, CONS-1) creates meaningful regulatory/environmental exposure pending confirmation of where the drain leads.", True),
        "ai_suggested_recurrence_likelihood": scalar("Possible", "ai_inference", 0.5,
            "Hose connector failure is an equipment-condition issue; recurrence likelihood depends on whether this connector/hose type is used at other stations (unconfirmed).", True),
        "status": "pending_human_confirmation",
        "requires_human_approval": True,
    },
    "stage_7_contributing_factors": {
        "factors": [
            item("CF-1", 0.85, "ai_inference", "Report directly attributes the spill to hose connector failure.", True,
                 category="Equipment", description="Hose connector failure during solvent transfer."),
            item("CF-2", 0.55, "ai_inference", "Spill reaching the drain before containment suggests either no secondary containment (berm/drain cover) was in place, or containment response time exceeded the spill spread rate.", True,
                 category="Procedural", description="Insufficient secondary containment or delayed spill response relative to spread to the drain."),
            item("CF-3", 0.3, "ai_inference", "Connector failures can stem from wear/inspection gaps; plausible but not evidenced in this report.", True,
                 category="Equipment", description="Possible inadequate inspection/replacement interval for transfer hose connectors (unconfirmed)."),
        ],
        "coverage_note": "CF-1 is directly evidenced; CF-2 and CF-3 are inferred from the outcome and should be confirmed by inspecting the failed connector and station layout.",
    },
    "stage_8_root_cause_hypotheses": {
        "hypotheses": [
            item("RC-1", 0.6, "ai_inference", "Consistent with CF-1 and CF-3; equipment failures at a transfer point often trace to wear not caught by inspection.", True,
                 rank=1, statement="The hose connector failed due to wear or damage that was not identified in a preventive inspection cycle.",
                 label="hypothesis_not_confirmed", supporting_evidence="Connector is confirmed as the failure point in the report.",
                 contradicting_evidence="No maintenance/inspection record for this connector was available to this analysis."),
            item("RC-2", 0.45, "ai_inference", "Consistent with CF-2; absence of a drain cover or containment berm at a solvent transfer point is a common design gap.", True,
                 rank=2, statement="The parts-cleaning station lacks secondary containment (e.g. drain cover, spill berm) sufficient to prevent a moderate-volume spill from reaching the floor drain.",
                 label="hypothesis_not_confirmed", supporting_evidence="Spill reached the drain despite spill kit response, suggesting the drain was not pre-protected."),
        ],
        "coverage_note": "Both hypotheses require facility walk-down/maintenance-record confirmation; report text does not directly address inspection history or containment design.",
    },
    "stage_9_existing_controls": {
        "controls": [
            item("CTRL-1", 0.85, "system_reference", "SOP-0015 (Spill Prevention & Response Plan) is Active for this facility.", False,
                 control_description="Spill Prevention & Response Plan, including evacuation and spill-kit use.", control_type="Procedural", status="present", related_sop_id="SOP-0015"),
            item("CTRL-2", 0.85, "extracted_from_report", "Report confirms a spill kit was used to contain the remainder of the spill.", False,
                 control_description="On-site spill kit at/near parts-cleaning station.", control_type="Engineering", status="present", related_sop_id=None),
            item("CTRL-3", 0.3, "extracted_from_report", "Report does not mention a drain cover or containment berm at the station.", False,
                 control_description="Drain cover or secondary containment berm at parts-cleaning station.", control_type="Engineering", status="unknown_insufficient_information", related_sop_id=None),
        ],
        "coverage_note": "Evacuation and spill-kit response controls functioned as intended; drain-specific containment control status is unconfirmed.",
    },
    "stage_10_control_gaps": {
        "gaps": [
            item("GAP-1", 0.6, "ai_inference", "Spill reached the drain despite response controls functioning, indicating a missing preventive (not just reactive) control at the drain itself.", True,
                 related_control_id="CTRL-3", gap_description="No confirmed drain cover/containment berm to prevent spills from reaching the floor drain before manual response.",
                 required_by_sop_id="SOP-0015"),
            item("GAP-2", 0.5, "ai_inference", "Connector failure suggests inspection/replacement interval for transfer equipment may not be catching wear before failure.", True,
                 related_control_id=None, gap_description="No confirmed preventive inspection/replacement schedule for solvent transfer hose connectors.",
                 required_by_sop_id=None),
        ],
        "coverage_note": "Both gaps target prevention of recurrence rather than response, since the response itself (evacuation, spill kit, EHS notification) worked as intended.",
    },
    "stage_11_recommended_actions": {
        "actions": [
            item("ACT-1", 0.65, "ai_inference", "Directly addresses GAP-1; drain covers/berms are the standard engineering control for this exact failure pathway.", True,
                 action_type="Preventive", description="Install a drain cover or spill berm at the parts-cleaning station floor drain.",
                 priority="High", suggested_owner_role="Maintenance Technician", suggested_timeframe_days=21,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
            item("ACT-2", 0.55, "ai_inference", "Directly addresses GAP-2; a defined inspection interval reduces recurrence of connector-failure-type spills.", True,
                 action_type="Preventive", description="Establish and document a periodic inspection/replacement schedule for solvent transfer hoses and connectors facility-wide.",
                 priority="Medium", suggested_owner_role="Maintenance Technician", suggested_timeframe_days=45,
                 addresses_gap_ids=["GAP-2"], requires_human_approval=True),
            item("ACT-3", 0.5, "ai_inference", "Confirms whether Stage 5 CONS-1 (environmental discharge) materialized, which determines if regulatory notification is required.", True,
                 action_type="Corrective", description="Confirm floor drain destination (sewer vs. contained system) with facility engineering and determine if regulatory notification is required for this event.",
                 priority="High", suggested_owner_role="Environmental Compliance Officer", suggested_timeframe_days=5,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
        ],
        "coverage_note": "ACT-3 is a fact-finding action, not a physical fix -- included because the report does not state where the drain leads, and this determines regulatory obligations the AI cannot assess on its own.",
    },
    "stage_12_risk_register_impact": {
        "proposed_action": "create_new_risk", "hazard_category": "Environmental Spill / Release",
        "likelihood": scalar(3, "ai_inference", 0.5, "Equipment-wear-driven connector failures are Possible without a confirmed inspection interval (Stage 10, GAP-2).", True),
        "impact": scalar(4, "ai_inference", 0.65, "Stage 5 worst case includes potential reportable environmental discharge, rated High impact pending drain-destination confirmation (ACT-3).", True),
        "risk_score": scalar(12, "derived_from_prior_stage", None, "likelihood (3) x impact (4) = 12.", True),
        "risk_level": scalar("High", "derived_from_prior_stage", None, "Score of 12 falls at the lower bound of the High band (12-19) per facility risk matrix.", True),
        "existing_risk_assessment_id": None,
        "reasoning": "No existing risk register entry covers solvent transfer spill/drain pathway at this station; proposing a new entry.",
        "requires_human_approval": True, "write_status": "not_written_pending_approval",
    },
    "stage_13_human_review_package": review_package(
        inc_id,
        "Solvent spill (est. 2-3 gal) from a failed hose connector at the parts-cleaning station reached a floor drain before containment. No injuries; evacuation and spill-kit response followed procedure. AI flags an unconfirmed drain-containment gap and recommends confirming whether this constitutes a reportable environmental discharge.",
        APPROVAL_STAGES,
    ),
}
examples.append(("incident-03-chemical-spill.json", wrap(inc_id, "A3", stages)))

# ===========================================================================
# EXAMPLE 4 — Working-at-height near miss
# ===========================================================================
inc_id = "INC-2104"
raw = (
    "Maintenance tech was on a rolling ladder replacing an air filter on the ventilation unit "
    "above the paint booth, approximately 10 feet up. The ladder shifted when the tech reached "
    "to the side, but they were able to grab the adjacent structural beam and climb down safely. "
    "No fall occurred. Tech was not using fall protection at the time, stating the job 'usually "
    "takes a few minutes.' Reported same day, afternoon."
)
stages = {
    "stage_1_ingestion": ingestion(inc_id, "FAC-001", "EMP-0009", raw, "2026-06-27T16:20:00Z"),
    "stage_2_information_extraction": {
        "who_involved": scalar("Maintenance technician (reporter)", "extracted_from_report", 0.9, "Reporter is the technician involved.", False),
        "what_happened": scalar("Rolling ladder shifted while tech reached to the side at ~10 ft height; tech grabbed an adjacent structural beam and climbed down safely; no fall occurred; fall protection was not in use.", "extracted_from_report", 0.95, "Directly stated.", False),
        "when_occurred": scalar("Afternoon, same day as report (2026-06-27)", "extracted_from_report", 0.7, "Only 'afternoon' given, no exact time.", False),
        "where_location": scalar("Above the paint booth, ventilation unit access point", "extracted_from_report", 0.85, "Directly stated.", False),
        "equipment_involved": scalar("Rolling ladder; ventilation unit above paint booth (EQ-0044)", "extracted_from_report", 0.7, "Ladder and ventilation unit both named; ventilation unit matched to facility equipment log.", False),
        "injuries_reported": scalar("None", "extracted_from_report", 0.95, "Directly stated no fall occurred.", False),
        "witnesses": scalar(None, "extracted_from_report", None, "No witnesses mentioned in report.", False, insufficient=True),
        "environmental_conditions": scalar("Height approx. 10 feet; work performed on a rolling (mobile) ladder", "extracted_from_report", 0.8, "Directly stated.", False),
    },
    "stage_3_classification": {
        "incident_category": scalar("Fall / Working at Height", "ai_inference", 0.9, "Event involves elevated work on a mobile ladder with an unstable-ladder near-fall event.", True),
        "incident_type": scalar("Near Miss", "ai_inference", 0.95, "No fall occurred; tech self-recovered.", True),
        "hazard_taxonomy_code": scalar("HT-LADR-01", "ai_inference", 0.85, "Maps to unsecured mobile ladder / height-work subcategory.", True),
    },
    "stage_4_hazard_identification": {
        "hazards": [
            item("HAZ-1", 0.9, "ai_inference", "Report explicitly states the ladder shifted at height and the tech had to grab a beam to avoid falling.", True,
                 hazard_type="Fall / Working at Height", description="Unstable/unsecured rolling ladder shifting during elevated work, creating fall risk."),
            item("HAZ-2", 0.85, "ai_inference", "Report explicitly states fall protection was not in use at ~10 feet.", True,
                 hazard_type="Fall / Working at Height", description="Elevated work performed without fall protection at a height where it would typically be required."),
        ],
        "coverage_note": "Both the equipment-stability hazard and the missing-fall-protection hazard are directly evidenced.",
    },
    "stage_5_potential_consequences": {
        "consequences": [
            item("CONS-1", 0.85, "ai_inference", "A fall from ~10 feet without fall protection is a well-established severe-injury/fatality hazard pattern.", True,
                 description="Fall from height resulting in serious injury or fatality.", plausible_worst_case_severity="Critical"),
        ],
        "coverage_note": "Reflects the worst-case outcome the near-miss narrowly avoided.",
    },
    "stage_6_preliminary_severity_assessment": {
        "ai_suggested_severity": scalar("High", "ai_inference", 0.8,
            "No injury occurred, but the combination of an actual ladder-instability event at height with no fall protection in use represents a high-severity near miss with narrowly avoided critical outcome (Stage 5).", True),
        "ai_suggested_recurrence_likelihood": scalar("Likely", "ai_inference", 0.7,
            "Tech's stated reasoning ('usually takes a few minutes') suggests this is a routine practice for short-duration height tasks, not a one-off lapse, implying high recurrence risk absent a control change.", True),
        "status": "pending_human_confirmation",
        "requires_human_approval": True,
    },
    "stage_7_contributing_factors": {
        "factors": [
            item("CF-1", 0.85, "ai_inference", "Report states the ladder shifted when the tech reached to the side, a known instability mode for rolling ladders under lateral load.", True,
                 category="Equipment", description="Rolling ladder instability under lateral reaching load."),
            item("CF-2", 0.9, "ai_inference", "Report directly quotes the tech's rationale for skipping fall protection.", True,
                 category="Human", description="Tech's own stated risk-normalization ('usually takes a few minutes') for a short-duration task."),
            item("CF-3", 0.4, "ai_inference", "Short-duration height tasks are a commonly cited driver of fall-protection non-compliance in industry data; consistent with but not separately evidenced here.", True,
                 category="Organizational", description="Possible gap in enforcement of fall-protection requirements for short-duration tasks (unconfirmed)."),
        ],
        "coverage_note": "CF-1 and CF-2 are directly evidenced by the report; CF-3 is an inferred organizational pattern requiring confirmation.",
    },
    "stage_8_root_cause_hypotheses": {
        "hypotheses": [
            item("RC-1", 0.75, "ai_inference", "Directly supported by CF-2, the tech's own quoted rationale.", True,
                 rank=1, statement="Fall protection is being routinely skipped for tasks perceived as short-duration, indicating a gap between the written fall-protection requirement and actual practice for quick maintenance tasks.",
                 label="hypothesis_not_confirmed", supporting_evidence="Tech directly attributes the omission to task duration expectation, not to unavailability of equipment."),
            item("RC-2", 0.35, "ai_inference", "Plausible equipment condition contributor but not directly evidenced.", True,
                 rank=2, statement="The rolling ladder's wheels/locks may not have been properly engaged or inspected before use.",
                 label="hypothesis_not_confirmed", supporting_evidence="Ladder shifted during use.",
                 contradicting_evidence="Report does not describe the ladder's lock/wheel state before or after the shift."),
        ],
        "coverage_note": "RC-1 is well-supported by the tech's own statement; RC-2 would require inspecting the specific ladder used.",
    },
    "stage_9_existing_controls": {
        "controls": [
            item("CTRL-1", 0.85, "system_reference", "SOP-0011 (Fall Protection Program) is Active for this facility.", False,
                 control_description="Fall Protection Program covering elevated work.", control_type="Procedural", status="present", related_sop_id="SOP-0011"),
            item("CTRL-2", 0.9, "extracted_from_report", "Report explicitly states fall protection was not in use.", False,
                 control_description="Personal fall arrest/restraint system for ladder work at height.", control_type="PPE", status="absent", related_sop_id="SOP-0011"),
        ],
        "coverage_note": "The governing SOP exists and is active; the PPE control it requires was confirmed absent in this specific instance.",
    },
    "stage_10_control_gaps": {
        "gaps": [
            item("GAP-1", 0.85, "ai_inference", "SOP-0011 requires fall protection for elevated work; this instance shows non-compliance, and the tech's stated reasoning suggests it may not be an isolated case.", True,
                 related_control_id="CTRL-2", gap_description="Fall protection requirement in SOP-0011 not followed for short-duration ladder tasks; possible broader practice gap, not a single lapse.",
                 required_by_sop_id="SOP-0011"),
        ],
        "coverage_note": "Single, well-evidenced gap: PPE requirement not applied in practice for this task type.",
    },
    "stage_11_recommended_actions": {
        "actions": [
            item("ACT-1", 0.75, "ai_inference", "Directly addresses GAP-1; reinforces the existing SOP-0011 requirement with no duration exception.", True,
                 action_type="Corrective", description="Retrain maintenance staff that SOP-0011 fall-protection requirements apply regardless of task duration; obtain signed acknowledgment.",
                 priority="High", suggested_owner_role="Safety Manager", suggested_timeframe_days=14,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
            item("ACT-2", 0.55, "ai_inference", "Addresses CF-1/RC-2 equipment-condition hypothesis; a targeted inspection is low-cost and directly relevant.", True,
                 action_type="Preventive", description="Inspect the specific rolling ladder used (wheel locks, stability) and include in routine ladder inspection program if not already covered.",
                 priority="Medium", suggested_owner_role="Maintenance Technician", suggested_timeframe_days=14,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
            item("ACT-3", 0.5, "ai_inference", "Addresses the recurrence risk implied by CF-2/RC-1 by evaluating whether a faster-to-deploy fall protection option exists for brief tasks, reducing the incentive to skip it.", True,
                 action_type="Preventive", description="Evaluate providing quicker-to-don fall protection (e.g. pre-rigged anchor points near the paint booth ventilation unit) to reduce time-pressure incentive to skip PPE.",
                 priority="Medium", suggested_owner_role="Mechanical Engineer", suggested_timeframe_days=60,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
        ],
        "coverage_note": "Actions address both immediate compliance (ACT-1) and the underlying time-pressure driver behind the gap (ACT-3).",
    },
    "stage_12_risk_register_impact": {
        "proposed_action": "create_new_risk", "hazard_category": "Fall / Working at Height",
        "likelihood": scalar(4, "ai_inference", 0.7, "Tech's own statement suggests this is routine practice for short tasks, not isolated; rated Likely per Stage 6.", True),
        "impact": scalar(5, "ai_inference", 0.85, "Stage 5 worst case is a fall from height resulting in fatality; impact rated at the top of the scale.", True),
        "risk_score": scalar(20, "derived_from_prior_stage", None, "likelihood (4) x impact (5) = 20.", True),
        "risk_level": scalar("Critical", "derived_from_prior_stage", None, "Score of 20 falls in the Critical band (20-25) per facility risk matrix.", True),
        "existing_risk_assessment_id": None,
        "reasoning": "No existing risk register entry covers fall-protection non-compliance for short-duration elevated maintenance tasks; proposing a new Critical-band entry given the severity and apparent routineness of the practice gap.",
        "requires_human_approval": True, "write_status": "not_written_pending_approval",
    },
    "stage_13_human_review_package": review_package(
        inc_id,
        "Maintenance tech avoided a fall from ~10 ft when a rolling ladder shifted; fall protection was not in use, and the tech's own statement suggests this is routine for short tasks. AI proposes a Critical risk-register entry and three actions, prioritizing reinforcement of the existing fall-protection SOP.",
        APPROVAL_STAGES,
    ),
}
examples.append(("incident-04-working-at-height-near-miss.json", wrap(inc_id, "A4", stages)))

# ===========================================================================
# EXAMPLE 5 — Contractor safety incident
# ===========================================================================
inc_id = "INC-2105"
raw = (
    "A contractor from an outside electrical firm was performing panel work in the main "
    "distribution room and was found by a shift supervisor working on an energized panel "
    "without a visible LOTO tag or permit on file at the facility. The contractor stated their "
    "company 'has its own safety process.' Work was stopped immediately and the contractor was "
    "escorted from the panel area. No injury occurred. Facility EHS was notified."
)
stages = {
    "stage_1_ingestion": ingestion(inc_id, "FAC-002", "EMP-0006", raw, "2026-08-30T09:50:00Z"),
    "stage_2_information_extraction": {
        "who_involved": scalar("Outside electrical contractor (unnamed, firm unnamed); shift supervisor (reporter, EMP-0006)", "extracted_from_report", 0.85, "Report identifies roles but not the contractor's name or firm name.", False),
        "what_happened": scalar("Contractor found working on an energized electrical panel without a visible LOTO tag or an on-file permit; work stopped and contractor escorted from area; no injury; EHS notified.", "extracted_from_report", 0.95, "Directly stated.", False),
        "when_occurred": scalar("2026-08-30, exact time not given", "extracted_from_report", 0.6, "Report submitted same-day; specific time of observation not stated.", False),
        "where_location": scalar("Main electrical distribution room", "extracted_from_report", 0.9, "Directly stated.", False),
        "equipment_involved": scalar("Energized electrical distribution panel", "extracted_from_report", 0.75, "Directly referenced; specific panel ID not given.", False),
        "injuries_reported": scalar("None", "extracted_from_report", 0.95, "Directly stated.", False),
        "witnesses": scalar("Shift supervisor (reporter) directly observed the condition", "extracted_from_report", 0.8, "Reporter is the observing witness.", False),
        "environmental_conditions": scalar(None, "extracted_from_report", None, "Panel energization details (voltage, PPE worn by contractor) are not described.", False, insufficient=True),
    },
    "stage_3_classification": {
        "incident_category": scalar("Contractor Safety Incident", "ai_inference", 0.9, "Event involves a third-party contractor's non-compliance with facility safety requirements, not a facility employee.", True),
        "incident_type": scalar("Near Miss", "ai_inference", 0.85, "No injury occurred, but exposure to an energized panel without LOTO is a significant averted-harm event.", True),
        "hazard_taxonomy_code": scalar("CTR-LOTO-01", "ai_inference", 0.8, "Maps to contractor LOTO/permit non-compliance subcategory.", True),
    },
    "stage_4_hazard_identification": {
        "hazards": [
            item("HAZ-1", 0.9, "ai_inference", "Report explicitly states no visible LOTO tag was in place while the contractor worked on an energized panel.", True,
                 hazard_type="Electrical Hazard / Arc Flash", description="Work performed on an energized electrical panel without lockout/tagout, creating shock/arc-flash exposure."),
            item("HAZ-2", 0.75, "ai_inference", "No permit was on file at the facility for this work, indicating the facility's contractor authorization/oversight process was bypassed.", True,
                 hazard_type="Contractor Safety Incident", description="Contractor performed high-risk electrical work without a facility-issued work permit on file."),
        ],
        "coverage_note": "Both the immediate electrical hazard and the underlying contractor-management control failure are identified.",
    },
    "stage_5_potential_consequences": {
        "consequences": [
            item("CONS-1", 0.85, "ai_inference", "Energized panel work without LOTO is a well-established arc-flash/electrocution hazard pattern.", True,
                 description="Severe electrical shock, arc flash burn, or fatality to the contractor.", plausible_worst_case_severity="Critical"),
        ],
        "coverage_note": "Reflects the hazard the facility's intervention averted, not an outcome that occurred.",
    },
    "stage_6_preliminary_severity_assessment": {
        "ai_suggested_severity": scalar("High", "ai_inference", 0.75,
            "No injury occurred because the condition was caught and stopped, but exposure to an energized panel without LOTO represents a high-severity control failure with critical potential consequence (Stage 5), compounded by a bypassed permit process.", True),
        "ai_suggested_recurrence_likelihood": scalar("Possible", "ai_inference", 0.5,
            "Contractor's stated belief that their firm 'has its own safety process' suggests a process/expectations gap that could recur with this or other contractors absent a facility-side control change.", True),
        "status": "pending_human_confirmation",
        "requires_human_approval": True,
    },
    "stage_7_contributing_factors": {
        "factors": [
            item("CF-1", 0.85, "ai_inference", "Report directly quotes the contractor's rationale for not following facility LOTO/permit requirements.", True,
                 category="Organizational", description="Contractor believed their own company safety process superseded facility requirements."),
            item("CF-2", 0.6, "ai_inference", "Work was discovered in progress, not pre-authorized, indicating the facility's contractor check-in/permit process did not catch this work before it began.", True,
                 category="Procedural", description="Facility contractor-authorization/permit process did not intercept this work before it started."),
            item("CF-3", 0.35, "ai_inference", "Common associated factor in similar contractor incidents; not separately evidenced here.", True,
                 category="Organizational", description="Possible gap in facility's pre-work safety orientation/briefing for outside contractors (unconfirmed)."),
        ],
        "coverage_note": "CF-1 is directly evidenced by the quoted statement; CF-2 is inferred from the sequence of events; CF-3 is a lower-confidence hypothesis.",
    },
    "stage_8_root_cause_hypotheses": {
        "hypotheses": [
            item("RC-1", 0.75, "ai_inference", "Directly supported by CF-1 and CF-2 together: the contractor operated under their own standards because the facility's permit/orientation process did not establish and enforce its own requirements before work began.", True,
                 rank=1, statement="The facility's contractor safety management process (permit issuance and pre-work verification) did not confirm the contractor's compliance with facility LOTO requirements before energized panel work began.",
                 label="hypothesis_not_confirmed", supporting_evidence="No permit was on file and the contractor proceeded under their own company's process, indicating no facility gate-check occurred."),
            item("RC-2", 0.4, "ai_inference", "Plausible contributor but not directly evidenced.", True,
                 rank=2, statement="Facility contractor safety orientation may not have clearly communicated that facility LOTO/permit rules apply regardless of the contractor's own internal safety program.",
                 label="hypothesis_not_confirmed", supporting_evidence="Contractor's stated belief implies a possible expectations gap.",
                 contradicting_evidence="Whether this contractor received facility orientation at all is not stated in the report."),
        ],
        "coverage_note": "Both hypotheses center on the facility's contractor-management control rather than contractor intent; confirming RC-2 requires checking orientation/sign-in records for this contractor visit.",
    },
    "stage_9_existing_controls": {
        "controls": [
            item("CTRL-1", 0.85, "system_reference", "SOP-0025 (Contractor Safety Management Program) is Active for this facility.", False,
                 control_description="Contractor Safety Management Program, including permit-to-work requirements.", control_type="Administrative", status="present", related_sop_id="SOP-0025"),
            item("CTRL-2", 0.85, "system_reference", "SOP-0001 (Lockout/Tagout Procedure) is Active and applies facility-wide, including to contractors per SOP-0025.", False,
                 control_description="Facility LOTO requirement applicable to all persons working on energized equipment.", control_type="Procedural", status="present", related_sop_id="SOP-0001"),
            item("CTRL-3", 0.85, "extracted_from_report", "Report explicitly states no permit was on file.", False,
                 control_description="Work permit for this specific contractor task.", control_type="Administrative", status="absent", related_sop_id="SOP-0025"),
        ],
        "coverage_note": "The governing SOPs exist and are active; the permit and LOTO controls they require were confirmed absent in this specific instance.",
    },
    "stage_10_control_gaps": {
        "gaps": [
            item("GAP-1", 0.8, "ai_inference", "Work permit was required under SOP-0025 and was confirmed absent, meaning the facility's pre-work gate-check did not occur or was bypassed.", True,
                 related_control_id="CTRL-3", gap_description="Contractor began energized electrical work without a facility-issued permit on file, indicating a gap in pre-work authorization enforcement.",
                 required_by_sop_id="SOP-0025"),
            item("GAP-2", 0.7, "ai_inference", "Contractor's own statement indicates they were not operating under facility LOTO requirements at the time of discovery.", True,
                 related_control_id="CTRL-2", gap_description="Facility LOTO requirement (applicable to contractors per SOP-0025) was not followed for this energized panel work.",
                 required_by_sop_id="SOP-0001"),
        ],
        "coverage_note": "Both gaps point to the same underlying issue: contractor entry/authorization was not gated on confirmed facility safety-rule acceptance before high-risk work began.",
    },
    "stage_11_recommended_actions": {
        "actions": [
            item("ACT-1", 0.75, "ai_inference", "Directly addresses GAP-1; a hard gate (no permit, no access to energized equipment) prevents this specific sequence from recurring.", True,
                 action_type="Corrective", description="Reinforce and audit the permit-to-work gate in SOP-0025 so contractors cannot access energized equipment areas without a verified, on-file permit.",
                 priority="High", suggested_owner_role="Safety Manager", suggested_timeframe_days=21,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
            item("ACT-2", 0.65, "ai_inference", "Directly addresses GAP-2 and CF-1; explicit communication that facility rules govern regardless of contractor's own program closes the stated expectations gap.", True,
                 action_type="Preventive", description="Update contractor pre-work orientation to explicitly state that facility LOTO/permit requirements apply regardless of the contractor's own company safety program, with signed acknowledgment required before work authorization.",
                 priority="High", suggested_owner_role="EHS Coordinator", suggested_timeframe_days=30,
                 addresses_gap_ids=["GAP-1", "GAP-2"], requires_human_approval=True),
            item("ACT-3", 0.5, "ai_inference", "Addresses the specific contracting firm involved in this event; a firm-level review is a reasonable containment step given the severity of the exposure.", True,
                 action_type="Corrective", description="Review this contracting firm's safety qualification status with procurement/EHS before authorizing further work at any facility.",
                 priority="Medium", suggested_owner_role="Safety Manager", suggested_timeframe_days=14,
                 addresses_gap_ids=["GAP-1"], requires_human_approval=True),
        ],
        "coverage_note": "Actions target the facility-side control gate (ACT-1, ACT-2) and the specific contractor firm (ACT-3) separately.",
    },
    "stage_12_risk_register_impact": {
        "proposed_action": "create_new_risk", "hazard_category": "Contractor Safety Incident",
        "likelihood": scalar(3, "ai_inference", 0.55, "Rated Possible: this is the first documented instance for this contractor, but the underlying permit-gate gap (GAP-1) could affect any contractor until fixed.", True),
        "impact": scalar(5, "ai_inference", 0.8, "Stage 5 worst case is severe shock/arc-flash/fatality to the contractor; impact rated at the top of the scale.", True),
        "risk_score": scalar(15, "derived_from_prior_stage", None, "likelihood (3) x impact (5) = 15.", True),
        "risk_level": scalar("High", "derived_from_prior_stage", None, "Score of 15 falls in the High band (12-19) per facility risk matrix.", True),
        "existing_risk_assessment_id": None,
        "reasoning": "No existing risk register entry covers contractor permit/LOTO gate failures at this facility; proposing a new entry given the severity of the averted exposure.",
        "requires_human_approval": True, "write_status": "not_written_pending_approval",
    },
    "stage_13_human_review_package": review_package(
        inc_id,
        "An outside electrical contractor was found working on an energized panel with no LOTO tag and no on-file work permit; work was stopped before injury occurred. AI attributes this to a gap in the facility's contractor permit-to-work gate rather than treating it as an isolated contractor error, and recommends tightening that gate plus a High risk-register entry.",
        APPROVAL_STAGES,
    ),
}
examples.append(("incident-05-contractor-safety.json", wrap(inc_id, "A5", stages)))

# ===========================================================================
# Write + validate
# ===========================================================================
out_dir = ROOT / "examples"
all_errors = {}
for fname, data in examples:
    errors = sorted(VALIDATOR.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        all_errors[fname] = [f"{list(e.path)}: {e.message}" for e in errors]
    else:
        with open(out_dir / fname, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"OK  {fname}")

if all_errors:
    print("\nVALIDATION ERRORS:")
    for fname, errs in all_errors.items():
        print(f"\n{fname}:")
        for e in errs:
            print(f"  - {e}")
    raise SystemExit(1)

print(f"\nAll {len(examples)} examples validated against schema and written to {out_dir}")
