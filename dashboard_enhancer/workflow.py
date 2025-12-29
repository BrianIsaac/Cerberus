"""Enhancement workflow for Dashboard Enhancement Agent."""

from pathlib import Path
from typing import Any

import structlog
from ddtrace.llmobs.decorators import workflow

from shared.governance import BudgetTracker

from .analyzer import AgentProfile, CodeAnalyzer, TelemetryDiscoverer
from .designer import GeminiWidgetDesigner
from .mcp_client import DashboardMCPClient
from .models import AgentProfileInput, WidgetPreview

logger = structlog.get_logger()


@workflow
async def enhance_dashboard(
    service: str,
    agent_source: Path | str | None,
    dashboard_id: str,
    budget_tracker: BudgetTracker,
    agent_profile_input: AgentProfileInput | None = None,
) -> dict[str, Any]:
    """Run the full enhancement workflow.

    Args:
        service: Service name of the agent.
        agent_source: Path to local directory or GitHub URL (optional).
        dashboard_id: Dashboard ID to update.
        budget_tracker: Budget tracker for governance.
        agent_profile_input: Optional agent profile when code analysis not possible.

    Returns:
        Enhancement result with widgets and metadata.
    """
    from .config import settings

    logger.info(
        "workflow_started",
        service=service,
        agent_source=str(agent_source) if agent_source else None,
        has_profile_input=agent_profile_input is not None,
    )

    # Step 1: Get agent profile (from code analysis or input)
    budget_tracker.increment_step()

    # Determine if we can do code analysis
    can_analyse_code = False
    if agent_source:
        if isinstance(agent_source, str) and agent_source.startswith("https://github.com"):
            can_analyse_code = True
        elif isinstance(agent_source, Path) and agent_source.exists():
            can_analyse_code = True

    if can_analyse_code and agent_source:
        # Analyse agent code (local or GitHub)
        analyzer = CodeAnalyzer(agent_source, github_token=settings.github_token)
        agent_profile = analyzer.analyze()
        # Override service name with the one from request (more reliable)
        agent_profile.service_name = service
        logger.info(
            "code_analysis_complete",
            domain=agent_profile.domain,
            agent_type=agent_profile.agent_type,
            source_type="github" if isinstance(agent_source, str) else "local",
        )
    elif agent_profile_input:
        # Use provided profile
        agent_profile = AgentProfile(
            service_name=service,
            domain=agent_profile_input.domain,
            agent_type=agent_profile_input.agent_type,
            llm_provider=agent_profile_input.llm_provider,
            framework=agent_profile_input.framework,
            description=agent_profile_input.description or f"{service} agent",
        )
        logger.info(
            "using_provided_profile",
            domain=agent_profile.domain,
            agent_type=agent_profile.agent_type,
        )
    else:
        raise ValueError("Either agent_dir or agent_profile_input must be provided")

    # Step 2: Discover existing telemetry
    budget_tracker.increment_step()
    discoverer = TelemetryDiscoverer(service)
    telemetry_profile = await discoverer.discover()

    logger.info(
        "telemetry_discovery_complete",
        metrics_count=len(telemetry_profile.metrics_found),
    )

    # Step 3: Design widgets using Gemini
    budget_tracker.increment_step()
    budget_tracker.increment_model_call()
    designer = GeminiWidgetDesigner()
    widgets = await designer.design_widgets(agent_profile, telemetry_profile)

    logger.info("widget_design_complete", widgets_count=len(widgets))

    # Convert to preview format
    widget_previews = [
        WidgetPreview(
            title=w.get("title", "Untitled"),
            type=w.get("type", "timeseries"),
            query=w.get("query", ""),
            description=w.get("description"),
        )
        for w in widgets
    ]

    # Generate group title
    group_title = f"{agent_profile.domain.title()} Analytics"

    return {
        "agent_profile": {
            "service_name": agent_profile.service_name,
            "agent_type": agent_profile.agent_type,
            "domain": agent_profile.domain,
            "description": agent_profile.description,
            "llm_provider": agent_profile.llm_provider,
            "framework": agent_profile.framework,
        },
        "telemetry_profile": {
            "metrics_found": telemetry_profile.metrics_found,
            "trace_operations": telemetry_profile.trace_operations,
            "has_llm_obs": telemetry_profile.has_llm_obs,
            "has_custom_metrics": telemetry_profile.has_custom_metrics,
        },
        "widgets": [w.model_dump() for w in widget_previews],
        "group_title": group_title,
    }


async def apply_enhancement(
    widgets: list[dict],
    group_title: str,
    service: str,
    dashboard_id: str,
) -> dict[str, Any]:
    """Apply approved enhancement to dashboard.

    Args:
        widgets: Widget definitions to add.
        group_title: Title for the widget group.
        service: Service name.
        dashboard_id: Dashboard ID to update.

    Returns:
        Result with dashboard URL and group ID.
    """
    logger.info(
        "applying_enhancement",
        widgets_count=len(widgets),
        group_title=group_title,
    )

    # Convert widget previews to full widget definitions
    full_widgets = []
    for i, w in enumerate(widgets):
        widget_def = {
            "id": 1000 + i,
            "definition": {
                "type": w.get("type", "timeseries"),
                "title": w.get("title", "Untitled"),
                "requests": [
                    {
                        "q": w.get("query", ""),
                    }
                ],
            },
        }
        # Add display_type for timeseries widgets
        if w.get("type") == "timeseries":
            widget_def["definition"]["requests"][0]["display_type"] = "line"

        full_widgets.append(widget_def)

    # Call MCP server to update dashboard
    async with DashboardMCPClient() as client:
        result = await client.add_widget_group(
            dashboard_id=dashboard_id,
            group_title=group_title,
            widgets=full_widgets,
            service=service,
        )

    logger.info(
        "enhancement_applied",
        dashboard_id=result.get("id"),
        group_id=result.get("group_id"),
    )

    return {
        "dashboard_id": result.get("id"),
        "group_id": result.get("group_id"),
        "widgets_added": len(widgets),
        "dashboard_url": result.get("url"),
    }
