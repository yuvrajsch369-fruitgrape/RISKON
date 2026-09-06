# Rex Industrial Manufacturing — Risk Assessment

**Risk Assessment ID:** RA-0003
**Hazard:** HAZ-0003 — Machine Guarding Failure ("Punch press point-of-operation guarding is prone to
being propped open during jam-clearing.")
**Facility:** Rex North Plant (FAC-001) — attributed as the hazard's primary site by incident history
**Assessment Date:** August 21, 2026
**Assessed By:** Rebecca Flores, EHS Coordinator
**Status:** Current

## Scoring (RISKON prototype methodology — see docs/database-design.md §6)

| Factor | Value | Source |
|---|---|---|
| Likelihood | 4 / 5 | Derived from recurrence tier |
| Severity | 4 / 5 | Category severity tier for Machine Guarding Failure |
| **Raw Score** | **16** | likelihood × severity |
| Control Effectiveness Rating | Ineffective | Most recent assessment of CTL-0001 as of this date |
| Control Effectiveness Factor | 1.00 | No credit — ineffective control |
| Recurrence (trailing 12mo) | 5 incidents | Real count from `incidents` where hazard_id = HAZ-0003 |
| Recurrence Factor | 1.30 | 3+ incidents tier |
| Trend | Decreasing | 6-month incident count vs. prior 6 months |
| Trend Factor | 0.90 | |
| **Adjusted Score** | **18.7** | 16 × 1.00 × 1.30 × 0.90, clipped to [0,25] |
| **Risk Level** | **High** | 12-19 |

**Methodology note (verbatim from record):** *"raw_score = likelihood(4) x severity(4) = 16.
control_effectiveness_factor=1.0 (rating: Ineffective). recurrence_factor=1.3 (5 incidents trailing
12mo). trend_factor=0.9 (trend: Decreasing). adjusted_score = 16 x 1.0 x 1.3 x 0.9 = 18.7, clipped to
[0,25]."*

## Interpretation
Despite a *decreasing* trend (fewer incidents in the most recent 6 months than the 6 months before), the
risk sits at the top of the High band — one point below Critical — because (a) the control meant to
prevent it has never sustained an "Effective" rating across five separate assessments, and (b) five
incidents in twelve months is a high absolute recurrence rate for a hazard with amputation/crush-injury
potential. **A decreasing trend does not by itself indicate the risk is resolved** — this row is a
demonstration case for why the prototype scoring model weights recurrence and control effectiveness
independently of trend direction, rather than letting a short-term dip override the underlying pattern.

## Recommendation
Register entry RISK-0006 remains **Open**. See corrective actions ACT-0001 through ACT-0004, all targeting
control CTL-0001, both ACT-0001 (North Plant) and ACT-0004 (Central Plant) currently Overdue with 2
reschedules each — the control fix itself has been slipping at both facilities, consistent with the
control never reaching a sustained Effective rating.

---
*Fictional record for the RISKON prototype. Not a real risk assessment; the scoring model itself is a
prototype methodology, not a certified industrial risk standard — see docs/database-design.md §6.*
