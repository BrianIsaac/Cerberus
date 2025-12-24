"""Datadog LLM Observability and metrics configuration."""

import os
from typing import Optional

import structlog
from datadog import initialize as dd_initialize
from datadog import statsd
from ddtrace.llmobs import LLMObs

from ops_triage_agent.config import settings


def setup_llm_observability():
    """Initialise Datadog LLM Observability.

    This enables auto-instrumentation for Vertex AI Gemini calls
    and provides decorators for custom span creation.
    """
    LLMObs.enable(
        ml_app=settings.dd_service,
        api_key=settings.dd_api_key,
        site=settings.dd_site,
        agentless_enabled=True,
        integrations_enabled=True,
    )


def setup_custom_metrics():
    """Initialise DogStatsD for custom metrics emission."""
    dd_initialize(
        statsd_host=os.getenv("DD_AGENT_HOST", "localhost"),
        statsd_port=int(os.getenv("DD_DOGSTATSD_PORT", "8125")),
        statsd_namespace="ops_assistant",
    )


def emit_request_metrics(
    endpoint: str,
    step_count: int,
    tool_calls: int,
    model_calls: int,
    latency_ms: float,
    success: bool,
):
    """Emit custom metrics for a request.

    Args:
        endpoint: API endpoint name
        step_count: Number of agent steps
        tool_calls: Number of tool calls made
        model_calls: Number of LLM calls made
        latency_ms: Request latency in milliseconds
        success: Whether the request succeeded
    """
    tags = [f"endpoint:{endpoint}", f"success:{success}"]

    statsd.gauge("agent.steps", step_count, tags=tags)
    statsd.gauge("agent.tool_calls", tool_calls, tags=tags)
    statsd.gauge("agent.model_calls", model_calls, tags=tags)
    statsd.histogram("request.latency_ms", latency_ms, tags=tags)

    if success:
        statsd.increment("request.success", tags=tags)
    else:
        statsd.increment("request.failure", tags=tags)


def emit_budget_exceeded(budget_type: str, limit: int, actual: int):
    """Emit metric when a budget is exceeded.

    Args:
        budget_type: Type of budget (steps, tool_calls, model_calls)
        limit: The configured limit
        actual: The actual count that exceeded the limit
    """
    tags = [f"budget_type:{budget_type}"]
    statsd.increment("agent.step_budget_exceeded", tags=tags)
    statsd.gauge("agent.budget_overage", actual - limit, tags=tags)


def emit_tool_error(tool_name: str, error_type: str):
    """Emit metric for tool errors.

    Args:
        tool_name: Name of the tool that failed
        error_type: Type of error encountered
    """
    tags = [f"tool:{tool_name}", f"error_type:{error_type}"]
    statsd.increment("agent.tool_error", tags=tags)


def emit_review_outcome(outcome: str):
    """Emit metric for human review outcomes.

    Args:
        outcome: Review outcome (approve, edit, reject)
    """
    statsd.increment(f"agent.review.{outcome}")


def emit_quality_metric(metric_name: str, value: float, tags: Optional[list[str]] = None):
    """Emit a quality evaluation metric.

    Args:
        metric_name: Name of the quality metric
        value: Metric value
        tags: Additional tags
    """
    all_tags = tags or []
    statsd.gauge(f"agent.quality.{metric_name}", value, tags=all_tags)


def emit_handoff_required(reason: str):
    """Emit metric when agent requires human handoff.

    Args:
        reason: Reason for requiring handoff
    """
    tags = [f"reason:{reason}"]
    statsd.increment("agent.handoff_required", tags=tags)


def emit_invalid_output(reason: str):
    """Emit metric when agent produces invalid output.

    Args:
        reason: Description of what was invalid (e.g., missing_required_field, invalid_format)
    """
    tags = [f"reason:{reason}"]
    statsd.increment("agent.invalid_output", tags=tags)


def emit_escalation(reason: str):
    """Emit metric when workflow is escalated to human.

    Args:
        reason: Reason for escalation (e.g., low_confidence, budget_exceeded, security_violation)
    """
    tags = [f"reason:{reason}"]
    statsd.increment("agent.escalation", tags=tags)


# Domain-specific event logging functions

def log_domain_event(
    event_type: str,
    message: str,
    **kwargs
):
    """Wrapper for structured logging with event_type field.

    Args:
        event_type: Type of event (tool_call, tool_result, budget, handoff, review_outcome)
        message: Log message describing the event
        **kwargs: Additional context fields to include in the log
    """
    logger = structlog.get_logger()
    logger.info(message, event_type=event_type, **kwargs)


def log_tool_call(tool_name: str, latency_ms: float, status: str):
    """Log a tool call event.

    Args:
        tool_name: Name of the tool being called
        latency_ms: Latency of the tool call in milliseconds
        status: Status of the tool call (success, failure, timeout)
    """
    log_domain_event(
        event_type="tool_call",
        message="tool_call_executed",
        tool_name=tool_name,
        tool_latency_ms=round(latency_ms, 2),
        tool_status=status,
    )


def log_tool_result(tool_name: str, result_summary: str, success: bool):
    """Log a tool result event.

    Args:
        tool_name: Name of the tool that returned a result
        result_summary: Brief summary of the result
        success: Whether the tool call succeeded
    """
    log_domain_event(
        event_type="tool_result",
        message="tool_result_received",
        tool_name=tool_name,
        result_summary=result_summary,
        success=success,
    )


def log_budget_event(budget_type: str, limit: int, actual: int):
    """Log a budget event.

    Args:
        budget_type: Type of budget (steps, tool_calls, model_calls)
        limit: The configured limit
        actual: The actual count
    """
    exceeded = actual > limit
    log_domain_event(
        event_type="budget",
        message="budget_check" if not exceeded else "budget_exceeded",
        budget_type=budget_type,
        budget_limit=limit,
        budget_actual=actual,
        exceeded=exceeded,
    )


def log_handoff(reason: str):
    """Log a handoff event.

    Args:
        reason: Reason for requiring handoff
    """
    log_domain_event(
        event_type="handoff",
        message="handoff_required",
        handoff_reason=reason,
    )


def log_review_outcome(outcome: str):
    """Log a review outcome event.

    Args:
        outcome: Review outcome (approve, edit, reject)
    """
    log_domain_event(
        event_type="review_outcome",
        message="review_completed",
        review_outcome=outcome,
    )
