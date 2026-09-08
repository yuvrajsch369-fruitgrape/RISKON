#!/usr/bin/env python3
"""
RISKON V0.1 — synthetic database generator for Rex Industrial Manufacturing.

Builds database/riskon.db (SQLite) from schema.sql, generating ~19 related
tables with deliberately injected patterns (see PATTERN NOTES below), then:
  - exports every table to database/csv/<table>.csv
  - writes database/test_scenarios.json (ground truth for 5 known scenarios)
  - writes database/example_records.json (one real row per table, for docs)

Consistency checks are a separate, manual step (this script does not run
them itself): `python3 database/validate.py` -> database/validation_report.md.

All content is fictional. No real company, person, or confidential data.

Run: python3 database/generate_database.py
"""
import json
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

random.seed(20260903)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "database" / "riskon.db"
SCHEMA_PATH = ROOT / "database" / "schema.sql"
CSV_DIR = ROOT / "database" / "csv"
CSV_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date(2026, 9, 3)
WINDOW_START = date(2025, 1, 1)  # ~20 months of operating history


def d(offset_days_from_today):
    return (TODAY - timedelta(days=offset_days_from_today)).isoformat()


def rand_date(start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=random.randint(0, max(span, 0)))


def iso(x):
    return x.isoformat() if isinstance(x, date) else x


# =============================================================================
# REFERENCE CATALOGS
# =============================================================================
FIRST_NAMES = [
    "James","Maria","Robert","Linda","Michael","Patricia","David","Barbara","John","Susan",
    "Carlos","Jennifer","Kevin","Lisa","Anthony","Karen","Daniel","Nancy","Mark","Betty",
    "Steven","Sandra","Paul","Ashley","Andrew","Kimberly","Joshua","Emily","Brian","Michelle",
    "George","Donna","Timothy","Carol","Jose","Rebecca","Larry","Sharon","Justin","Laura",
    "Scott","Amanda","Brandon","Melissa","Raymond","Deborah","Gregory","Stephanie","Frank","Angela",
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
    "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin",
    "Lee","Perez","Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson",
    "Walker","Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
]
_used_names = set()
def unique_name():
    while True:
        fn, ln = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        if (fn, ln) not in _used_names:
            _used_names.add((fn, ln))
            return fn, ln

CONTRACTOR_FIRST = ["Tyler","Marcus","Derek","Shane","Cody","Miguel","Trevor","Dustin","Wesley","Cole",
                     "Alicia","Brenda","Monica","Renee","Kayla","Tasha","Dana","Erin","Vanessa","Holly"]
CONTRACTOR_LAST = ["Boone","Farley","Kessler","Whitfield","Dunlap","Prater","Osborn","Maddox","Crenshaw","Tolliver",
                    "Nash","Pruett","Culpepper","Winfrey","Sledge","Dorsey","Kirby","Landreth","Coker","Vance"]
_used_contractor_names = set()
def unique_contractor_name():
    while True:
        fn, ln = random.choice(CONTRACTOR_FIRST), random.choice(CONTRACTOR_LAST)
        if (fn, ln) not in _used_contractor_names:
            _used_contractor_names.add((fn, ln))
            return fn, ln

ROLE_CATALOG = [
    ("Plant Manager", "Operations", True),
    ("Safety Manager", "EHS", True),
    ("EHS Coordinator", "EHS", True),
    ("Environmental Compliance Officer", "EHS", True),
    ("Shift Supervisor", "Operations", True),
    ("Maintenance Technician", "Maintenance", True),
    ("Senior Maintenance Technician", "Maintenance", True),
    ("Electrician", "Maintenance", True),
    ("Mechanical Engineer", "Engineering", False),
    ("Process Engineer", "Engineering", False),
    ("Machine Operator", "Production", True),
    ("CNC Operator", "Production", True),
    ("Welder", "Production", True),
    ("Forklift Operator", "Warehouse", True),
    ("Warehouse Associate", "Warehouse", False),
    ("Quality Inspector", "Quality", False),
    ("Quality Manager", "Quality", False),
    ("HR Generalist", "Human Resources", False),
]

EQUIPMENT_TYPES = [
    ("CNC Machining Center", "Production", ["Haas","Mazak","DMG Mori","Okuma"]),
    ("Hydraulic Press", "Production", ["Schuler","Minster","Verson"]),
    ("Punch Press", "Production", ["Amada","Trumpf"]),
    ("Overhead Bridge Crane", "Material Handling", ["Konecranes","Demag","Gorbel"]),
    ("Conveyor System", "Material Handling", ["Hytrol","Dematic","FlexLink"]),
    ("Forklift (Electric)", "Material Handling", ["Toyota","Hyster","Crown"]),
    ("Forklift (Propane)", "Material Handling", ["Toyota","Yale","Caterpillar"]),
    ("Air Compressor", "Utilities", ["Atlas Copco","Ingersoll Rand","Kaeser"]),
    ("Industrial Boiler", "Utilities", ["Cleaver-Brooks","Fulton"]),
    ("Robotic Welding Arm", "Production", ["FANUC","ABB","KUKA"]),
    ("Packaging Line", "Production", ["Bosch Packaging","ProMach"]),
    ("Cooling Tower", "Utilities", ["BAC","SPX Marley"]),
    ("Pressure Vessel / Tank", "Utilities", ["Manchester Tank","Trinity"]),
    ("Ventilation / Dust Collection System", "Utilities", ["Camfil","Donaldson"]),
    ("Electrical Distribution Panel", "Utilities", ["Square D","Eaton","Siemens"]),
    ("Standby Generator", "Utilities", ["Cummins","Generac","Caterpillar"]),
    ("Paint Booth / Coating Line", "Production", ["Global Finishing Solutions"]),
]

HAZARD_CATEGORIES = [
    "Machine Guarding Failure","Lockout/Tagout Violation","Slip/Trip/Fall","Chemical Exposure",
    "Electrical Hazard / Arc Flash","Forklift / Vehicle Incident","Falling Object / Struck-By",
    "Ergonomic Strain","Fire / Explosion Risk","Confined Space Hazard","Noise Exposure",
    "Pressure System Failure","Environmental Spill / Release","Overhead Crane / Rigging Hazard",
    "Caught-In / Caught-Between","Heat Stress","Housekeeping / Walkway Obstruction",
]

SOP_CATALOG = [
    ("Lockout/Tagout (LOTO) Procedure","Energy Control"),
    ("Confined Space Entry Permit Procedure","Confined Space"),
    ("Personal Protective Equipment (PPE) Requirements","PPE"),
    ("Machine Guarding Standard","Machine Safety"),
    ("Powered Industrial Truck (Forklift) Operation","Vehicle Safety"),
    ("Hot Work Permit Procedure","Fire Safety"),
    ("Hazardous Chemical Handling & Storage","Chemical Safety"),
    ("Emergency Response & Evacuation Plan","Emergency Preparedness"),
    ("Overhead Crane & Rigging Operation","Material Handling"),
    ("Electrical Safe Work Practices (Arc Flash)","Electrical Safety"),
    ("Fall Protection Program","Fall Safety"),
    ("Hazardous Waste Disposal Procedure","Environmental"),
    ("Ergonomic Workstation Guidelines","Ergonomics"),
    ("Fire Prevention & Extinguisher Use","Fire Safety"),
    ("Spill Prevention & Response Plan","Environmental"),
    ("Respiratory Protection Program","PPE"),
    ("Hearing Conservation Program","Industrial Hygiene"),
    ("Incident Reporting & Investigation Procedure","EHS Management"),
    ("New Employee Safety Orientation","Training"),
    ("Job Hazard Analysis (JHA) Procedure","EHS Management"),
    ("Compressed Gas Cylinder Handling","Chemical Safety"),
    ("Robotic Cell Safety Procedure","Machine Safety"),
    ("Preventive Maintenance Safety Procedure","Maintenance"),
    ("Housekeeping & Walkway Safety Standard","General Safety"),
    ("Contractor Safety Management Program","EHS Management"),
    ("Welding & Cutting Safety Procedure","Fire Safety"),
    ("Boiler & Pressure Vessel Safety Procedure","Utilities Safety"),
    ("Environmental Air Emissions Monitoring","Environmental"),
    ("Slip, Trip & Fall Prevention Standard","General Safety"),
    ("Management of Change (MOC) Procedure","EHS Management"),
]

CONTRACTOR_FIRMS = [
    ("Ironclad Electrical Services", "Electrical"),
    ("Summit Mechanical Contractors", "Mechanical/HVAC"),
    ("Bridgeway Crane & Rigging", "Crane/Rigging"),
    ("Redline Welding & Fabrication", "Welding/Fabrication"),
    ("ClearPath Facilities Group", "Janitorial/Facilities"),
    ("Vantage Industrial Coatings", "Painting/Coatings"),
]

TRADES = ["Electrical","Mechanical/HVAC","Crane/Rigging","Welding/Fabrication","Janitorial/Facilities","Painting/Coatings"]


def new_id_counter():
    return {"n": 0}

# =============================================================================
# STORAGE — every table as a list of dict rows
# =============================================================================
T = {k: [] for k in [
    "companies","facilities","roles","employees","contractors","equipment","sops","hazards",
    "controls","maintenance_records","incidents","risk_assessments","risk_register",
    "control_assessments","inspections","audit_findings","actions","training_records","evidence",
]}

# =============================================================================
# 1. COMPANY
# =============================================================================
T["companies"].append({
    "company_id": "CO-001", "name": "Rex Industrial Manufacturing", "industry": "Industrial Manufacturing",
    "founded_year": 1974, "headquarters_city": "Canton", "headquarters_state": "OH",
})

# =============================================================================
# 2. FACILITIES
# =============================================================================
T["facilities"] = [
    {"facility_id":"FAC-001","company_id":"CO-001","name":"Rex North Plant","facility_type":"Heavy Manufacturing",
     "city":"Canton","state":"OH","country":"United States","address":"4820 Blue Ridge Industrial Pkwy, Canton, OH 44706",
     "square_footage":285000,"year_established":1978,"employee_capacity":340},
    {"facility_id":"FAC-002","company_id":"CO-001","name":"Rex Central Plant","facility_type":"Assembly & Fabrication",
     "city":"Baytown","state":"TX","country":"United States","address":"1150 Gulf Freight Rd, Baytown, TX 77520",
     "square_footage":190000,"year_established":1996,"employee_capacity":260},
    {"facility_id":"FAC-003","company_id":"CO-001","name":"Rex South Plant","facility_type":"Distribution & Light Fabrication",
     "city":"Savannah","state":"GA","country":"United States","address":"770 Peachtree Logistics Dr, Savannah, GA 31408",
     "square_footage":150000,"year_established":2008,"employee_capacity":180},
]
FAC_IDS = [f["facility_id"] for f in T["facilities"]]
FAC_NORTH, FAC_CENTRAL, FAC_SOUTH = FAC_IDS

# =============================================================================
# 3a. ROLES
# =============================================================================
for i, (title, dept, crit) in enumerate(ROLE_CATALOG, start=1):
    T["roles"].append({"role_id": f"ROLE-{i:02d}", "title": title, "department": dept,
                        "description": f"{title} within the {dept} function.", "is_safety_critical": int(crit)})
ROLE_BY_TITLE = {r["title"]: r["role_id"] for r in T["roles"]}

# =============================================================================
# 3b. EMPLOYEES (30)
# =============================================================================
role_cycle = ROLE_CATALOG * 2
random.shuffle(role_cycle)
for i in range(30):
    fn, ln = unique_name()
    title, dept, _ = role_cycle[i % len(role_cycle)]
    facility_id = FAC_IDS[i % 3]
    hire_date = rand_date(date(2005, 1, 1), date(2025, 6, 1))
    T["employees"].append({
        "employee_id": f"EMP-{i+1:04d}", "facility_id": facility_id, "role_id": ROLE_BY_TITLE[title],
        "first_name": fn, "last_name": ln, "email": f"{fn.lower()}.{ln.lower()}@rexindustrial-example.com",
        "hire_date": iso(hire_date), "is_active": 1,
    })
# guarantee each facility has >=1 Plant Manager and >=1 Safety Manager
for fid in FAC_IDS:
    for needed in ["Plant Manager", "Safety Manager"]:
        if not any(e["facility_id"] == fid and e["role_id"] == ROLE_BY_TITLE[needed] for e in T["employees"]):
            cand = next(e for e in T["employees"] if e["role_id"] not in (ROLE_BY_TITLE["Plant Manager"], ROLE_BY_TITLE["Safety Manager"]))
            cand["facility_id"] = fid
            cand["role_id"] = ROLE_BY_TITLE[needed]

def employees_at(facility_id, title=None):
    """Facility-then-role filter. If the exact (facility, title) combination is empty,
    relax FACILITY first (any site with that title) rather than relaxing title — an
    empty pool must never fall back to "any employee regardless of role", since that
    would hand a Machine Guarding corrective action to, say, an HR Generalist. Only if
    literally nobody company-wide holds that title does it fall back to the facility's
    general roster."""
    pool = [e for e in T["employees"] if e["facility_id"] == facility_id]
    if not title:
        return pool or T["employees"]
    exact = [e for e in pool if e["role_id"] == ROLE_BY_TITLE[title]]
    if exact:
        return exact
    any_site_same_role = [e for e in T["employees"] if e["role_id"] == ROLE_BY_TITLE[title]]
    return any_site_same_role or pool or T["employees"]

def any_employee(title=None):
    pool = [e for e in T["employees"] if (title is None or e["role_id"] == ROLE_BY_TITLE.get(title))]
    return random.choice(pool or T["employees"])

# =============================================================================
# 4. CONTRACTORS (20) — reserve 4 for Pattern 6 (training gaps)
# =============================================================================
for i in range(20):
    fn, ln = unique_contractor_name()
    firm, trade = random.choice(CONTRACTOR_FIRMS)
    facility_id = random.choice(FAC_IDS)
    assigned = rand_date(WINDOW_START, TODAY - timedelta(days=30))
    T["contractors"].append({
        "contractor_id": f"CTR-{i+1:04d}", "contracting_firm": firm, "trade": trade,
        "primary_facility_id": facility_id, "assigned_date": iso(assigned),
        "safety_orientation_completed": 1, "safety_orientation_date": iso(assigned - timedelta(days=random.randint(1,10))),
        "status": "Active",
    })
PATTERN6_CONTRACTOR_IDS = ["CTR-0003", "CTR-0007", "CTR-0011", "CTR-0014"]
for cid in PATTERN6_CONTRACTOR_IDS:
    c = next(c for c in T["contractors"] if c["contractor_id"] == cid)
    c["safety_orientation_completed"] = 0
    c["safety_orientation_date"] = None
    if cid in ("CTR-0003", "CTR-0007"):
        c["contracting_firm"], c["trade"] = "Redline Welding & Fabrication", "Welding/Fabrication"
    else:
        c["contracting_firm"], c["trade"] = "Vantage Industrial Coatings", "Painting/Coatings"

