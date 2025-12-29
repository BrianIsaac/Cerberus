"""Request and response schemas for Dashboard Enhancement Agent."""

from pydantic import BaseModel, Field


class EnhanceRequest(BaseModel):
    """Request to enhance dashboard for an agent."""

    service: str = Field(..., description="Service name of the agent")
    agent_dir: str = Field(..., description="Path to agent source directory")
    dashboard_id: str | None = Field(
        None,
        description="Dashboard ID to update (uses default if not provided)",
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
