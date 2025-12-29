"""Enhancement workflow for Dashboard Enhancement Agent."""

from pathlib import Path
from typing import Any

import structlog
from ddtrace.llmobs.decorators import workflow

from shared.governance import BudgetTracker

from .analyzer import CodeAnalyzer, TelemetryDiscoverer
from .designer import GeminiWidgetDesigner
from .mcp_client import DashboardMCPClient
from .models import WidgetPreview

logger = structlog.get_logger()


@workflow
async def enhance_dashboard(
    service: str,
    agent_dir: Path,
    dashboard_id: str,
    budget_tracker: BudgetTracker,
) -> dict[str, Any]:
    """Run the full enhancement workflow.

    Args:
        service: Service name of the agent.
        agent_dir: Path to agent source directory.
        dashboard_id: Dashboard ID to update.
        budget_tracker: Budget tracker for governance.

    Returns:
        Enhancement result with widgets and metadata.
    """
    logger.info("workflow_started", service=service, agent_dir=str(agent_dir))

    # Step 1: Analyse agent code
    budget_tracker.increment_step()
    analyzer = CodeAnalyzer(agent_dir)
    agent_profile = analyzer.analyze()

    logger.info(
        "code_analysis_complete",
        domain=agent_profile.domain,
        agent_type=agent_profile.agent_type,
    )

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