# =============================================================================
# 5. EQUIPMENT (30) — reserve ids for Pattern 2 (machine guarding) and Pattern 5 (maintenance delay)
# =============================================================================
for i in range(30):
    etype, category, makers = random.choice(EQUIPMENT_TYPES)
    facility_id = random.choice(FAC_IDS)
    install = rand_date(date(1998,1,1), date(2024,6,1))
    last_maint = rand_date(max(install, date(2025,3,1)), TODAY - timedelta(days=10))
    next_due = last_maint + timedelta(days=random.choice([90,120,180]))
    T["equipment"].append({
        "equipment_id": f"EQ-{i+1:04d}", "facility_id": facility_id, "equipment_type": etype, "category": category,
        "manufacturer": random.choice(makers), "model_number": f"{random.choice(['MX','GX','TX','RX','PX'])}-{random.randint(100,999)}",
        "serial_number": f"SN{random.randint(100000,999999)}", "install_date": iso(install),
        "last_maintenance_date": iso(last_maint), "next_maintenance_due": iso(next_due),
        "status": "Operational", "criticality": random.choice(["Medium","Medium","High"]),
    })

# force two Punch Press units (Pattern 2) at North and Central
T["equipment"][0].update({"equipment_id":"EQ-0001","equipment_type":"Punch Press","category":"Production",
                           "facility_id":FAC_NORTH,"manufacturer":"Amada","criticality":"High"})
T["equipment"][1].update({"equipment_id":"EQ-0002","equipment_type":"Punch Press","category":"Production",
                           "facility_id":FAC_CENTRAL,"manufacturer":"Trumpf","criticality":"High"})
PATTERN2_EQUIPMENT_IDS = ["EQ-0001", "EQ-0002"]

# force two forklifts at North and South (Pattern 1)
T["equipment"][2].update({"equipment_id":"EQ-0003","equipment_type":"Forklift (Electric)","category":"Material Handling",
                           "facility_id":FAC_NORTH,"manufacturer":"Toyota","criticality":"Medium"})
T["equipment"][3].update({"equipment_id":"EQ-0004","equipment_type":"Forklift (Propane)","category":"Material Handling",
                           "facility_id":FAC_SOUTH,"manufacturer":"Hyster","criticality":"Medium"})
PATTERN1_EQUIPMENT_IDS = {"NORTH": "EQ-0003", "SOUTH": "EQ-0004"}

# reserve two equipment ids for Pattern 5 (maintenance delay -> incident), distinct from patterns 1/2
T["equipment"][4].update({"equipment_id":"EQ-0005","equipment_type":"Air Compressor","category":"Utilities",
                           "facility_id":FAC_CENTRAL,"manufacturer":"Ingersoll Rand","criticality":"High"})
T["equipment"][5].update({"equipment_id":"EQ-0006","equipment_type":"Conveyor System","category":"Material Handling",
                           "facility_id":FAC_SOUTH,"manufacturer":"Hytrol","criticality":"Medium"})
PATTERN5_EQUIPMENT_IDS = ["EQ-0005", "EQ-0006"]
# re-sync ids/index map after manual overrides (ids 1-6 are now fixed; ids for i>=6 keep EQ-{i+1:04d} pattern already)
for idx in range(6):
    T["equipment"][idx]["equipment_id"] = f"EQ-{idx+1:04d}"

def equip_at(facility_id):
    pool = [e for e in T["equipment"] if e["facility_id"] == facility_id]
    return pool or T["equipment"]

def equip_type(eid):
    return next(e["equipment_type"] for e in T["equipment"] if e["equipment_id"] == eid)

def equip_facility(eid):
    return next(e["facility_id"] for e in T["equipment"] if e["equipment_id"] == eid)

print(f"Setup complete: {len(T['facilities'])} facilities, {len(T['employees'])} employees, "
      f"{len(T['contractors'])} contractors, {len(T['equipment'])} equipment.")

# =============================================================================
# 6. SOPs (30)
# =============================================================================
for i, (title, category) in enumerate(SOP_CATALOG, start=1):
    owner = any_employee(random.choice(["Safety Manager","EHS Coordinator","Plant Manager"]))
    effective = rand_date(date(2019,1,1), date(2025,6,1))
    T["sops"].append({
        "sop_id": f"SOP-{i:04d}", "title": title, "category": category,
        "version": f"{random.randint(1,4)}.{random.randint(0,9)}", "effective_date": iso(effective),
        "next_review_date": iso(effective + timedelta(days=365*random.choice([1,2,3]))),
        "owner_employee_id": owner["employee_id"],
        "facility_id": None if random.random() < 0.6 else random.choice(FAC_IDS),
        "status": random.choices(["Active","Under Revision","Retired"], weights=[0.8,0.15,0.05])[0],
    })
SOP_BY_TITLE = {s["title"]: s["sop_id"] for s in T["sops"]}

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
    return SOP_BY_TITLE.get(mapping.get(hazard_category), random.choice(T["sops"])["sop_id"])

# =============================================================================
# 7. HAZARDS (75)
# =============================================================================
hazard_seq = 0
def add_hazard(category, description, facility_id=None, equipment_id=None, consequence="Injury or property damage", forced_id=None):
    global hazard_seq
    hazard_seq += 1
    hid = forced_id or f"HAZ-{hazard_seq:04d}"
    identified = rand_date(WINDOW_START, TODAY - timedelta(days=20))
    T["hazards"].append({
        "hazard_id": hid, "hazard_category": category, "description": description,
        "facility_id": facility_id, "equipment_id": equipment_id, "typical_consequence": consequence,
        "identified_date": iso(identified),
        "identified_by_employee_id": any_employee("Safety Manager")["employee_id"],
        "status": "Active",
    })
    return hid

# Pattern-reserved hazards first, so their ids are stable/easy to find
HAZ_FORKLIFT_NORTH = add_hazard("Forklift / Vehicle Incident",
    "Pedestrian and forklift traffic share aisles without segregated walkways in the North Plant warehouse.",
    facility_id=FAC_NORTH, equipment_id=PATTERN1_EQUIPMENT_IDS["NORTH"],
    consequence="Struck-by injury to pedestrian")
HAZ_FORKLIFT_SOUTH = add_hazard("Forklift / Vehicle Incident",
    "Blind corners near the South Plant loading dock create forklift/pedestrian conflict points.",
    facility_id=FAC_SOUTH, equipment_id=PATTERN1_EQUIPMENT_IDS["SOUTH"],
    consequence="Struck-by injury to pedestrian")
HAZ_PUNCHPRESS = add_hazard("Machine Guarding Failure",
    "Punch press point-of-operation guarding is prone to being propped open during jam-clearing.",
    facility_id=None, equipment_id=None, consequence="Amputation or crush injury to hand/fingers")
HAZ_MAINT_5A = add_hazard("Equipment Failure Risk",
    "Air compressor condition degrades without timely preventive maintenance, risking uncontrolled failure.",
    facility_id=FAC_CENTRAL, equipment_id=PATTERN5_EQUIPMENT_IDS[0], consequence="Equipment failure, possible injury")
HAZ_MAINT_5B = add_hazard("Equipment Failure Risk",
    "Conveyor drive components wear without timely preventive maintenance, risking jams and belt failure.",
    facility_id=FAC_SOUTH, equipment_id=PATTERN5_EQUIPMENT_IDS[1], consequence="Equipment failure, possible injury")
HAZ_CONTRACTOR_LOTO = add_hazard("Lockout/Tagout Violation",
    "Contractors performing energized/mechanical work without confirmed facility LOTO training or permit sign-off.",
    facility_id=None, equipment_id=None, consequence="Severe injury to contractor")

# background hazards: distribute remaining categories across facilities/equipment realistically
CATEGORY_CONSEQUENCE = {
    "Machine Guarding Failure": "Amputation or crush injury",
    "Lockout/Tagout Violation": "Severe injury during equipment servicing",
    "Slip/Trip/Fall": "Sprain, fracture, or laceration",
    "Chemical Exposure": "Skin/respiratory irritation or burn",
    "Electrical Hazard / Arc Flash": "Electrical shock or arc flash burn",
    "Forklift / Vehicle Incident": "Struck-by injury or property damage",
    "Falling Object / Struck-By": "Head or upper body injury",
    "Ergonomic Strain": "Musculoskeletal injury",
    "Fire / Explosion Risk": "Burn injury or facility damage",
    "Confined Space Hazard": "Asphyxiation or severe injury",
    "Noise Exposure": "Hearing loss",
    "Pressure System Failure": "Blast injury or equipment damage",
    "Environmental Spill / Release": "Environmental contamination",
    "Overhead Crane / Rigging Hazard": "Struck-by or crush injury",
    "Caught-In / Caught-Between": "Crush injury or amputation",
    "Heat Stress": "Heat exhaustion or heat stroke",
    "Housekeeping / Walkway Obstruction": "Slip, trip, or fall injury",
    "Equipment Failure Risk": "Uncontrolled equipment failure resulting in injury or property damage",
}
HAZARD_DESC_TEMPLATES = {
    "Machine Guarding Failure": "Guarding on {equip} can be bypassed during jam-clearing or changeover.",
    "Lockout/Tagout Violation": "Energy isolation points on {equip} are not consistently verified before service.",
    "Slip/Trip/Fall": "Walkway near {equip} is prone to fluid leaks and debris accumulation.",
    "Chemical Exposure": "Chemical transfer/handling near {equip} lacks secondary containment.",
    "Electrical Hazard / Arc Flash": "Electrical panel servicing {equip} lacks current arc-flash labeling.",
    "Forklift / Vehicle Incident": "Vehicle traffic near {equip} shares a path with pedestrians.",
    "Falling Object / Struck-By": "Overhead storage near {equip} is not secured against shifting.",
    "Ergonomic Strain": "Manual material handling at {equip} requires repetitive lifting.",
    "Fire / Explosion Risk": "Hot work performed near {equip} without consistent permit controls.",
    "Confined Space Hazard": "Confined space adjacent to {equip} lacks continuous atmospheric monitoring.",
    "Noise Exposure": "Sustained noise levels near {equip} exceed the facility action level.",
    "Pressure System Failure": "Pressure relief devices on {equip} are due for recertification.",
    "Environmental Spill / Release": "{equip} drain/containment path is not fully protected against spill migration.",
    "Overhead Crane / Rigging Hazard": "Rigging inspection cadence for loads near {equip} is inconsistent.",
    "Caught-In / Caught-Between": "Nip points on {equip} are accessible during normal operation.",
    "Heat Stress": "Ambient temperature near {equip} rises significantly during summer shifts.",
    "Housekeeping / Walkway Obstruction": "Storage near {equip} intrudes on the marked egress path.",
}
while len(T["hazards"]) < 75:
    cat = random.choice(HAZARD_CATEGORIES)
    # a hazard citing a specific equipment instance always inherits THAT equipment's facility
    # (a hazard can't be "company-wide" while pointing at one site's specific machine — that
    # would be exactly the kind of disconnected record the spec asks us to avoid). Only a
    # hazard with no equipment reference at all can be genuinely company-wide (facility_id=NULL).
    if random.random() < 0.35:
        facility_id, equipment_id, equip_label = None, None, cat.lower()
    else:
        eq_choice = random.choice(T["equipment"])
        facility_id, equipment_id, equip_label = eq_choice["facility_id"], eq_choice["equipment_id"], eq_choice["equipment_type"]
    add_hazard(cat, HAZARD_DESC_TEMPLATES[cat].format(equip=equip_label),
               facility_id=facility_id, equipment_id=equipment_id,
               consequence=CATEGORY_CONSEQUENCE[cat])

def hazards_by_category(cat):
    return [h for h in T["hazards"] if h["hazard_category"] == cat]

print(f"SOPs: {len(T['sops'])}, Hazards: {len(T['hazards'])}")

# =============================================================================
# 8. CONTROLS (50)
# =============================================================================
control_seq = 0
def add_control(name, ctype, hazard_id, sop_id=None, facility_id=None, description="", forced_id=None, implemented=None):
    global control_seq
    control_seq += 1
    cid = forced_id or f"CTL-{control_seq:04d}"
    impl = implemented or rand_date(date(2019,1,1), WINDOW_START)
    T["controls"].append({
        "control_id": cid, "control_name": name, "control_type": ctype, "hazard_id": hazard_id,
        "related_sop_id": sop_id, "facility_id": facility_id, "description": description,
        "implemented_date": iso(impl), "status": "Active",
    })
    return cid

# Pattern 4: the control that repeatedly fails
CTL_PUNCHPRESS_GUARD = add_control(
    "Fixed Machine Guard Interlock Program", "Engineering", HAZ_PUNCHPRESS,
    sop_id=SOP_BY_TITLE["Machine Guarding Standard"], facility_id=None,
    description="Interlocked point-of-operation guards on punch presses, verified by periodic inspection.",
    implemented=date(2021, 3, 1))

CTL_FORKLIFT_NORTH = add_control("Warehouse Pedestrian/Forklift Segregation", "Engineering", HAZ_FORKLIFT_NORTH,
    sop_id=SOP_BY_TITLE["Powered Industrial Truck (Forklift) Operation"], facility_id=FAC_NORTH,
    description="Marked pedestrian lanes and mirrors at blind corners in the North Plant warehouse.")
CTL_FORKLIFT_SOUTH = add_control("Loading Dock Traffic Control", "Administrative", HAZ_FORKLIFT_SOUTH,
    sop_id=SOP_BY_TITLE["Powered Industrial Truck (Forklift) Operation"], facility_id=FAC_SOUTH,
    description="Posted traffic patterns and horn-at-corner requirement near the South Plant loading dock.")
CTL_CONTRACTOR_LOTO = add_control("Contractor LOTO Verification Gate", "Administrative", HAZ_CONTRACTOR_LOTO,
    sop_id=SOP_BY_TITLE["Contractor Safety Management Program"], facility_id=None,
    description="Verification that contractors have current LOTO training before energized/mechanical work is authorized.")

# background controls: 1-2 per remaining hazard until we reach 50
remaining_hazards = [h for h in T["hazards"] if h["hazard_id"] not in
                      (HAZ_PUNCHPRESS, HAZ_FORKLIFT_NORTH, HAZ_FORKLIFT_SOUTH, HAZ_CONTRACTOR_LOTO)]
CONTROL_TYPE_BY_CATEGORY = {
    "Machine Guarding Failure": "Engineering", "Lockout/Tagout Violation": "Procedural",
    "Slip/Trip/Fall": "Administrative", "Chemical Exposure": "PPE",
    "Electrical Hazard / Arc Flash": "Engineering", "Forklift / Vehicle Incident": "Administrative",
    "Falling Object / Struck-By": "Engineering", "Ergonomic Strain": "Administrative",
    "Fire / Explosion Risk": "Procedural", "Confined Space Hazard": "Procedural",
    "Noise Exposure": "PPE", "Pressure System Failure": "Engineering",
    "Environmental Spill / Release": "Engineering", "Overhead Crane / Rigging Hazard": "Procedural",
    "Caught-In / Caught-Between": "Engineering", "Heat Stress": "Administrative",
    "Housekeeping / Walkway Obstruction": "Administrative", "Equipment Failure Risk": "Procedural",
}
random.shuffle(remaining_hazards)
i = 0
while len(T["controls"]) < 50 and remaining_hazards:
    hz = remaining_hazards[i % len(remaining_hazards)]
    i += 1
    ctype = CONTROL_TYPE_BY_CATEGORY.get(hz["hazard_category"], "Administrative")
    add_control(f"{hz['hazard_category']} Control — {hz['hazard_id']}", ctype, hz["hazard_id"],
                sop_id=sop_for_category(hz["hazard_category"]), facility_id=hz["facility_id"],
                description=f"Control addressing: {hz['description']}")
    if i > 300:
        break

