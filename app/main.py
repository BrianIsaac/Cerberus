"""FastAPI application for Ops Assistant."""

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_config import configure_logging
from app.models.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    ReviewRequest,
    ReviewResponse,
    TriageRequest,
    TriageResponse,
)
from app.observability import setup_custom_metrics, setup_llm_observability

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
    """Free-form triage question endpoint."""
    logger.info("ask_request_received", question=request.question[:100])

    # TODO: Implement in Phase 4
    raise HTTPException(status_code=501, detail="Not implemented yet")


@app.post("/triage", response_model=TriageResponse)
async def triage(request: TriageRequest) -> TriageResponse:
    """Structured triage payload endpoint."""
    logger.info(
        "triage_request_received",
        service=request.service,
        severity=request.severity,
    )

    # TODO: Implement in Phase 4
    raise HTTPException(status_code=501, detail="Not implemented yet")


@app.post("/review", response_model=ReviewResponse)
async def review(request: ReviewRequest) -> ReviewResponse:
    """Human review outcome capture endpoint."""
    logger.info(
        "review_request_received",
        trace_id=request.trace_id,
        outcome=request.outcome,
    )

    # TODO: Implement in Phase 4
    raise HTTPException(status_code=501, detail="Not implemented yet")


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
