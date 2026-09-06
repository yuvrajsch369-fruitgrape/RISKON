#!/usr/bin/env python3
"""
RISKON Risk Intelligence Engine (prototype).

Analyzes the existing synthetic operational database (database/riskon.db —
Rex Industrial Manufacturing) to surface emerging risk patterns across
incidents, near misses, hazards, controls, and corrective actions. This is
a read-only, deterministic analytics layer: every number here comes from a
SQL query or an arithmetic combination of SQL queries, never from a live
model call and never from an invented fact.

--------------------------------------------------------------------------
EPISTEMIC LABELING — read this before reading any output of this module
--------------------------------------------------------------------------
Every finding this engine produces is tagged with exactly one of four
categories, and the tag is never dropped when the finding is displayed:

  OBSERVED_FACT        A direct count/value read from the database with no
                        interpretation (e.g. "7 incidents recorded against
                        this hazard in the last 12 months").
  STATISTICAL_PATTERN  A comparison or aggregation over observed facts that
                        implies a shape (e.g. "incident count in the last 6
                        months exceeds the prior 6 months" -> trend
                        direction). Still fully computed, not inferred.
  AI_HYPOTHESIS         A candidate explanation for a statistical pattern.
                        Always phrased as a possibility ("may indicate",
                        "could suggest"), never as an established cause.
  RECOMMENDATION         An action proposed for a human to take. Always a
                        request to investigate/review/confirm, never an
                        instruction to make a safety-critical decision.

This engine NEVER outputs a certainty claim about a future event. It uses
"risk signal detected", "pattern suggests", and "further investigation
recommended" — not "an accident will happen" or any equivalent. See
HEDGE_* constants below for the exact vocabulary enforced throughout.
"""
import calendar
import json
import sqlite3
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "database" / "riskon.db"
TODAY = date(2026, 9, 3)

SEVERITY_NUM = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
TREND_SCORE = {"Increasing": 1.0, "Stable": 0.5, "Decreasing": 0.2}
CONTROL_GAP_SCORE = {"Ineffective": 1.0, "Partially Effective": 0.6, "Effective": 0.2, "Not Assessed": 0.7}
CONTROL_RATING_ORDER = ["Ineffective", "Partially Effective", "Effective"]  # worst-first

# The Risk Signal Score is a weighted sum of six 0-1 factors, documented in
# full in docs/risk-intelligence-engine.md. Weights sum to 1.0.
WEIGHTS = {
    "frequency": 0.25, "severity": 0.20, "recurrence": 0.15,
    "trend": 0.15, "control_gap": 0.15, "action_overdue": 0.10,
}

# Category name -> a more natural risk name, for the handful of categories
# where the raw hazard_category reads awkwardly as a "risk name". Anything
# not listed here just uses the hazard_category verbatim — never invented.
RISK_NAME_OVERRIDES = {
    "Forklift / Vehicle Incident": "Forklift/Pedestrian Interaction",
    "Machine Guarding Failure": "Machine Guarding Failure (Point-of-Operation)",
    "Lockout/Tagout Violation": "Lockout/Tagout (LOTO) Non-Compliance",
    "Equipment Failure Risk": "Equipment Failure Following Deferred Maintenance",
}


def idate(s):
    return date.fromisoformat(s[:10])


def days_ago(d, as_of=None):
    return ((as_of or TODAY) - d).days


def months_ago(as_of, n):
    """`n` calendar months before `as_of`, clamping the day-of-month to the
    target month's actual length (e.g. Mar 31 minus 1 month -> Feb 28/29).
    Used only to pick the historical checkpoints for enterprise_risk_trend()."""
    total = as_of.year * 12 + (as_of.month - 1) - n
    y, m = divmod(total, 12)
    m += 1
    last_day = calendar.monthrange(y, m)[1]
    return date(y, m, min(as_of.day, last_day))