def controls_for_hazard(hazard_id):
    return [c for c in T["controls"] if c["hazard_id"] == hazard_id]

print(f"Controls: {len(T['controls'])}")

# =============================================================================
# 9. MAINTENANCE RECORDS (50) — Pattern 5 seeded here (delayed maintenance)
# =============================================================================
maint_seq = 0
def add_maintenance(equipment_id, scheduled, status, mtype="Preventive", delay_days=0, description=None, forced_id=None):
    global maint_seq
    maint_seq += 1
    mid = forced_id or f"MNT-{maint_seq:04d}"
    facility_id = equip_facility(equipment_id)
    actual = None
    if status == "Completed":
        actual = scheduled + timedelta(days=random.randint(-2, 3))
    elif status == "Delayed":
        actual = scheduled + timedelta(days=delay_days)
    # Overdue/Scheduled -> actual stays None
    T["maintenance_records"].append({
        "maintenance_record_id": mid, "equipment_id": equipment_id, "facility_id": facility_id,
        "maintenance_type": mtype, "scheduled_date": iso(scheduled), "actual_date": iso(actual) if actual else None,
        "delay_days": delay_days if status in ("Delayed","Overdue") else 0,
        "performed_by_employee_id": random.choice(employees_at(facility_id, "Maintenance Technician"))["employee_id"] if status in ("Completed","Delayed") else None,
        "description": description or f"Routine {mtype.lower()} maintenance on {equip_type(equipment_id)}.",
        "status": status, "related_incident_id": None,
    })
    return mid

# Pattern 5: two equipment items get a clearly delayed PM cycle, ~5-16 days before a follow-on incident
PATTERN5_EVENTS = []  # (equipment_id, maintenance_record_id, incident_trigger_date)
for eq_id, delay in zip(PATTERN5_EQUIPMENT_IDS, [34, 41]):
    scheduled = rand_date(date(2025, 9, 1), date(2026, 5, 1))
    mid = add_maintenance(eq_id, scheduled, "Delayed", mtype="Preventive", delay_days=delay,
        description=f"Scheduled preventive maintenance on {equip_type(eq_id)} delayed due to backlog/parts availability.")
    actual_date = scheduled + timedelta(days=delay)
    trigger_date = actual_date + timedelta(days=random.randint(6, 15))
    PATTERN5_EVENTS.append((eq_id, mid, trigger_date))

# background maintenance history (mostly Completed, some routine Delayed/Overdue elsewhere for realism)
while len(T["maintenance_records"]) < 50:
    eq = random.choice(T["equipment"])
    scheduled = rand_date(WINDOW_START, TODAY - timedelta(days=5))
    status = random.choices(["Completed","Delayed","Overdue","Scheduled"], weights=[0.72,0.13,0.08,0.07])[0]
    delay = random.randint(5, 25) if status in ("Delayed","Overdue") else 0
    mtype = random.choices(["Preventive","Corrective","Inspection"], weights=[0.6,0.25,0.15])[0]
    add_maintenance(eq["equipment_id"], scheduled, status, mtype=mtype, delay_days=delay)

print(f"Maintenance records: {len(T['maintenance_records'])} (Pattern 5 events: {len(PATTERN5_EVENTS)})")

# =============================================================================
# 10. TRAINING RECORDS (50) — Pattern 6 seeded here (contractor training gaps)
# =============================================================================
train_seq = 0
def add_training(topic, status, employee_id=None, contractor_id=None, training_date=None, expiry=None, result=None, forced_id=None):
    global train_seq
    train_seq += 1
    tid = forced_id or f"TRN-{train_seq:04d}"
    T["training_records"].append({
        "training_record_id": tid, "employee_id": employee_id, "contractor_id": contractor_id,
        "training_topic": topic, "training_date": iso(training_date) if training_date else None,
        "expiry_date": iso(expiry) if expiry else None, "status": status,
        "conducted_by_employee_id": any_employee("EHS Coordinator")["employee_id"] if status != "Not Completed" else None,
        "result": result,
    })
    return tid

SAFETY_TOPICS = ["Lockout/Tagout (LOTO)","Confined Space Entry","Forklift Operation","Machine Guarding",
                  "Fall Protection","Hazard Communication / Chemical Safety","Contractor Safety Orientation",
                  "PPE Requirements","Hearing Conservation","Emergency Response"]

# Pattern 6: flagged contractors get an explicit gap on a safety-critical topic
PATTERN6_GAP_TOPICS = {
    "CTR-0003": "Lockout/Tagout (LOTO)", "CTR-0007": "Confined Space Entry",
    "CTR-0011": "Contractor Safety Orientation", "CTR-0014": "Lockout/Tagout (LOTO)",
}
for cid, topic in PATTERN6_GAP_TOPICS.items():
    status = random.choice(["Not Completed", "Expired"])
    if status == "Not Completed":
        add_training(topic, "Not Completed", contractor_id=cid)
    else:
        old_date = rand_date(date(2023, 6, 1), date(2024, 8, 1))
        add_training(topic, "Expired", contractor_id=cid, training_date=old_date,
                     expiry=old_date + timedelta(days=365), result="Pass (expired)")

# background training: employees (safety-critical roles get more), remaining contractors
safety_critical_employees = [e for e in T["employees"]
                              if next(r["is_safety_critical"] for r in T["roles"] if r["role_id"] == e["role_id"])]
other_contractors = [c["contractor_id"] for c in T["contractors"] if c["contractor_id"] not in PATTERN6_GAP_TOPICS]

while len(T["training_records"]) < 50:
    if random.random() < 0.75 and safety_critical_employees:
        emp = random.choice(safety_critical_employees)
        topic = random.choice(SAFETY_TOPICS)
        tdate = rand_date(WINDOW_START, TODAY - timedelta(days=10))
        status = "Current"
        expiry = tdate + timedelta(days=730)
        if expiry < TODAY:
            status = "Expired"
        add_training(topic, status, employee_id=emp["employee_id"], training_date=tdate, expiry=expiry, result="Pass")
    else:
        cid = random.choice(other_contractors)
        topic = random.choice(["Contractor Safety Orientation","Lockout/Tagout (LOTO)","Confined Space Entry","PPE Requirements"])
        tdate = rand_date(WINDOW_START, TODAY - timedelta(days=10))
        add_training(topic, "Current", contractor_id=cid, training_date=tdate, expiry=tdate+timedelta(days=365), result="Pass")

print(f"Training records: {len(T['training_records'])} (Pattern 6 gaps: {len(PATTERN6_GAP_TOPICS)})")

# second Pattern-5 delay/incident cycle on EQ-0005, earlier in the window, for a clearer trend signal
_scheduled2 = rand_date(date(2025, 3, 1), date(2025, 7, 1))
_mid2 = add_maintenance(PATTERN5_EQUIPMENT_IDS[0], _scheduled2, "Delayed", mtype="Preventive", delay_days=29,
    description=f"Scheduled preventive maintenance on {equip_type(PATTERN5_EQUIPMENT_IDS[0])} delayed due to backlog/parts availability.")
PATTERN5_EVENTS.append((PATTERN5_EQUIPMENT_IDS[0], _mid2, _scheduled2 + timedelta(days=29) + timedelta(days=random.randint(6,15))))

# ---- sync equipment.last_maintenance_date / next_maintenance_due to the REAL maintenance_records
# table (all maintenance_records generation is done as of this point). Previously these two columns
# were populated independently at random when `equipment` rows were first created, which meant an
# equipment's "last maintenance" date usually matched no maintenance_records row at all — the exact
# kind of disconnected-but-FK-valid record the spec warned against. Equipment with no maintenance
# history at all keeps its originally-generated placeholder value, since there's nothing real to
# derive it from.
for eq in T["equipment"]:
    recs = [m for m in T["maintenance_records"] if m["equipment_id"] == eq["equipment_id"]]
    performed = [m for m in recs if m["actual_date"]]
    if performed:
        latest = max(performed, key=lambda m: m["actual_date"])
        eq["last_maintenance_date"] = latest["actual_date"]
    unperformed_future = [m for m in recs if m["status"] in ("Scheduled", "Overdue") and not m["actual_date"]]
    if unperformed_future:
        nearest = min(unperformed_future, key=lambda m: m["scheduled_date"])
        eq["next_maintenance_due"] = nearest["scheduled_date"]
    elif performed:
        base = date.fromisoformat(eq["last_maintenance_date"])
        eq["next_maintenance_due"] = iso(base + timedelta(days=random.choice([90, 120, 180])))

print("Equipment maintenance dates synced to real maintenance_records.")

# add a couple of "Fall / Working at Height" hazards (category not needed elsewhere in the 75 background draw)
HAZARD_CATEGORIES.append("Fall / Working at Height")
CATEGORY_CONSEQUENCE["Fall / Working at Height"] = "Fall injury or fatality"
HAZARD_DESC_TEMPLATES["Fall / Working at Height"] = "Elevated work near {equip} is performed on mobile ladders/platforms without consistent fall protection."
CONTROL_TYPE_BY_CATEGORY["Fall / Working at Height"] = "Administrative"
HAZ_HEIGHT_1 = add_hazard("Fall / Working at Height",
    "Rooftop and elevated ventilation-unit maintenance is performed on rolling ladders without consistent fall protection.",
    facility_id=FAC_NORTH, equipment_id=None, consequence="Fall injury or fatality")
HAZ_HEIGHT_2 = add_hazard("Fall / Working at Height",
    "Elevated racking access at the South Plant distribution area lacks a fixed platform.",
    facility_id=FAC_SOUTH, equipment_id=None, consequence="Fall injury or fatality")
add_control("Fall Protection Program — Elevated Maintenance", "Administrative", HAZ_HEIGHT_1,
            sop_id=SOP_BY_TITLE["Fall Protection Program"], facility_id=FAC_NORTH,
            description="Mandatory harness/anchor use for elevated maintenance tasks regardless of duration.")

print(f"Hazards (final): {len(T['hazards'])}, Controls (final): {len(T['controls'])}")

# =============================================================================
# 11. INCIDENTS (100) — background variety + 6 deliberate patterns
# =============================================================================
INCIDENT_TEMPLATES = {
    "Machine Guarding Failure": [
        "Operator found the point-of-operation guard on {equip} propped open during jam-clearing.",
        "Interlock on {equip} was bypassed, allowing operation with the guard door open.",
    ],
    "Lockout/Tagout Violation": [
        "Technician began servicing {equip} before verifying zero energy state.",
        "LOTO device was found removed from {equip} while work was still in progress.",
    ],
    "Slip/Trip/Fall": [
        "Employee slipped on a fluid leak near {equip}.",
        "Worker tripped over an unsecured cable near {equip}.",
    ],
    "Chemical Exposure": [
        "Employee reported skin irritation after contact with cleaning solvent near {equip}.",
        "Small chemical splash occurred during transfer near {equip}; PPE limited exposure.",
    ],
    "Electrical Hazard / Arc Flash": [
        "Technician opened the electrical panel on {equip} without confirming de-energization.",
        "Exposed wiring was identified on {equip} during a routine walk-through.",
    ],
    "Forklift / Vehicle Incident": [
        "Forklift operator narrowly avoided a pedestrian near {equip} traffic lane.",
        "Forklift struck a storage rack while maneuvering near {equip}; minor property damage.",
    ],
    "Falling Object / Struck-By": [
        "A component fell from overhead storage near {equip}.",
        "Worker was struck by an ejected part from {equip} during operation.",
    ],
    "Ergonomic Strain": [
        "Employee reported lower back strain after repetitive lifting at the {equip} station.",
        "Operator reported repetitive strain after an extended shift at {equip}.",
    ],
    "Fire / Explosion Risk": [
        "Overheating was detected on {equip} motor housing; no ignition occurred.",
        "Hot work performed near {equip} ignited nearby debris; extinguished immediately.",
    ],
    "Confined Space Hazard": [
        "Atmospheric monitoring flagged low oxygen prior to entry near {equip}.",
        "Entry was attempted into a confined space near {equip} without a permit on file.",
    ],
    "Noise Exposure": [
        "Sound level survey near {equip} exceeded the facility action level without hearing protection in use.",
    ],
    "Pressure System Failure": [
        "Relief valve on {equip} activated unexpectedly during startup.",
        "Pressure gauge anomaly on {equip} prompted the unit to be taken offline as a precaution.",
    ],
    "Environmental Spill / Release": [
        "Hydraulic fluid leak from {equip} reached the floor drain before containment.",
        "Coolant leak from {equip} required an environmental spill response.",
    ],
    "Overhead Crane / Rigging Hazard": [
        "A load shifted unexpectedly while being lifted by {equip}; operator halted the lift safely.",
        "Rigging inspection near {equip} found a frayed sling, removed from service.",
    ],
    "Caught-In / Caught-Between": [
        "Employee's sleeve caught briefly on a moving component of {equip}.",
        "Worker's hand came close to a nip point on {equip} while clearing a jam.",
    ],
    "Heat Stress": [
        "Employee reported heat exhaustion symptoms working near {equip} during a summer shift.",
    ],
    "Housekeeping / Walkway Obstruction": [
        "Pallets stored in the designated walkway near {equip} created an obstruction.",
        "Debris accumulation near {equip} partially blocked an emergency egress path.",
    ],
    "Fall / Working at Height": [
        "Technician on a rolling ladder near {equip} lost balance briefly while reaching to the side.",
        "Elevated access near {equip} was performed without fall protection in use.",
    ],
    "Equipment Failure Risk": [
        "{equip} exhibited abnormal vibration/noise consistent with deferred maintenance before failing.",
        "{equip} shut down unexpectedly during production, consistent with a missed preventive maintenance cycle.",
    ],
}
TYPES_BY_CATEGORY = {
    "Machine Guarding Failure": ["Near Miss","Unsafe Condition","Injury"],
    "Lockout/Tagout Violation": ["Near Miss","Unsafe Condition"],
    "Slip/Trip/Fall": ["Injury","Near Miss"],
    "Chemical Exposure": ["Injury","Near Miss","Environmental"],
    "Electrical Hazard / Arc Flash": ["Near Miss","Unsafe Condition"],
    "Forklift / Vehicle Incident": ["Near Miss","Property Damage"],
    "Falling Object / Struck-By": ["Near Miss","Injury"],
    "Ergonomic Strain": ["Injury"],
    "Fire / Explosion Risk": ["Property Damage","Near Miss"],
    "Confined Space Hazard": ["Unsafe Condition","Near Miss"],
    "Noise Exposure": ["Unsafe Condition"],
    "Pressure System Failure": ["Equipment Failure","Near Miss"],
    "Environmental Spill / Release": ["Environmental","Property Damage"],
    "Overhead Crane / Rigging Hazard": ["Near Miss","Property Damage"],
    "Caught-In / Caught-Between": ["Near Miss","Injury"],
    "Heat Stress": ["Injury"],
    "Housekeeping / Walkway Obstruction": ["Unsafe Condition","Near Miss"],
    "Fall / Working at Height": ["Near Miss","Injury"],
    "Equipment Failure Risk": ["Equipment Failure","Unsafe Condition"],
}
ROOT_CAUSE_CATEGORIES = ["Procedural Non-Compliance","Equipment Failure","Inadequate Training",
    "Inadequate Engineering Control","Communication Breakdown","Time Pressure / Production Pressure",
    "Inadequate Maintenance","Human Error","Design Deficiency"]

