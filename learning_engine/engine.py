#!/usr/bin/env python3
"""
RISKON Continuous Learning Engine (prototype).

Reads the tables added in database/schema.sql Part 2 (ai_versions,
recommendations, learning_candidates, learning_evaluations) plus the
existing operational tables they reference, and computes every number this
module's callers use — nothing here is a stored, potentially-stale
statistic; every aggregate is a live query/aggregation over
`recommendations`, same discipline as risk_intelligence/engine.py.

--------------------------------------------------------------------------
WHAT THIS MODULE DOES AND DOES NOT DO
--------------------------------------------------------------------------
It DOES: compute recommendation performance by pattern, detect recurring
learning signals (Positive / Negative / Modification / Insufficient Data /
Conflicting) from real decision and outcome data, detect repeated expert
feedback, compare effectiveness across facilities, and assemble the
Incident -> Recommendation -> Decision -> Action -> Outcome -> Signal chain
for one recommendation.

It NEVER: writes back to `ai_versions`/`recommendations`/`learning_candidates`
(those are workflow state changed only by an explicit human decision,
recorded by the caller — see frontend's live recommendation-feedback
handler), invents an outcome, claims causation, or promotes a candidate
version on its own. See docs/continuous-learning-engine.md §4 "Safety
guardrails" for the full list of things this engine is structurally
prevented from doing.
"""
import json
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "database" / "riskon.db"

POSITIVE_RATE_THRESHOLD = 0.60
NEGATIVE_RATE_THRESHOLD = 0.40
MODIFICATION_RATE_THRESHOLD = 0.25
CONFLICT_RATE_GAP = 0.50


def confidence_for(n):
    return "Low" if n < 3 else ("Medium" if n < 6 else "High")


