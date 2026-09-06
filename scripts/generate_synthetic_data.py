#!/usr/bin/env python3
"""Synthetic data generator for RISKON prototype — Rex Industrial Manufacturing.

Generates 7 related datasets (facilities, employees, equipment, SOPs,
incidents, risk assessments, corrective actions) with real foreign-key
relationships, and writes each as CSV + JSON.
"""
import csv
import json
import random
from datetime import date, timedelta, datetime
from pathlib import Path

random.seed(42)

OUT_DIR = Path(__file__).resolve().parent.parent / "synthetic-data"
(OUT_DIR / "csv").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "json").mkdir(parents=True, exist_ok=True)

TODAY = date(2026, 9, 3)

# ---------------------------------------------------------------------------
# Reference lists
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "James", "Maria", "Robert", "Linda", "Michael", "Patricia", "David", "Barbara",
    "John", "Susan", "Carlos", "Jennifer", "Kevin", "Lisa", "Anthony", "Karen",
    "Daniel", "Nancy", "Mark", "Betty", "Steven", "Sandra", "Paul", "Ashley",
    "Andrew", "Kimberly", "Joshua", "Emily", "Brian", "Michelle", "George", "Donna",
    "Timothy", "Carol", "Jose", "Rebecca", "Larry", "Sharon", "Justin", "Laura",
    "Scott", "Amanda", "Brandon", "Melissa", "Raymond", "Deborah", "Gregory", "Stephanie",
    "Frank", "Angela", "Alexander", "Rachel", "Samuel", "Christine", "Dennis", "Tiffany",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
]

FACILITIES = [
    {
        "facility_id": "FAC-001",
        "name": "Rex Industrial – Plant 1 (Ohio Manufacturing Complex)",
        "facility_type": "Heavy Manufacturing",
        "address": "4820 Blue Ridge Industrial Pkwy, Canton, OH 44706",
        "square_footage": 285000,
        "year_established": 1978,
        "employee_capacity": 340,
    },
    {
        "facility_id": "FAC-002",
        "name": "Rex Industrial – Plant 2 (Texas Assembly Facility)",
        "facility_type": "Assembly & Fabrication",
        "address": "1150 Gulf Freight Rd, Baytown, TX 77520",
        "square_footage": 190000,
        "year_established": 1996,
        "employee_capacity": 260,
    },
    {
        "facility_id": "FAC-003",
        "name": "Rex Industrial – Plant 3 (Georgia Distribution & Fab Center)",
        "facility_type": "Distribution & Light Fabrication",
        "address": "770 Peachtree Logistics Dr, Savannah, GA 31408",
        "square_footage": 150000,
        "year_established": 2008,
        "employee_capacity": 180,
    },
]
FACILITY_IDS = [f["facility_id"] for f in FACILITIES]

ROLES = [
    ("Plant Manager", "Operations"),
    ("Safety Manager", "EHS"),
    ("EHS Coordinator", "EHS"),
    ("Environmental Compliance Officer", "EHS"),
    ("Shift Supervisor", "Operations"),
    ("Maintenance Technician", "Maintenance"),
    ("Senior Maintenance Technician", "Maintenance"),
    ("Electrician", "Maintenance"),
    ("Mechanical Engineer", "Engineering"),
    ("Process Engineer", "Engineering"),
    ("Machine Operator", "Production"),
    ("CNC Operator", "Production"),
    ("Welder", "Production"),
    ("Forklift Operator", "Warehouse"),
    ("Warehouse Associate", "Warehouse"),
    ("Quality Inspector", "Quality"),
    ("Quality Manager", "Quality"),
    ("HR Generalist", "Human Resources"),
    ("Production Supervisor", "Operations"),
    ("Logistics Coordinator", "Warehouse"),
]

