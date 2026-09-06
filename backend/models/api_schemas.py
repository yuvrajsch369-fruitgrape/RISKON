"""Request bodies for the CRUD-ish endpoints — kept intentionally small,
matching the fields the frontend's existing forms/handlers already collect
(see frontend/app.template.html's submitIncident(), handleApproval(),
handleRecommendationFeedback()) rather than a generic, larger schema."""
from typing import Literal

from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1, max_length=5000)
    facility_id: str
    location: str | None = None
    severity_reported: Literal["Low", "Medium", "High", "Critical"] = "Medium"
    date_occurred: str | None = None  # ISO date; defaults to today server-side if omitted
    reporter_employee_id: str | None = None


class IncidentReviewDecision(BaseModel):
    decision: Literal["Approved", "Rejected"]
    reviewer_employee_id: str | None = None
    comment: str | None = None


class RecommendationDecision(BaseModel):
    decision: Literal["Approved", "Rejected", "Modified", "Request More Information"]
    reason: str | None = None
    modification_text: str | None = None
    decided_by_employee_id: str | None = None


class ActionComplete(BaseModel):
    completion_date: str | None = None  # ISO date; defaults to today server-side if omitted
    verification_method: str | None = None


class UserSignup(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    occupation: str = Field(..., min_length=1, max_length=120)
    post: str = Field(..., min_length=1, max_length=120)