class LearningEngine:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._load()

    def q(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params)]

    def _load(self):
        self.recommendations = self.q("SELECT * FROM recommendations")
        self.ai_versions = self.q("SELECT * FROM ai_versions")
        self.learning_candidates = self.q("SELECT * FROM learning_candidates")
        self.learning_evaluations = self.q("SELECT * FROM learning_evaluations")
        self.incidents = self.q("SELECT * FROM incidents")
        self.actions = self.q("SELECT * FROM actions")
        self.hazards = self.q("SELECT * FROM hazards")
        self.facilities = self.q("SELECT * FROM facilities")
        self.employees = self.q("SELECT * FROM employees")

        self.rec_by_id = {r["recommendation_id"]: r for r in self.recommendations}
        self.incident_by_id = {i["incident_id"]: i for i in self.incidents}
        self.action_by_id = {a["action_id"]: a for a in self.actions}
        self.hazard_by_id = {h["hazard_id"]: h for h in self.hazards}
        self.facility_by_id = {f["facility_id"]: f for f in self.facilities}
        self.employee_by_id = {e["employee_id"]: e for e in self.employees}
        self.version_by_id = {v["version_id"]: v for v in self.ai_versions}

        for r in self.recommendations:
            hz = self.hazard_by_id.get(r["hazard_id"])
            r["hazard_category"] = hz["hazard_category"] if hz else "Uncategorized"

    def fac_name(self, fid):
        f = self.facility_by_id.get(fid)
        return f["name"] if f else fid

    def emp_name(self, eid):
        e = self.employee_by_id.get(eid)
        return f"{e['first_name']} {e['last_name']}" if e else None

    # -------------------------------------------------------------------
    # SECTION 10 — Learning Overview
    # -------------------------------------------------------------------
    def learning_overview(self):
        decided = [r for r in self.recommendations if r["human_decision"] != "Pending"]
        pending_candidates = [c for c in self.learning_candidates if c["status"] in
                               ("Proposed", "Sandbox Testing", "Evaluated")]
        return {
            "recommendations_analyzed": len(self.recommendations),
            "human_feedback_received": len(decided),
            "learning_signals": len(self.detect_signals()),
            "learning_candidates": len(self.learning_candidates),
            "validated_improvements": sum(1 for c in self.learning_candidates if c["status"] == "Deployed"),
            "pending_reviews": sum(1 for r in self.recommendations if r["human_decision"] == "Pending") + len(pending_candidates),
        }

    # -------------------------------------------------------------------
    # SECTION 4 — Recommendation Performance (grouped by hazard category,
    # the same clustering unit risk_intelligence/engine.py uses for
    # "Emerging Risk" — a recurring pattern of recommendation, not a
    # one-off). Every number below is a COUNT() over real rows.
    # -------------------------------------------------------------------
    def performance_by_pattern(self):
        by_cat = defaultdict(list)
        for r in self.recommendations:
            by_cat[r["hazard_category"]].append(r)
        out = []
        for cat, recs in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
            decided = [r for r in recs if r["human_decision"] != "Pending"]
            approved = [r for r in recs if r["human_decision"] == "Approved"]
            modified = [r for r in recs if r["human_decision"] == "Modified"]
            rejected = [r for r in recs if r["human_decision"] == "Rejected"]
            info_req = [r for r in recs if r["human_decision"] == "Request More Information"]
            completed = [r for r in recs if r["action_status"] == "Completed"]
            evaluated = [r for r in recs if r["evaluation_status"] == "Evaluated"]
            positive = [r for r in evaluated if r["learning_signal"] == "Positive"]
            negative = [r for r in evaluated if r["learning_signal"] == "Negative"]
            uncertain = [r for r in recs if r["evaluation_status"] == "Insufficient Data"] + \
                        [r for r in evaluated if r["learning_signal"] not in ("Positive", "Negative")]
            n_decided = len(decided) or 1
            out.append({
                "hazard_category": cat,
                "recommendations": len(recs),
                "approved": len(approved),
                "modified": len(modified),
                "rejected": len(rejected),
                "request_more_info": len(info_req),
                "completed": len(completed),
                "positive_outcomes": len(positive),
                "poor_outcomes": len(negative),
                "uncertain_outcomes": len(uncertain),
                "approval_rate": round(len(approved) / n_decided, 2),
                "modification_rate": round(len(modified) / n_decided, 2),
                "rejection_rate": round(len(rejected) / n_decided, 2),
                "completion_rate": round(len(completed) / (len(recs) or 1), 2),
                "effectiveness_rate": round(len(positive) / len(evaluated), 2) if evaluated else None,
            })
        return out

    # -------------------------------------------------------------------
    # SECTION 5 — Learning Signals (recomputed live every call; nothing
    # stored). SECTION 13 folds Conflicting-signal detection in here since
    # it's the same per-category facility comparison.
    # -------------------------------------------------------------------
    def detect_signals(self):
        by_cat = defaultdict(list)
        for r in self.recommendations:
            by_cat[r["hazard_category"]].append(r)

        signals = []
        for cat, recs in by_cat.items():
            decided = [r for r in recs if r["human_decision"] != "Pending"]
            n = len(decided)
            if n == 0:
                continue
            modified = [r for r in decided if r["human_decision"] == "Modified"]
            evaluated = [r for r in recs if r["evaluation_status"] == "Evaluated"]
            positive = [r for r in evaluated if r["learning_signal"] == "Positive"]
            negative = [r for r in evaluated if r["learning_signal"] == "Negative"]

            if len(modified) >= 2 and (len(modified) / n) >= MODIFICATION_RATE_THRESHOLD:
                mod_texts = [r["human_modification_text"] for r in modified if r["human_modification_text"]]
                common_note = ""
                if len(mod_texts) >= 2 and len(set(t.split(".")[0] for t in mod_texts)) == 1:
                    common_note = f" In every case the modification was the same: \"{mod_texts[0]}\""
                signals.append({
                    "signal_type": "Modification", "scope_type": "Hazard Category", "scope_label": cat,
                    "sample_size": n, "related_recommendation_ids": [r["recommendation_id"] for r in modified],
                    "observation": {"type": "STATISTICAL_PATTERN",
                        "statement": f"Repeated human modification detected: {len(modified)} of {n} decided "
                                     f"'{cat}' recommendations were modified by a human reviewer "
                                     f"({round(len(modified)/n*100)}%).{common_note}"},
                    "learning_opportunity": {"type": "RECOMMENDATION",
                        "statement": "Potential learning opportunity: consider adjusting the recommendation "
                                     "template for similar operational conditions. This is a candidate for "
                                     "human/engineering review, not an automatic change — see Learning Candidates."},
                    "confidence": confidence_for(n),
                })

            if len(evaluated) >= 2 and (len(positive) / len(evaluated)) >= POSITIVE_RATE_THRESHOLD:
                signals.append({
                    "signal_type": "Positive", "scope_type": "Hazard Category", "scope_label": cat,
                    "sample_size": len(evaluated), "related_recommendation_ids": [r["recommendation_id"] for r in positive],
                    "observation": {"type": "STATISTICAL_PATTERN",
                        "statement": f"{len(positive)} of {len(evaluated)} evaluated '{cat}' recommendations "
                                     f"showed a positive observed outcome following implementation "
                                     f"({round(len(positive)/len(evaluated)*100)}%)."},
                    "learning_opportunity": {"type": "RECOMMENDATION",
                        "statement": "Recommended next step: continue applying this recommendation pattern and "
                                     "keep monitoring outcomes; observed association, not a guarantee of future effect."},
                    "confidence": confidence_for(len(evaluated)),
                })

            rejected = [r for r in decided if r["human_decision"] == "Rejected"]
            if len(evaluated) >= 2 and (len(negative) / len(evaluated)) >= NEGATIVE_RATE_THRESHOLD:
                signals.append({
                    "signal_type": "Negative", "scope_type": "Hazard Category", "scope_label": cat,
                    "sample_size": len(evaluated), "related_recommendation_ids": [r["recommendation_id"] for r in negative],
                    "observation": {"type": "STATISTICAL_PATTERN",
                        "statement": f"{len(negative)} of {len(evaluated)} evaluated '{cat}' recommendations "
                                     f"showed a negative or no observed outcome following implementation "
                                     f"({round(len(negative)/len(evaluated)*100)}%)."},
                    "learning_opportunity": {"type": "RECOMMENDATION",
                        "statement": "Recommended next step: EHS leadership should review this recommendation "
                                     "pattern before continuing to rely on it in similar future cases."},
                    "confidence": confidence_for(len(evaluated)),
                })
            elif n >= 3 and (len(rejected) / n) >= NEGATIVE_RATE_THRESHOLD:
                signals.append({
                    "signal_type": "Negative", "scope_type": "Hazard Category", "scope_label": cat,
                    "sample_size": n, "related_recommendation_ids": [r["recommendation_id"] for r in rejected],
                    "observation": {"type": "STATISTICAL_PATTERN",
                        "statement": f"{len(rejected)} of {n} decided '{cat}' recommendations were rejected "
                                     f"by a human reviewer ({round(len(rejected)/n*100)}%)."},
                    "learning_opportunity": {"type": "RECOMMENDATION",
                        "statement": "Recommended next step: review whether this recommendation template fits "
                                     "the actual operating conditions for this hazard category."},
                    "confidence": confidence_for(n),
                })

            if n >= 2 and len(evaluated) < 2:
                signals.append({
                    "signal_type": "Insufficient Data", "scope_type": "Hazard Category", "scope_label": cat,
                    "sample_size": n, "related_recommendation_ids": [r["recommendation_id"] for r in decided],
                    "observation": {"type": "OBSERVED_FACT",
                        "statement": f"{n} '{cat}' recommendations have been decided, but fewer than 2 have "
                                     f"measurable outcome data yet. Insufficient evidence for learning."},
                    "learning_opportunity": None,
                    "confidence": "Low",
                })

            # Conflicting: per-facility outcome comparison (section 13)
            by_fac = defaultdict(list)
            for r in evaluated:
                by_fac[r["facility_id"]].append(r)
            fac_rates = {}
            for fid, frecs in by_fac.items():
                if len(frecs) >= 2:
                    pos = sum(1 for r in frecs if r["learning_signal"] == "Positive")
                    fac_rates[fid] = (pos / len(frecs), len(frecs))
            if len(fac_rates) >= 2:
                ordered = sorted(fac_rates.items(), key=lambda kv: -kv[1][0])
                best_fid, (best_rate, best_n) = ordered[0]
                worst_fid, (worst_rate, worst_n) = ordered[-1]
                if best_rate - worst_rate >= CONFLICT_RATE_GAP:
                    signals.append({
                        "signal_type": "Conflicting", "scope_type": "Hazard Category", "scope_label": cat,
                        "sample_size": best_n + worst_n,
                        "related_recommendation_ids": [r["recommendation_id"] for r in by_fac[best_fid] + by_fac[worst_fid]],
                        "observation": {"type": "STATISTICAL_PATTERN",
                            "statement": f"Different facilities show different outcomes for '{cat}' recommendations: "
                                         f"{self.fac_name(best_fid)} shows a positive outcome in {round(best_rate*100)}% "
                                         f"of {best_n} evaluated case(s), vs. {round(worst_rate*100)}% of {worst_n} at "
                                         f"{self.fac_name(worst_fid)}."},
                        "learning_opportunity": {"type": "AI_HYPOTHESIS",
                            "statement": f"Evidence from {self.fac_name(best_fid)} suggests this control may be "
                                         f"effective. {self.fac_name(worst_fid)} has different operating conditions; "
                                         f"local validation is recommended rather than transferring the recommendation "
                                         f"as-is."},
                        "confidence": confidence_for(min(best_n, worst_n)),
                    })
        signals.sort(key=lambda s: (s["signal_type"] != "Negative", s["signal_type"] != "Conflicting",
                                     -s["sample_size"]))
        return signals

    # -------------------------------------------------------------------
    # SECTION 6 — Learning from human expertise: repeated identical
    # rejection reasoning for the same hazard category.
    # -------------------------------------------------------------------
    def expert_feedback_patterns(self):
        by_key = defaultdict(list)
        for r in self.recommendations:
            if r["human_decision"] in ("Rejected", "Modified") and r["decision_reason"]:
                by_key[(r["hazard_category"], r["decision_reason"])].append(r)
        patterns = []
        for (cat, reason), recs in by_key.items():
            if len(recs) >= 2:
                patterns.append({
                    "hazard_category": cat, "decision_reason": reason,
                    "occurrences": len(recs),
                    "related_recommendation_ids": [r["recommendation_id"] for r in recs],
                    "observation": {"type": "STATISTICAL_PATTERN",
                        "statement": f"Expert feedback pattern detected: {len(recs)} '{cat}' recommendations "
                                     f"received the same reviewer reasoning: \"{reason}\""},
                    "flag": {"type": "RECOMMENDATION",
                        "statement": "Flagged for evaluation — recurring identical expert feedback is a stronger "
                                     "signal than any single rejection and warrants review of the underlying "
                                     "recommendation template."},
                    "confidence": confidence_for(len(recs)),
                })
        patterns.sort(key=lambda p: -p["occurrences"])
        return patterns

    # -------------------------------------------------------------------
    # SECTION 13 — Multi-facility learning (broader view than the
    # Conflicting signal above: shows every hazard category with enough
    # cross-facility outcome data, not just the ones that conflict).
    # -------------------------------------------------------------------
    def multi_facility_learning(self):
        by_cat = defaultdict(list)
        for r in self.recommendations:
            if r["evaluation_status"] == "Evaluated":
                by_cat[r["hazard_category"]].append(r)
        out = []
        for cat, recs in by_cat.items():
            by_fac = defaultdict(list)
            for r in recs:
                by_fac[r["facility_id"]].append(r)
            if len(by_fac) < 2:
                continue
            fac_summaries = []
            for fid, frecs in by_fac.items():
                pos = sum(1 for r in frecs if r["learning_signal"] == "Positive")
                fac_summaries.append({
                    "facility_id": fid, "facility": self.fac_name(fid), "n": len(frecs),
                    "positive_rate": round(pos / len(frecs), 2) if frecs else None,
                })
            fac_summaries.sort(key=lambda s: -(s["positive_rate"] or 0))
            rates = [s["positive_rate"] for s in fac_summaries if s["n"] >= 2]
            spread = (max(rates) - min(rates)) if len(rates) >= 2 else None
            if spread is not None and spread >= CONFLICT_RATE_GAP:
                note = (f"Evidence from {fac_summaries[0]['facility']} suggests this recommendation pattern may be "
                        f"effective. {fac_summaries[-1]['facility']} has different operating conditions and a lower "
                        f"observed positive-outcome rate; local validation is recommended rather than assuming the "
                        f"same result will transfer.")
            elif spread is not None:
                note = ("Observed effectiveness is broadly consistent across facilities for this recommendation "
                        "pattern so far, though sample sizes remain small.")
            else:
                note = "Not enough evaluated cases per facility yet to compare."
            out.append({"hazard_category": cat, "facilities": fac_summaries, "note": note})
        out.sort(key=lambda o: -len(o["facilities"]))
        return out

    # -------------------------------------------------------------------
    # SECTION 12 — context-aware note for a future recommendation. Only
    # returns text when a REAL Active/Deployed candidate exists for this
    # exact hazard category; otherwise returns None (no note is invented).
    # -------------------------------------------------------------------
    def context_aware_note(self, hazard_category):
        for c in self.learning_candidates:
            if c["status"] != "Deployed":
                continue
            cand_version = self.version_by_id.get(c["candidate_version_id"])
            norm_cat = "".join(hazard_category.lower().split())
            norm_desc = "".join(c["description"].lower().split())
            if cand_version and norm_cat in norm_desc:
                return {
                    "note": c["proposed_change"],
                    "source": f"Historical organizational learning — {c['candidate_id']}, deployed "
                              f"{cand_version.get('activated_date')} (see Learning Candidates).",
                    "candidate_id": c["candidate_id"],
                }
        return None

    # -------------------------------------------------------------------
    # SECTION 11 — Learning Graph for one recommendation: Incident ->
    # Recommendation -> Human Decision -> Action -> Outcome -> Learning
    # Signal. Pure lookup/join over already-loaded rows.
    # -------------------------------------------------------------------
    def learning_graph_for(self, recommendation_id):
        r = self.rec_by_id.get(recommendation_id)
        if not r:
            return None
        inc = self.incident_by_id.get(r["incident_id"]) if r["incident_id"] else None
        act = self.action_by_id.get(r["assigned_action_id"]) if r["assigned_action_id"] else None
        nodes = []
        if inc:
            nodes.append({"step": "Incident", "label": f"{inc['incident_id']} — {inc['incident_type']}",
                           "detail": inc["description"][:140]})
        else:
            nodes.append({"step": "Emerging Risk", "label": r.get("risk_signal_id") or "Risk signal",
                           "detail": "Recommendation originated from a cross-incident emerging-risk cluster, not a single incident."})
        nodes.append({"step": "AI Recommendation", "label": r["recommendation_type"],
                       "detail": r["recommendation_text"]})
        nodes.append({"step": "Human Decision", "label": r["human_decision"],
                       "detail": r["human_modification_text"] or r["decision_reason"] or "No reason recorded."})
        if act:
            nodes.append({"step": "Action", "label": f"{act['action_id']} — {act['status']}",
                           "detail": act["description"]})
        else:
            nodes.append({"step": "Action", "label": "No action assigned",
                           "detail": "This recommendation was not approved, so no corrective action was created."})
        if r["evaluation_status"] == "Evaluated":
            nodes.append({"step": "Outcome", "label": r["effectiveness_rating"], "detail": r["outcome_measurement"]})
        else:
            nodes.append({"step": "Outcome", "label": r["evaluation_status"],
                           "detail": r["outcome_measurement"] or "No outcome measured yet."})
        nodes.append({"step": "Learning Signal", "label": r["learning_signal"] or "Not Yet Determined",
                       "detail": "Per-recommendation signal; see Continuous Learning for cross-recommendation patterns."})
        return nodes

    # -------------------------------------------------------------------
    # Versions / candidates / evaluations — thin passthroughs with names
    # resolved, for display.
    # -------------------------------------------------------------------
    def versions(self):
        return sorted(self.ai_versions, key=lambda v: (v["version_type"], v["created_date"]))

    def candidates_with_evaluations(self):
        evals_by_candidate = defaultdict(list)
        for e in self.learning_evaluations:
            evals_by_candidate[e["candidate_id"]].append(e)
        out = []
        for c in self.learning_candidates:
            c = dict(c)
            c["source_recommendation_ids"] = json.loads(c["source_recommendation_ids"])
            c["reviewed_by"] = self.emp_name(c["reviewed_by_employee_id"])
            c["baseline_version"] = self.version_by_id.get(c["baseline_version_id"])
            c["candidate_version"] = self.version_by_id.get(c["candidate_version_id"])
            c["evaluations"] = evals_by_candidate.get(c["candidate_id"], [])
            for e in c["evaluations"]:
                e["thresholds"] = json.loads(e["thresholds_json"])
            out.append(c)
        return out

    def answer_all(self):
        return {
            "overview": self.learning_overview(),
            "performance_by_pattern": self.performance_by_pattern(),
            "signals": self.detect_signals(),
            "expert_feedback_patterns": self.expert_feedback_patterns(),
            "multi_facility_learning": self.multi_facility_learning(),
            "versions": self.versions(),
            "candidates": self.candidates_with_evaluations(),
        }
