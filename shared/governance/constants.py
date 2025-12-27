"""Governance constants for bounded autonomy across all agents.

This module defines the canonical governance configuration, escalation reasons,
and approval statuses used across all AI agents for consistent bounded autonomy.
"""

from enum import Enum
from typing import NamedTuple


class GovernanceDefaults(NamedTuple):
    """Default governance limits aligned with paper recommendations.

    These defaults are based on the "Measuring Agents in Production" paper
    (arXiv 2512.04123) which found that 68% of production agents execute
    fewer than 10 steps before human intervention.

    Attributes:
        max_steps: Maximum workflow steps allowed per request.
        max_model_calls: Maximum LLM API calls allowed per request.
        max_tool_calls: Maximum tool/MCP calls allowed per request.
        confidence_threshold: Minimum confidence score before escalation.
        max_clarification_attempts: Maximum clarification rounds before escalation.
        max_input_length: Maximum allowed input text length in characters.
    """

    max_steps: int = 8
    max_model_calls: int = 5
    max_tool_calls: int = 6
    confidence_threshold: float = 0.7
    max_clarification_attempts: int = 2
    max_input_length: int = 10000


GOVERNANCE_DEFAULTS = GovernanceDefaults()


class EscalationReason(str, Enum):
    """Standardised escalation reasons for metrics tagging.

    Each reason corresponds to a specific governance boundary that was reached,
    triggering human-in-the-loop escalation.
    """

    STEP_BUDGET_EXCEEDED = "step_budget_exceeded"
    MODEL_BUDGET_EXCEEDED = "model_budget_exceeded"
    TOOL_BUDGET_EXCEEDED = "tool_budget_exceeded"
    LOW_CONFIDENCE = "low_confidence"
    SECURITY_VIOLATION = "security_violation"
    PROMPT_INJECTION = "prompt_injection"
    PII_DETECTED = "pii_detected"
    ALL_SOURCES_FAILED = "all_sources_failed"
    CLARIFICATION_EXHAUSTED = "clarification_exhausted"
    QUALITY_THRESHOLD_FAILED = "quality_threshold_failed"
    HUMAN_REJECTED = "human_rejected"


class ApprovalStatus(str, Enum):
    """Status values for approval gate decisions.

    These track the state of human approval for proposed actions.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class GovernanceMetrics:
    """Standard governance metric names for consistent telemetry.

    All governance metrics are prefixed with 'ai_agent.governance.' to ensure
    they are grouped together in dashboards and monitors.
    """

    PREFIX = "ai_agent.governance"

    BUDGET_CHECK = f"{PREFIX}.budget_check"
    BUDGET_REMAINING = f"{PREFIX}.budget_remaining"
    ESCALATION = f"{PREFIX}.escalation"
    APPROVAL_REQUESTED = f"{PREFIX}.approval_requested"
    APPROVAL_DECISION = f"{PREFIX}.approval_decision"
    APPROVAL_LATENCY = f"{PREFIX}.approval_latency"
    SECURITY_CHECK = f"{PREFIX}.security_check"
    SECURITY_VIOLATION = f"{PREFIX}.security_violation"
    QUALITY_CHECK = f"{PREFIX}.quality_check"


class GovernanceTags:
    """Standard tag keys for governance metrics."""

    BUDGET_TYPE = "budget_type"
    REASON = "reason"
    ACTION_TYPE = "action_type"
    DECISION = "decision"
    CHECK_TYPE = "check_type"
    RESULT = "result"
