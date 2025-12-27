"""FastAPI wrapper for SAS Generator to enable programmatic access."""

import time
import uuid
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sas_generator.config import settings
from sas_generator.generator import generate_sas_code
from sas_generator.observability import setup_llm_observability
from sas_generator.workflow import generate_sas_code_agentic

logger = structlog.get_logger()


class GenerateRequest(BaseModel):
    """Request model for SAS code generation."""

    query: str = Field(..., description="Natural language query describing the analysis")
    use_governance: bool = Field(
        default=True,
        description="Enable governance controls (security, quality, budget tracking)",
    )


class GenerateResponse(BaseModel):
    """Response model for SAS code generation."""

    trace_id: str
    code: str
    explanation: str
    procedures_used: list[str]
    latency_ms: float
    quality_score: float = Field(default=0.0, description="LLM-as-judge quality score")
    quality_issues: list[str] = Field(default_factory=list, description="Quality issues found")
    requires_approval: bool = Field(
        default=False, description="Whether human approval is recommended"
    )
    governance: dict[str, Any] = Field(default_factory=dict, description="Governance state")


app = FastAPI(
    title="SAS Generator API",
    description="Generate SAS code from natural language queries",
    version=settings.dd_version,
)


@app.on_event("startup")
async def startup_event():
    """Initialise observability on startup."""
    setup_llm_observability()
    logger.info("sas_generator_api_started", service=settings.dd_service)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.dd_service,
        "version": settings.dd_version,
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """Generate SAS code from natural language query.

    Args:
        request: Generation request with query.

    Returns:
        Generated SAS code with explanation and governance metadata.
    """
    trace_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "generate_request_received",
        query=request.query[:100],
        trace_id=trace_id,
        use_governance=request.use_governance,
    )

    try:
        if request.use_governance:
            # Use agentic workflow with full governance
            result = await generate_sas_code_agentic(request.query)
            latency_ms = (time.time() - start_time) * 1000

            # Check for escalation
            if result.get("escalated"):
                logger.warning(
                    "generate_request_escalated",
                    trace_id=trace_id,
                    reason=result.get("reason"),
                )
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": result.get("error"),
                        "reason": result.get("reason"),
                        "trace_id": trace_id,
                    },
                )

            logger.info(
                "generate_request_completed",
                trace_id=trace_id,
                latency_ms=round(latency_ms, 2),
                procedures=result.get("procedures_used", []),
                quality_score=result.get("quality_score", 0.0),
                requires_approval=result.get("requires_approval", False),
            )

            return GenerateResponse(
                trace_id=trace_id,
                code=result["code"],
                explanation=result["explanation"],
                procedures_used=result["procedures_used"],
                latency_ms=latency_ms,
                quality_score=result.get("quality_score", 0.0),
                quality_issues=result.get("quality_issues", []),
                requires_approval=result.get("requires_approval", False),
                governance=result.get("governance", {}),
            )
        else:
            # Use simple generator without governance
            result = generate_sas_code(request.query)
            latency_ms = (time.time() - start_time) * 1000

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "generate_request_failed",
            trace_id=trace_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "trace_id": trace_id},
        )