incident_seq = 0
def add_incident(facility_id, hazard, equipment_id=None, incident_type=None, involved_employee_id=None,
                  involved_contractor_id=None, incident_dt=None, description=None, severity=None,
                  root_cause=None, forced_id=None, injury_status=None):
    global incident_seq
    incident_seq += 1
    iid = forced_id or f"INC-{incident_seq:04d}"
    cat = hazard["hazard_category"]
    itype = incident_type or random.choice(TYPES_BY_CATEGORY.get(cat, ["Near Miss","Unsafe Condition"]))
    equip_id = equipment_id or hazard["equipment_id"]
    equip_label = equip_type(equip_id) if equip_id else cat.lower()
    desc = description or random.choice(INCIDENT_TEMPLATES.get(cat, ["An incident occurred involving {equip}."])).format(equip=equip_label)
    dt = incident_dt or rand_date(WINDOW_START, TODAY - timedelta(days=1))
    if isinstance(dt, date) and not isinstance(dt, datetime):
        # datetime is a subclass of date — this guard must not match an already-full datetime,
        # or it would silently discard a real time-of-day and replace it with a random one.
        dt = datetime.combine(dt, datetime.min.time()) + timedelta(hours=random.randint(6,22), minutes=random.choice([0,15,30,45]))

    if itype == "Injury":
        inj = injury_status or random.choices(["First Aid Only","Minor Injury - Treated Offsite","Recordable Injury"], weights=[0.55,0.3,0.15])[0]
        sev = severity or random.choices(["Low","Medium","High"], weights=[0.35,0.45,0.2])[0]
    else:
        inj = injury_status or "None"
        sev = severity or random.choices(["Low","Medium","High","Critical"], weights=[0.4,0.35,0.18,0.07])[0]

    potential = CATEGORY_CONSEQUENCE.get(cat, "Injury or property damage")
    # a report is always filed by someone who works at that facility
    reporter = random.choice(employees_at(facility_id))
    reported_at = dt + timedelta(hours=random.randint(0,6))

    age_days = (TODAY - dt.date()).days
    if age_days > 45:
        inv_status = "Completed"; closure = "Closed"
        closed_date = dt.date() + timedelta(days=random.randint(20,40))
        if closed_date > TODAY: closed_date = TODAY
        rc = root_cause or random.choice(ROOT_CAUSE_CATEGORIES)
    elif age_days > 14:
        inv_status = random.choice(["Completed","In Progress"])
        if inv_status == "Completed":
            closure = random.choice(["Closed","Open"]); closed_date = dt.date() + timedelta(days=random.randint(10,age_days)) if closure=="Closed" else None
            rc = root_cause or random.choice(ROOT_CAUSE_CATEGORIES)
        else:
            closure = "Open"; closed_date = None; rc = None
    else:
        inv_status = random.choice(["Not Started","In Progress"])
        closure = "Open"; closed_date = None; rc = None

    immediate_actions = {
        "Injury": "First aid administered; area secured; supervisor notified.",
        "Near Miss": "Work paused; area inspected; supervisor and EHS notified.",
        "Property Damage": "Area secured; damage documented; equipment tagged out of service pending inspection.",
        "Environmental": "Spill contained with on-site kit; EHS and environmental compliance notified.",
        "Equipment Failure": "Equipment shut down and locked out; maintenance notified.",
        "Unsafe Condition": "Condition flagged and barricaded pending correction; supervisor notified.",
    }

    T["incidents"].append({
        "incident_id": iid, "facility_id": facility_id, "location": f"{equip_label} area, {facility_id}",
        "incident_datetime": dt.isoformat(sep=" "), "incident_type": itype, "description": desc,
        "equipment_id": equip_id, "hazard_id": hazard["hazard_id"],
        "involved_employee_id": involved_employee_id, "involved_contractor_id": involved_contractor_id,
        "injury_status": inj, "potential_consequence": potential, "initial_severity": sev,
        "immediate_action": immediate_actions.get(itype, "Area secured; supervisor notified."),
        "investigation_status": inv_status, "root_cause_category": rc, "related_risk_register_id": None,
        "reported_by_employee_id": reporter["employee_id"], "reported_at": reported_at.isoformat(sep=" "),
        "closure_status": closure, "closed_date": iso(closed_date) if closed_date else None,
    })
    return iid, dt.date()

HAZ_BY_ID = {h["hazard_id"]: h for h in T["hazards"]}

# ---- Pattern 1: forklift/pedestrian near misses at North (4) and South (3) ----
PATTERN1_INCIDENT_IDS = []
for _ in range(4):
    iid, _ = add_incident(FAC_NORTH, HAZ_BY_ID[HAZ_FORKLIFT_NORTH], equipment_id=PATTERN1_EQUIPMENT_IDS["NORTH"],
                           incident_type="Near Miss")
    PATTERN1_INCIDENT_IDS.append(iid)
for _ in range(3):
    iid, _ = add_incident(FAC_SOUTH, HAZ_BY_ID[HAZ_FORKLIFT_SOUTH], equipment_id=PATTERN1_EQUIPMENT_IDS["SOUTH"],
                           incident_type="Near Miss")
    PATTERN1_INCIDENT_IDS.append(iid)

# ---- Pattern 2 (+4): repeated machine-guarding incidents on the same punch-press type ----
PATTERN2_INCIDENT_IDS = []
for eq_id in PATTERN2_EQUIPMENT_IDS:
    fac = equip_facility(eq_id)
    for k in range(3):
        itype = "Injury" if k == 2 else random.choice(["Near Miss","Unsafe Condition"])
        iid, _ = add_incident(fac, HAZ_BY_ID[HAZ_PUNCHPRESS], equipment_id=eq_id, incident_type=itype,
                               injury_status="First Aid Only" if itype=="Injury" else None)
        PATTERN2_INCIDENT_IDS.append(iid)

# ---- Pattern 5: incidents following delayed maintenance (temporal causality) ----
PATTERN5_INCIDENT_IDS = []
for eq_id, mid, trigger_date in PATTERN5_EVENTS:
    hz = HAZ_BY_ID[HAZ_MAINT_5A] if eq_id == PATTERN5_EQUIPMENT_IDS[0] else HAZ_BY_ID[HAZ_MAINT_5B]
    fac = equip_facility(eq_id)
    iid, _ = add_incident(fac, hz, equipment_id=eq_id, incident_type="Equipment Failure",
                           incident_dt=trigger_date,
                           description=f"{equip_type(eq_id)} failed during production shortly after a delayed preventive maintenance cycle.")
    PATTERN5_INCIDENT_IDS.append(iid)
    m = next(m for m in T["maintenance_records"] if m["maintenance_record_id"] == mid)
    m["related_incident_id"] = iid

# ---- Pattern 6: contractor incidents tied to training-gap contractors ----
PATTERN6_INCIDENT_IDS = []
PATTERN6_COUNTS = {"CTR-0003": 2, "CTR-0007": 1, "CTR-0011": 2, "CTR-0014": 1}
for cid, n in PATTERN6_COUNTS.items():
    contractor = next(c for c in T["contractors"] if c["contractor_id"] == cid)
    fac = contractor["primary_facility_id"]
    topic = PATTERN6_GAP_TOPICS[cid]
    cat = "Lockout/Tagout Violation" if "Lockout" in topic else ("Confined Space Hazard" if "Confined" in topic else "Housekeeping / Walkway Obstruction")
    hz_pool = hazards_by_category(cat) or [HAZ_BY_ID[HAZ_CONTRACTOR_LOTO]]
    for _ in range(n):
        hz = random.choice(hz_pool)
        iid, _ = add_incident(fac, hz, incident_type=random.choice(["Unsafe Condition","Near Miss"]),
                               involved_contractor_id=cid,
                               description=f"Contractor from {contractor['contracting_firm']} observed performing "
                                           f"{topic.lower()}-controlled work without current {topic} training on file.")
        PATTERN6_INCIDENT_IDS.append(iid)

pattern_count = len(PATTERN1_INCIDENT_IDS)+len(PATTERN2_INCIDENT_IDS)+len(PATTERN5_INCIDENT_IDS)+len(PATTERN6_INCIDENT_IDS)
print(f"Pattern incidents seeded: {pattern_count} "
      f"(P1={len(PATTERN1_INCIDENT_IDS)}, P2={len(PATTERN2_INCIDENT_IDS)}, P5={len(PATTERN5_INCIDENT_IDS)}, P6={len(PATTERN6_INCIDENT_IDS)})")

# ---- background incidents: fill to 100, covering full variety, excluding pattern-reserved hazards/contractors ----
EXCLUDED_HAZARDS_FROM_BACKGROUND = {HAZ_FORKLIFT_NORTH, HAZ_FORKLIFT_SOUTH, HAZ_PUNCHPRESS, HAZ_MAINT_5A, HAZ_MAINT_5B}
background_hazard_pool = [h for h in T["hazards"] if h["hazard_id"] not in EXCLUDED_HAZARDS_FROM_BACKGROUND]
non_pattern_contractors = [c["contractor_id"] for c in T["contractors"] if c["contractor_id"] not in PATTERN6_GAP_TOPICS]

while len(T["incidents"]) < 100:
    hz = random.choice(background_hazard_pool)
    fac = hz["facility_id"] or random.choice(FAC_IDS)
    eq_id = hz["equipment_id"]
    if eq_id is None and random.random() < 0.7:
        pool = equip_at(fac)
        eq_id = random.choice(pool)["equipment_id"] if pool else None
    involved_contractor = None
    if hz["hazard_category"] in ("Lockout/Tagout Violation","Confined Space Hazard","Fall / Working at Height") and random.random() < 0.25:
        involved_contractor = random.choice(non_pattern_contractors)
    involved_employee = None if involved_contractor else (random.choice(employees_at(fac))["employee_id"] if random.random() < 0.7 else None)
    add_incident(fac, hz, equipment_id=eq_id, involved_employee_id=involved_employee, involved_contractor_id=involved_contractor)

print(f"Incidents total: {len(T['incidents'])}")

def incidents_for_hazard(hazard_id):
    return [i for i in T["incidents"] if i["hazard_id"] == hazard_id]

def incident_dt(i):
    return datetime.fromisoformat(i["incident_datetime"])

# =============================================================================
# 12. CONTROL ASSESSMENTS (~60) — Pattern 4 seeded here (repeated control failure)
# =============================================================================
ca_seq = 0
def add_control_assessment(control_id, assess_date, rating, findings, related_incident_id=None, forced_id=None):
    global ca_seq
    ca_seq += 1
    caid = forced_id or f"CTLA-{ca_seq:04d}"
    T["control_assessments"].append({
        "control_assessment_id": caid, "control_id": control_id, "assessment_date": iso(assess_date),
        "assessed_by_employee_id": any_employee(random.choice(["Safety Manager","EHS Coordinator"]))["employee_id"],
        "effectiveness_rating": rating, "findings": findings,
        "related_incident_id": related_incident_id, "related_inspection_id": None,
    })
    return caid

# Pattern 4: punch-press guard control assessed 5 times, repeatedly slipping back to ineffective
p2_dates_sorted = sorted(PATTERN2_INCIDENT_IDS, key=lambda iid: incident_dt(next(i for i in T["incidents"] if i["incident_id"]==iid)))
p2_incident_objs = [next(i for i in T["incidents"] if i["incident_id"]==iid) for iid in p2_dates_sorted]
add_control_assessment(CTL_PUNCHPRESS_GUARD, date(2025,2,10), "Effective",
    "Interlocked guards verified in place and functioning during scheduled walkthrough.")
add_control_assessment(CTL_PUNCHPRESS_GUARD, p2_incident_objs[1]["incident_datetime"][:10] if len(p2_incident_objs)>1 else "2025-06-15",
    "Partially Effective", "Guard interlock functions, but operators observed propping the guard during jam-clearing under production pressure.",
    related_incident_id=p2_incident_objs[1]["incident_id"] if len(p2_incident_objs)>1 else None)
add_control_assessment(CTL_PUNCHPRESS_GUARD, p2_incident_objs[3]["incident_datetime"][:10] if len(p2_incident_objs)>3 else "2025-11-01",
    "Ineffective", "Guard found propped open with a physical object at time of incident; interlock defeated.",
    related_incident_id=p2_incident_objs[3]["incident_id"] if len(p2_incident_objs)>3 else None)
add_control_assessment(CTL_PUNCHPRESS_GUARD, date(2026,3,5), "Partially Effective",
    "Guard hardware upgraded after prior finding; compliance improved but not yet sustained across all shifts.")
add_control_assessment(CTL_PUNCHPRESS_GUARD, p2_incident_objs[-1]["incident_datetime"][:10],
    "Ineffective", "Second instance of guard defeat found at time of incident, on the opposite unit; remediation from the prior finding did not transfer facility-wide.",
    related_incident_id=p2_incident_objs[-1]["incident_id"])
PATTERN4_CONTROL_ID = CTL_PUNCHPRESS_GUARD

# forklift + contractor LOTO controls: 2-3 assessments each, mixed results
for ctl_id, hz_ids in [(CTL_FORKLIFT_NORTH, [HAZ_FORKLIFT_NORTH]), (CTL_FORKLIFT_SOUTH, [HAZ_FORKLIFT_SOUTH]),
                        (CTL_CONTRACTOR_LOTO, [HAZ_CONTRACTOR_LOTO])]:
    for _ in range(random.randint(2,3)):
        rating = random.choices(["Effective","Partially Effective","Ineffective"], weights=[0.35,0.4,0.25])[0]
        add_control_assessment(ctl_id, rand_date(WINDOW_START, TODAY-timedelta(days=15)), rating,
            f"Periodic effectiveness review of control for {HAZ_BY_ID[hz_ids[0]]['hazard_category']}.")

# background control assessments for a sample of remaining controls
other_controls = [c for c in T["controls"] if c["control_id"] not in (CTL_PUNCHPRESS_GUARD, CTL_FORKLIFT_NORTH, CTL_FORKLIFT_SOUTH, CTL_CONTRACTOR_LOTO)]
random.shuffle(other_controls)
for c in other_controls:
    if len(T["control_assessments"]) >= 60:
        break
    rating = random.choices(["Effective","Partially Effective","Ineffective"], weights=[0.55,0.32,0.13])[0]
    findings = {
        "Effective": "Control observed functioning as designed during review.",
        "Partially Effective": "Control generally functions but inconsistent compliance was observed.",
        "Ineffective": "Control was not functioning as intended at time of review.",
    }[rating]
    add_control_assessment(c["control_id"], rand_date(WINDOW_START, TODAY-timedelta(days=10)), rating, findings)

