"""Shared observability utilities for AI agents.

This module provides standardised telemetry patterns for all AI agents,
ensuring consistent metrics, tags, and observability across the fleet.
"""

from shared.observability.constants import (
    METRIC_PREFIX,
    TEAM_AI_AGENTS,
    Metrics,
    Tags,
)
from shared.observability.decorators import observed_workflow
from shared.observability.metrics import (
    build_tags,
    emit_handoff_required,
    emit_llm_call,
    emit_quality_score,
    emit_request_complete,
    emit_request_start,
    emit_step_budget_exceeded,
    emit_tool_call,
    emit_tool_error,
    timed_request,
)

__all__ = [
    # Constants
    "METRIC_PREFIX",
    "TEAM_AI_AGENTS",
    "Metrics",
    "Tags",
    # Metrics
    "build_tags",
    "emit_handoff_required",
    "emit_llm_call",
    "emit_quality_score",
    "emit_request_complete",
    "emit_request_start",
    "emit_step_budget_exceeded",
    "emit_tool_call",
    "emit_tool_error",
    "timed_request",
    # Decorators
    "observed_workflow",
]