EQUIPMENT_TYPES = [
    ("CNC Machining Center", "Production", ["Haas", "Mazak", "DMG Mori", "Okuma"]),
    ("Hydraulic Press", "Production", ["Schuler", "Minster", "Verson"]),
    ("Overhead Bridge Crane", "Material Handling", ["Konecranes", "Demag", "Gorbel"]),
    ("Conveyor System", "Material Handling", ["Hytrol", "Dematic", "FlexLink"]),
    ("Forklift (Electric)", "Material Handling", ["Toyota", "Hyster", "Crown"]),
    ("Forklift (Propane)", "Material Handling", ["Toyota", "Yale", "Caterpillar"]),
    ("Air Compressor", "Utilities", ["Atlas Copco", "Ingersoll Rand", "Kaeser"]),
    ("Industrial Boiler", "Utilities", ["Cleaver-Brooks", "Fulton"]),
    ("Robotic Welding Arm", "Production", ["FANUC", "ABB", "KUKA"]),
    ("Packaging Line", "Production", ["Bosch Packaging", "ProMach"]),
    ("Cooling Tower", "Utilities", ["BAC", "SPX Marley"]),
    ("Pressure Vessel / Tank", "Utilities", ["Manchester Tank", "Trinity"]),
    ("Ventilation / Dust Collection System", "Utilities", ["Camfil", "Donaldson"]),
    ("Electrical Distribution Panel", "Utilities", ["Square D", "Eaton", "Siemens"]),
    ("Standby Generator", "Utilities", ["Cummins", "Generac", "Caterpillar"]),
    ("Automated Guided Vehicle (AGV)", "Material Handling", ["Dematic", "JBT"]),
    ("Punch Press", "Production", ["Amada", "Trumpf"]),
    ("Paint Booth / Coating Line", "Production", ["Global Finishing Solutions"]),
]

STATUS_BY_AGE = None  # computed inline

SOP_CATALOG = [
    ("Lockout/Tagout (LOTO) Procedure", "Energy Control"),
    ("Confined Space Entry Permit Procedure", "Confined Space"),
    ("Personal Protective Equipment (PPE) Requirements", "PPE"),
    ("Machine Guarding Standard", "Machine Safety"),
    ("Powered Industrial Truck (Forklift) Operation", "Vehicle Safety"),
    ("Hot Work Permit Procedure", "Fire Safety"),
    ("Hazardous Chemical Handling & Storage", "Chemical Safety"),
    ("Emergency Response & Evacuation Plan", "Emergency Preparedness"),
    ("Overhead Crane & Rigging Operation", "Material Handling"),
    ("Electrical Safe Work Practices (Arc Flash)", "Electrical Safety"),
    ("Fall Protection Program", "Fall Safety"),
    ("Hazardous Waste Disposal Procedure", "Environmental"),
    ("Ergonomic Workstation Guidelines", "Ergonomics"),
    ("Fire Prevention & Extinguisher Use", "Fire Safety"),
    ("Spill Prevention & Response Plan", "Environmental"),
    ("Respiratory Protection Program", "PPE"),
    ("Hearing Conservation Program", "Industrial Hygiene"),
    ("Incident Reporting & Investigation Procedure", "EHS Management"),
    ("New Employee Safety Orientation", "Training"),
    ("Job Hazard Analysis (JHA) Procedure", "EHS Management"),
    ("Compressed Gas Cylinder Handling", "Chemical Safety"),
    ("Robotic Cell Safety Procedure", "Machine Safety"),
    ("Preventive Maintenance Safety Procedure", "Maintenance"),
    ("Housekeeping & Walkway Safety Standard", "General Safety"),
    ("Contractor Safety Management Program", "EHS Management"),
    ("Welding & Cutting Safety Procedure", "Fire Safety"),
    ("Boiler & Pressure Vessel Safety Procedure", "Utilities Safety"),
    ("Environmental Air Emissions Monitoring", "Environmental"),
    ("Slip, Trip & Fall Prevention Standard", "General Safety"),
    ("Management of Change (MOC) Procedure", "EHS Management"),
]

HAZARD_CATEGORIES = [
    "Machine Guarding Failure",
    "Lockout/Tagout Violation",
    "Slip/Trip/Fall",
    "Chemical Exposure",
    "Electrical Hazard / Arc Flash",
    "Forklift / Vehicle Incident",
    "Falling Object / Struck-By",
    "Ergonomic Strain",
    "Fire / Explosion Risk",
    "Confined Space Hazard",
    "Noise Exposure",
    "Pressure System Failure",
    "Environmental Spill / Release",
    "Overhead Crane / Rigging Hazard",
    "Caught-In / Caught-Between",
    "Heat Stress",
    "Housekeeping / Walkway Obstruction",
]