print(f"Control assessments: {len(T['control_assessments'])}")

# =============================================================================
# 13. RISK ASSESSMENTS (50)
# =============================================================================
SEVERITY_TIER = {
    "Machine Guarding Failure": 4, "Lockout/Tagout Violation": 4, "Slip/Trip/Fall": 2, "Chemical Exposure": 3,
    "Electrical Hazard / Arc Flash": 4, "Forklift / Vehicle Incident": 4, "Falling Object / Struck-By": 3,
    "Ergonomic Strain": 2, "Fire / Explosion Risk": 4, "Confined Space Hazard": 5, "Noise Exposure": 2,
    "Pressure System Failure": 4, "Environmental Spill / Release": 3, "Overhead Crane / Rigging Hazard": 4,
    "Caught-In / Caught-Between": 4, "Heat Stress": 2, "Housekeeping / Walkway Obstruction": 2,
    "Fall / Working at Height": 5, "Equipment Failure Risk": 3,
}
EFFECTIVENESS_FACTOR = {"Effective": 0.6, "Partially Effective": 0.85, "Ineffective": 1.0, "Not Assessed": 1.0}

def latest_control_rating(hazard_id, as_of):
    ctl_ids = [c["control_id"] for c in controls_for_hazard(hazard_id)]
    assessments = [ca for ca in T["control_assessments"] if ca["control_id"] in ctl_ids and ca["assessment_date"] <= iso(as_of)]
    if not assessments:
        return "Not Assessed"
    return sorted(assessments, key=lambda a: a["assessment_date"])[-1]["effectiveness_rating"]

def recurrence_and_trend(hazard_id, as_of: date):
    incs = [i for i in incidents_for_hazard(hazard_id) if incident_dt(i).date() <= as_of]
    trailing_12mo = [i for i in incs if (as_of - incident_dt(i).date()).days <= 365]
    recent_6mo = len([i for i in incs if 0 <= (as_of - incident_dt(i).date()).days <= 182])
    prior_6mo = len([i for i in incs if 183 <= (as_of - incident_dt(i).date()).days <= 365])
    trend = "Increasing" if recent_6mo > prior_6mo else ("Decreasing" if recent_6mo < prior_6mo else "Stable")
    return len(trailing_12mo), trend

def risk_level_band(score):
    if score >= 20: return "Critical"
    if score >= 12: return "High"
    if score >= 6: return "Medium"
    return "Low"

ra_seq = 0
def hazard_primary_facility(hazard):
    """Facility attribution must follow real signal, never a random pick — a hazard with
    no facility_id of its own is attributed to whichever facility has the most incidents
    against it (its actual primary site); only a hazard with zero incident history and no
    facility_id falls back to a random facility, since there is genuinely no data to base
    the attribution on."""
    if hazard["facility_id"]:
        return hazard["facility_id"]
    incs = incidents_for_hazard(hazard["hazard_id"])
    if incs:
        counts = {}
        for i in incs:
            counts[i["facility_id"]] = counts.get(i["facility_id"], 0) + 1
        return max(counts.items(), key=lambda kv: kv[1])[0]
    if hazard["equipment_id"]:
        return equip_facility(hazard["equipment_id"])
    return random.choice(FAC_IDS)

def add_risk_assessment(hazard, assess_date, source_incident_id=None, forced_id=None):
    global ra_seq
    ra_seq += 1
    raid = forced_id or f"RA-{ra_seq:04d}"
    facility_id = hazard_primary_facility(hazard)
    severity_val = SEVERITY_TIER.get(hazard["hazard_category"], 3)
    recurrence_n, trend = recurrence_and_trend(hazard["hazard_id"], assess_date)
    likelihood_val = 1 if recurrence_n == 0 else (2 if recurrence_n <= 1 else (3 if recurrence_n <= 3 else (4 if recurrence_n <= 5 else 5)))
    raw = likelihood_val * severity_val
    rating = latest_control_rating(hazard["hazard_id"], assess_date)
    ceff = EFFECTIVENESS_FACTOR[rating]
    rfactor = 1.0 if recurrence_n == 0 else (1.15 if recurrence_n <= 2 else 1.3)
    tfactor = {"Increasing": 1.1, "Stable": 1.0, "Decreasing": 0.9}[trend]
    adjusted = min(25.0, round(raw * ceff * rfactor * tfactor, 1))
    level = risk_level_band(adjusted)
    notes = (f"raw_score = likelihood({likelihood_val}) x severity({severity_val}) = {raw}. "
             f"control_effectiveness_factor={ceff} (rating: {rating}). "
             f"recurrence_factor={rfactor} ({recurrence_n} incidents trailing 12mo). "
             f"trend_factor={tfactor} (trend: {trend}). "
             f"adjusted_score = {raw} x {ceff} x {rfactor} x {tfactor} = {adjusted}, clipped to [0,25].")
    T["risk_assessments"].append({
        "risk_assessment_id": raid, "hazard_id": hazard["hazard_id"], "facility_id": facility_id,
        "equipment_id": hazard["equipment_id"], "source_incident_id": source_incident_id,
        "assessment_date": iso(assess_date), "assessed_by_employee_id": any_employee(random.choice(["Safety Manager","EHS Coordinator"]))["employee_id"],
        "likelihood": likelihood_val, "severity": severity_val, "raw_score": raw,
        "control_effectiveness_rating": rating, "control_effectiveness_factor": ceff,
        "recurrence_count_trailing_12mo": recurrence_n, "recurrence_factor": rfactor,
        "trend": trend, "trend_factor": tfactor, "adjusted_score": adjusted, "risk_level": level,
        "methodology_notes": notes, "status": "Current",
    })
    return raid

# ensure the 6 pattern hazards + a broad hazard sample all get assessed
pattern_hazard_ids = [HAZ_FORKLIFT_NORTH, HAZ_FORKLIFT_SOUTH, HAZ_PUNCHPRESS, HAZ_MAINT_5A, HAZ_MAINT_5B,
                       HAZ_CONTRACTOR_LOTO, HAZ_HEIGHT_1, HAZ_HEIGHT_2]
for hid in pattern_hazard_ids:
    add_risk_assessment(HAZ_BY_ID[hid], TODAY - timedelta(days=random.randint(2,20)))

# give the punch-press hazard TWO assessments (early + current) to show adjusted_score moving with the pattern
add_risk_assessment(HAZ_BY_ID[HAZ_PUNCHPRESS], date(2025, 4, 1))

assessed_hazard_ids = set(pattern_hazard_ids)
other_hazards_for_ra = [h for h in T["hazards"] if h["hazard_id"] not in assessed_hazard_ids]
random.shuffle(other_hazards_for_ra)
for h in other_hazards_for_ra:
    if len(T["risk_assessments"]) >= 50:
        break
    add_risk_assessment(h, rand_date(WINDOW_START + timedelta(days=60), TODAY - timedelta(days=5)))

print(f"Risk assessments: {len(T['risk_assessments'])}")

# =============================================================================
# 14. RISK REGISTER (derived: one row per hazard with a Current assessment)
# =============================================================================
rr_seq = 0
latest_ra_by_hazard = {}
for ra in sorted(T["risk_assessments"], key=lambda r: r["assessment_date"]):
    latest_ra_by_hazard[ra["hazard_id"]] = ra

for hazard_id, ra in latest_ra_by_hazard.items():
    rr_seq += 1
    hz = HAZ_BY_ID[hazard_id]
    created_from = "Incident" if ra["source_incident_id"] or incidents_for_hazard(hazard_id) else "Proactive Assessment"
    created_date = min([ra["assessment_date"]] + [i["incident_datetime"][:10] for i in incidents_for_hazard(hazard_id)])
    T["risk_register"].append({
        "risk_register_id": f"RISK-{rr_seq:04d}", "hazard_id": hazard_id, "facility_id": ra["facility_id"],
        "current_risk_assessment_id": ra["risk_assessment_id"], "title": f"{hz['hazard_category']} — {hz['hazard_id']}",
        "current_score": ra["adjusted_score"], "current_level": ra["risk_level"],
        "owner_employee_id": any_employee(random.choice(["Safety Manager","Plant Manager"]))["employee_id"],
        "created_date": created_date, "created_from": created_from,
        "last_reviewed_date": ra["assessment_date"],
        "next_review_due": iso(date.fromisoformat(ra["assessment_date"]) + timedelta(days=180)),
        "status": "Open" if ra["risk_level"] in ("High","Critical") else random.choice(["Open","Mitigated"]),
    })

RISK_REGISTER_BY_HAZARD = {r["hazard_id"]: r["risk_register_id"] for r in T["risk_register"]}
# back-fill incidents.related_risk_register_id where the incident's hazard has a register entry
for i in T["incidents"]:
    if i["hazard_id"] in RISK_REGISTER_BY_HAZARD:
        i["related_risk_register_id"] = RISK_REGISTER_BY_HAZARD[i["hazard_id"]]

print(f"Risk register entries: {len(T['risk_register'])}")

# =============================================================================
# 15. INSPECTIONS (75)
# =============================================================================
INSPECTION_TYPES = ["Safety Walkthrough","Equipment Inspection","Fire System Inspection","PPE Compliance Audit",
                     "Housekeeping Audit","Environmental Compliance Check","Crane & Rigging Inspection"]
insp_seq = 0
def add_inspection(facility_id, itype, insp_date, equipment_id=None, area=None, deficiencies=None, forced_id=None):
    global insp_seq
    insp_seq += 1
    iid = forced_id or f"INSP-{insp_seq:04d}"
    deficiencies = deficiencies if deficiencies is not None else random.choices([0,1,2,3], weights=[0.45,0.3,0.17,0.08])[0]
    area = area or (equip_type(equipment_id) + " area" if equipment_id else random.choice(
        ["Production Floor","Warehouse","Loading Dock","Utilities Room","Main Aisle","Break Area"]))
    findings = (f"No deficiencies noted during {itype.lower()}." if deficiencies == 0 else
                f"{deficiencies} deficiency(ies) noted during {itype.lower()} in the {area}; see linked corrective actions.")
    T["inspections"].append({
        "inspection_id": iid, "facility_id": facility_id, "inspection_type": itype, "inspection_date": iso(insp_date),
        "inspector_employee_id": random.choice(employees_at(facility_id, random.choice(["Safety Manager","EHS Coordinator","Shift Supervisor"])))["employee_id"],
        "equipment_id": equipment_id, "area_location": area, "findings_summary": findings,
        "deficiencies_found": deficiencies, "status": "Findings Open" if deficiencies > 0 and random.random() < 0.4 else "Completed",
    })
    return iid

# a few inspections deliberately tied to the pattern-2 punch presses (cross-links for the AI to find)
for eq_id in PATTERN2_EQUIPMENT_IDS:
    add_inspection(equip_facility(eq_id), "Equipment Inspection", rand_date(date(2025,7,1), TODAY-timedelta(days=5)),
                    equipment_id=eq_id, deficiencies=random.choice([1,2]))

while len(T["inspections"]) < 75:
    fac = random.choice(FAC_IDS)
    itype = random.choice(INSPECTION_TYPES)
    eq_id = random.choice(equip_at(fac))["equipment_id"] if random.random() < 0.4 else None
    add_inspection(fac, itype, rand_date(WINDOW_START, TODAY - timedelta(days=3)), equipment_id=eq_id)

print(f"Inspections: {len(T['inspections'])}")

# =============================================================================
# 16. AUDIT FINDINGS (30)
# =============================================================================
AUDITORS_EXTERNAL = ["Meridian Safety Consulting", "TriState EHS Audit Group", "Cornerstone Risk Advisors"]
FINDING_CATEGORIES = ["Machine Safety","Energy Control (LOTO)","PPE Compliance","Contractor Management",
                      "Emergency Preparedness","Environmental Compliance","Documentation/Recordkeeping","Housekeeping"]
af_seq = 0
def add_audit_finding(facility_id, audit_date, category, description, severity, sop_id=None, control_id=None,
                       auditor_employee_id=None, forced_id=None):
    global af_seq
    af_seq += 1
    afid = forced_id or f"AUD-{af_seq:04d}"
    if auditor_employee_id:
        # the display name must be built FROM the actual FK target, never a fresh random
        # pick — otherwise auditor_name and auditor_employee_id can name two different people
        emp = next(e for e in T["employees"] if e["employee_id"] == auditor_employee_id)
        auditor = f"{emp['first_name']} {emp['last_name']} (Internal Audit)"
    else:
        auditor = random.choice(AUDITORS_EXTERNAL)
    T["audit_findings"].append({
        "audit_finding_id": afid, "facility_id": facility_id, "audit_date": iso(audit_date), "auditor_name": auditor,
        "auditor_employee_id": auditor_employee_id, "finding_category": category, "description": description,
        "severity": severity, "related_sop_id": sop_id, "related_control_id": control_id,
        "status": "Closed" if (TODAY - audit_date).days > 90 else random.choice(["Open","Closed"]),
    })
    return afid

# Pattern 4 tie-in: an external audit independently flags the same punch-press guarding control
add_audit_finding(equip_facility(PATTERN2_EQUIPMENT_IDS[0]), date(2025, 12, 8), "Machine Safety",
    "Point-of-operation guarding on punch press equipment was found defeated during the walkthrough; this matches a "
    "condition noted in a prior internal control assessment and at least one recent incident report.",
    "High", sop_id=SOP_BY_TITLE["Machine Guarding Standard"], control_id=CTL_PUNCHPRESS_GUARD)

# Pattern 6 tie-in: audit flags contractor training verification gap
add_audit_finding(FAC_CENTRAL, date(2026, 2, 20), "Contractor Management",
    "Sampled contractor files did not consistently contain evidence of current LOTO or confined-space training "
    "prior to work authorization.", "Medium", sop_id=SOP_BY_TITLE["Contractor Safety Management Program"],
    control_id=CTL_CONTRACTOR_LOTO)

while len(T["audit_findings"]) < 30:
    fac = random.choice(FAC_IDS)
    cat = random.choice(FINDING_CATEGORIES)
    sev = random.choices(["Low","Medium","High"], weights=[0.4,0.45,0.15])[0]
    sop = random.choice(T["sops"])["sop_id"] if random.random() < 0.6 else None
    internal = random.random() < 0.4
    add_audit_finding(fac, rand_date(WINDOW_START, TODAY - timedelta(days=10)), cat,
        f"{cat} finding identified during scheduled audit at {fac}; see recommended corrective action.", sev,
        sop_id=sop, auditor_employee_id=(any_employee("Safety Manager")["employee_id"] if internal else None))

print(f"Audit findings: {len(T['audit_findings'])}")

# =============================================================================
# 17. ACTIONS (100) — corrective + preventive; Pattern 3 seeded here (repeat overdue)
# =============================================================================
act_seq = 0
VERIFICATION_METHODS = ["Follow-up inspection","Supervisor sign-off","Maintenance work order closure",
                         "Retraining attendance record","EHS audit confirmation"]

