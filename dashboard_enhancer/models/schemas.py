"""Request and response schemas for Dashboard Enhancement Agent."""

from pydantic import BaseModel, Field


class AgentProfileInput(BaseModel):
    """Optional agent profile input when code analysis is not possible."""

    domain: str = Field(..., description="Agent domain (e.g., sas, ops, analytics)")
    agent_type: str = Field(
        default="assistant",
        description="Agent type (e.g., assistant, generator, triage)",
    )
    llm_provider: str = Field(default="gemini", description="LLM provider used")
    framework: str = Field(default="langgraph", description="Agent framework used")
    description: str | None = Field(None, description="Brief agent description")


class EnhanceRequest(BaseModel):
    """Request to enhance dashboard for an agent."""

    service: str = Field(..., description="Service name of the agent")
    agent_dir: str | None = Field(
        None,
        description="Path to agent source directory (optional if agent_profile provided)",
    )
    github_url: str | None = Field(
        None,
        description="GitHub URL to agent source (e.g., https://github.com/owner/repo/tree/main/agent_dir)",
    )
    agent_profile: AgentProfileInput | None = Field(
        None,
        description="Agent profile (required if agent_dir and github_url not available)",
    )
    dashboard_id: str | None = Field(
        None,
        description="Dashboard ID to update (uses default if not provided)",
    )
    run_evaluations: bool = Field(
        True,
        description="Whether to run evaluations on existing spans",
    )
    provision_metrics: bool = Field(
        True,
        description="Whether to provision span-based metrics",
    )


class WidgetPreview(BaseModel):
    """Preview of a generated widget."""

    title: str
    type: str
    query: str
    description: str | None = None


class EnhanceResponse(BaseModel):
    """Response with enhancement recommendations."""

    trace_id: str
    service: str
    agent_profile: dict
    telemetry_profile: dict
    widgets: list[WidgetPreview]
    group_title: str
    requires_approval: bool = True
    message: str
    llmobs_status: dict = Field(default_factory=dict)
    provisioned_metrics: list[dict] = Field(default_factory=list)
    evaluation_results: dict = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """Request to approve and apply enhancements."""

    trace_id: str
    outcome: str = Field(..., pattern="^(approved|rejected)$")
    modifications: dict | None = None


class ApprovalResponse(BaseModel):
    """Response after applying enhancements."""

    success: bool
    dashboard_id: str | None = None
    group_id: int | None = None
    widgets_added: int = 0
    message: str
    dashboard_url: str | None = None
