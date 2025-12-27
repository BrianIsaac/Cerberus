"""FastAPI application for SAS Generator backend."""

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sas_generator.config import settings
from sas_generator.logging_config import configure_logging
from sas_generator.observability import (
    emit_agent_metrics,
    setup_custom_metrics,
    setup_llm_observability,
)
from sas_generator.workflow import generate_sas_code_agentic

configure_logging()
logger = structlog.get_logger()


class GenerateRequest(BaseModel):
    """Request model for SAS code generation."""

    query: str = Field(..., description="Natural language query describing the analysis")


class GenerateResponse(BaseModel):
    """Response model for SAS code generation."""

    trace_id: str
    code: str
    explanation: str
    procedures_used: list[str]
    latency_ms: float


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    logger.info(
        "sas_generator_starting",
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
    logger.info("sas_generator_shutting_down")


app = FastAPI(
    title="SAS Generator API",
    description="Generate SAS code from natural language queries",
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
        service=settings.dd_service,
        version=settings.dd_version,
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """Generate SAS code from natural language query.

    Args:
        request: Generation request with query.

    Returns:
        Generated SAS code with explanation.
    """
    trace_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "generate_request_received",
        query=request.query[:100],
        trace_id=trace_id,
    )

    try:
        result = await generate_sas_code_agentic(request.query)
        latency_ms = (time.time() - start_time) * 1000

        # Emit metrics for dashboard visibility
        emit_agent_metrics(
            tool_calls=1,  # MCP schema fetch
            llm_calls=1,
            latency_ms=latency_ms,
            success=True,
        )

        logger.info(
            "generate_request_completed",
            trace_id=trace_id,
            latency_ms=round(latency_ms, 2),
            procedures=result.procedures_used,
        )

        return GenerateResponse(
            trace_id=trace_id,
            code=result.code,
            explanation=result.explanation,
            procedures_used=result.procedures_used,
            latency_ms=latency_ms,
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000

        emit_agent_metrics(
            tool_calls=0,
            llm_calls=0,
            latency_ms=latency_ms,
            success=False,
        )

        logger.error(
            "generate_request_failed",
            trace_id=trace_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "trace_id": trace_id},
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
