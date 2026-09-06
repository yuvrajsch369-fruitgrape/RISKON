#!/usr/bin/env python3
"""
Runs the RISKON Risk Intelligence Engine against database/riskon.db, writes
risk_intelligence/output.json (full machine-readable output: all emerging
risks + all 10 Q&A answers), and prints a human-readable demonstration to
stdout in the format requested in the spec.

Run: python3 risk_intelligence/run.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import RiskIntelligenceEngine  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = Path(__file__).resolve().parent / "output.json"


def fmt_emerging_risk_block(r):
    """Formats one emerging risk in the exact block style given in the spec:
    EMERGING RISK: / SIGNAL: / EVIDENCE: / POSSIBLE SYSTEMIC ISSUE: / RECOMMENDED NEXT STEP:
    """
    lines = []
    lines.append("EMERGING RISK:")
    lines.append(r["risk_name"])
    lines.append("")
    lines.append("FACILITY:")
    lines.append(r["facility"] if r["facility"] != "Multiple" else "Multiple (" + ", ".join(r["facilities"]) + ")")
    lines.append("")
    lines.append("RISK SIGNAL SCORE:")
    lines.append(f"{r['risk_signal_score']} / 100  ({r['risk_band']})  -- confidence: {r['confidence']}")
    lines.append("")
    lines.append("SIGNAL:")
    lines.append(r["signal"])
    lines.append("")
    lines.append("EVIDENCE:")
    for ev in r["evidence"]:
        lines.append(f"* [{ev['type']}] {ev['statement']}")
    lines.append("")
    lines.append("POSSIBLE SYSTEMIC ISSUE:")
    lines.append("[AI_HYPOTHESIS] " + r["possible_systemic_issue"]["statement"])
    lines.append("")
    lines.append("RECOMMENDED NEXT STEP:")
    lines.append("[RECOMMENDATION] " + r["recommended_investigation"]["statement"])
    lines.append("")
    lines.append(f"HUMAN REVIEW STATUS: {r['human_review_status']}")
    return "\n".join(lines)


def main():
    engine = RiskIntelligenceEngine()

    all_risks = engine.all_emerging_risks()
    top5 = all_risks[:5]
    answers = engine.answer_all()

    output = {
        "generated_at": "2026-09-03",
        "source": "database/riskon.db (Rex Industrial Manufacturing synthetic dataset)",
        "methodology_doc": "docs/risk-intelligence-engine.md",
        "emerging_risks_all": all_risks,
        "emerging_risks_top5": top5,
        "qa": answers,
    }
    OUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("=" * 78)
    print("RISKON RISK INTELLIGENCE ENGINE -- DEMONSTRATION")
    print("Source: database/riskon.db (Rex Industrial Manufacturing, synthetic)")
    print("=" * 78)
    print()
    print(f"Computed {len(all_risks)} candidate risk clusters from {len(engine.incidents)} incidents.")
    print()

    print("-" * 78)
    print("TOP 5 EMERGING RISKS (Q1)")
    print("-" * 78)
    for r in top5:
        print()
        print(fmt_emerging_risk_block(r))
        print()
        print("-" * 78)

    # The spec's own worked example is Forklift/Pedestrian Interaction -- show
    # it explicitly regardless of its rank in the top 5, for direct comparison
    # against the requested output format.
    forklift = next((r for r in all_risks if r["risk_id"] not in [t["risk_id"] for t in top5]
                      and r["risk_name"] == "Forklift/Pedestrian Interaction"), None)
    if forklift:
        print()
        print("SPEC WORKED EXAMPLE (shown even though not in the top 5 by score):")
        print()
        print(fmt_emerging_risk_block(forklift))
        print()
        print("-" * 78)

    for key in ["q2_increasing_risks", "q3_recurring_risks", "q4_unusual_facility_patterns",
                "q5_repeatedly_overdue_actions", "q6_ineffective_controls", "q7_cross_facility_hazards",
                "q8_systemic_problem_incidents", "q10_recommended_investigations"]:
        block = answers[key]
        print()
        print(block["question"])
        for f in block["findings"]:
            print(f"  [{f['type']}] {f['statement']}")

    print()
    print("=" * 78)
    print(f"Full machine-readable output written to {OUT_PATH.relative_to(ROOT)}")
    print("=" * 78)


if __name__ == "__main__":
    main()