INCIDENT_TEMPLATES = {
    "Machine Guarding Failure": [
        "Operator reported missing guard on {equip} allowing access to pinch point during {shift} shift.",
        "Interlock switch on {equip} bypassed, permitting operation with guard door open.",
    ],
    "Lockout/Tagout Violation": [
        "Technician began maintenance on {equip} before verifying zero energy state; near-miss caught by co-worker.",
        "LOTO device found removed from {equip} while work was still in progress.",
    ],
    "Slip/Trip/Fall": [
        "Employee slipped on hydraulic fluid leak near {equip}, sustained minor bruising.",
        "Worker tripped over unsecured cable near {equip} walkway, no injury reported.",
    ],
    "Chemical Exposure": [
        "Employee experienced skin irritation after contact with degreasing solvent used near {equip}.",
        "Small chemical splash occurred during transfer of cleaning agent, PPE prevented injury.",
    ],
    "Electrical Hazard / Arc Flash": [
        "Arc flash incident occurred while technician opened electrical panel on {equip} without verifying de-energization.",
        "Exposed wiring identified on {equip} control cabinet during routine inspection.",
    ],
    "Forklift / Vehicle Incident": [
        "Forklift operator struck a storage rack while maneuvering near {equip}, minor property damage.",
        "Near-miss between forklift and pedestrian in aisle adjacent to {equip}.",
    ],
    "Falling Object / Struck-By": [
        "Component fell from overhead storage near {equip}, narrowly missing employee below.",
        "Worker struck by ejected part from {equip} during operation.",
    ],
    "Ergonomic Strain": [
        "Employee reported lower back strain after repetitive lifting at {equip} station.",
        "Repetitive motion injury reported by operator working at {equip} for extended shift.",
    ],
    "Fire / Explosion Risk": [
        "Overheating detected on {equip} motor housing, smoke observed, no ignition.",
        "Hot work near {equip} ignited nearby debris; extinguished with portable extinguisher.",
    ],
    "Confined Space Hazard": [
        "Atmospheric monitoring flagged low oxygen levels prior to entry near {equip} tank.",
        "Entry attempted into confined space adjacent to {equip} without permit.",
    ],
    "Noise Exposure": [
        "Sound level survey near {equip} exceeded 90 dBA without proper hearing protection use.",
        "Employee reported ringing in ears after extended exposure near {equip}.",
    ],
    "Pressure System Failure": [
        "Relief valve on {equip} activated unexpectedly during startup.",
        "Pressure gauge reading anomaly detected on {equip}, unit taken offline as precaution.",
    ],
    "Environmental Spill / Release": [
        "Hydraulic oil spill from {equip} reached floor drain before containment.",
        "Coolant leak from {equip} required environmental spill response team.",
    ],
    "Overhead Crane / Rigging Hazard": [
        "Load shifted unexpectedly while being lifted by {equip}, operator halted lift safely.",
        "Rigging inspection on {equip} found frayed sling, removed from service.",
    ],
    "Caught-In / Caught-Between": [
        "Employee's sleeve caught in moving components of {equip}, stopped before injury.",
        "Worker's hand came close to nip point on {equip} conveyor during clearing of jam.",
    ],
    "Heat Stress": [
        "Employee reported heat exhaustion symptoms working near {equip} during summer shift.",
        "High ambient temperature near {equip} area exceeded safe working thresholds.",
    ],
    "Housekeeping / Walkway Obstruction": [
        "Pallets stored in designated walkway near {equip} created obstruction hazard.",
        "Debris accumulation near {equip} blocked emergency egress path.",
    ],
}

SEVERITIES = ["Low", "Medium", "High", "Critical"]
SEVERITY_WEIGHTS = [0.42, 0.33, 0.19, 0.06]
SHIFTS = ["Day", "Swing", "Night"]

INCIDENT_STATUSES = ["Closed", "Closed", "Closed", "In Review", "Approved", "Open"]

CA_TYPES = ["Corrective", "Preventive"]
CA_STATUSES = ["Completed", "Completed", "In Progress", "Open", "Overdue"]

