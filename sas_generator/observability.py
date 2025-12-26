"""Datadog LLM Observability for SAS Query Generator."""

from datadog import initialize as dd_initialize
from datadog import statsd
from ddtrace.llmobs import LLMObs

from sas_generator.config import settings


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
    """Emit standardised agent metrics.

    Args:
        tool_calls: Number of MCP tool calls made.
        llm_calls: Number of LLM calls made.
        latency_ms: Total request latency in milliseconds.
        success: Whether the request succeeded.
    """
    tags = [
        f"service:{settings.dd_service}",
        "team:ai-agents",
        "agent_type:code-generation",
        f"env:{settings.dd_env}",
    ]

    statsd.increment("request.count", tags=tags)
    statsd.histogram("request.latency_ms", latency_ms, tags=tags)

    if tool_calls:
        statsd.increment("tool.calls", tool_calls, tags=tags)

    if llm_calls:
        statsd.increment("llm.calls", llm_calls, tags=tags)

    if not success:
        statsd.increment("request.error", tags=tags)
