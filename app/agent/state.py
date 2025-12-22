"""LangGraph state schema for the ops assistant workflow."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class WorkflowStage(str, Enum):
    """Current stage of the workflow."""

    INTAKE = "intake"
    COLLECT = "collect"
    SYNTHESIS = "synthesis"
    APPROVAL = "approval"
    WRITEBACK = "writeback"
    COMPLETE = "complete"
    ESCALATED = "escalated"


class IntentType(str, Enum):
    """Classified intent of the user request."""

    READ_ONLY = "read_only"
    WRITE_INTENT = "write_intent"
    CLARIFICATION_NEEDED = "clarification_needed"


class Hypothesis(BaseModel):
    """A ranked hypothesis with evidence."""

    rank: int
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    query_links: list[str] = Field(default_factory=list)


class CollectedEvidence(BaseModel):
    """Evidence collected from Datadog APIs."""

    metrics: dict[str, Any] | None = None
    logs: dict[str, Any] | None = None
    traces: dict[str, Any] | None = None
    collection_errors: list[str] = Field(default_factory=list)


class ProposedAction(BaseModel):
    """Proposed write action requiring approval."""

    action_type: Literal["incident", "case"]
    title: str
    description: str
    severity: str
    evidence_links: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


def merge_messages(left: list[str], right: list[str]) -> list[str]:
    """Merge message lists (append only)."""
    return left + right


class AgentState(TypedDict):
    """State schema for the ops assistant LangGraph workflow.

    This TypedDict defines all state that flows through the graph.
    Budget tracking is managed through step_count, tool_calls, model_calls fields.
    """

    # Input
    user_query: str
    service: str | None
    environment: str
    time_window: str

    # Workflow tracking
    stage: WorkflowStage
    started_at: str
    trace_id: str | None

    # Budget tracking
    step_count: int
    tool_calls: int
    model_calls: int

    # Intake outputs
    intent: IntentType | None
    extracted_service: str | None
    extracted_time_window: str | None
    intake_confidence: float
    clarification_attempts: int

    # Collection outputs
    evidence: CollectedEvidence | None

    # Synthesis outputs
    summary: str | None
    hypotheses: list[Hypothesis]
    next_steps: list[str]
    synthesis_confidence: float
    synthesis_retry_count: int

    # Approval gate
    requires_approval: bool
    proposed_action: ProposedAction | None
    approval_status: Literal["pending", "approved", "rejected", "skipped"] | None
    approval_decision: str | None

    # Write-back outputs
    incident_id: str | None
    case_id: str | None

    # Final outputs
    final_response: dict[str, Any] | None
    error: str | None
    escalation_reason: str | None

    # Messages for debugging
    messages: Annotated[list[str], merge_messages]


def create_initial_state(
    user_query: str,
    service: str | None = None,
    environment: str = "production",
    time_window: str = "last_15m",
    trace_id: str | None = None,
) -> AgentState:
    """Create initial state for a new workflow run.

    Args:
        user_query: The user's triage question
        service: Optional service name (if known)
        environment: Target environment
        time_window: Time window for queries
        trace_id: Optional trace ID for correlation

    Returns:
        Initialised AgentState
    """
    return AgentState(
        user_query=user_query,
        service=service,
        environment=environment,
        time_window=time_window,
        stage=WorkflowStage.INTAKE,
        started_at=datetime.now().isoformat(),
        trace_id=trace_id,
        step_count=0,
        tool_calls=0,
        model_calls=0,
        intent=None,
        extracted_service=None,
        extracted_time_window=None,
        intake_confidence=0.0,
        clarification_attempts=0,
        evidence=None,
        summary=None,
        hypotheses=[],
        next_steps=[],
        synthesis_confidence=0.0,
        synthesis_retry_count=0,
        requires_approval=False,
        proposed_action=None,
        approval_status=None,
        approval_decision=None,
        incident_id=None,
        case_id=None,
        final_response=None,
        error=None,
        escalation_reason=None,
        messages=[],
    )