CA_TEMPLATES = {
    "Machine Guarding Failure": [
        "Install/repair fixed guard and verify interlock function on {equip}.",
        "Retrain operators on machine guarding requirements for {equip}.",
    ],
    "Lockout/Tagout Violation": [
        "Retrain affected technicians on LOTO procedure for {equip}; conduct audit within 30 days.",
        "Update LOTO isolation points documentation for {equip}.",
    ],
    "Slip/Trip/Fall": [
        "Repair fluid leak source and install absorbent mats near {equip}.",
        "Reroute or secure cabling near {equip} walkway; add signage.",
    ],
    "Chemical Exposure": [
        "Update SDS access point and reinforce PPE requirement for solvent handling near {equip}.",
        "Install secondary containment for chemical transfer near {equip}.",
    ],
    "Electrical Hazard / Arc Flash": [
        "Perform arc flash risk assessment and update warning labels on {equip}.",
        "Repair exposed wiring and schedule electrical safety inspection for {equip}.",
    ],
    "Forklift / Vehicle Incident": [
        "Install convex mirrors and repaint pedestrian lanes near {equip}.",
        "Retrain forklift operator; review speed limits in {equip} zone.",
    ],
    "Falling Object / Struck-By": [
        "Secure overhead storage and inspect racking near {equip}.",
        "Install debris guard on {equip} to contain ejected parts.",
    ],
    "Ergonomic Strain": [
        "Conduct ergonomic assessment of {equip} workstation and implement adjustable fixtures.",
        "Rotate staff assignments at {equip} station to reduce repetitive strain exposure.",
    ],
    "Fire / Explosion Risk": [
        "Inspect and service {equip} motor/cooling system; add thermal monitoring.",
        "Reinforce hot work permit compliance near {equip}.",
    ],
    "Confined Space Hazard": [
        "Reinforce confined space permit process for entries near {equip}.",
        "Install fixed gas monitoring near {equip} confined space entry point.",
    ],
    "Noise Exposure": [
        "Provide additional hearing protection and post noise hazard signage near {equip}.",
        "Evaluate engineering noise controls for {equip}.",
    ],
    "Pressure System Failure": [
        "Inspect and recalibrate relief valve and gauges on {equip}.",
        "Schedule third-party pressure system certification for {equip}.",
    ],
    "Environmental Spill / Release": [
        "Repair seal/leak source on {equip} and replenish spill kit inventory nearby.",
        "Update spill response drill schedule for {equip} area.",
    ],
    "Overhead Crane / Rigging Hazard": [
        "Replace worn rigging and conduct full inspection of {equip}.",
        "Retrain crane operators on load-securing procedure for {equip}.",
    ],
    "Caught-In / Caught-Between": [
        "Install additional e-stop and nip point guarding on {equip}.",
        "Update jam-clearing procedure and require LOTO before clearing {equip}.",
    ],
    "Heat Stress": [
        "Install additional ventilation/cooling near {equip}; adjust work-rest cycles.",
        "Provide electrolyte stations and heat stress training for {equip} area staff.",
    ],
    "Housekeeping / Walkway Obstruction": [
        "Designate and mark storage zones away from egress paths near {equip}.",
        "Implement daily housekeeping audit checklist for {equip} area.",
    ],
}

ROOT_CAUSE_TEMPLATES = [
    "Insufficient preventive maintenance schedule for {equip} allowed component degradation to go undetected.",
    "Gap in operator training on {equip} safety procedures contributed to unsafe practice.",
    "Existing engineering control on {equip} was inadequate for current operating conditions.",
    "Procedure for {equip} was not followed due to production time pressure.",
    "SOP for {equip} was outdated and did not reflect current equipment configuration.",
    "Communication breakdown between shifts regarding {equip} status contributed to the incident.",
    "Design of {equip} work area did not adequately separate personnel from hazard zone.",
]

INVESTIGATION_TEMPLATES = [
    "Initial review of {equip} maintenance logs and interviews with shift personnel confirmed hazard was present prior to incident.",
    "Site walk-down of {equip} area and review of CCTV footage conducted; contributing factors identified in equipment condition and procedure adherence.",
    "Investigation team reviewed {equip} operating parameters, training records, and prior near-miss reports for the area.",
]


def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))


def weighted_choice(options, weights):
    return random.choices(options, weights=weights, k=1)[0]


def to_iso(d) -> str:
    return d.isoformat() if isinstance(d, date) else d


# ---------------------------------------------------------------------------
# 1. Facilities
# ---------------------------------------------------------------------------
facilities = FACILITIES

