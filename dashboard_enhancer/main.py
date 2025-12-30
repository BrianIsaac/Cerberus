"""FastAPI backend for Dashboard Enhancement Agent."""

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from ddtrace.llmobs import LLMObs
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .governance import create_budget_tracker, create_security_validator
from .models import (
    ApprovalRequest,
    ApprovalResponse,
    EnhanceRequest,
    EnhanceResponse,
    WidgetPreview,
)
from .observability import (
    emit_agent_metrics,
    emit_approval_required,
    setup_custom_metrics,
    setup_llm_observability,
)
from .workflow import (
    analyze_and_preview,
    apply_enhancement,
    enhance_dashboard,
    provision_and_apply,
    rollback_provisioning,
)

logger = structlog.get_logger()

# In-memory store for pending approvals
pending_approvals: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(
        "service_starting",
        service=settings.dd_service,
        version=settings.dd_version,
        env=settings.dd_env,
    )

    setup_llm_observability()
    setup_custom_metrics()
    logger.info("observability_configured")

    yield

    LLMObs.flush()
    logger.info("service_shutting_down")


app = FastAPI(
    title="Dashboard Enhancement Agent",
    description="AI-powered dashboard customisation for AI agents",
    version=settings.dd_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request, call_next):
    """Add timing and logging to all requests."""
    start_time = time.time()

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        path=request.url.path,
        method=request.method,
    )

    try:
        response = await call_next(request)
        latency_ms = (time.time() - start_time) * 1000

        logger.info(
            "request_completed",
            status_code=response.status_code,
            latency_ms=round(latency_ms, 2),
        )

        return response

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error("request_failed", error=str(e), latency_ms=round(latency_ms, 2))
        raise


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.dd_service,
        "version": settings.dd_version,
    }


