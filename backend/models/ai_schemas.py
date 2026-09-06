"""
The structured shape every AI response must satisfy before RISKON stores or
displays it — adapted from the FACT / AI HYPOTHESIS / AI RECOMMENDATION /
HUMAN DECISION distinction used throughout the rest of the app (see
docs/risk-intelligence-engine.md §1 and docs/continuous-learning-engine.md).

`requires_human_review` is typed `Literal[True]` — Pydantic will reject any
response where the model returns `false` for that field, and
`claude_service.py` additionally hard-codes it to True after validation
regardless. This mirrors the JSON-Schema `const` lock already used by the
(unexecuted) 13-stage design in schemas/ai-reasoning-output.schema.json: the
human-in-the-loop requirement is enforced structurally, not left to the
model's discretion.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class IncidentAIAnalysis(BaseModel):
    summary: str = Field(..., min_length=1, max_length=2000,
                          description="A short, neutral summary of the incident and what the context shows.")
    observed_facts: list[str] = Field(default_factory=list,
                                       description="Statements directly supported by the supplied context only — "
                                                    "no inference, no data not present in the context.")
    ai_hypotheses: list[str] = Field(default_factory=list,
                                      description="Hedged candidate explanations ('may indicate', 'could suggest') — "
                                                   "never phrased as an established cause.")
    related_risk_signals: list[str] = Field(default_factory=list,
                                             description="Hedged references to broader patterns this incident may "
                                                          "relate to — never a claim that an accident will happen.")
    evidence: list[str] = Field(default_factory=list,
                                 description="Real incident/hazard/control/action IDs from the supplied context that "
                                              "support the above — never an invented ID.")
    recommendations: list[str] = Field(default_factory=list,
                                        description="Suggested next steps for a human to investigate/review/confirm — "
                                                     "never an instruction to take a unilateral safety action.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertainties: list[str] = Field(default_factory=list,
                                      description="What the context does not establish, stated plainly.")
    requires_human_review: Literal[True] = True

    @field_validator("summary", "observed_facts", "ai_hypotheses", "related_risk_signals",
                      "recommendations", "uncertainties", mode="before")
    @classmethod
    def _no_none(cls, v):
        return v if v is not None else ([] if isinstance(v, list) else "")


class IncidentAnalysisRecord(BaseModel):
    """What GET /api/incidents/{id}/analyses returns — the persisted record,
    not just the model's raw output."""
    analysis_id: str
    incident_id: str
    created_at: str
    model: str
    analysis: IncidentAIAnalysis
    human_review_status: Literal["Pending", "Approved", "Rejected"]
    reviewed_by_employee_id: str | None = None
    reviewed_at: str | None = None
