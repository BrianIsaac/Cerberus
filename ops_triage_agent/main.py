"""FastAPI application for Ops Assistant."""

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from ops_triage_agent.agent.workflow import resume_workflow, run_triage_workflow
from ops_triage_agent.config import settings
from ops_triage_agent.logging_config import configure_logging
from ops_triage_agent.models.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    Hypothesis,
    ReviewRequest,
    ReviewResponse,
    TriageRequest,
    TriageResponse,
)
from ops_triage_agent.observability import (
    emit_request_metrics,
    emit_review_outcome,
    setup_custom_metrics,
    setup_llm_observability,
)
from shared.observability import emit_request_start

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    logger.info(
        "ops_assistant_starting",
        service=settings.dd_service,
        version=settings.dd_version,
        env=settings.dd_env,
    )

    setup_llm_observability()
    setup_custom_metrics()
    logger.info("observability_configured")

    yield

    from ddtrace.llmobs import LLMObs

    LLMObs.flush()
    logger.info("ops_assistant_shutting_down")


app = FastAPI(
    title="Ops Assistant API",
    description="Bounded ops assistant for Datadog triage",
    version=settings.dd_version,
    lifespan=lifespan,
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
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
        logger.error(
            "request_failed",
            error=str(e),
            latency_ms=round(latency_ms, 2),
        )
        raise


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint for Cloud Run."""
    return HealthResponse(
        status="healthy",
        version=settings.dd_version,
        service=settings.dd_service,
    )


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    """Free-form triage question endpoint.

    Runs the LangGraph triage workflow to analyse the user's question,
    collect evidence from Datadog, and synthesise hypotheses.
    """
    start_time = time.time()
    trace_id = str(uuid.uuid4())

    emit_request_start(service="ops-assistant", agent_type="triage")

    logger.info(
        "ask_request_received",
        question=request.question[:100],
        trace_id=trace_id,
    )

    try:
        # Run the triage workflow
        result = await run_triage_workflow(
            user_query=request.question,
            service=request.service,
            time_window=request.time_window or "last_15m",
            thread_id=trace_id,
        )

        latency_ms = (time.time() - start_time) * 1000
        success = result.get("status") == "completed"

        emit_request_metrics(
            endpoint="ask",
            step_count=result.get("step_count", 0),
            tool_calls=result.get("tool_calls", 0),
            model_calls=result.get("model_calls", 0),
            latency_ms=latency_ms,
            success=success,
        )

        # Handle escalated or error responses
        if result.get("status") == "escalated":
            raise HTTPException(
                status_code=422,
                detail={
                    "status": "escalated",
                    "reason": result.get("reason", "Unknown"),
                    "trace_id": trace_id,
                },
            )

        if result.get("status") == "error":
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "error": result.get("error", "Unknown error"),
                    "trace_id": trace_id,
                },
            )

        # Build response with hypothesis objects
        hypotheses = [
            Hypothesis(
                rank=h.get("rank", i + 1),
                description=h.get("description", ""),
                confidence=h.get("confidence", 0.0),
                evidence=h.get("evidence", []),
                query_links=h.get("query_links", []),
            )
            for i, h in enumerate(result.get("hypotheses", []))
        ]

        return AskResponse(
            trace_id=trace_id,
            summary=result.get("summary", ""),
            hypotheses=hypotheses,
            next_steps=result.get("next_steps", []),
            requires_approval=result.get("requires_approval", False),
            confidence=result.get("confidence", 0.0),
            step_count=result.get("step_count", 0),
            tool_calls=result.get("tool_calls", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ask_request_failed", error=str(e), trace_id=trace_id)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "trace_id": trace_id},
        )


@app.post("/triage", response_model=TriageResponse)
async def triage(request: TriageRequest) -> TriageResponse:
    """Structured triage payload endpoint.

    Runs the LangGraph triage workflow with structured input including
    service, environment, and optional symptoms.
    """
    start_time = time.time()
    trace_id = str(uuid.uuid4())

    emit_request_start(service="ops-assistant", agent_type="triage")

    logger.info(
        "triage_request_received",
        service=request.service,
        severity=request.severity,
        trace_id=trace_id,
    )

    # Build query from structured input
    query_parts = [f"Triage {request.service} in {request.environment}"]
    if request.symptoms:
        query_parts.append(f"Symptoms: {request.symptoms}")
    if request.severity:
        query_parts.append(f"Severity: {request.severity.value}")
    if request.alert_id:
        query_parts.append(f"Alert ID: {request.alert_id}")

    user_query = ". ".join(query_parts)

    try:
        # Run the triage workflow
        result = await run_triage_workflow(
            user_query=user_query,
            service=request.service,
            environment=request.environment,
            time_window=request.time_window,
            thread_id=trace_id,
        )

        latency_ms = (time.time() - start_time) * 1000
        success = result.get("status") == "completed"

        emit_request_metrics(
            endpoint="triage",
            step_count=result.get("step_count", 0),
            tool_calls=result.get("tool_calls", 0),
            model_calls=result.get("model_calls", 0),
            latency_ms=latency_ms,
            success=success,
        )

        # Handle escalated or error responses
        if result.get("status") == "escalated":
            raise HTTPException(
                status_code=422,
                detail={
                    "status": "escalated",
                    "reason": result.get("reason", "Unknown"),
                    "trace_id": trace_id,
                },
            )

        if result.get("status") == "error":
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "error": result.get("error", "Unknown error"),
                    "trace_id": trace_id,
                },
            )

        # Build response with hypothesis objects
        hypotheses = [
            Hypothesis(
                rank=h.get("rank", i + 1),
                description=h.get("description", ""),
                confidence=h.get("confidence", 0.0),
                evidence=h.get("evidence", []),
                query_links=h.get("query_links", []),
            )
            for i, h in enumerate(result.get("hypotheses", []))
        ]

        # Build proposed incident if applicable
        proposed_incident = None
        if result.get("requires_approval"):
            proposed_incident = {
                "title": f"Triage: {request.service}",
                "service": request.service,
                "severity": request.severity.value if request.severity else "SEV-3",
                "summary": result.get("summary", ""),
            }

        return TriageResponse(
            trace_id=trace_id,
            summary=result.get("summary", ""),
            hypotheses=hypotheses,
            next_steps=result.get("next_steps", []),
            requires_approval=result.get("requires_approval", False),
            proposed_incident=proposed_incident,
            confidence=result.get("confidence", 0.0),
            step_count=result.get("step_count", 0),
            tool_calls=result.get("tool_calls", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("triage_request_failed", error=str(e), trace_id=trace_id)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "trace_id": trace_id},
        )


@app.post("/review", response_model=ReviewResponse)
async def review(request: ReviewRequest) -> ReviewResponse:
    """Human review outcome capture endpoint.

    Resumes a paused workflow with the user's approval decision.
    Used when a workflow is waiting at the approval gate.
    """
    logger.info(
        "review_request_received",
        trace_id=request.trace_id,
        outcome=request.outcome,
    )

    # Emit review outcome metric
    emit_review_outcome(request.outcome.value)

    try:
        # Map outcome to workflow decision
        decision = request.outcome.value
        if request.modifications:
            decision = f"{decision}: {request.modifications}"

        # Resume the workflow with the decision
        result = await resume_workflow(
            thread_id=request.trace_id,
            user_input=decision,
        )

        incident_id = result.get("incident_id")
        case_id = result.get("case_id")

        logger.info(
            "review_completed",
            trace_id=request.trace_id,
            outcome=request.outcome,
            incident_id=incident_id,
            case_id=case_id,
        )

        return ReviewResponse(
            trace_id=request.trace_id,
            outcome=request.outcome,
            incident_id=incident_id,
            case_id=case_id,
            recorded_at=datetime.now(),
        )

    except Exception as e:
        logger.error(
            "review_failed",
            trace_id=request.trace_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "trace_id": request.trace_id,
            },
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler with logging."""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