def add_action(action_type, source_type, facility_id, owner_employee_id, description, created_date,
               timeframe_days=30, related_control_id=None, source_incident_id=None, source_audit_finding_id=None,
               source_inspection_id=None, source_risk_assessment_id=None, force_status=None,
               force_reschedule=0, forced_id=None):
    global act_seq
    act_seq += 1
    aid = forced_id or f"ACT-{act_seq:04d}"
    original_due = created_date + timedelta(days=timeframe_days)
    reschedule_count = force_reschedule
    due = original_due + timedelta(days=21 * reschedule_count)
    age_days = (TODAY - due).days

    if force_status:
        status = force_status
    elif due > TODAY:
        status = random.choices(["Open","In Progress"], weights=[0.5,0.5])[0]
    else:
        status = random.choices(["Completed","Overdue"], weights=[0.75,0.25])[0]

    completion_date = None
    if status == "Completed":
        completion_date = due - timedelta(days=random.randint(0, min(10, max(timeframe_days-1,1))))
        if completion_date > TODAY: completion_date = TODAY
    elif status == "Overdue" and due > TODAY:
        due = TODAY - timedelta(days=random.randint(1, 20))  # ensure genuinely overdue

    T["actions"].append({
        "action_id": aid, "action_type": action_type, "source_type": source_type,
        "source_incident_id": source_incident_id, "source_audit_finding_id": source_audit_finding_id,
        "source_inspection_id": source_inspection_id, "source_risk_assessment_id": source_risk_assessment_id,
        "related_control_id": related_control_id, "description": description, "facility_id": facility_id,
        "owner_employee_id": owner_employee_id, "created_date": iso(created_date),
        "original_due_date": iso(original_due), "due_date": iso(due), "reschedule_count": reschedule_count,
        "status": status, "completion_date": iso(completion_date) if completion_date else None,
        "verification_method": random.choice(VERIFICATION_METHODS),
    })
    return aid

# ---- Pattern 3: repeat-overdue cluster (three overlapping angles) ----
OVERLOADED_EMP = (employees_at(FAC_CENTRAL, "Maintenance Technician") or employees_at(FAC_CENTRAL, "Senior Maintenance Technician") or [any_employee("Maintenance Technician")])[0]["employee_id"]
PATTERN3_ACTION_IDS = []

# angle A: actions targeting the Pattern-4 control keep slipping (ties Pattern 3 <-> Pattern 4)
for i, iid in enumerate(PATTERN2_INCIDENT_IDS[:4]):
    inc = next(x for x in T["incidents"] if x["incident_id"] == iid)
    created = incident_dt(inc).date() + timedelta(days=random.randint(1,4))
    aid = add_action("Corrective", "Incident", inc["facility_id"], OVERLOADED_EMP if i % 2 == 0 else any_employee("Mechanical Engineer")["employee_id"],
        "Repair/upgrade punch press guard interlock and confirm it cannot be propped open.",
        created, timeframe_days=21, related_control_id=CTL_PUNCHPRESS_GUARD, source_incident_id=iid,
        force_status="Overdue", force_reschedule=random.choice([2,3]))
    PATTERN3_ACTION_IDS.append(aid)

# angle B: one overloaded owner accumulates repeat-overdue actions across unrelated sources
for _ in range(5):
    src_incident = random.choice([i for i in T["incidents"] if i["facility_id"] == FAC_CENTRAL and i["investigation_status"]=="Completed"])
    created = date.fromisoformat(src_incident["closed_date"]) if src_incident["closed_date"] else TODAY - timedelta(days=60)
    aid = add_action("Corrective", "Incident", FAC_CENTRAL, OVERLOADED_EMP,
        f"Address maintenance-related corrective action arising from {src_incident['incident_id']}.",
        created, timeframe_days=14, source_incident_id=src_incident["incident_id"],
        force_status="Overdue", force_reschedule=random.choice([2,3]))
    PATTERN3_ACTION_IDS.append(aid)

# angle C: facility-wide slippage at Rex Central Plant beyond just the overloaded owner
for _ in range(5):
    src_insp = random.choice([i for i in T["inspections"] if i["facility_id"] == FAC_CENTRAL and i["deficiencies_found"] > 0])
    created = date.fromisoformat(src_insp["inspection_date"]) + timedelta(days=3)
    aid = add_action(random.choice(["Corrective","Preventive"]), "Inspection", FAC_CENTRAL,
        any_employee_facility := random.choice(employees_at(FAC_CENTRAL))["employee_id"],
        f"Correct deficiency identified during {src_insp['inspection_type'].lower()} ({src_insp['inspection_id']}).",
        created, timeframe_days=21, source_inspection_id=src_insp["inspection_id"],
        force_status="Overdue", force_reschedule=random.choice([2,3]))
    PATTERN3_ACTION_IDS.append(aid)

print(f"Pattern 3 (repeat-overdue) actions seeded: {len(PATTERN3_ACTION_IDS)}")

# ---- general action pool from incidents, audit findings, inspections, risk assessments ----
completed_incidents = [i for i in T["incidents"] if i["investigation_status"] == "Completed" and i["incident_id"] not in PATTERN2_INCIDENT_IDS[:4]]
random.shuffle(completed_incidents)
for inc in completed_incidents:
    if len(T["actions"]) >= 78:
        break
    created = date.fromisoformat(inc["incident_datetime"][:10]) + timedelta(days=random.randint(1,5))
    action_type = "Corrective" if inc["incident_type"] in ("Injury","Property Damage","Environmental","Equipment Failure") else random.choice(["Corrective","Preventive"])
    ctl = controls_for_hazard(inc["hazard_id"])
    add_action(action_type, "Incident", inc["facility_id"], random.choice(employees_at(inc["facility_id"], random.choice(["Maintenance Technician","Safety Manager","Shift Supervisor","EHS Coordinator"])))["employee_id"],
        f"Address root cause identified for {inc['incident_id']} ({inc['hazard_id']}: {HAZ_BY_ID[inc['hazard_id']]['hazard_category']}).",
        created, timeframe_days=random.choice([14,21,30,45]),
        related_control_id=(ctl[0]["control_id"] if ctl else None), source_incident_id=inc["incident_id"])

open_audit_findings = [a for a in T["audit_findings"] if a["audit_finding_id"] not in ("AUD-0001","AUD-0002")]
random.shuffle(open_audit_findings)
for af in open_audit_findings:
    if len(T["actions"]) >= 90:
        break
    created = date.fromisoformat(af["audit_date"]) + timedelta(days=random.randint(2,7))
    add_action("Corrective", "Audit Finding", af["facility_id"], random.choice(employees_at(af["facility_id"], random.choice(["Safety Manager","EHS Coordinator"])))["employee_id"],
        f"Remediate audit finding {af['audit_finding_id']}: {af['finding_category']}.",
        created, timeframe_days=random.choice([21,30,45]), related_control_id=af["related_control_id"],
        source_audit_finding_id=af["audit_finding_id"])

deficient_inspections = [i for i in T["inspections"] if i["deficiencies_found"] > 0]
random.shuffle(deficient_inspections)
for insp in deficient_inspections:
    if len(T["actions"]) >= 97:
        break
    created = date.fromisoformat(insp["inspection_date"]) + timedelta(days=random.randint(1,5))
    add_action("Preventive", "Inspection", insp["facility_id"], random.choice(employees_at(insp["facility_id"], random.choice(["Maintenance Technician","Shift Supervisor"])))["employee_id"],
        f"Correct deficiency from {insp['inspection_id']} ({insp['inspection_type']}).",
        created, timeframe_days=random.choice([14,21,30]), source_inspection_id=insp["inspection_id"])

high_risks = [r for r in T["risk_assessments"] if r["risk_level"] in ("High","Critical")]
random.shuffle(high_risks)
for ra in high_risks:
    if len(T["actions"]) >= 100:
        break
    created = date.fromisoformat(ra["assessment_date"]) + timedelta(days=random.randint(1,5))
    hz = HAZ_BY_ID[ra["hazard_id"]]
    add_action("Preventive", "Risk Assessment", ra["facility_id"], random.choice(employees_at(ra["facility_id"], random.choice(["Safety Manager","Mechanical Engineer"])))["employee_id"],
        f"Implement additional preventive control for {hz['hazard_category']} risk ({ra['risk_assessment_id']}).",
        created, timeframe_days=45, source_risk_assessment_id=ra["risk_assessment_id"])

# top off to exactly 100 with generic preventive actions off remaining risk assessments if still short
remaining_ra = [r for r in T["risk_assessments"] if r["risk_assessment_id"] not in [a["source_risk_assessment_id"] for a in T["actions"] if a["source_risk_assessment_id"]]]
i = 0
while len(T["actions"]) < 100 and i < len(remaining_ra):
    ra = remaining_ra[i]; i += 1
    created = date.fromisoformat(ra["assessment_date"]) + timedelta(days=3)
    add_action("Preventive", "Risk Assessment", ra["facility_id"], random.choice(employees_at(ra["facility_id"], "Safety Manager"))["employee_id"],
        f"Proactive risk-reduction action for {HAZ_BY_ID[ra['hazard_id']]['hazard_category']} ({ra['risk_assessment_id']}).",
        created, timeframe_days=45, source_risk_assessment_id=ra["risk_assessment_id"])

print(f"Actions total: {len(T['actions'])}")

# =============================================================================
# 18. EVIDENCE (~90) — fictional attachment records, no real files
# =============================================================================
ev_seq = 0
def add_evidence(entity_type, entity_id, file_name, file_type, description, uploaded_date, uploader=None, forced_id=None):
    global ev_seq
    ev_seq += 1
    eid = forced_id or f"EVD-{ev_seq:04d}"
    T["evidence"].append({
        "evidence_id": eid, "related_entity_type": entity_type, "related_entity_id": entity_id,
        "file_name": file_name, "file_type": file_type, "description": description,
        "uploaded_by_employee_id": uploader or any_employee()["employee_id"], "uploaded_date": iso(uploaded_date),
    })
    return eid

for inc in T["incidents"]:
    if inc["incident_type"] in ("Injury","Property Damage","Environmental","Equipment Failure"):
        udate = date.fromisoformat(inc["reported_at"][:10])
        add_evidence("Incident", inc["incident_id"], f"{inc['incident_id']}-scene-photo-01.jpg", "image/jpeg",
                     f"Scene photo documenting conditions at time of report for {inc['incident_id']}.", udate,
                     uploader=inc["reported_by_employee_id"])

for insp in T["inspections"]:
    if insp["deficiencies_found"] > 1:
        add_evidence("Inspection", insp["inspection_id"], f"{insp['inspection_id']}-findings-photo.jpg", "image/jpeg",
                     f"Photo documentation of deficiency noted during {insp['inspection_id']}.",
                     date.fromisoformat(insp["inspection_date"]), uploader=insp["inspector_employee_id"])

for af in T["audit_findings"][:18]:
    add_evidence("Audit Finding", af["audit_finding_id"], f"{af['audit_finding_id']}-audit-report-excerpt.pdf", "application/pdf",
                 f"Audit report excerpt covering finding {af['audit_finding_id']}.", date.fromisoformat(af["audit_date"]))

for act in T["actions"]:
    if act["status"] == "Completed" and random.random() < 0.35:
        add_evidence("Action", act["action_id"], f"{act['action_id']}-completion-signoff.pdf", "application/pdf",
                     f"Completion sign-off and verification record for {act['action_id']}.",
                     date.fromisoformat(act["completion_date"]), uploader=act["owner_employee_id"])

for m in T["maintenance_records"]:
    if m["status"] == "Delayed":
        add_evidence("Maintenance Record", m["maintenance_record_id"], f"{m['maintenance_record_id']}-work-order.pdf", "application/pdf",
                     f"Work order record for delayed maintenance on {m['equipment_id']}.",
                     date.fromisoformat(m["actual_date"]) if m["actual_date"] else TODAY)

print(f"Evidence records: {len(T['evidence'])}")
print(f"\n=== GENERATION COMPLETE ===")
for k, v in T.items():
    print(f"  {k}: {len(v)}")

# =============================================================================
# INTERNATIONAL EXPANSION — 4 new facilities (UK, Germany, India, Australia)
# under the existing company CO-001, with proportional linked data for the new
# "Global Risk Map" UI feature. This block is a PURE APPEND: it runs after
# every random.* call above it, so nothing about the original 3-facility
# dataset (ids, dates, patterns, or the specific rows docs/database-design.md
# and docs/sample-documents/*.md cite verbatim) is perturbed by its presence.
# It is also the LAST consumer of the random stream in the whole script —
# everything after this point (SQLite build, CSV export, JSON writes) makes
# no random.* calls — so nothing downstream is order-sensitive to it either.
#
# Written as a clean per-facility loop (unlike the flat-random generation
# above) since this is new code, not a rewrite of the original. It reuses the
# EXISTING helper functions (add_hazard, add_control, add_maintenance,
# add_training, add_incident, add_control_assessment, add_risk_assessment,
# add_inspection, add_audit_finding, add_action, add_evidence) exactly as-is,
# so every new row has the identical column shape/behavior as the original
# 3-facility dataset. It deliberately does NOT replicate the 6 hand-wired
# "Pattern" narratives — those are fixtures tied to test_scenarios.json
# ground truth for the original 3 facilities. New facilities get organic,
# realistic variety from the same template pools instead.
# =============================================================================

# ---- small per-country name pools, used ONLY for these facilities' employees
# (the original FIRST_NAMES/LAST_NAMES/unique_name() are untouched) ----
UK_FIRST_NAMES = ["Oliver","Harry","George","Jack","Charlie","Thomas","Jacob","Alfie","Freddie","Archie",
                   "Amelia","Olivia","Isla","Ava","Emily","Sophie","Grace","Lily","Chloe","Ella"]
UK_LAST_NAMES = ["Smith","Jones","Taylor","Brown","Williams","Wilson","Johnson","Davies","Robinson","Wright",
                  "Thompson","Evans","Walker","White","Roberts","Green","Hall","Wood","Clarke","Hughes"]
GERMANY_FIRST_NAMES = ["Lukas","Maximilian","Felix","Jonas","Paul","Leon","Finn","Elias","Noah","Ben",
                        "Anna","Emma","Mia","Hannah","Lea","Lena","Laura","Sophie","Marie","Johanna"]
GERMANY_LAST_NAMES = ["Müller","Schmidt","Schneider","Fischer","Weber","Meyer","Wagner","Becker","Hoffmann","Schulz",
                       "Koch","Bauer","Richter","Klein","Wolf","Schröder","Neumann","Zimmermann","Braun","Krüger"]
INDIA_FIRST_NAMES = ["Arjun","Rohan","Vikram","Aditya","Rahul","Amit","Sanjay","Karan","Nikhil","Suresh",
                      "Priya","Ananya","Neha","Pooja","Divya","Kavita","Meera","Sunita","Anjali","Deepa"]
INDIA_LAST_NAMES = ["Sharma","Verma","Gupta","Patel","Iyer","Nair","Reddy","Kulkarni","Joshi","Rao",
                     "Deshmukh","Kapoor","Chatterjee","Mehta","Choudhary","Bhat","Pillai","Menon","Agarwal","Naik"]
AUSTRALIA_FIRST_NAMES = ["Jack","William","Noah","Lucas","Ethan","James","Oliver","Liam","Henry","Mason",
                          "Charlotte","Olivia","Ava","Mia","Isla","Zoe","Ruby","Chloe","Grace","Ella"]
