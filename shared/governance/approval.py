"""Human approval gate for bounded autonomy.

This module provides the ApprovalGate class for managing human-in-the-loop
approval workflows with consistent formatting and metrics.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import structlog
from datadog import statsd

from shared.governance.constants import (
    GOVERNANCE_DEFAULTS,
    ApprovalStatus,
    GovernanceMetrics,
    GovernanceTags,
)
from shared.observability import build_tags

logger = structlog.get_logger()


@dataclass
class ProposedAction:
    """Action proposed for human approval.

    Attributes:
        action_type: Type of action (e.g., 'create_incident', 'code_execution').
        title: Short title describing the action.
        description: Detailed description of what will happen.
        severity: Optional severity level (e.g., 'low', 'medium', 'high').
        evidence: List of evidence items supporting the action.
        context: Additional context for the reviewer.
    """

    action_type: str
    title: str
    description: str
    severity: str | None = None
    evidence: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalDecision:
    """Result of human approval decision.

    Attributes:
        status: The approval status (approved, rejected, etc.).
        decision_text: The raw text of the human's decision.
        approved_action: The action that was approved (if approved).
        latency_ms: Time taken for the human to decide in milliseconds.
    """

    status: ApprovalStatus
    decision_text: str | None
    approved_action: ProposedAction | None
    latency_ms: float


class ApprovalGate:
    """Manages human approval gates for write operations.

    This class provides a unified interface for requesting human approval
    for proposed actions, with consistent formatting, logging, and metrics.

    Attributes:
        service: Service name for metrics tagging.
        agent_type: Agent type for metrics tagging.

    Example:
        gate = ApprovalGate("my-agent", "triage")
        action = ProposedAction(
            action_type="create_incident",
            title="Create P2 Incident",
            description="API latency degradation detected",
            severity="medium",
        )
        decision = gate.request_approval(action, interrupt_fn=interrupt)
        if decision.status == ApprovalStatus.APPROVED:
            execute_action(decision.approved_action)
    """

    def __init__(self, service: str, agent_type: str) -> None:
        """Initialise the approval gate.

        Args:
            service: Service name for metrics tagging.
            agent_type: Agent type for metrics tagging.
        """
        self.service = service
        self.agent_type = agent_type

    def _emit_approval_metric(self, metric: str, tags: list[str]) -> None:
        """Emit approval-related metric.

        Args:
            metric: Metric name to emit.
            tags: Additional tags to include.
        """
        base_tags = build_tags(self.service, self.agent_type)
        statsd.increment(metric, tags=base_tags + tags)

    def _emit_approval_latency(self, latency_ms: float) -> None:
        """Emit approval latency histogram.

        Args:
            latency_ms: Time taken for approval in milliseconds.
        """
        tags = build_tags(self.service, self.agent_type)
        statsd.histogram(GovernanceMetrics.APPROVAL_LATENCY, latency_ms, tags=tags)

    def format_approval_message(self, action: ProposedAction) -> str:
        """Format a human-readable approval request message.

        Args:
            action: The proposed action to format.

        Returns:
            Formatted message string for human review.
        """
        lines = [
            f"## Approval Required: {action.action_type.upper()}",
            "",
            f"**Title**: {action.title}",
            f"**Severity**: {action.severity or 'Not specified'}",
            "",
            "### Description",
            action.description,
            "",
        ]

        if action.evidence:
            lines.extend([
                "### Evidence",
                *[f"- {e}" for e in action.evidence],
                "",
            ])

        if action.context:
            lines.extend([
                "### Context",
                *[f"- **{k}**: {v}" for k, v in action.context.items()],
                "",
            ])

        lines.extend([
            "---",
            "Please respond with: **approve**, **reject**, or **edit**",
        ])

        return "\n".join(lines)

    def request_approval(
        self,
        action: ProposedAction,
        interrupt_fn: Callable[[str], str],
    ) -> ApprovalDecision:
        """Request human approval for a proposed action.

        This method formats an approval message, calls the interrupt function
        to pause the workflow for human input, and records the decision.

        Args:
            action: The proposed action requiring approval.
            interrupt_fn: Function to interrupt workflow and get human input.
                         Typically LangGraph's `interrupt()` or similar.

        Returns:
            ApprovalDecision with the human's decision.
        """
        self._emit_approval_metric(
            GovernanceMetrics.APPROVAL_REQUESTED,
            [f"{GovernanceTags.ACTION_TYPE}:{action.action_type}"],
        )

        message = self.format_approval_message(action)

        start_time = time.perf_counter()
        decision_text = interrupt_fn(message)
        latency_ms = (time.perf_counter() - start_time) * 1000

        self._emit_approval_latency(latency_ms)

        # Parse decision
        decision_lower = (decision_text or "").strip().lower()
        if decision_lower in ("approve", "approved", "yes", "y"):
            status = ApprovalStatus.APPROVED
        elif decision_lower in ("edit", "modify"):
            status = ApprovalStatus.APPROVED  # Treat edit as approve for now
        else:
            status = ApprovalStatus.REJECTED

        self._emit_approval_metric(
            GovernanceMetrics.APPROVAL_DECISION,
            [
                f"{GovernanceTags.ACTION_TYPE}:{action.action_type}",
                f"{GovernanceTags.DECISION}:{status.value}",
            ],
        )

        logger.info(
            "Approval decision received",
            service=self.service,
            action_type=action.action_type,
            status=status.value,
            latency_ms=latency_ms,
        )

        return ApprovalDecision(
            status=status,
            decision_text=decision_text,
            approved_action=action if status == ApprovalStatus.APPROVED else None,
            latency_ms=latency_ms,
        )

    def check_requires_approval(
        self,
        has_write_intent: bool,
        confidence: float | None = None,
        confidence_threshold: float = GOVERNANCE_DEFAULTS.confidence_threshold,
        force_approval: bool = False,
    ) -> bool:
        """Determine if an action requires human approval.

        Args:
            has_write_intent: Whether the action involves writes.
            confidence: Optional confidence score.
            confidence_threshold: Threshold below which approval is required.
            force_approval: Always require approval regardless of other factors.

        Returns:
            True if approval is required, False otherwise.
        """
        if force_approval:
            return True
        if has_write_intent:
            return True
        if confidence is not None and confidence < confidence_threshold:
            return True
        return False

    def skip_approval(self, reason: str) -> ApprovalDecision:
        """Create a skipped approval decision.

        Use this when approval is not required but you need a decision record.

        Args:
            reason: Reason for skipping approval.

        Returns:
            ApprovalDecision with SKIPPED status.
        """
        logger.info(
            "Approval skipped",
            service=self.service,
            reason=reason,
        )
        return ApprovalDecision(
            status=ApprovalStatus.SKIPPED,
            decision_text=reason,
            approved_action=None,
            latency_ms=0.0,
        )