# ---------------------------------------------------------------------------
# 2. Employees (30)
# ---------------------------------------------------------------------------
employees = []
used_names = set()
emp_id = 1
role_cycle = ROLES * 3
random.shuffle(role_cycle)
for i in range(30):
    while True:
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        if (fn, ln) not in used_names:
            used_names.add((fn, ln))
            break
    role, dept = role_cycle[i]
    facility = FACILITY_IDS[i % 3] if role != "Plant Manager" else FACILITY_IDS[i % 3]
    hire_date = rand_date(date(2005, 1, 1), date(2026, 1, 1))
    employees.append({
        "employee_id": f"EMP-{emp_id:04d}",
        "first_name": fn,
        "last_name": ln,
        "email": f"{fn.lower()}.{ln.lower()}@reximanufacturing.com",
        "role": role,
        "department": dept,
        "facility_id": facility,
        "hire_date": to_iso(hire_date),
        "is_active": random.random() > 0.05,
    })
    emp_id += 1

# ensure each facility has exactly one Plant Manager and one Safety Manager
for fid in FACILITY_IDS:
    for needed_role in ["Plant Manager", "Safety Manager"]:
        if not any(e["facility_id"] == fid and e["role"] == needed_role for e in employees):
            candidate = next(e for e in employees if e["role"] not in ("Plant Manager", "Safety Manager"))
            candidate["role"] = needed_role
            candidate["facility_id"] = fid

def employees_at(facility_id, role=None):
    pool = [e for e in employees if e["facility_id"] == facility_id]
    if role:
        pool = [e for e in pool if e["role"] == role]
    return pool or [e for e in employees]

# ---------------------------------------------------------------------------
# 3. Equipment (50)
# ---------------------------------------------------------------------------
equipment = []
for i in range(1, 51):
    etype, category, manufacturers = random.choice(EQUIPMENT_TYPES)
    facility = random.choice(FACILITY_IDS)
    install_date = rand_date(date(1995, 1, 1), date(2024, 6, 1))
    last_maint = rand_date(max(install_date, date(2025, 1, 1)), TODAY)
    status = weighted_choice(
        ["Operational", "Operational", "Operational", "Under Maintenance", "Decommissioned"],
        [0.55, 0.2, 0.15, 0.07, 0.03],
    )
    criticality = weighted_choice(["Low", "Medium", "High"], [0.3, 0.45, 0.25])
    equipment.append({
        "equipment_id": f"EQ-{i:04d}",
        "equipment_type": etype,
        "category": category,
        "manufacturer": random.choice(manufacturers),
        "model_number": f"{random.choice(['MX','GX','TX','RX','PX'])}-{random.randint(100,999)}{random.choice(['','A','B','S'])}",
        "serial_number": f"SN{random.randint(100000,999999)}",
        "facility_id": facility,
        "install_date": to_iso(install_date),
        "last_maintenance_date": to_iso(last_maint),
        "status": status,
        "criticality": criticality,
    })

def equip_at(facility_id):
    pool = [e for e in equipment if e["facility_id"] == facility_id]
    return pool or equipment

# ---------------------------------------------------------------------------
# 4. SOPs (30)
# ---------------------------------------------------------------------------
sops = []
for i, (title, category) in enumerate(SOP_CATALOG, start=1):
    owner = random.choice([e for e in employees if e["role"] in ("Safety Manager", "EHS Coordinator", "Plant Manager")] or employees)
    effective = rand_date(date(2018, 1, 1), date(2025, 1, 1))
    review = effective + timedelta(days=365 * random.choice([1, 2, 3]))
    sops.append({
        "sop_id": f"SOP-{i:04d}",
        "title": title,
        "category": category,
        "version": f"{random.randint(1,4)}.{random.randint(0,9)}",
        "effective_date": to_iso(effective),
        "next_review_date": to_iso(review),
        "owner_employee_id": owner["employee_id"],
        "facility_id": random.choice(FACILITY_IDS + ["ALL"]),
        "status": weighted_choice(["Active", "Active", "Under Revision", "Retired"], [0.75, 0.15, 0.07, 0.03]),
    })