AUSTRALIA_LAST_NAMES = ["Smith","Jones","Williams","Brown","Wilson","Taylor","Anderson","Thompson","Martin","Clarke",
                         "King","Mitchell","Robinson","Campbell","Stewart","Kelly","Harris","Ryan","Cooper","Bell"]

_used_intl_names = set()
def unique_intl_name(first_pool, last_pool):
    while True:
        fn, ln = random.choice(first_pool), random.choice(last_pool)
        if (fn, ln) not in _used_intl_names:
            _used_intl_names.add((fn, ln))
            return fn, ln

NEW_FACILITIES = [
    {"facility_id": "FAC-004", "company_id": "CO-001", "name": "Rex UK Plant",
     "facility_type": "Precision Fabrication", "city": "Manchester", "state": "England", "country": "United Kingdom",
     "address": "14 Trafford Park Road, Manchester, M17 1EH, United Kingdom",
     "square_footage": 210000, "year_established": 1989, "employee_capacity": 260},
    {"facility_id": "FAC-005", "company_id": "CO-001", "name": "Rex Germany Plant",
     "facility_type": "Precision Engineering & Machining", "city": "Stuttgart", "state": "Baden-Württemberg", "country": "Germany",
     "address": "Industriestraße 42, 70565 Stuttgart, Germany",
     "square_footage": 225000, "year_established": 1992, "employee_capacity": 280},
    {"facility_id": "FAC-006", "company_id": "CO-001", "name": "Rex India Plant",
     "facility_type": "Component Manufacturing & Assembly", "city": "Pune", "state": "Maharashtra", "country": "India",
     "address": "Plot 27, MIDC Industrial Area, Pune, Maharashtra 411019, India",
     "square_footage": 195000, "year_established": 2003, "employee_capacity": 320},
    {"facility_id": "FAC-007", "company_id": "CO-001", "name": "Rex Australia Plant",
     "facility_type": "Distribution & Light Fabrication", "city": "Melbourne", "state": "Victoria", "country": "Australia",
     "address": "88 Ricketts Road, Mount Waverley, VIC 3149, Australia",
     "square_footage": 155000, "year_established": 1998, "employee_capacity": 200},
]
T["facilities"].extend(NEW_FACILITIES)
NEW_FAC_IDS = [f["facility_id"] for f in NEW_FACILITIES]
FAC_UK, FAC_DE, FAC_IN, FAC_AU = NEW_FAC_IDS
FACILITY_NAME_POOLS = {
    FAC_UK: (UK_FIRST_NAMES, UK_LAST_NAMES),
    FAC_DE: (GERMANY_FIRST_NAMES, GERMANY_LAST_NAMES),
    FAC_IN: (INDIA_FIRST_NAMES, INDIA_LAST_NAMES),
    FAC_AU: (AUSTRALIA_FIRST_NAMES, AUSTRALIA_LAST_NAMES),
}

EMPLOYEES_PER_FACILITY = 10
EQUIPMENT_PER_FACILITY = 9
HAZARDS_PER_FACILITY = 18
CONTROLS_PER_FACILITY = 11
MAINTENANCE_PER_FACILITY = 10
TRAINING_PER_FACILITY = 10
INCIDENTS_PER_FACILITY = 23

NEW_EMPLOYEES, NEW_EQUIPMENT, NEW_HAZARDS, NEW_CONTROLS = [], [], [], []
NEW_MAINTENANCE, NEW_TRAINING, NEW_INCIDENTS = [], [], []

for fac in NEW_FACILITIES:
    fid = fac["facility_id"]
    first_pool, last_pool = FACILITY_NAME_POOLS[fid]

    # ---- employees ----
    fac_employees = []
    role_pool = ROLE_CATALOG.copy()
    random.shuffle(role_pool)
    for i in range(EMPLOYEES_PER_FACILITY):
        fn, ln = unique_intl_name(first_pool, last_pool)
        title, dept, _ = role_pool[i % len(role_pool)]
        hire_date = rand_date(date(2008, 1, 1), date(2025, 9, 1))
        emp_idx = len(T["employees"]) + 1
        emp = {
            "employee_id": f"EMP-{emp_idx:04d}", "facility_id": fid, "role_id": ROLE_BY_TITLE[title],
            "first_name": fn, "last_name": ln, "email": f"{fn.lower()}.{ln.lower()}@rexindustrial-example.com",
            "hire_date": iso(hire_date), "is_active": 1,
        }
        T["employees"].append(emp)
        NEW_EMPLOYEES.append(emp)
        fac_employees.append(emp)
    # guarantee this facility has >=1 Plant Manager and >=1 Safety Manager,
    # mirroring the original 3-facility guarantee logic but scoped to this facility's own roster
    for needed in ["Plant Manager", "Safety Manager"]:
        if not any(e["role_id"] == ROLE_BY_TITLE[needed] for e in fac_employees):
            cand = next(e for e in fac_employees if e["role_id"] not in (ROLE_BY_TITLE["Plant Manager"], ROLE_BY_TITLE["Safety Manager"]))
            cand["role_id"] = ROLE_BY_TITLE[needed]

    # ---- equipment ----
    fac_equipment = []
    for i in range(EQUIPMENT_PER_FACILITY):
        etype, category, makers = random.choice(EQUIPMENT_TYPES)
        install = rand_date(date(2005, 1, 1), date(2024, 6, 1))
        last_maint = rand_date(max(install, date(2025, 3, 1)), TODAY - timedelta(days=10))
        next_due = last_maint + timedelta(days=random.choice([90, 120, 180]))
        eq_idx = len(T["equipment"]) + 1
        eq = {
            "equipment_id": f"EQ-{eq_idx:04d}", "facility_id": fid, "equipment_type": etype, "category": category,
            "manufacturer": random.choice(makers), "model_number": f"{random.choice(['MX','GX','TX','RX','PX'])}-{random.randint(100,999)}",
            "serial_number": f"SN{random.randint(100000,999999)}", "install_date": iso(install),
            "last_maintenance_date": iso(last_maint), "next_maintenance_due": iso(next_due),
            "status": "Operational", "criticality": random.choice(["Medium", "Medium", "High"]),
        }
        T["equipment"].append(eq)
        NEW_EQUIPMENT.append(eq)
        fac_equipment.append(eq)

    # ---- hazards (organic variety from the shared template pools; no hand-wired patterns) ----
    fac_hazards = []
    for i in range(HAZARDS_PER_FACILITY):
        cat = random.choice(HAZARD_CATEGORIES)
        if fac_equipment and random.random() < 0.65:
            eq_choice = random.choice(fac_equipment)
            equipment_id, equip_label = eq_choice["equipment_id"], eq_choice["equipment_type"]
        else:
            equipment_id, equip_label = None, cat.lower()
        add_hazard(cat, HAZARD_DESC_TEMPLATES[cat].format(equip=equip_label),
                   facility_id=fid, equipment_id=equipment_id, consequence=CATEGORY_CONSEQUENCE[cat])
        fac_hazards.append(T["hazards"][-1])
    NEW_HAZARDS.extend(fac_hazards)

    # ---- controls: 1-2 per hazard until this facility's target is reached ----
    fac_controls = []
    hz_shuffled = fac_hazards.copy()
    random.shuffle(hz_shuffled)
    i = 0
    while len(fac_controls) < CONTROLS_PER_FACILITY and hz_shuffled:
        hz = hz_shuffled[i % len(hz_shuffled)]
        i += 1
        ctype = CONTROL_TYPE_BY_CATEGORY.get(hz["hazard_category"], "Administrative")
        add_control(f"{hz['hazard_category']} Control — {hz['hazard_id']}", ctype, hz["hazard_id"],
                    sop_id=sop_for_category(hz["hazard_category"]), facility_id=fid,
                    description=f"Control addressing: {hz['description']}")
        fac_controls.append(T["controls"][-1])
        if i > 200:
            break
    NEW_CONTROLS.extend(fac_controls)

    # ---- maintenance ----
    fac_maintenance = []
    for i in range(MAINTENANCE_PER_FACILITY):
        eq = random.choice(fac_equipment)
        scheduled = rand_date(WINDOW_START, TODAY - timedelta(days=5))
        status = random.choices(["Completed", "Delayed", "Overdue", "Scheduled"], weights=[0.72, 0.13, 0.08, 0.07])[0]
        delay = random.randint(5, 25) if status in ("Delayed", "Overdue") else 0
        mtype = random.choices(["Preventive", "Corrective", "Inspection"], weights=[0.6, 0.25, 0.15])[0]
        add_maintenance(eq["equipment_id"], scheduled, status, mtype=mtype, delay_days=delay)
        fac_maintenance.append(T["maintenance_records"][-1])
    NEW_MAINTENANCE.extend(fac_maintenance)

    # sync this facility's equipment maintenance dates to its real maintenance_records,
    # mirroring the original post-generation sync pass
    for eq in fac_equipment:
        recs = [m for m in T["maintenance_records"] if m["equipment_id"] == eq["equipment_id"]]
        performed = [m for m in recs if m["actual_date"]]
        if performed:
            latest = max(performed, key=lambda m: m["actual_date"])
            eq["last_maintenance_date"] = latest["actual_date"]
        unperformed_future = [m for m in recs if m["status"] in ("Scheduled", "Overdue") and not m["actual_date"]]
        if unperformed_future:
            nearest = min(unperformed_future, key=lambda m: m["scheduled_date"])
            eq["next_maintenance_due"] = nearest["scheduled_date"]
        elif performed:
            base = date.fromisoformat(eq["last_maintenance_date"])
            eq["next_maintenance_due"] = iso(base + timedelta(days=random.choice([90, 120, 180])))

    # ---- training (employees only — no international contractor roster in scope) ----
    fac_training = []
    safety_critical_fac_employees = [e for e in fac_employees
                                      if next(r["is_safety_critical"] for r in T["roles"] if r["role_id"] == e["role_id"])]
    for i in range(TRAINING_PER_FACILITY):
        emp = random.choice(safety_critical_fac_employees or fac_employees)
        topic = random.choice(SAFETY_TOPICS)
        tdate = rand_date(WINDOW_START, TODAY - timedelta(days=10))
        expiry = tdate + timedelta(days=730)
        status = "Expired" if expiry < TODAY else "Current"
        add_training(topic, status, employee_id=emp["employee_id"], training_date=tdate, expiry=expiry, result="Pass")
        fac_training.append(T["training_records"][-1])
    NEW_TRAINING.extend(fac_training)

    # ---- incidents ----
    fac_incidents = []
    for i in range(INCIDENTS_PER_FACILITY):
        hz = random.choice(fac_hazards)
        eq_id = hz["equipment_id"]
        if eq_id is None and fac_equipment and random.random() < 0.7:
            eq_id = random.choice(fac_equipment)["equipment_id"]
        involved_employee = random.choice(fac_employees)["employee_id"] if random.random() < 0.7 else None
        add_incident(fid, hz, equipment_id=eq_id, involved_employee_id=involved_employee)
        fac_incidents.append(T["incidents"][-1])
    NEW_INCIDENTS.extend(fac_incidents)

print(f"International expansion — facilities:{len(NEW_FACILITIES)} employees:{len(NEW_EMPLOYEES)} "
      f"equipment:{len(NEW_EQUIPMENT)} hazards:{len(NEW_HAZARDS)} controls:{len(NEW_CONTROLS)} "
      f"maintenance:{len(NEW_MAINTENANCE)} training:{len(NEW_TRAINING)} incidents:{len(NEW_INCIDENTS)}")

# ---- control assessments for the new controls ----
NEW_CONTROL_ASSESSMENTS = []
for c in NEW_CONTROLS:
    for _ in range(random.choice([1, 1, 2])):
        rating = random.choices(["Effective", "Partially Effective", "Ineffective"], weights=[0.55, 0.32, 0.13])[0]
        findings = {
            "Effective": "Control observed functioning as designed during review.",
            "Partially Effective": "Control generally functions but inconsistent compliance was observed.",
            "Ineffective": "Control was not functioning as intended at time of review.",
        }[rating]
        add_control_assessment(c["control_id"], rand_date(WINDOW_START, TODAY - timedelta(days=10)), rating, findings)
        NEW_CONTROL_ASSESSMENTS.append(T["control_assessments"][-1])

# ---- risk assessments + risk register for the new hazards (not every hazard gets a
# formal assessment, matching the ~65% ratio the original 3-facility dataset used) ----
NEW_RISK_ASSESSMENTS = []
for hz in NEW_HAZARDS:
    if random.random() < 0.65:
        add_risk_assessment(hz, rand_date(WINDOW_START + timedelta(days=60), TODAY - timedelta(days=5)))
        NEW_RISK_ASSESSMENTS.append(T["risk_assessments"][-1])

NEW_HAZ_BY_ID = {h["hazard_id"]: h for h in NEW_HAZARDS}
latest_ra_by_hazard_new = {}
for ra in sorted(NEW_RISK_ASSESSMENTS, key=lambda r: r["assessment_date"]):
    latest_ra_by_hazard_new[ra["hazard_id"]] = ra

NEW_RISK_REGISTER = []
for hazard_id, ra in latest_ra_by_hazard_new.items():
    rr_seq += 1
    hz = NEW_HAZ_BY_ID[hazard_id]
    hz_incidents = [i for i in NEW_INCIDENTS if i["hazard_id"] == hazard_id]
    created_from = "Incident" if ra["source_incident_id"] or hz_incidents else "Proactive Assessment"
    created_date = min([ra["assessment_date"]] + [i["incident_datetime"][:10] for i in hz_incidents])
    rr = {
        "risk_register_id": f"RISK-{rr_seq:04d}", "hazard_id": hazard_id, "facility_id": ra["facility_id"],
        "current_risk_assessment_id": ra["risk_assessment_id"], "title": f"{hz['hazard_category']} — {hz['hazard_id']}",
        "current_score": ra["adjusted_score"], "current_level": ra["risk_level"],
        "owner_employee_id": random.choice(employees_at(ra["facility_id"], random.choice(["Safety Manager", "Plant Manager"])))["employee_id"],
        "created_date": created_date, "created_from": created_from,
        "last_reviewed_date": ra["assessment_date"],
        "next_review_due": iso(date.fromisoformat(ra["assessment_date"]) + timedelta(days=180)),
        "status": "Open" if ra["risk_level"] in ("High", "Critical") else random.choice(["Open", "Mitigated"]),
    }
    T["risk_register"].append(rr)
    NEW_RISK_REGISTER.append(rr)

NEW_RISK_REGISTER_BY_HAZARD = {r["hazard_id"]: r["risk_register_id"] for r in NEW_RISK_REGISTER}
for i in NEW_INCIDENTS:
    if i["hazard_id"] in NEW_RISK_REGISTER_BY_HAZARD:
        i["related_risk_register_id"] = NEW_RISK_REGISTER_BY_HAZARD[i["hazard_id"]]

