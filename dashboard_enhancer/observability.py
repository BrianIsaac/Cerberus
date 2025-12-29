"""Observability setup for Dashboard Enhancement Agent."""

import structlog
from datadog import initialize as dd_initialize
from ddtrace.llmobs import LLMObs

from shared.observability import (
    emit_handoff_required,
    emit_quality_score,
    emit_request_complete,
)

from .config import settings

logger = structlog.get_logger()

AGENT_SERVICE = "dashboard-enhancer"
AGENT_TYPE = "analysis"


def setup_llm_observability() -> None:
    """Initialise Datadog LLM Observability."""
    if not settings.dd_llmobs_enabled:
        logger.info("llm_observability_disabled")
        return

    LLMObs.enable(
        ml_app=settings.dd_llmobs_ml_app,
        api_key=settings.dd_api_key,
        site=settings.dd_site,
        agentless_enabled=True,
        integrations_enabled=True,
    )
    logger.info("llm_observability_enabled", ml_app=settings.dd_llmobs_ml_app)


def setup_custom_metrics() -> None:
    """Initialise DogStatsD metrics client."""
    dd_initialize(
        statsd_host="localhost",
        statsd_port=8125,
    )
    logger.info("custom_metrics_initialised")


def emit_agent_metrics(
    tool_calls: int = 0,
    llm_calls: int = 0,
    latency_ms: float = 0,
    success: bool = True,
) -> None:
    """Emit metrics for agent execution.

    Args:
        tool_calls: Number of tool calls made.
        llm_calls: Number of LLM calls made.
        latency_ms: Total latency in milliseconds.
        success: Whether the request succeeded.
    """
    emit_request_complete(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        latency_ms=latency_ms,
        success=success,
        llm_calls=llm_calls,
        tool_calls=tool_calls,
    )


def emit_enhancement_quality(
    score: float,
    metric_name: str = "widget_quality",
) -> None:
    """Emit quality score for generated widgets.

    Args:
        score: Quality score between 0 and 1.
        metric_name: Name of the quality metric.
    """
    emit_quality_score(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        score=score,
        metric_name=metric_name,
    )


def emit_approval_required(reason: str) -> None:
    """Emit metric when human approval is required.

    Args:
        reason: Reason for requiring approval.
    """
    emit_handoff_required(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        reason=reason,
    )
