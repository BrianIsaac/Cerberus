"""Enhanced workflow for Observability Provisioning Agent."""

from pathlib import Path
from typing import Any

import structlog
from ddtrace.llmobs.decorators import workflow

from shared.governance import BudgetTracker

from .analyzer import AgentProfile, CodeAnalyzer, TelemetryDiscoverer
from .designer import GeminiWidgetDesigner
from .evaluator import DomainEvaluator, get_evaluations_for_agent_type
from .mcp_client import DashboardMCPClient
from .models import AgentProfileInput, WidgetPreview
from .provisioner import MetricsProvisioner

logger = structlog.get_logger()


@workflow
async def enhance_dashboard(
    service: str,
    agent_source: Path | str | None,
    dashboard_id: str,
    budget_tracker: BudgetTracker,
    agent_profile_input: AgentProfileInput | None = None,
    run_evaluations: bool = True,
    provision_metrics: bool = True,
) -> dict[str, Any]:
    """Run the full observability provisioning workflow.

    Args:
        service: Service name of the agent.
        agent_source: Path to local directory or GitHub URL (optional).
        dashboard_id: Dashboard ID to update.
        budget_tracker: Budget tracker for governance.
        agent_profile_input: Optional agent profile when code analysis not possible.
        run_evaluations: Whether to run evaluations on existing spans.
        provision_metrics: Whether to provision span-based metrics.

    Returns:
        Enhancement result with widgets, metrics, and evaluations.
    """
    from .config import settings

    logger.info(
        "workflow_started",
        service=service,
        agent_source=str(agent_source) if agent_source else None,
        run_evaluations=run_evaluations,
        provision_metrics=provision_metrics,
    )

    result: dict[str, Any] = {
        "agent_profile": {},
        "telemetry_profile": {},
        "llmobs_status": {},
        "provisioned_metrics": [],
        "evaluation_results": {},
        "widgets": [],
        "group_title": "",
    }

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
            llmobs_enabled=agent_profile.llmobs_enabled,
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
            llmobs_enabled=True,  # Assume enabled if not analysing code
        )
        logger.info("using_provided_profile", domain=agent_profile.domain)
    else:
        raise ValueError("Either agent_source or agent_profile_input must be provided")

    result["agent_profile"] = {
        "service_name": agent_profile.service_name,
        "agent_type": agent_profile.agent_type,
        "domain": agent_profile.domain,
        "description": agent_profile.description,
        "llm_provider": agent_profile.llm_provider,
        "framework": agent_profile.framework,
        "llmobs_enabled": agent_profile.llmobs_enabled,
        "span_operations": agent_profile.span_operations,
    }

    # Step 2: Check LLM Observability status
    budget_tracker.increment_step()

    async with DashboardMCPClient() as mcp:
        llmobs_status = await mcp.check_llm_obs_enabled(service)
        result["llmobs_status"] = llmobs_status

        if not llmobs_status.get("enabled"):
            logger.warning(
                "llmobs_not_enabled",
                service=service,
                message=llmobs_status.get("message"),
            )

    # Step 3: Discover existing telemetry
    budget_tracker.increment_step()
    discoverer = TelemetryDiscoverer(service)
    telemetry_profile = await discoverer.discover()

    result["telemetry_profile"] = {
        "metrics_found": telemetry_profile.metrics_found,
        "trace_operations": telemetry_profile.trace_operations,
        "has_llm_obs": telemetry_profile.has_llm_obs,
        "has_custom_metrics": telemetry_profile.has_custom_metrics,
    }

    # Step 4: Provision span-based metrics
    provisioned_metrics: list[dict] = []
    if provision_metrics:
        budget_tracker.increment_step()
        provisioner = MetricsProvisioner(agent_profile)
        provision_result = await provisioner.provision_metrics()
        result["provisioned_metrics"] = provision_result.get("metrics", [])
        provisioned_metrics = [
            {"id": m["id"], "status": m["status"]}
            for m in result["provisioned_metrics"]
            if m["status"] in ("created", "exists")
        ]
        logger.info(
            "metrics_provisioned",
            created=provision_result.get("created", 0),
            existing=provision_result.get("existing", 0),
        )

    # Step 5: Run evaluations on existing spans
    evaluation_labels: list[str] = []
    if run_evaluations and llmobs_status.get("enabled"):
        budget_tracker.increment_step()
        budget_tracker.increment_model_call()  # Evaluation uses Gemini

        evaluator = DomainEvaluator(agent_profile)
        eval_result = await evaluator.run_evaluations(hours_back=1, limit=20)
        result["evaluation_results"] = eval_result

        if eval_result.get("success"):
            evaluation_labels = eval_result.get("evaluation_types", [])
            logger.info(
                "evaluations_complete",
                spans_evaluated=eval_result.get("spans_evaluated", 0),
                successful=eval_result.get("successful", 0),
            )

    # Step 6: Design widgets using Gemini
    budget_tracker.increment_step()
    budget_tracker.increment_model_call()

    designer = GeminiWidgetDesigner()
    widgets = await designer.design_widgets(
        agent_profile,
        telemetry_profile,
        provisioned_metrics=provisioned_metrics,
        evaluation_labels=evaluation_labels,
    )

    logger.info("widget_design_complete", widgets_count=len(widgets))

    result["widgets"] = [
        WidgetPreview(
            title=w.get("title", "Untitled"),
            type=w.get("type", "timeseries"),
            query=w.get("query", ""),
            description=w.get("description"),
        ).model_dump()
        for w in widgets
    ]

    result["group_title"] = f"{agent_profile.domain.title()} Analytics"

    return result


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