def sop_for_category(hazard_category):
    mapping = {
        "Machine Guarding Failure": "Machine Guarding Standard",
        "Lockout/Tagout Violation": "Lockout/Tagout (LOTO) Procedure",
        "Slip/Trip/Fall": "Slip, Trip & Fall Prevention Standard",
        "Chemical Exposure": "Hazardous Chemical Handling & Storage",
        "Electrical Hazard / Arc Flash": "Electrical Safe Work Practices (Arc Flash)",
        "Forklift / Vehicle Incident": "Powered Industrial Truck (Forklift) Operation",
        "Falling Object / Struck-By": "Housekeeping & Walkway Safety Standard",
        "Ergonomic Strain": "Ergonomic Workstation Guidelines",
        "Fire / Explosion Risk": "Fire Prevention & Extinguisher Use",
        "Confined Space Hazard": "Confined Space Entry Permit Procedure",
        "Noise Exposure": "Hearing Conservation Program",
        "Pressure System Failure": "Boiler & Pressure Vessel Safety Procedure",
        "Environmental Spill / Release": "Spill Prevention & Response Plan",
        "Overhead Crane / Rigging Hazard": "Overhead Crane & Rigging Operation",
        "Caught-In / Caught-Between": "Machine Guarding Standard",
        "Heat Stress": "Ergonomic Workstation Guidelines",
        "Housekeeping / Walkway Obstruction": "Housekeeping & Walkway Safety Standard",
    }
    title = mapping.get(hazard_category)
    match = next((s for s in sops if s["title"] == title), None)
    return match["sop_id"] if match else random.choice(sops)["sop_id"]

# ---------------------------------------------------------------------------
# 5. Incidents (100)
# ---------------------------------------------------------------------------
incidents = []
for i in range(1, 101):
    facility = random.choice(FACILITY_IDS)
    equip = random.choice(equip_at(facility))
    hazard = random.choice(HAZARD_CATEGORIES)
    template = random.choice(INCIDENT_TEMPLATES[hazard])
    shift = random.choice(SHIFTS)
    reporter = random.choice(employees_at(facility))
    occurred = rand_date(date(2023, 9, 1), TODAY - timedelta(days=1))
    severity_reported = weighted_choice(SEVERITIES, SEVERITY_WEIGHTS)
    sev_idx = SEVERITIES.index(severity_reported)
    ai_shift = random.choice([-1, 0, 0, 0, 1])
    severity_ai = SEVERITIES[max(0, min(3, sev_idx + ai_shift))]
    status = random.choice(INCIDENT_STATUSES)
    confidence = round(random.uniform(0.68, 0.98), 2)

    incidents.append({
        "incident_id": f"INC-{i:04d}",
        "facility_id": facility,
        "equipment_id": equip["equipment_id"],
        "related_sop_id": sop_for_category(hazard),
        "reporter_employee_id": reporter["employee_id"],
        "title": f"{hazard} – {equip['equipment_type']}",
        "description": template.format(equip=equip["equipment_type"], shift=shift.lower()),
        "hazard_category": hazard,
        "shift": shift,
        "date_occurred": to_iso(occurred),
        "severity_reported": severity_reported,
        "severity_ai_classified": severity_ai,
        "ai_confidence": confidence,
        "status": status,
        "ai_investigation_summary": random.choice(INVESTIGATION_TEMPLATES).format(equip=equip["equipment_type"]),
        "ai_root_cause": random.choice(ROOT_CAUSE_TEMPLATES).format(equip=equip["equipment_type"]),
        "created_at": to_iso(occurred + timedelta(days=random.randint(0, 2))),
    })

def incidents_for_facility(fid):
    return [x for x in incidents if x["facility_id"] == fid]