@app.post("/enhance", response_model=EnhanceResponse)
async def enhance(request: EnhanceRequest):
    """Analyse an agent and generate dashboard enhancement recommendations.

    Args:
        request: Enhancement request with service and agent directory.

    Returns:
        Enhancement recommendations requiring approval.
    """
    trace_id = str(uuid.uuid4())
    start_time = time.time()

    structlog.contextvars.bind_contextvars(
        trace_id=trace_id,
        service=request.service,
    )

    logger.info(
        "enhance_started",
        agent_dir=request.agent_dir,
        github_url=request.github_url,
        has_profile=request.agent_profile is not None,
    )

    # Validate we have at least one source of agent info
    if not request.agent_dir and not request.github_url and not request.agent_profile:
        raise HTTPException(
            status_code=400,
            detail={"error": "One of agent_dir, github_url, or agent_profile must be provided"},
        )

    agent_source = None
    if request.github_url:
        # Use GitHub URL directly - CodeAnalyzer will handle fetching
        agent_source = request.github_url
        logger.info("using_github_source", github_url=request.github_url)
    elif request.agent_dir:
        # Validate input path
        validator = create_security_validator()
        validation = validator.validate_input(request.agent_dir)
        if not validation.is_valid:
            raise HTTPException(
                status_code=400,
                detail={"error": validation.reason, "details": validation.detected_items},
            )

        # Check agent directory exists
        agent_path = Path(request.agent_dir)
        if not agent_path.exists():
            # If agent_profile is provided, we can proceed without local code
            if not request.agent_profile:
                raise HTTPException(
                    status_code=400,
                    detail={"error": f"Agent directory not found: {request.agent_dir}"},
                )
            logger.info("agent_dir_not_found_using_profile", agent_dir=request.agent_dir)
        else:
            agent_source = agent_path

    try:
        # Run enhancement workflow
        tracker = create_budget_tracker()
        result = await enhance_dashboard(  # type: ignore[reportCallIssue, reportGeneralTypeIssues]
            service=request.service,
            agent_source=agent_source,
            agent_profile_input=request.agent_profile,
            dashboard_id=request.dashboard_id or settings.dashboard_id,
            budget_tracker=tracker,
            run_evaluations=request.run_evaluations,
            provision_metrics=request.provision_metrics,
        )

        # Store for approval
        pending_approvals[trace_id] = {
            "result": result,
            "request": request.model_dump(),
            "dashboard_id": request.dashboard_id or settings.dashboard_id,
        }

        # Emit metrics
        latency_ms = (time.time() - start_time) * 1000
        emit_agent_metrics(
            tool_calls=tracker.tool_calls,
            llm_calls=tracker.model_calls,
            latency_ms=latency_ms,
            success=True,
        )
        emit_approval_required("widget_generation")

        logger.info(
            "enhance_completed",
            widgets_count=len(result["widgets"]),
            latency_ms=round(latency_ms, 2),
        )

        # Convert widget dicts to WidgetPreview objects
        widget_previews = [
            WidgetPreview(
                title=w.get("title", "Untitled"),
                type=w.get("type", "timeseries"),
                query=w.get("query", ""),
                description=w.get("description"),
            )
            for w in result["widgets"]
        ]

        return EnhanceResponse(
            trace_id=trace_id,
            service=request.service,
            agent_profile=result["agent_profile"],
            telemetry_profile=result["telemetry_profile"],
            widgets=widget_previews,
            group_title=result["group_title"],
            requires_approval=True,
            message="Observability infrastructure provisioned. Review and approve to apply widgets.",
            llmobs_status=result.get("llmobs_status", {}),
            provisioned_metrics=result.get("provisioned_metrics", []),
            evaluation_results=result.get("evaluation_results", {}),
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        emit_agent_metrics(latency_ms=latency_ms, success=False)
        logger.error("enhance_failed", error=str(e))
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.post("/approve", response_model=ApprovalResponse)
async def approve(request: ApprovalRequest):
    """Approve or reject enhancement recommendations.

    Args:
        request: Approval request with trace_id and outcome.

    Returns:
        Result of applying the enhancement.
    """
    structlog.contextvars.bind_contextvars(trace_id=request.trace_id)

    logger.info("approval_received", outcome=request.outcome)

    # Get pending approval
    pending = pending_approvals.get(request.trace_id)
    if not pending:
        raise HTTPException(
            status_code=404,
            detail={"error": f"No pending approval found for trace_id: {request.trace_id}"},
        )

    if request.outcome == "rejected":
        del pending_approvals[request.trace_id]
        logger.info("enhancement_rejected")
        return ApprovalResponse(
            success=True,
            message="Enhancement rejected. No changes made.",
        )

    try:
        # Apply enhancement
        result = await apply_enhancement(
            widgets=pending["result"]["widgets"],
            group_title=pending["result"]["group_title"],
            service=pending["request"]["service"],
            dashboard_id=pending["dashboard_id"],
        )

        del pending_approvals[request.trace_id]

        logger.info(
            "enhancement_applied",
            dashboard_id=result["dashboard_id"],
            group_id=result["group_id"],
        )

        return ApprovalResponse(
            success=True,
            dashboard_id=result["dashboard_id"],
            group_id=result["group_id"],
            widgets_added=result["widgets_added"],
            message="Enhancement applied successfully.",
            dashboard_url=result["dashboard_url"],
        )

    except Exception as e:
        logger.error("apply_failed", error=str(e))
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.get("/pending")
async def list_pending():
    """List pending approval requests."""
    return {
        "count": len(pending_approvals),
        "trace_ids": list(pending_approvals.keys()),
    }


@app.delete("/metrics/{service}")
async def cleanup_metrics(service: str):
    """Delete all provisioned metrics for a service.

    Lists all span-based metrics matching the service prefix and deletes them.

    Args:
        service: Service name to cleanup metrics for.

    Returns:
        Cleanup results.
    """
    from .mcp_client import DashboardMCPClient
    from .provisioner import MetricsProvisioner

    logger.info("cleanup_metrics_started", service=service)

    # Find all metrics matching this service's naming pattern
    normalised_service = service.replace("-", "_")
    metric_ids_to_delete: list[str] = []

    async with DashboardMCPClient() as mcp:
        existing = await mcp.list_spans_metrics()
        for metric in existing.get("metrics", []):
            metric_id = metric.get("id", "")
            if metric_id.startswith(normalised_service):
                metric_ids_to_delete.append(metric_id)

    if not metric_ids_to_delete:
        return {
            "service": service,
            "deleted": [],
            "failed": [],
            "message": f"No metrics found for service {service}",
        }

    provisioner = MetricsProvisioner(service)
    result = await provisioner.cleanup_metrics(metric_ids_to_delete)

    logger.info(
        "cleanup_metrics_completed",
        service=service,
        deleted_count=len(result.get("deleted", [])),
    )

    return {
        "service": service,
        "deleted": result.get("deleted", []),
        "failed": result.get("failed", []),
        "message": f"Deleted {len(result.get('deleted', []))} metrics",
    }


# =============================================================================
# Two-Phase Personalised Observability Endpoints
# =============================================================================


@app.post("/analyze")
async def analyze(request: EnhanceRequest):
    """Analyse service and preview personalised observability.

    Returns preview without creating any resources. Call /provision/{trace_id}
    to create metrics and apply widgets.

    Args:
        request: Enhancement request with service and agent profile.

    Returns:
        Preview of proposed metrics and widgets.
    """
    trace_id = str(uuid.uuid4())[:8]

    structlog.contextvars.bind_contextvars(
        trace_id=trace_id,
        service=request.service,
    )

    logger.info(
        "analyze_started",
        agent_dir=request.agent_dir,
        github_url=request.github_url,
        has_profile=request.agent_profile is not None,
    )

    # Determine agent source
    agent_source = None
    if request.github_url:
        agent_source = request.github_url
    elif request.agent_dir:
        security_validator = create_security_validator()
        validation = security_validator.validate_input(request.agent_dir)
        if validation.is_valid:
            validated_path = Path(request.agent_dir)
            if validated_path.is_file():
                validated_path = validated_path.parent
            if validated_path.exists():
                agent_source = validated_path

    try:
        profile = request.agent_profile
        if not profile:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "agent_profile is required for /analyze endpoint",
                    "trace_id": trace_id,
                },
            )

        result = await analyze_and_preview(  # type: ignore[reportCallIssue, reportGeneralTypeIssues]
            service=request.service,
            domain=profile.domain,
            agent_type=profile.agent_type,
            agent_source=agent_source,
            llm_provider=profile.llm_provider,
            framework=profile.framework,
        )

        # Store for provisioning phase
        pending_approvals[trace_id] = {
            "type": "preview",
            "result": result,
            "dashboard_id": request.dashboard_id or settings.dashboard_id,
        }

        logger.info(
            "analyze_completed",
            proposed_metrics=len(result.get("proposed_metrics", [])),
            widgets=len(result.get("widget_preview", {}).get("widgets", [])),
        )

        return {
            "trace_id": trace_id,
            "service": request.service,
            "discovery": result.get("discovery", {}),
            "llmobs_status": result.get("llmobs_status", {}),
            "proposed_metrics": result.get("proposed_metrics", []),
            "widget_preview": result.get("widget_preview", {}),
            "message": "Analysis complete. Review and call /provision/{trace_id} to apply.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("analyze_failed", error=str(e), trace_id=trace_id)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "trace_id": trace_id},
        )


