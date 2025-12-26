"""Datadog LLM Observability for SAS Query Generator."""

from datadog import initialize as dd_initialize
from ddtrace.llmobs import LLMObs

from sas_generator.config import settings
from shared.observability import emit_quality_score, emit_request_complete

# Agent configuration for shared observability
AGENT_SERVICE = "sas-generator"
AGENT_TYPE = "code-generation"


def setup_llm_observability() -> None:
    """Initialise Datadog LLM Observability."""
    LLMObs.enable(
        ml_app=settings.dd_llmobs_ml_app,
        api_key=settings.dd_api_key,
        site=settings.dd_site,
        agentless_enabled=True,
        integrations_enabled=True,
    )


def setup_custom_metrics() -> None:
    """Initialise DogStatsD for custom metrics emission."""
    dd_initialize(
        statsd_host="localhost",
        statsd_port=8125,
        statsd_namespace="ai_agent",
    )


def emit_agent_metrics(
    tool_calls: int = 0,
    llm_calls: int = 1,
    latency_ms: float = 0,
    success: bool = True,
) -> None:
    """Emit standardised agent metrics using shared observability module.

    Args:
        tool_calls: Number of MCP tool calls made.
        llm_calls: Number of LLM calls made.
        latency_ms: Total request latency in milliseconds.
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


def emit_sas_quality_score(score: float, metric_name: str = "overall") -> None:
    """Emit quality score for SAS code generation.

    Args:
        score: Quality score (0-1).
        metric_name: Name of the quality metric.
    """
    emit_quality_score(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        score=score,
        metric_name=metric_name,
    )
