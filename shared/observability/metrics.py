"""Standardised metrics emission for AI agents.

This module provides functions for emitting consistent metrics across all AI agents,
following OpenTelemetry GenAI semantic conventions.
"""

import os
import time
from contextlib import contextmanager
from typing import Any, Generator

from datadog import statsd

from shared.observability.constants import TEAM_AI_AGENTS, Metrics, Tags


def build_tags(
    service: str,
    agent_type: str,
    extra_tags: list[str] | None = None,
) -> list[str]:
    """Build standard tag list for metrics.

    Args:
        service: Service name (e.g., 'ops-assistant', 'sas-generator').
        agent_type: Type of agent (e.g., 'triage', 'code-generation').
        extra_tags: Additional tags to include.

    Returns:
        List of tag strings in 'key:value' format.
    """
    tags = [
        f"{Tags.SERVICE}:{service}",
        f"{Tags.TEAM}:{TEAM_AI_AGENTS}",
        f"{Tags.AGENT_TYPE}:{agent_type}",
        f"{Tags.ENV}:{os.getenv('DD_ENV', 'development')}",
    ]

    if extra_tags:
        tags.extend(extra_tags)

    return tags


def emit_request_start(service: str, agent_type: str) -> None:
    """Emit metric for request start.

    Args:
        service: Service name.
        agent_type: Type of agent.
    """
    tags = build_tags(service, agent_type)
    statsd.increment(Metrics.REQUEST_COUNT, tags=tags)


