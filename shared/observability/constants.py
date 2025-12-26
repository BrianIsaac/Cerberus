"""Standard observability constants for AI agents.

This module defines the canonical metric names, tag keys, and constant values
used across all AI agents for consistent telemetry.
"""

METRIC_PREFIX = "ai_agent"


class Metrics:
    """Standard metric names following OpenTelemetry GenAI semantic conventions."""

    REQUEST_COUNT = f"{METRIC_PREFIX}.request.count"
    REQUEST_LATENCY = f"{METRIC_PREFIX}.request.latency"
    REQUEST_ERROR = f"{METRIC_PREFIX}.request.error"
    LLM_CALLS = f"{METRIC_PREFIX}.llm.calls"
    LLM_LATENCY = f"{METRIC_PREFIX}.llm.latency"
    LLM_TOKENS_INPUT = f"{METRIC_PREFIX}.llm.tokens.input"
    LLM_TOKENS_OUTPUT = f"{METRIC_PREFIX}.llm.tokens.output"
    TOOL_CALLS = f"{METRIC_PREFIX}.tool.calls"
    TOOL_ERRORS = f"{METRIC_PREFIX}.tool.errors"
    TOOL_LATENCY = f"{METRIC_PREFIX}.tool.latency"
    QUALITY_SCORE = f"{METRIC_PREFIX}.quality.score"
    STEP_BUDGET_EXCEEDED = f"{METRIC_PREFIX}.step_budget_exceeded"
    HANDOFF_REQUIRED = f"{METRIC_PREFIX}.handoff_required"


class Tags:
    """Standard tag keys for consistent labelling across agents."""

    SERVICE = "service"
    TEAM = "team"
    AGENT_TYPE = "agent_type"
    ENV = "env"
    TOOL_NAME = "tool_name"
    ERROR_TYPE = "error_type"
    METRIC_NAME = "metric_name"
    HANDOFF_REASON = "handoff_reason"


TEAM_AI_AGENTS = "ai-agents"
