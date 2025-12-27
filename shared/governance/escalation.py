"""Escalation handling for bounded autonomy.

This module provides the EscalationHandler class for consistent escalation
event handling with logging and metrics across all agents.
"""

from dataclasses import dataclass
from typing import Any

import structlog
from datadog import statsd

from shared.governance.budget import BudgetTracker
from shared.governance.constants import EscalationReason, GovernanceMetrics, GovernanceTags
from shared.observability import build_tags, emit_handoff_required

logger = structlog.get_logger()


@dataclass
class EscalationResult:
    """Result of an escalation event.

    Attributes:
        reason: The reason for escalation.
        message: Human-readable escalation message.
        partial_result: Any partial results collected before escalation.
        context: Additional context for debugging and audit.
    """

    reason: EscalationReason
    message: str
    partial_result: dict[str, Any] | None
    context: dict[str, Any]


# Default messages for each escalation reason
DEFAULT_ESCALATION_MESSAGES = {
    EscalationReason.STEP_BUDGET_EXCEEDED: "Maximum workflow steps exceeded",
    EscalationReason.MODEL_BUDGET_EXCEEDED: "Maximum LLM calls exceeded",
    EscalationReason.TOOL_BUDGET_EXCEEDED: "Maximum tool calls exceeded",
    EscalationReason.LOW_CONFIDENCE: "Confidence below threshold",
    EscalationReason.SECURITY_VIOLATION: "Security validation failed",
    EscalationReason.PROMPT_INJECTION: "Prompt injection detected",
    EscalationReason.PII_DETECTED: "PII detected in input",
    EscalationReason.ALL_SOURCES_FAILED: "All data sources failed",
    EscalationReason.CLARIFICATION_EXHAUSTED: "Maximum clarification attempts reached",
    EscalationReason.QUALITY_THRESHOLD_FAILED: "Output quality below threshold",
    EscalationReason.HUMAN_REJECTED: "Human reviewer rejected action",
}


class EscalationHandler:
    """Handles escalation events with consistent logging and metrics.

    This class provides a unified interface for escalating workflows to
    human review, ensuring consistent logging, metrics, and audit trails.

    Attributes:
        service: Service name for metrics tagging.
        agent_type: Agent type for metrics tagging.

    Example:
        handler = EscalationHandler("my-agent", "triage")
        if tracker.is_exceeded():
            result = handler.escalate_from_budget(tracker)
            return {"error": result.message, "escalated": True}
    """

    def __init__(self, service: str, agent_type: str) -> None:
        """Initialise the escalation handler.

        Args:
            service: Service name for metrics tagging.
            agent_type: Agent type for metrics tagging.
        """
        self.service = service
        self.agent_type = agent_type

    def _emit_escalation_metric(self, reason: EscalationReason) -> None:
        """Emit escalation metric with reason tag.

        Args:
            reason: The reason for escalation.
        """
        tags = build_tags(
            self.service,
            self.agent_type,
            [f"{GovernanceTags.REASON}:{reason.value}"],
        )
        statsd.increment(GovernanceMetrics.ESCALATION, tags=tags)
        emit_handoff_required(self.service, self.agent_type, reason.value)

    def escalate(
        self,
        reason: EscalationReason,
        message: str | None = None,
        partial_result: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> EscalationResult:
        """Record and emit an escalation event.

        This method logs the escalation, emits metrics, and returns a
        structured EscalationResult for the calling code to handle.

        Args:
            reason: The reason for escalation.
            message: Optional custom message (defaults to standard message).
            partial_result: Any partial results to include in the response.
            context: Additional context for debugging and audit.

        Returns:
            EscalationResult with all escalation details.
        """
        final_message = message or DEFAULT_ESCALATION_MESSAGES.get(
            reason, f"Escalation: {reason.value}"
        )
        final_context = context or {}

        logger.warning(
            "Workflow escalated to human",
            service=self.service,
            agent_type=self.agent_type,
            reason=reason.value,
            message=final_message,
            **final_context,
        )

        self._emit_escalation_metric(reason)

        return EscalationResult(
            reason=reason,
            message=final_message,
            partial_result=partial_result,
            context=final_context,
        )

    def escalate_from_budget(
        self,
        tracker: BudgetTracker,
        partial_result: dict[str, Any] | None = None,
    ) -> EscalationResult | None:
        """Check budget and escalate if exceeded.

        This is a convenience method that checks the budget tracker and
        escalates with appropriate context if any budget is exceeded.

        Args:
            tracker: BudgetTracker to check.
            partial_result: Any partial results to include.

        Returns:
            EscalationResult if budget exceeded, None otherwise.
        """
        reason = tracker.check_budget()
        if reason:
            return self.escalate(
                reason=reason,
                context=tracker.get_state(),
                partial_result=partial_result,
            )
        return None

    def escalate_from_confidence(
        self,
        confidence: float,
        threshold: float,
        partial_result: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> EscalationResult | None:
        """Escalate if confidence is below threshold.

        Args:
            confidence: Current confidence score.
            threshold: Minimum required confidence.
            partial_result: Any partial results to include.
            context: Additional context for debugging.

        Returns:
            EscalationResult if confidence below threshold, None otherwise.
        """
        if confidence < threshold:
            escalation_context = context or {}
            escalation_context.update({
                "confidence": confidence,
                "threshold": threshold,
            })
            return self.escalate(
                reason=EscalationReason.LOW_CONFIDENCE,
                message=f"Confidence {confidence:.2f} below threshold {threshold:.2f}",
                partial_result=partial_result,
                context=escalation_context,
            )
        return None
