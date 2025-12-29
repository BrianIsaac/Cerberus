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
from .workflow import apply_enhancement, enhance_dashboard

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
                detail={"error": validation.reason, "details": validation.details},
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
        result = await enhance_dashboard(
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

    Args:
        service: Service name to cleanup metrics for.

    Returns:
        Cleanup results.
    """
    from .analyzer import AgentProfile
    from .provisioner import MetricsProvisioner

    logger.info("cleanup_metrics_started", service=service)

    # Create minimal profile for cleanup
    profile = AgentProfile(
        service_name=service,
        agent_type="unknown",
        domain="unknown",
        description="",
    )

    provisioner = MetricsProvisioner(profile)
    result = await provisioner.cleanup_metrics()

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