# ---------------------------------------------------------------------------
# 6. Risk Assessments (50) — ~30 linked to an incident, ~20 proactive
# ---------------------------------------------------------------------------
risk_assessments = []
incident_sample = random.sample(incidents, 30)
for i in range(1, 51):
    facility = random.choice(FACILITY_IDS)
    linked_incident = incident_sample[i - 1] if i <= 30 else None
    if linked_incident:
        hazard = linked_incident["hazard_category"]
        equip_id = linked_incident["equipment_id"]
        facility = linked_incident["facility_id"]
    else:
        hazard = random.choice(HAZARD_CATEGORIES)
        equip_id = random.choice(equip_at(facility))["equipment_id"]

    likelihood = random.randint(1, 5)
    impact = random.randint(1, 5)
    score = likelihood * impact
    assessor = random.choice(employees_at(facility, "Safety Manager") + employees_at(facility, "EHS Coordinator"))
    assess_date = rand_date(date(2024, 1, 1), TODAY)

    risk_assessments.append({
        "risk_assessment_id": f"RISK-{i:04d}",
        "facility_id": facility,
        "hazard_category": hazard,
        "equipment_id": equip_id,
        "source_incident_id": linked_incident["incident_id"] if linked_incident else "",
        "related_sop_id": sop_for_category(hazard),
        "likelihood": likelihood,
        "impact": impact,
        "risk_score": score,
        "risk_level": "Critical" if score >= 20 else "High" if score >= 12 else "Medium" if score >= 6 else "Low",
        "existing_controls": f"Current SOP compliance and PPE use for {hazard.lower()} exposure.",
        "recommended_controls": f"Enhance engineering/administrative controls for {hazard.lower()} at point of work.",
        "assessed_by_employee_id": assessor["employee_id"],
        "assessment_date": to_iso(assess_date),
        "status": weighted_choice(["Open", "Mitigated", "Closed"], [0.35, 0.25, 0.4]),
    })

# ---------------------------------------------------------------------------
# 7. Corrective Actions (100) — linked to incidents and/or risk assessments
# ---------------------------------------------------------------------------
corrective_actions = []
ca_id = 1

# link to incidents that have status Approved/Closed/In Review (i.e., processed)
processed_incidents = [x for x in incidents if x["status"] in ("Approved", "Closed", "In Review")]
targets = []
for inc in processed_incidents:
    targets.append(("incident", inc))
for ra in risk_assessments:
    if ra["status"] != "Closed" or random.random() < 0.3:
        targets.append(("risk", ra))

random.shuffle(targets)
targets = targets[:100] if len(targets) >= 100 else targets + random.choices(targets, k=100 - len(targets))

for kind, obj in targets[:100]:
    if kind == "incident":
        hazard = obj["hazard_category"]
        equip_id = obj["equipment_id"]
        facility = obj["facility_id"]
        incident_id = obj["incident_id"]
        risk_id = ""
    else:
        hazard = obj["hazard_category"]
        equip_id = obj["equipment_id"]
        facility = obj["facility_id"]
        incident_id = obj["source_incident_id"]
        risk_id = obj["risk_assessment_id"]

    equip_type = next((e["equipment_type"] for e in equipment if e["equipment_id"] == equip_id), "equipment")
    action_text = random.choice(CA_TEMPLATES[hazard]).format(equip=equip_type)
    action_type = random.choice(CA_TYPES)
    owner = random.choice(employees_at(facility, "Maintenance Technician") + employees_at(facility, "Safety Manager"))
    created = rand_date(date(2024, 1, 1), TODAY)
    due = created + timedelta(days=random.choice([14, 30, 45, 60, 90]))
    status = random.choice(CA_STATUSES)
    if status == "Completed":
        completion_date = to_iso(due - timedelta(days=random.randint(0, 10)))
    elif status == "Overdue":
        due = TODAY - timedelta(days=random.randint(1, 30))
        completion_date = ""
    else:
        completion_date = ""

    corrective_actions.append({
        "corrective_action_id": f"CA-{ca_id:04d}",
        "incident_id": incident_id,
        "risk_assessment_id": risk_id,
        "facility_id": facility,
        "equipment_id": equip_id,
        "action_type": action_type,
        "description": action_text,
        "owner_employee_id": owner["employee_id"],
        "created_date": to_iso(created),
        "due_date": to_iso(due),
        "status": status,
        "completion_date": completion_date,
        "verification_method": random.choice([
            "Follow-up inspection", "Supervisor sign-off", "Maintenance work order closure",
            "Retraining attendance record", "EHS audit confirmation",
        ]),
    })
    ca_id += 1

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------
DATASETS = {
    "facilities": facilities,
    "employees": employees,
    "equipment": equipment,
    "sops": sops,
    "incidents": incidents,
    "risk_assessments": risk_assessments,
    "corrective_actions": corrective_actions,
}

for name, rows in DATASETS.items():
    csv_path = OUT_DIR / "csv" / f"{name}.csv"
    json_path = OUT_DIR / "json" / f"{name}.json"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    print(f"{name}: {len(rows)} rows -> {csv_path.name}, {json_path.name}")

print("\nDone.")
