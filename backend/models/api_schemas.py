"""Request bodies for the CRUD-ish endpoints — kept intentionally small,
matching the fields the frontend's existing forms/handlers already collect
(see frontend/app.template.html's submitIncident(), handleApproval(),
handleRecommendationFeedback()) rather than a generic, larger schema."""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Hand-rolled rather than pydantic's EmailStr, to avoid adding the
# email-validator dependency for one field -- not RFC-exhaustive, just
# enough to catch "clearly not an email" input before it reaches the DB.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    email: str = Field(..., min_length=3, max_length=254)
    # Length over composition rules, per current NIST 800-63B guidance --
    # no forced upper/lower/digit/symbol classes.
    password: str = Field(..., min_length=12, max_length=72)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v


class UserLogin(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        return v.strip().lower()
