"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ReviewOutcome(str, Enum):
    """Possible outcomes for human review."""

    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class Severity(str, Enum):
    """Incident severity levels."""

    SEV1 = "SEV-1"
    SEV2 = "SEV-2"
    SEV3 = "SEV-3"
    SEV4 = "SEV-4"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    service: str


class AskRequest(BaseModel):
    """Free-form triage question request."""

    question: str = Field(..., min_length=10, max_length=2000)
    service: Optional[str] = None
    time_window: Optional[str] = Field(default="last_15m")
    severity: Optional[str] = None


class Hypothesis(BaseModel):
    """A ranked hypothesis with evidence."""

    rank: int
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str]
    query_links: list[str]


class AskResponse(BaseModel):
    """Response to a triage question."""

    trace_id: str
    summary: str
    hypotheses: list[Hypothesis]
    next_steps: list[str]
    requires_approval: bool
    confidence: float
    step_count: int
    tool_calls: int


class TriageRequest(BaseModel):
    """Structured triage payload request."""

    service: str
    environment: str = Field(default="production")
    time_window: str = Field(default="last_15m")
    severity: Optional[Severity] = None
    symptoms: Optional[str] = None
    alert_id: Optional[str] = None


class TriageResponse(BaseModel):
    """Response to a structured triage request."""

    trace_id: str
    summary: str
    hypotheses: list[Hypothesis]
    next_steps: list[str]
    requires_approval: bool
    proposed_incident: Optional[dict] = None
    confidence: float
    step_count: int
    tool_calls: int


class ReviewRequest(BaseModel):
    """Human review outcome request."""

    trace_id: str
    outcome: ReviewOutcome
    modifications: Optional[str] = None
    reviewer_notes: Optional[str] = None


class ReviewResponse(BaseModel):
    """Response after recording review outcome."""

    trace_id: str
    outcome: ReviewOutcome
    incident_id: Optional[str] = None
    case_id: Optional[str] = None
    recorded_at: datetime