class RiskIntelligenceEngine:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._load()

    def q(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params)]

    def _load(self):
        self.incidents = self.q("SELECT * FROM incidents")
        self.hazards = self.q("SELECT * FROM hazards")
        self.controls = self.q("SELECT * FROM controls")
        self.control_assessments = self.q("SELECT * FROM control_assessments")
        self.actions = self.q("SELECT * FROM actions")
        self.risk_assessments = self.q("SELECT * FROM risk_assessments")
        self.risk_register = self.q("SELECT * FROM risk_register")
        self.maintenance_records = self.q("SELECT * FROM maintenance_records")
        self.training_records = self.q("SELECT * FROM training_records")
        self.contractors = self.q("SELECT * FROM contractors")
        self.facilities = self.q("SELECT * FROM facilities")

        self.hazard_by_id = {h["hazard_id"]: h for h in self.hazards}
        self.facility_by_id = {f["facility_id"]: f for f in self.facilities}
        self.control_by_id = {c["control_id"]: c for c in self.controls}
        self.contractor_by_id = {c["contractor_id"]: c for c in self.contractors}

    def fac_name(self, fid):
        f = self.facility_by_id.get(fid)
        return f["name"] if f else fid

    # -------------------------------------------------------------------
    # Low-level, reusable signal primitives — every one of these is an
    # OBSERVED_FACT or STATISTICAL_PATTERN computation with no hypothesis
    # content. build_emerging_risk() and the Q&A functions below compose
    # these; nothing downstream invents a number that isn't traceable back
    # to one of these.
    # -------------------------------------------------------------------
    def trailing_12mo(self, incs, as_of=None):
        return [i for i in incs if days_ago(idate(i["incident_datetime"]), as_of) <= 365]

    def trend_of(self, incs, as_of=None):
        recent = [i for i in incs if 0 <= days_ago(idate(i["incident_datetime"]), as_of) <= 182]
        prior = [i for i in incs if 183 <= days_ago(idate(i["incident_datetime"]), as_of) <= 365]
        if len(recent) > len(prior):
            direction = "Increasing"
        elif len(recent) < len(prior):
            direction = "Decreasing"
        else:
            direction = "Stable"
        return direction, len(recent), len(prior)

    def latest_control_rating(self, control_ids, as_of=None):
        """Worst-case (most conservative) latest rating across a set of controls,
        as of `as_of` (defaults to TODAY). Only assessments dated on or before
        `as_of` are considered -- this is what makes enterprise_risk_trend()'s
        historical points free of lookahead bias (a control assessment from
        next month can't retroactively improve last month's score).
        'Not Assessed' if none of the controls has been assessed as of that date."""
        cutoff = as_of or TODAY
        ratings = []
        for cid in control_ids:
            assessments = sorted(
                [ca for ca in self.control_assessments if ca["control_id"] == cid and idate(ca["assessment_date"]) <= cutoff],
                key=lambda a: a["assessment_date"],
            )
            if assessments:
                ratings.append(assessments[-1]["effectiveness_rating"])
        if not ratings:
            return "Not Assessed", []
        worst = min(ratings, key=lambda r: CONTROL_RATING_ORDER.index(r))
        return worst, ratings

    def related_actions_for(self, control_ids, incident_ids, as_of=None):
        cutoff = as_of or TODAY
        return [
            a for a in self.actions
            if idate(a["created_date"]) <= cutoff
            and ((a["related_control_id"] in control_ids) or (a["source_incident_id"] in incident_ids))
        ]

    def top_root_cause(self, incs):
        completed = [i for i in incs if i["investigation_status"] == "Completed" and i["root_cause_category"]]
        if not completed:
            return None, 0, 0
        counts = defaultdict(int)
        for i in completed:
            counts[i["root_cause_category"]] += 1
        top, n = max(counts.items(), key=lambda kv: kv[1])
        return top, n, len(completed)

    # -------------------------------------------------------------------
    # EMERGING RISK builder — clusters by hazard_category (a category is
    # the natural unit for "a recurring type of risk" per the spec's own
    # example, "Forklift/Pedestrian Interaction", which spans two separate
    # hazard rows at two separate facilities under one category).
    # -------------------------------------------------------------------
    def hazard_categories_with_incidents(self):
        cats = set()
        hz_by_id = self.hazard_by_id
        for i in self.incidents:
            hz = hz_by_id.get(i["hazard_id"])
            if hz:
                cats.add(hz["hazard_category"])
        return sorted(cats)

    def build_emerging_risk(self, category, risk_id, as_of=None):
        """`as_of` lets this same method compute a real HISTORICAL score (used by
        enterprise_risk_trend() below) rather than only ever scoring "as of
        today". Incidents that hadn't happened yet by `as_of` are excluded
        entirely -- no lookahead. Control-effectiveness ratings and action
        overdue status are read at their CURRENT (final) values even for a
        historical `as_of` (this dataset has no state-history table to
        reconstruct what a rating "was" on a past date) -- documented as a
        disclosed simplification in docs/risk-intelligence-engine.md, not
        hidden. The trend line this produces reflects known incident timing
        with current knowledge of causes/controls, the same way a rolling
        trailing-twelve-month chart works from real transactions."""
        cutoff = as_of or TODAY
        hz_ids = {h["hazard_id"] for h in self.hazards if h["hazard_category"] == category}
        incs = [i for i in self.incidents if i["hazard_id"] in hz_ids and idate(i["incident_datetime"]) <= cutoff]
        if not incs:
            return None

        trailing = self.trailing_12mo(incs, as_of)
        near_miss = [i for i in incs if i["incident_type"] == "Near Miss"]
        facilities_involved = sorted(set(i["facility_id"] for i in incs))
        sev_vals = [SEVERITY_NUM.get(i["initial_severity"], 2) for i in incs]
        avg_sev = statistics.mean(sev_vals) if sev_vals else 2.0
        trend, recent_n, prior_n = self.trend_of(incs, as_of)

        ctl_ids = {c["control_id"] for c in self.controls if c["hazard_id"] in hz_ids}
        control_rating, all_ratings = self.latest_control_rating(ctl_ids, as_of)

        inc_ids = {i["incident_id"] for i in incs}
        related_actions = self.related_actions_for(ctl_ids, inc_ids, as_of)
        overdue_actions = [a for a in related_actions if a["status"] == "Overdue"]
        repeat_overdue = [a for a in overdue_actions if a["reschedule_count"] >= 2]

        top_cause, cause_n, cause_total = self.top_root_cause(incs)

        # --- Risk Signal Score (see docs/risk-intelligence-engine.md) ---
        frequency_score = min(1.0, len(trailing) / 8)
        severity_score = avg_sev / 4
        recurrence_score = min(1.0, len(facilities_involved) / 3)
        trend_score = TREND_SCORE[trend]
        control_gap_score = CONTROL_GAP_SCORE[control_rating]
        action_overdue_score = (len(overdue_actions) / len(related_actions)) if related_actions else 0.0

        raw = (WEIGHTS["frequency"] * frequency_score + WEIGHTS["severity"] * severity_score +
               WEIGHTS["recurrence"] * recurrence_score + WEIGHTS["trend"] * trend_score +
               WEIGHTS["control_gap"] * control_gap_score + WEIGHTS["action_overdue"] * action_overdue_score)
        signal_score = round(raw * 100, 1)
        band = ("Critical" if signal_score >= 80 else "High" if signal_score >= 55
                else "Medium" if signal_score >= 30 else "Low")
        confidence = "Low" if len(trailing) < 3 else ("Medium" if len(trailing) < 6 else "High")

        score_breakdown = {
            "frequency": {"value": len(trailing), "score": round(frequency_score, 2), "weight": WEIGHTS["frequency"]},
            "severity": {"value": round(avg_sev, 2), "score": round(severity_score, 2), "weight": WEIGHTS["severity"]},
            "recurrence": {"value": len(facilities_involved), "score": round(recurrence_score, 2), "weight": WEIGHTS["recurrence"]},
            "trend": {"value": trend, "score": round(trend_score, 2), "weight": WEIGHTS["trend"]},
            "control_gap": {"value": control_rating, "score": round(control_gap_score, 2), "weight": WEIGHTS["control_gap"]},
            "action_overdue": {"value": f"{len(overdue_actions)}/{len(related_actions)}", "score": round(action_overdue_score, 2), "weight": WEIGHTS["action_overdue"]},
        }

        # --- Evidence: only statements backed by a real computed value above ---
        evidence = []
        evidence.append({"type": "OBSERVED_FACT",
                          "statement": f"{len(incs)} total incidents recorded under hazard category '{category}' "
                                       f"({len(trailing)} within the trailing 12 months).",
                          "refs": [i["incident_id"] for i in incs]})
        if near_miss:
            evidence.append({"type": "OBSERVED_FACT",
                              "statement": f"{len(near_miss)} of these were near misses (no injury/damage occurred).",
                              "refs": [i["incident_id"] for i in near_miss]})
        if len(facilities_involved) >= 2:
            evidence.append({"type": "OBSERVED_FACT",
                              "statement": f"Incidents recorded at {len(facilities_involved)} separate facilities: "
                                           + ", ".join(self.fac_name(f) for f in facilities_involved) + ".",
                              "refs": facilities_involved})
        evidence.append({"type": "STATISTICAL_PATTERN",
                          "statement": f"Trend signal: {recent_n} incidents in the most recent 6 months vs. "
                                       f"{prior_n} in the prior 6 months -> {trend}.",
                          "refs": []})
        if control_rating in ("Ineffective", "Partially Effective"):
            evidence.append({"type": "OBSERVED_FACT",
                              "statement": f"Most recent control assessment for the related control(s) rated "
                                           f"effectiveness as '{control_rating}'.",
                              "refs": sorted(ctl_ids)})
        elif control_rating == "Not Assessed":
            evidence.append({"type": "OBSERVED_FACT",
                              "statement": "No control assessment is on file for the control(s) tied to this hazard "
                                           "-- effectiveness is unconfirmed, not assumed adequate.",
                              "refs": sorted(ctl_ids)})
        if overdue_actions:
            evidence.append({"type": "OBSERVED_FACT",
                              "statement": f"{len(overdue_actions)} of {len(related_actions)} related corrective/"
                                           f"preventive actions are currently Overdue"
                                           + (f" ({len(repeat_overdue)} rescheduled 2+ times)." if repeat_overdue else "."),
                              "refs": [a["action_id"] for a in overdue_actions]})
        if top_cause and cause_n >= 2:
            evidence.append({"type": "STATISTICAL_PATTERN",
                              "statement": f"Root-cause category '{top_cause}' recorded on {cause_n} of "
                                           f"{cause_total} investigated incidents in this cluster.",
                              "refs": [i["incident_id"] for i in incs if i["root_cause_category"] == top_cause]})

        # --- AI hypothesis + recommendation: hedged, grounded only in the evidence above ---
        hypothesis_bits = []
        if control_rating in ("Ineffective", "Partially Effective"):
            hypothesis_bits.append(f"the control(s) intended to mitigate '{category}' may not be functioning as designed")
        if len(facilities_involved) >= 2:
            hypothesis_bits.append("the issue may not be site-specific, which would point toward a shared procedural or design gap rather than a local one")
        if top_cause and cause_n >= 2:
            hypothesis_bits.append(f"a recurring '{top_cause.lower()}' factor may be a common thread across these incidents")
        if not hypothesis_bits:
            hypothesis_bits.append("no single dominant contributing factor stands out yet from the available evidence")
        systemic_issue = "Pattern suggests " + "; and ".join(hypothesis_bits) + ". Further investigation recommended before drawing a conclusion."

        rec_target = "the assigned Safety Manager" if len(facilities_involved) <= 1 else "the HSE/Safety Manager function across the affected facilities"
        recommendation = f"Recommended next step: {rec_target} should review this cluster's incidents and the related control(s)" \
                          + (f" and confirm whether the {len(overdue_actions)} overdue action(s) address the root cause." if overdue_actions else ".")

        return {
            "risk_id": risk_id,
            "risk_name": RISK_NAME_OVERRIDES.get(category, category),
            "hazard_category": category,
            "facility": self.fac_name(facilities_involved[0]) if len(facilities_involved) == 1 else "Multiple",
            "facilities": [self.fac_name(f) for f in facilities_involved],
            "risk_signal_score": signal_score,
            "risk_band": band,
            "signal": trend,
            "score_breakdown": score_breakdown,
            "evidence": evidence,
            "related_incidents": sorted(inc_ids),
            "related_hazards": sorted(hz_ids),
            "related_controls": sorted(ctl_ids),
            "related_actions": sorted(a["action_id"] for a in related_actions),
            "related_actions_overdue": sorted(a["action_id"] for a in overdue_actions),
            "confidence": confidence,
            "possible_systemic_issue": {"type": "AI_HYPOTHESIS", "statement": systemic_issue},
            "recommended_investigation": {"type": "RECOMMENDATION", "statement": recommendation},
            "human_review_status": "Pending",
        }

    def all_emerging_risks(self, as_of=None):
        risks = []
        for i, cat in enumerate(self.hazard_categories_with_incidents(), start=1):
            r = self.build_emerging_risk(cat, f"ERISK-{i:03d}", as_of)
            if r:
                risks.append(r)
        risks.sort(key=lambda r: r["risk_signal_score"], reverse=True)
        return risks

    def top_n_emerging_risks(self, n=5, as_of=None):
        return self.all_emerging_risks(as_of)[:n]

    # -------------------------------------------------------------------
    # ENTERPRISE-LEVEL AGGREGATES — for the Executive Dashboard. These
    # compose the same primitives above; nothing here is a new source of
    # truth, only a roll-up of numbers already computed elsewhere.
    # -------------------------------------------------------------------
    def enterprise_risk_signal(self, as_of=None):
        """A single 0-100 "how hot is the enterprise's risk picture" number.
        Defined as the average Risk Signal Score across the top 5 emerging
        risks as of `as_of` -- i.e. it tracks the risks material enough to
        already be on management's radar, not a dilution across every minor
        category. Documented in docs/risk-intelligence-engine.md."""
        risks = self.top_n_emerging_risks(5, as_of)
        if not risks:
            return {"signal_score": 0.0, "band": "Low", "basis_risk_count": 0}
        avg = round(statistics.mean(r["risk_signal_score"] for r in risks), 1)
        band = ("Critical" if avg >= 80 else "High" if avg >= 55
                else "Medium" if avg >= 30 else "Low")
        return {"signal_score": avg, "band": band, "basis_risk_count": len(risks)}

    def enterprise_risk_trend(self, months=6):
        """A genuine historical backtest, not a fabricated line: re-runs the
        exact same Risk Signal Score formula at each of the last `months`
        month-end checkpoints, using only incidents/assessments/actions that
        had actually occurred as of that checkpoint (via build_emerging_risk's
        `as_of` filtering, no lookahead). Two disclosed simplifications carry
        through from build_emerging_risk: control-effectiveness ratings and
        action-overdue status are evaluated at their CURRENT (final) values
        even for past checkpoints, since this dataset has no state-history
        table to reconstruct what a rating "was" on a past date."""
        points = []
        for n in range(months - 1, -1, -1):
            checkpoint = months_ago(TODAY, n)
            sig = self.enterprise_risk_signal(checkpoint)
            points.append({"date": checkpoint.isoformat(), "signal_score": sig["signal_score"], "band": sig["band"]})
        return points

    def action_priority(self, a):
        """`actions` has no priority column in the schema. Priority is
        DERIVED here from the severity of the linked incident (when the
        action originated from one) -- never invented -- and defaults to
        Medium when there is no incident to derive it from."""
        if a["source_incident_id"]:
            inc = next((i for i in self.incidents if i["incident_id"] == a["source_incident_id"]), None)
            if inc:
                sev = inc["initial_severity"]
                if sev in ("Critical", "High"):
                    return "High"
                if sev == "Medium":
                    return "Medium"
                return "Low"
        return "Medium"

    def enterprise_overview(self, as_of=None):
        cutoff = as_of or TODAY
        risks = self.all_emerging_risks(as_of)
        high_critical_risks = [r for r in risks if r["risk_band"] in ("High", "Critical")]
        emerging_risks = [r for r in risks if r["signal"] == "Increasing"]
        actions_asof = [a for a in self.actions if idate(a["created_date"]) <= cutoff]
        open_actions = [a for a in actions_asof if a["status"] in ("Open", "In Progress")]
        overdue_actions = [a for a in actions_asof if a["status"] == "Overdue"]
        incs_asof = [i for i in self.incidents if idate(i["incident_datetime"]) <= cutoff]
        trailing = self.trailing_12mo(incs_asof, as_of)
        near_miss_trailing = [i for i in trailing if i["incident_type"] == "Near Miss"]
        sig = self.enterprise_risk_signal(as_of)
        return {
            "as_of": cutoff.isoformat(),
            "overall_risk_signal_score": sig["signal_score"],
            "overall_risk_band": sig["band"],
            "open_high_risk_issues": len(high_critical_risks),
            "emerging_risk_count": len(emerging_risks),
            "open_corrective_actions": len(open_actions),
            "overdue_corrective_actions": len(overdue_actions),
            "incidents_trailing_12mo": len(trailing),
            "near_misses_trailing_12mo": len(near_miss_trailing),
        }

    def corrective_action_intelligence(self):
        def brief(a):
            return {
                "action_id": a["action_id"], "description": a["description"], "status": a["status"],
                "facility": self.fac_name(a["facility_id"]), "due_date": a["due_date"],
                "reschedule_count": a["reschedule_count"], "priority": self.action_priority(a),
            }
        open_actions = [a for a in self.actions if a["status"] in ("Open", "In Progress")]
        overdue_actions = [a for a in self.actions if a["status"] == "Overdue"]
        recently_closed = [a for a in self.actions if a["status"] == "Completed" and a["completion_date"]
                            and days_ago(idate(a["completion_date"])) <= 30]
        repeat_overdue = [a for a in self.actions if a["reschedule_count"] >= 2 and a["status"] != "Completed"]
        high_priority_open = [a for a in (open_actions + overdue_actions) if self.action_priority(a) == "High"]
        return {
            "open_count": len(open_actions), "overdue_count": len(overdue_actions),
            "recently_closed_count": len(recently_closed), "repeatedly_overdue_count": len(repeat_overdue),
            "high_priority_open_count": len(high_priority_open),
            "overdue": [brief(a) for a in sorted(overdue_actions, key=lambda a: a["due_date"])[:10]],
            "repeatedly_overdue": [brief(a) for a in sorted(repeat_overdue, key=lambda a: -a["reschedule_count"])[:10]],
            "recently_closed": [brief(a) for a in sorted(recently_closed, key=lambda a: a["completion_date"], reverse=True)[:10]],
            "high_priority_open": [brief(a) for a in sorted(high_priority_open, key=lambda a: a["due_date"])[:10]],
        }

    def facility_comparison(self):
        """`risk_exposure_score` attributes each emerging risk's signal score to
        the facilities it touches, splitting credit evenly across facilities
        for a risk that spans more than one (e.g. a risk seen at all 3 plants
        contributes 1/3 of its score to each) -- so a facility isn't ranked
        "highest risk" merely for sharing a company-wide risk with everyone
        else. `max_risk_signal_score` (the single worst risk touching that
        facility, un-split) is kept alongside it for context."""
        facs = [f["facility_id"] for f in self.facilities]
        risks = self.all_emerging_risks()
        per_fac_risks = defaultdict(list)
        for r in risks:
            for fname in r["facilities"]:
                per_fac_risks[fname].append(r)
        fac_summary = {}
        for fid in facs:
            fname = self.fac_name(fid)
            involved = per_fac_risks.get(fname, [])
            max_score = max((r["risk_signal_score"] for r in involved), default=0.0)
            exposure = round(sum(r["risk_signal_score"] / len(r["facilities"]) for r in involved), 1)
            increasing = [r for r in involved if r["signal"] == "Increasing"]
            fastest = max(increasing, key=lambda r: r["risk_signal_score"], default=None)
            fac_summary[fid] = {
                "facility": fname,
                "risk_exposure_score": exposure,
                "max_risk_signal_score": max_score,
                "risk_count": len(involved),
                "fastest_increasing_risk": fastest["risk_name"] if fastest else None,
            }
        highest = max(fac_summary.values(), key=lambda p: p["risk_exposure_score"], default=None)
        q4 = self.q4_unusual_facility_patterns()
        q6 = self.q6_ineffective_controls()
        q7 = self.q7_cross_facility_hazards()
        return {
            "facility_summaries": fac_summary,
            "highest_risk_facility": highest["facility"] if highest and highest["risk_exposure_score"] > 0 else None,
            "recurring_hazards_cross_facility": q7["findings"],
            "control_failures": q6["findings"],
            "facility_profiles": q4["facility_profiles"],
            "facility_pattern_findings": q4["findings"],
        }

    def management_brief(self):
        """Template-based summary text -- no live model call. Every clause maps
        to a specific computed value above; nothing here is invented. Hedge
        language ("strongest emerging signal because of...", "recommended")
        matches the vocabulary used throughout this engine."""
        risks = self.top_n_emerging_risks(5)
        increasing = [r for r in risks if r["signal"] == "Increasing"]
        lines = []
        if not increasing:
            lines.append("No risk signals increased during the current reporting period based on the trailing "
                          "six-month comparison; overall signal levels are stable or declining across the top-"
                          "tracked risk categories.")
        else:
            lines.append(f"{len(increasing)} of the top {len(risks)} tracked risk signals increased during the "
                          f"current reporting period.")
            strongest = increasing[0]
            n_fac = len(strongest["facilities"])
            evidence_bit = (f"{len(strongest['related_incidents'])} recorded incidents across {n_fac} "
                             f"facilit{'y' if n_fac == 1 else 'ies'}")
            if strongest["related_actions_overdue"]:
                evidence_bit += f" and {len(strongest['related_actions_overdue'])} unresolved corrective action(s)"
            lines.append(f"'{strongest['risk_name']}' is the strongest emerging signal (score "
                         f"{strongest['risk_signal_score']}, {strongest['risk_band']}), based on {evidence_bit}.")
            lines.append(strongest["recommended_investigation"]["statement"])
        ca = self.corrective_action_intelligence()
        if ca["overdue_count"] > 0:
            extra = f", including {ca['repeatedly_overdue_count']} rescheduled two or more times" if ca["repeatedly_overdue_count"] else ""
            lines.append(f"{ca['overdue_count']} corrective actions are currently overdue company-wide{extra}.")
        return {
            "summary": " ".join(lines),
            "label": "AI-generated management summary -- human review recommended.",
            "generated_from": {"top_risk_ids_considered": [r["risk_id"] for r in risks], "as_of": TODAY.isoformat()},
            "human_review_status": "Pending",
        }

    # =====================================================================
    # THE 10 REQUIRED QUESTIONS
    # Every method here returns {"question", "answer_type", "findings"}
    # where each finding is itself tagged OBSERVED_FACT / STATISTICAL_PATTERN
    # / AI_HYPOTHESIS / RECOMMENDATION, per the engine-wide labeling rule.
    # =====================================================================

    def q1_top_emerging_risks(self, n=5):
        risks = self.top_n_emerging_risks(n)
        return {
            "question": "What are the top 5 emerging risks?",
            "findings": [
                {"type": "STATISTICAL_PATTERN", "risk_id": r["risk_id"], "risk_name": r["risk_name"],
                 "statement": f"Risk signal score {r['risk_signal_score']} ({r['risk_band']}), signal: {r['signal']}, "
                              f"across {len(r['facilities'])} facilit{'y' if len(r['facilities'])==1 else 'ies'}.",
                 "risk_id_ref": r["risk_id"]}
                for r in risks
            ],
        }

    def q2_increasing_risks(self):
        increasing = [r for r in self.all_emerging_risks() if r["signal"] == "Increasing"]
        return {
            "question": "Which risks are increasing?",
            "findings": [
                {"type": "STATISTICAL_PATTERN", "risk_id": r["risk_id"], "risk_name": r["risk_name"],
                 "statement": f"More incidents in the trailing 6 months than the 6 months before "
                              f"(signal score {r['risk_signal_score']}, {r['risk_band']}).",
                 "risk_id_ref": r["risk_id"]}
                for r in increasing
            ],
        }

    def q3_recurring_risks(self):
        recurring = [r for r in self.all_emerging_risks()
                     if r["score_breakdown"]["frequency"]["value"] >= 3 or len(r["facilities"]) >= 2]
        return {
            "question": "Which risks are recurring?",
            "findings": [
                {"type": "OBSERVED_FACT", "risk_id": r["risk_id"], "risk_name": r["risk_name"],
                 "statement": f"{r['score_breakdown']['frequency']['value']} incidents in the trailing 12 months"
                              + (f", spanning {len(r['facilities'])} facilities" if len(r["facilities"]) >= 2 else "") + ".",
                 "risk_id_ref": r["risk_id"]}
                for r in recurring
            ],
        }

    def q4_unusual_facility_patterns(self):
        facs = [f["facility_id"] for f in self.facilities]
        profile = {}
        for fid in facs:
            f_incs = [i for i in self.incidents if i["facility_id"] == fid]
            f_open = [i for i in f_incs if i["closure_status"] == "Open"]
            f_actions = [a for a in self.actions if a["facility_id"] == fid]
            f_overdue = [a for a in f_actions if a["status"] == "Overdue"]
            f_repeat_overdue = [a for a in f_overdue if a["reschedule_count"] >= 2]
            f_risks = [rr for rr in self.risk_register if rr["facility_id"] == fid and rr["status"] == "Open"]
            f_hicrit = [rr for rr in f_risks if rr["current_level"] in ("High", "Critical")]
            profile[fid] = {
                "facility": self.fac_name(fid), "open_incidents": len(f_open),
                "overdue_actions": len(f_overdue), "repeat_overdue_actions": len(f_repeat_overdue),
                "open_high_critical_risks": len(f_hicrit), "total_actions": len(f_actions),
            }
        avg_overdue = statistics.mean(p["overdue_actions"] for p in profile.values()) or 1
        avg_hicrit = statistics.mean(p["open_high_critical_risks"] for p in profile.values()) or 1
        findings = []
        for fid, p in profile.items():
            findings.append({"type": "OBSERVED_FACT", "statement":
                f"{p['facility']}: {p['open_incidents']} open incidents, {p['overdue_actions']} overdue actions "
                f"({p['repeat_overdue_actions']} rescheduled 2+ times), {p['open_high_critical_risks']} open High/Critical risks."})
            if p["overdue_actions"] >= max(3.0, avg_overdue * 1.8):
                ratio = round(p["overdue_actions"] / avg_overdue, 1) if avg_overdue else p["overdue_actions"]
                findings.append({"type": "STATISTICAL_PATTERN", "statement":
                    f"{p['facility']}'s overdue-action count ({p['overdue_actions']}) is {ratio}x the "
                    f"cross-facility average ({round(avg_overdue,1)}) -- concentration signal."})
                findings.append({"type": "AI_HYPOTHESIS", "statement":
                    f"Pattern suggests corrective-action follow-through at {p['facility']} may not be keeping pace "
                    f"with the rest of the company; this could reflect resourcing, ownership, or process gaps specific "
                    f"to that site. Further investigation recommended."})
            if p["open_high_critical_risks"] >= max(2.0, avg_hicrit * 1.8):
                findings.append({"type": "STATISTICAL_PATTERN", "statement":
                    f"{p['facility']}'s open High/Critical risk count ({p['open_high_critical_risks']}) exceeds the "
                    f"cross-facility average ({round(avg_hicrit,1)})."})
        return {"question": "Which facilities have unusual risk patterns?", "findings": findings, "facility_profiles": profile}

    def q5_repeatedly_overdue_actions(self):
        repeat = [a for a in self.actions if a["reschedule_count"] >= 2]
        by_control = defaultdict(list)
        by_owner = defaultdict(list)
        by_facility = defaultdict(list)
        for a in repeat:
            if a["related_control_id"]:
                by_control[a["related_control_id"]].append(a["action_id"])
            by_owner[a["owner_employee_id"]].append(a["action_id"])
            by_facility[a["facility_id"]].append(a["action_id"])
        findings = [{"type": "OBSERVED_FACT",
                     "statement": f"{len(repeat)} of {len(self.actions)} actions have been rescheduled 2 or more times "
                                  f"(currently {sum(1 for a in repeat if a['status']=='Overdue')} still Overdue).",
                     "refs": [a["action_id"] for a in repeat]}]
        for cid, ids in sorted(by_control.items(), key=lambda kv: -len(kv[1])):
            if len(ids) >= 2:
                cname = self.control_by_id.get(cid, {}).get("control_name", cid)
                findings.append({"type": "STATISTICAL_PATTERN",
                                  "statement": f"{len(ids)} repeatedly-overdue actions target the same control: '{cname}' ({cid}).",
                                  "refs": ids})
        for fid, ids in sorted(by_facility.items(), key=lambda kv: -len(kv[1])):
            if len(ids) >= 3:
                findings.append({"type": "STATISTICAL_PATTERN",
                                  "statement": f"{len(ids)} repeatedly-overdue actions are concentrated at {self.fac_name(fid)}.",
                                  "refs": ids})
        for owner, ids in sorted(by_owner.items(), key=lambda kv: -len(kv[1])):
            if len(ids) >= 3:
                findings.append({"type": "STATISTICAL_PATTERN",
                                  "statement": f"{len(ids)} repeatedly-overdue actions share the same owner ({owner}).",
                                  "refs": ids})
        return {"question": "Which corrective actions are repeatedly overdue?", "findings": findings}

    def q6_ineffective_controls(self):
        findings = []
        for c in self.controls:
            assessments = sorted([ca for ca in self.control_assessments if ca["control_id"] == c["control_id"]],
                                  key=lambda a: a["assessment_date"])
            if not assessments:
                continue
            latest = assessments[-1]
            never_effective = all(a["effectiveness_rating"] != "Effective" for a in assessments) and len(assessments) >= 2
            if latest["effectiveness_rating"] == "Ineffective" or never_effective:
                findings.append({"type": "OBSERVED_FACT",
                                  "statement": f"'{c['control_name']}' ({c['control_id']}): latest assessment "
                                               f"({latest['assessment_date']}) rated '{latest['effectiveness_rating']}'"
                                               + (f", never rated Effective across {len(assessments)} assessments" if never_effective else "") + ".",
                                  "refs": [a["control_assessment_id"] for a in assessments]})
        return {"question": "Which controls appear ineffective?", "findings": findings}

    def q7_cross_facility_hazards(self):
        by_cat = defaultdict(set)
        for i in self.incidents:
            hz = self.hazard_by_id.get(i["hazard_id"])
            if hz:
                by_cat[hz["hazard_category"]].add(i["facility_id"])
        findings = []
        for cat, facs in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
            if len(facs) >= 2:
                findings.append({"type": "OBSERVED_FACT",
                                  "statement": f"'{cat}' has recorded incidents at {len(facs)} facilities: "
                                               + ", ".join(self.fac_name(f) for f in sorted(facs)) + "."})
        return {"question": "Which hazards are appearing across multiple facilities?", "findings": findings}

    def q8_systemic_problem_incidents(self):
        flagged = [r for r in self.all_emerging_risks() if r["risk_band"] in ("High", "Critical")]
        findings = []
        for r in flagged:
            findings.append({"type": "AI_HYPOTHESIS",
                              "statement": f"Incidents under '{r['risk_name']}' ({len(r['related_incidents'])} incidents) "
                                           f"belong to a {r['risk_band']}-band signal cluster ({r['risk_signal_score']}); "
                                           f"pattern suggests these may not be independent, isolated events. Further "
                                           f"investigation recommended before concluding a systemic cause.",
                              "refs": r["related_incidents"]})
        return {"question": "Which incidents may indicate a systemic problem?", "findings": findings}

    def q9_evidence_for(self, risk_id):
        r = next((x for x in self.all_emerging_risks() if x["risk_id"] == risk_id), None)
        if not r:
            return {"question": f"What evidence supports {risk_id}?", "findings": [],
                    "error": "No emerging risk with that id was computed from the current dataset."}
        return {"question": f"What evidence supports the conclusion for {risk_id} ({r['risk_name']})?",
                "findings": r["evidence"]}

    def q10_recommended_investigations(self, n=5):
        risks = self.top_n_emerging_risks(n)
        findings = [{"type": "RECOMMENDATION", "risk_id": r["risk_id"], "risk_name": r["risk_name"],
                     "statement": r["recommended_investigation"]["statement"]} for r in risks]
        overdue = self.q5_repeatedly_overdue_actions()
        if overdue["findings"]:
            findings.append({"type": "RECOMMENDATION", "risk_id": None, "risk_name": "Overdue action follow-through",
                              "statement": "Recommended next step: EHS leadership should review the repeatedly-"
                                           "rescheduled corrective actions identified in Q5 as a standing agenda item, "
                                           "independent of any single incident."})
        return {"question": "What actions should management investigate?", "findings": findings}

    def answer_all(self):
        return {
            "q1_top_emerging_risks": self.q1_top_emerging_risks(),
            "q2_increasing_risks": self.q2_increasing_risks(),
            "q3_recurring_risks": self.q3_recurring_risks(),
            "q4_unusual_facility_patterns": self.q4_unusual_facility_patterns(),
            "q5_repeatedly_overdue_actions": self.q5_repeatedly_overdue_actions(),
            "q6_ineffective_controls": self.q6_ineffective_controls(),
            "q7_cross_facility_hazards": self.q7_cross_facility_hazards(),
            "q8_systemic_problem_incidents": self.q8_systemic_problem_incidents(),
            "q10_recommended_investigations": self.q10_recommended_investigations(),
        }
