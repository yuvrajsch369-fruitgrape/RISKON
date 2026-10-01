"""Request bodies for the CRUD-ish endpoints — kept intentionally small,
matching the fields the frontend's existing forms/handlers already collect
(see frontend/app.template.html's submitIncident(), handleApproval(),
handleRecommendationFeedback()) rather than a generic, larger schema."""
import re
from datetime import date as _date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Hand-rolled rather than pydantic's EmailStr, to avoid adding the
# email-validator dependency for one field -- not RFC-exhaustive, just
# enough to catch "clearly not an email" input before it reaches the DB.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_iso_date(v: str | None) -> str | None:
    """Shared by every optional ISO-date field below. Confirmed necessary by
    a real failure: an unvalidated date string ('not-a-date-at-all') stored
    straight into incidents.incident_datetime crashed GET /api/bootstrap for
    EVERY user (export_frontend_data.py's _derive_shift() does
    int(incident_datetime[11:13]) with no guard) -- one bad incident took
    down the whole dashboard. That crash is now also guarded defensively at
    the source, but input this malformed should never reach the database in
    the first place."""
    if v is None:
        return v
    try:
        _date.fromisoformat(v)
    except ValueError:
        raise ValueError("Must be a valid ISO date (YYYY-MM-DD).")
    return v


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1, max_length=5000)
    facility_id: str
    location: str | None = Field(default=None, max_length=300)
    severity_reported: Literal["Low", "Medium", "High", "Critical"] = "Medium"
    date_occurred: str | None = None  # ISO date; defaults to today server-side if omitted
    reporter_employee_id: str | None = None

    @field_validator("date_occurred")
    @classmethod
    def _valid_date_occurred(cls, v: str | None) -> str | None:
        return _validate_iso_date(v)


class IncidentReviewDecision(BaseModel):
    decision: Literal["Approved", "Rejected"]
    reviewer_employee_id: str | None = None
    comment: str | None = Field(default=None, max_length=2000)


class RecommendationDecision(BaseModel):
    decision: Literal["Approved", "Rejected", "Modified", "Request More Information"]
    reason: str | None = Field(default=None, max_length=2000)
    modification_text: str | None = Field(default=None, max_length=2000)
    decided_by_employee_id: str | None = None


class ActionComplete(BaseModel):
    completion_date: str | None = None  # ISO date; defaults to today server-side if omitted
    verification_method: str | None = Field(default=None, max_length=500)

    @field_validator("completion_date")
    @classmethod
    def _valid_completion_date(cls, v: str | None) -> str | None:
        return _validate_iso_date(v)


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