@app.post("/provision/{trace_id}")
async def provision(trace_id: str):
    """Provision metrics and apply widgets for an analysed service.

    Creates metrics in Datadog and adds widget group to dashboard.
    Call /rollback/{trace_id} to undo if needed.

    Args:
        trace_id: Trace ID from /analyze response.

    Returns:
        Provisioning result with dashboard URL.
    """
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    logger.info("provision_started")

    if trace_id not in pending_approvals:
        raise HTTPException(
            status_code=404,
            detail={"error": "Analysis not found", "trace_id": trace_id},
        )

    pending = pending_approvals[trace_id]
    if pending.get("type") != "preview":
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid trace_id - not a preview", "trace_id": trace_id},
        )

    try:
        tracker = create_budget_tracker()
        result = await provision_and_apply(  # type: ignore[reportCallIssue, reportGeneralTypeIssues]
            preview_result=pending["result"],
            dashboard_id=pending["dashboard_id"],
            budget_tracker=tracker,
        )

        # Update for potential rollback
        pending_approvals[trace_id] = {
            "type": "provisioned",
            "result": result,
            "service": pending["result"]["service"],
        }

        logger.info(
            "provision_completed",
            metrics_created=result["metrics_created"],
            widgets_added=len(result["widget_group"].get("widgets", [])),
        )

        return {
            "trace_id": trace_id,
            "success": True,
            "service": result["service"],
            "metrics_created": result["metrics_created"],
            "metrics_existing": result["metrics_existing"],
            "metrics_failed": result["metrics_failed"],
            "widgets_added": len(result["widget_group"].get("widgets", [])),
            "dashboard_url": result.get("dashboard_url"),
            "message": "Provisioning complete. Personalised widget group added to dashboard.",
        }

    except Exception as e:
        logger.error("provision_failed", error=str(e), trace_id=trace_id)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "trace_id": trace_id},
        )


@app.delete("/rollback/{trace_id}")
async def rollback(trace_id: str):
    """Rollback provisioned metrics.

    Deletes metrics created during provisioning. Note: widget group
    removal from dashboard is not yet supported.

    Args:
        trace_id: Trace ID from /provision response.

    Returns:
        Rollback result with deleted metric IDs.
    """
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    logger.info("rollback_started")

    if trace_id not in pending_approvals:
        raise HTTPException(
            status_code=404,
            detail={"error": "Provisioning not found", "trace_id": trace_id},
        )

    pending = pending_approvals[trace_id]
    if pending.get("type") != "provisioned":
        raise HTTPException(
            status_code=400,
            detail={"error": "Nothing to rollback - not provisioned", "trace_id": trace_id},
        )

    try:
        result = pending["result"]
        rollback_result = await rollback_provisioning(
            service=pending["service"],
            created_metric_ids=result.get("created_metric_ids", []),
        )

        del pending_approvals[trace_id]

        logger.info(
            "rollback_completed",
            deleted=len(rollback_result.get("deleted", [])),
            failed=len(rollback_result.get("failed", [])),
        )

        return {
            "trace_id": trace_id,
            "success": True,
            "deleted": rollback_result.get("deleted", []),
            "failed": rollback_result.get("failed", []),
            "message": f"Rolled back {len(rollback_result.get('deleted', []))} metrics.",
        }

    except Exception as e:
        logger.error("rollback_failed", error=str(e), trace_id=trace_id)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "trace_id": trace_id},
        )