def emit_request_complete(
    service: str,
    agent_type: str,
    latency_ms: float,
    success: bool = True,
    llm_calls: int = 0,
    tool_calls: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> None:
    """Emit metrics for completed request.

    Args:
        service: Service name.
        agent_type: Type of agent.
        latency_ms: Request latency in milliseconds.
        success: Whether request succeeded.
        llm_calls: Number of LLM calls made.
        tool_calls: Number of tool calls made.
        tokens_in: Total input tokens.
        tokens_out: Total output tokens.
    """
    tags = build_tags(service, agent_type)

    statsd.histogram(Metrics.REQUEST_LATENCY, latency_ms, tags=tags)

    if not success:
        statsd.increment(Metrics.REQUEST_ERROR, tags=tags)

    if llm_calls:
        statsd.increment(Metrics.LLM_CALLS, llm_calls, tags=tags)

    if tool_calls:
        statsd.increment(Metrics.TOOL_CALLS, tool_calls, tags=tags)

    if tokens_in:
        statsd.gauge(Metrics.LLM_TOKENS_INPUT, tokens_in, tags=tags)

    if tokens_out:
        statsd.gauge(Metrics.LLM_TOKENS_OUTPUT, tokens_out, tags=tags)


def emit_llm_call(
    service: str,
    agent_type: str,
    latency_ms: float,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> None:
    """Emit metrics for a single LLM call.

    Args:
        service: Service name.
        agent_type: Type of agent.
        latency_ms: LLM call latency in milliseconds.
        tokens_in: Input tokens for this call.
        tokens_out: Output tokens for this call.
    """
    tags = build_tags(service, agent_type)

    statsd.increment(Metrics.LLM_CALLS, tags=tags)
    statsd.histogram(Metrics.LLM_LATENCY, latency_ms, tags=tags)

    if tokens_in:
        statsd.gauge(Metrics.LLM_TOKENS_INPUT, tokens_in, tags=tags)

    if tokens_out:
        statsd.gauge(Metrics.LLM_TOKENS_OUTPUT, tokens_out, tags=tags)


def emit_tool_call(
    service: str,
    agent_type: str,
    tool_name: str,
    latency_ms: float,
    success: bool = True,
) -> None:
    """Emit metrics for a tool call.

    Args:
        service: Service name.
        agent_type: Type of agent.
        tool_name: Name of the tool called.
        latency_ms: Tool call latency in milliseconds.
        success: Whether the tool call succeeded.
    """
    extra_tags = [f"{Tags.TOOL_NAME}:{tool_name}"]
    tags = build_tags(service, agent_type, extra_tags)

    statsd.increment(Metrics.TOOL_CALLS, tags=tags)
    statsd.histogram(Metrics.TOOL_LATENCY, latency_ms, tags=tags)

    if not success:
        statsd.increment(Metrics.TOOL_ERRORS, tags=tags)


def emit_tool_error(
    service: str,
    agent_type: str,
    tool_name: str,
    error_type: str,
) -> None:
    """Emit metric for tool error.

    Args:
        service: Service name.
        agent_type: Type of agent.
        tool_name: Name of the failed tool.
        error_type: Type of error encountered.
    """
    extra_tags = [
        f"{Tags.TOOL_NAME}:{tool_name}",
        f"{Tags.ERROR_TYPE}:{error_type}",
    ]
    tags = build_tags(service, agent_type, extra_tags)
    statsd.increment(Metrics.TOOL_ERRORS, tags=tags)


def emit_quality_score(
    service: str,
    agent_type: str,
    score: float,
    metric_name: str = "overall",
) -> None:
    """Emit quality evaluation metric.

    Args:
        service: Service name.
        agent_type: Type of agent.
        score: Quality score (typically 0-1).
        metric_name: Name of the quality metric (e.g., 'faithfulness', 'relevancy').
    """
    extra_tags = [f"{Tags.METRIC_NAME}:{metric_name}"]
    tags = build_tags(service, agent_type, extra_tags)
    statsd.gauge(Metrics.QUALITY_SCORE, score, tags=tags)


def emit_handoff_required(
    service: str,
    agent_type: str,
    reason: str,
) -> None:
    """Emit metric for human handoff requirement.

    Args:
        service: Service name.
        agent_type: Type of agent.
        reason: Reason for handoff (e.g., 'low_confidence', 'budget_exceeded').
    """
    extra_tags = [f"{Tags.HANDOFF_REASON}:{reason}"]
    tags = build_tags(service, agent_type, extra_tags)
    statsd.increment(Metrics.HANDOFF_REQUIRED, tags=tags)


def emit_step_budget_exceeded(
    service: str,
    agent_type: str,
    actual_steps: int,
    max_steps: int,
) -> None:
    """Emit metric for step budget exceeded.

    Args:
        service: Service name.
        agent_type: Type of agent.
        actual_steps: Actual number of steps taken.
        max_steps: Maximum allowed steps.
    """
    tags = build_tags(service, agent_type)
    statsd.increment(Metrics.STEP_BUDGET_EXCEEDED, tags=tags)
    statsd.gauge(f"{Metrics.STEP_BUDGET_EXCEEDED}.overage", actual_steps - max_steps, tags=tags)


@contextmanager
def timed_request(
    service: str,
    agent_type: str,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for timing requests with automatic metric emission.

    Args:
        service: Service name.
        agent_type: Type of agent.

    Yields:
        Metrics collector dict for tracking llm_calls, tool_calls, tokens, success.

    Example:
        with timed_request("sas-generator", "code-generation") as metrics:
            result = await do_work()
            metrics["llm_calls"] = 1
            metrics["tool_calls"] = 2
    """
    start_time = time.perf_counter()
    metrics: dict[str, Any] = {
        "llm_calls": 0,
        "tool_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "success": True,
    }

    try:
        yield metrics
    except Exception:
        metrics["success"] = False
        raise
    finally:
        latency_ms = (time.perf_counter() - start_time) * 1000
        emit_request_complete(
            service=service,
            agent_type=agent_type,
            latency_ms=latency_ms,
            success=metrics["success"],
            llm_calls=metrics["llm_calls"],
            tool_calls=metrics["tool_calls"],
            tokens_in=metrics["tokens_in"],
            tokens_out=metrics["tokens_out"],
        )