# ---- inspections ----
NEW_INSPECTIONS = []
INSPECTIONS_PER_FACILITY = 15
for fac in NEW_FACILITIES:
    fid = fac["facility_id"]
    fac_equip_pool = equip_at(fid)
    for i in range(INSPECTIONS_PER_FACILITY):
        itype = random.choice(INSPECTION_TYPES)
        eq_id = random.choice(fac_equip_pool)["equipment_id"] if random.random() < 0.4 else None
        add_inspection(fid, itype, rand_date(WINDOW_START, TODAY - timedelta(days=3)), equipment_id=eq_id)
        NEW_INSPECTIONS.append(T["inspections"][-1])

# ---- audit findings ----
NEW_AUDIT_FINDINGS = []
AUDIT_PER_FACILITY = 6
for fac in NEW_FACILITIES:
    fid = fac["facility_id"]
    for i in range(AUDIT_PER_FACILITY):
        cat = random.choice(FINDING_CATEGORIES)
        sev = random.choices(["Low", "Medium", "High"], weights=[0.4, 0.45, 0.15])[0]
        sop = random.choice(T["sops"])["sop_id"] if random.random() < 0.6 else None
        internal = random.random() < 0.4
        auditor_emp = random.choice(employees_at(fid, "Safety Manager"))["employee_id"] if internal else None
        add_audit_finding(fid, rand_date(WINDOW_START, TODAY - timedelta(days=10)), cat,
            f"{cat} finding identified during scheduled audit at {fid}; see recommended corrective action.", sev,
            sop_id=sop, auditor_employee_id=auditor_emp)
        NEW_AUDIT_FINDINGS.append(T["audit_findings"][-1])

# ---- actions: incidents -> audit findings -> inspections -> risk assessments, same cascade order as the original ----
NEW_ACTIONS = []
ACTIONS_TOTAL_TARGET = 80

completed_new_incidents = [i for i in NEW_INCIDENTS if i["investigation_status"] == "Completed"]
random.shuffle(completed_new_incidents)
for inc in completed_new_incidents:
    if len(NEW_ACTIONS) >= int(ACTIONS_TOTAL_TARGET * 0.45):
        break
    created = date.fromisoformat(inc["incident_datetime"][:10]) + timedelta(days=random.randint(1, 5))
    action_type = "Corrective" if inc["incident_type"] in ("Injury", "Property Damage", "Environmental", "Equipment Failure") else random.choice(["Corrective", "Preventive"])
    ctl = controls_for_hazard(inc["hazard_id"])
    owner = random.choice(employees_at(inc["facility_id"], random.choice(["Maintenance Technician", "Safety Manager", "Shift Supervisor", "EHS Coordinator"])))["employee_id"]
    add_action(action_type, "Incident", inc["facility_id"], owner,
        f"Address root cause identified for {inc['incident_id']} ({inc['hazard_id']}: {NEW_HAZ_BY_ID[inc['hazard_id']]['hazard_category']}).",
        created, timeframe_days=random.choice([14, 21, 30, 45]),
        related_control_id=(ctl[0]["control_id"] if ctl else None), source_incident_id=inc["incident_id"])
    NEW_ACTIONS.append(T["actions"][-1])

random.shuffle(NEW_AUDIT_FINDINGS)
for af in NEW_AUDIT_FINDINGS:
    if len(NEW_ACTIONS) >= int(ACTIONS_TOTAL_TARGET * 0.65):
        break
    created = date.fromisoformat(af["audit_date"]) + timedelta(days=random.randint(2, 7))
    owner = random.choice(employees_at(af["facility_id"], random.choice(["Safety Manager", "EHS Coordinator"])))["employee_id"]
    add_action("Corrective", "Audit Finding", af["facility_id"], owner,
        f"Remediate audit finding {af['audit_finding_id']}: {af['finding_category']}.",
        created, timeframe_days=random.choice([21, 30, 45]), related_control_id=af["related_control_id"],
        source_audit_finding_id=af["audit_finding_id"])
    NEW_ACTIONS.append(T["actions"][-1])

deficient_new_inspections = [i for i in NEW_INSPECTIONS if i["deficiencies_found"] > 0]
random.shuffle(deficient_new_inspections)
for insp in deficient_new_inspections:
    if len(NEW_ACTIONS) >= int(ACTIONS_TOTAL_TARGET * 0.85):
        break
    created = date.fromisoformat(insp["inspection_date"]) + timedelta(days=random.randint(1, 5))
    owner = random.choice(employees_at(insp["facility_id"], random.choice(["Maintenance Technician", "Shift Supervisor"])))["employee_id"]
    add_action("Preventive", "Inspection", insp["facility_id"], owner,
        f"Correct deficiency from {insp['inspection_id']} ({insp['inspection_type']}).",
        created, timeframe_days=random.choice([14, 21, 30]), source_inspection_id=insp["inspection_id"])
    NEW_ACTIONS.append(T["actions"][-1])

high_new_risks = [r for r in NEW_RISK_ASSESSMENTS if r["risk_level"] in ("High", "Critical")]
random.shuffle(high_new_risks)
for ra in high_new_risks:
    if len(NEW_ACTIONS) >= ACTIONS_TOTAL_TARGET:
        break
    created = date.fromisoformat(ra["assessment_date"]) + timedelta(days=random.randint(1, 5))
    hz = NEW_HAZ_BY_ID[ra["hazard_id"]]
    owner = random.choice(employees_at(ra["facility_id"], random.choice(["Safety Manager", "Mechanical Engineer"])))["employee_id"]
    add_action("Preventive", "Risk Assessment", ra["facility_id"], owner,
        f"Implement additional preventive control for {hz['hazard_category']} risk ({ra['risk_assessment_id']}).",
        created, timeframe_days=45, source_risk_assessment_id=ra["risk_assessment_id"])
    NEW_ACTIONS.append(T["actions"][-1])

# ---- evidence, same source rules as the original ----
NEW_EVIDENCE = []
for inc in NEW_INCIDENTS:
    if inc["incident_type"] in ("Injury", "Property Damage", "Environmental", "Equipment Failure"):
        udate = date.fromisoformat(inc["reported_at"][:10])
        add_evidence("Incident", inc["incident_id"], f"{inc['incident_id']}-scene-photo-01.jpg", "image/jpeg",
                     f"Scene photo documenting conditions at time of report for {inc['incident_id']}.", udate,
                     uploader=inc["reported_by_employee_id"])
        NEW_EVIDENCE.append(T["evidence"][-1])

for insp in NEW_INSPECTIONS:
    if insp["deficiencies_found"] > 1:
        add_evidence("Inspection", insp["inspection_id"], f"{insp['inspection_id']}-findings-photo.jpg", "image/jpeg",
                     f"Photo documentation of deficiency noted during {insp['inspection_id']}.",
                     date.fromisoformat(insp["inspection_date"]), uploader=insp["inspector_employee_id"])
        NEW_EVIDENCE.append(T["evidence"][-1])

for af in NEW_AUDIT_FINDINGS[:12]:
    add_evidence("Audit Finding", af["audit_finding_id"], f"{af['audit_finding_id']}-audit-report-excerpt.pdf", "application/pdf",
                 f"Audit report excerpt covering finding {af['audit_finding_id']}.", date.fromisoformat(af["audit_date"]))
    NEW_EVIDENCE.append(T["evidence"][-1])

for act in NEW_ACTIONS:
    if act["status"] == "Completed" and random.random() < 0.35:
        add_evidence("Action", act["action_id"], f"{act['action_id']}-completion-signoff.pdf", "application/pdf",
                     f"Completion sign-off and verification record for {act['action_id']}.",
                     date.fromisoformat(act["completion_date"]), uploader=act["owner_employee_id"])
        NEW_EVIDENCE.append(T["evidence"][-1])

for m in NEW_MAINTENANCE:
    if m["status"] == "Delayed":
        add_evidence("Maintenance Record", m["maintenance_record_id"], f"{m['maintenance_record_id']}-work-order.pdf", "application/pdf",
                     f"Work order record for delayed maintenance on {m['equipment_id']}.",
                     date.fromisoformat(m["actual_date"]) if m["actual_date"] else TODAY)
        NEW_EVIDENCE.append(T["evidence"][-1])

print(f"International expansion complete: control_assessments:{len(NEW_CONTROL_ASSESSMENTS)} "
      f"risk_assessments:{len(NEW_RISK_ASSESSMENTS)} risk_register:{len(NEW_RISK_REGISTER)} "
      f"inspections:{len(NEW_INSPECTIONS)} audit_findings:{len(NEW_AUDIT_FINDINGS)} "
      f"actions:{len(NEW_ACTIONS)} evidence:{len(NEW_EVIDENCE)}")
print(f"Totals after expansion: facilities={len(T['facilities'])} employees={len(T['employees'])} "
      f"equipment={len(T['equipment'])} hazards={len(T['hazards'])} controls={len(T['controls'])} "
      f"incidents={len(T['incidents'])} actions={len(T['actions'])}")

# =============================================================================
# BUILD SQLITE DATABASE
# =============================================================================
INSERT_ORDER = ["companies","facilities","roles","employees","contractors","equipment","sops","hazards",
    "controls","maintenance_records","incidents","risk_assessments","risk_register","control_assessments",
    "inspections","audit_findings","actions","training_records","evidence"]

if DB_PATH.exists():
    DB_PATH.unlink()
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON;")
conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

for table in INSERT_ORDER:
    rows = T[table]
    if not rows:
        continue
    cols = list(rows[0].keys())
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])

conn.commit()
print(f"\nSQLite database written to {DB_PATH}")

# =============================================================================
# EXPORT CSVs
# =============================================================================
import csv as csv_mod
for table in INSERT_ORDER:
    rows = T[table]
    if not rows:
        continue
    with open(CSV_DIR / f"{table}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv_mod.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
print(f"CSV exports written to {CSV_DIR}")

# =============================================================================
# TEST SCENARIOS — ground truth for the 5 requested pattern-detection tests.
# Dev/test fixture only — never surfaced verbatim in the product UI.
# =============================================================================
test_scenarios = [
    {
        "scenario_id": "TS-01",
        "name": "Forklift/Pedestrian Emerging Risk",
        "description": "Multiple forklift/pedestrian near misses recur at two separate facilities (Rex North Plant "
                        "and Rex South Plant) involving different forklift units, with no injuries yet recorded.",
        "expected_finding": "The engine should surface this as an emerging cross-facility pattern (not isolated "
                             "one-off events) tied to hazard category 'Forklift / Vehicle Incident', and flag it "
                             "as higher-priority than its individual near-miss severities would suggest given the "
                             "repeat count and multi-site spread.",
        "ground_truth": {
            "hazard_ids": [HAZ_FORKLIFT_NORTH, HAZ_FORKLIFT_SOUTH],
            "incident_ids": PATTERN1_INCIDENT_IDS,
            "equipment_ids": list(PATTERN1_EQUIPMENT_IDS.values()),
            "facility_ids": [FAC_NORTH, FAC_SOUTH],
        },
    },
    {
        "scenario_id": "TS-02",
        "name": "Repeated Machine-Guarding Failures",
        "description": "The same machine type (Punch Press) produces repeated guarding-related incidents on two "
                        "separate units at two facilities, and the control meant to prevent it "
                        f"({PATTERN4_CONTROL_ID}) has been reassessed 5 times, oscillating between "
                        "'Partially Effective' and 'Ineffective' without ever sustaining 'Effective'.",
        "expected_finding": "The engine should link the incident cluster, the equipment type, and the repeatedly "
                             "failing control together as one systemic pattern, rather than treating each incident "
                             "or each control assessment independently.",
        "ground_truth": {
            "hazard_id": HAZ_PUNCHPRESS,
            "incident_ids": PATTERN2_INCIDENT_IDS,
            "equipment_ids": PATTERN2_EQUIPMENT_IDS,
            "control_id": PATTERN4_CONTROL_ID,
            "control_assessment_ids": [ca["control_assessment_id"] for ca in T["control_assessments"] if ca["control_id"] == PATTERN4_CONTROL_ID],
            "related_audit_finding_id": "AUD-0001",
        },
    },
    {
        "scenario_id": "TS-03",
        "name": "Overdue Corrective-Action Pattern",
        "description": "A cluster of corrective/preventive actions repeatedly slip past their due date "
                        "(reschedule_count >= 2, status = Overdue), visible from three angles: actions tied to the "
                        f"punch-press guard control ({PATTERN4_CONTROL_ID}), actions owned by one recurring "
                        f"employee ({OVERLOADED_EMP}), and a facility-wide cluster at Rex Central Plant.",
        "expected_finding": "The engine should detect that overdue-ness is concentrated (by control, by owner, and "
                             "by facility) rather than randomly distributed across the 100 actions, and should be "
                             "able to name at least one of these three concentration angles.",
        "ground_truth": {
            "action_ids": PATTERN3_ACTION_IDS,
            "overloaded_owner_employee_id": OVERLOADED_EMP,
            "concentrated_facility_id": FAC_CENTRAL,
            "concentrated_control_id": PATTERN4_CONTROL_ID,
        },
    },
    {
        "scenario_id": "TS-04",
        "name": "Contractor Training Risk",
        "description": "Several incidents involving contractors trace back to contractors whose training_records "
                        "show 'Not Completed' or 'Expired' status on a directly relevant safety topic (LOTO, "
                        "Confined Space Entry, or Contractor Safety Orientation) at the time of the incident.",
        "expected_finding": "The engine should connect the incident -> contractor -> training_records chain and "
                             "identify that these are not independent contractor errors but a training-verification "
                             "gap in the contractor onboarding/authorization process.",
        "ground_truth": {
            "contractor_ids": PATTERN6_CONTRACTOR_IDS,
            "incident_ids": PATTERN6_INCIDENT_IDS,
            "training_gap_topics": PATTERN6_GAP_TOPICS,
            "related_control_id": CTL_CONTRACTOR_LOTO,
            "related_audit_finding_id": "AUD-0002",
        },
    },
    {
        "scenario_id": "TS-05",
        "name": "Maintenance-Related Risk",
        "description": "Equipment failure incidents follow shortly (6-15 days) after preventive maintenance was "
                        "delayed on the same equipment unit, across three separate delay events on two equipment ids.",
        "expected_finding": "The engine should surface the temporal link between maintenance_records.status='Delayed' "
                             "and a subsequent incidents.incident_type='Equipment Failure' on the SAME equipment_id, "
                             "rather than treating the incidents as unrelated equipment failures.",
        "ground_truth": {
            "equipment_ids": PATTERN5_EQUIPMENT_IDS,
            "maintenance_record_ids": [e[1] for e in PATTERN5_EVENTS],
            "incident_ids": PATTERN5_INCIDENT_IDS,
        },
    },
]
with open(ROOT / "database" / "test_scenarios.json", "w", encoding="utf-8") as f:
    json.dump(test_scenarios, f, indent=2)
print(f"\nTest scenarios written to database/test_scenarios.json ({len(test_scenarios)} scenarios)")

# =============================================================================
# EXAMPLE RECORDS — one real row per table, for docs/database-design.md
# =============================================================================
example_records = {table: (rows[0] if rows else None) for table, rows in T.items()}
with open(ROOT / "database" / "example_records.json", "w", encoding="utf-8") as f:
    json.dump(example_records, f, indent=2)
print(f"Example records written to database/example_records.json")
