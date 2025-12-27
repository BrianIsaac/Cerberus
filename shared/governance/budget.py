"""Budget tracking for bounded autonomy.

This module provides the BudgetTracker class for tracking execution budgets
(steps, model calls, tool calls) and emitting governance metrics.
"""

from dataclasses import dataclass, field

from datadog import statsd

from shared.governance.constants import (
    GOVERNANCE_DEFAULTS,
    EscalationReason,
    GovernanceMetrics,
    GovernanceTags,
)
from shared.observability import build_tags


@dataclass
class BudgetTracker:
    """Tracks execution budgets and emits governance metrics.

    This class provides bounded autonomy by tracking the number of steps,
    model calls, and tool calls in a workflow. It emits metrics to Datadog
    for monitoring and alerting.

    Attributes:
        service: Service name for metrics tagging.
        agent_type: Agent type for metrics tagging.
        max_steps: Maximum workflow steps allowed.
        max_model_calls: Maximum LLM API calls allowed.
        max_tool_calls: Maximum tool/MCP calls allowed.
        step_count: Current number of steps taken.
        model_calls: Current number of model calls made.
        tool_calls: Current number of tool calls made.

    Example:
        tracker = BudgetTracker.from_config("my-agent", "triage")
        tracker.increment_step()
        if tracker.is_exceeded():
            return escalation.escalate_from_budget(tracker)
    """

    service: str
    agent_type: str
    max_steps: int = GOVERNANCE_DEFAULTS.max_steps
    max_model_calls: int = GOVERNANCE_DEFAULTS.max_model_calls
    max_tool_calls: int = GOVERNANCE_DEFAULTS.max_tool_calls

    step_count: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    tool_calls: int = field(default=0, init=False)

    def _emit_metric(
        self,
        metric: str,
        value: float,
        extra_tags: list[str] | None = None,
    ) -> None:
        """Emit a governance metric with standard tags.

        Args:
            metric: Metric name to emit.
            value: Value to emit.
            extra_tags: Additional tags to include.
        """
        tags = build_tags(self.service, self.agent_type, extra_tags)
        statsd.gauge(metric, value, tags=tags)

    def increment_step(self) -> None:
        """Increment step counter and emit remaining budget metric."""
        self.step_count += 1
        self._emit_metric(
            GovernanceMetrics.BUDGET_REMAINING,
            self.max_steps - self.step_count,
            [f"{GovernanceTags.BUDGET_TYPE}:steps"],
        )

    def increment_model_call(self) -> None:
        """Increment model call counter and emit remaining budget metric."""
        self.model_calls += 1
        self._emit_metric(
            GovernanceMetrics.BUDGET_REMAINING,
            self.max_model_calls - self.model_calls,
            [f"{GovernanceTags.BUDGET_TYPE}:model_calls"],
        )

    def increment_tool_call(self) -> None:
        """Increment tool call counter and emit remaining budget metric."""
        self.tool_calls += 1
        self._emit_metric(
            GovernanceMetrics.BUDGET_REMAINING,
            self.max_tool_calls - self.tool_calls,
            [f"{GovernanceTags.BUDGET_TYPE}:tool_calls"],
        )

    def check_budget(self, buffer: int = 0) -> EscalationReason | None:
        """Check if any budget is exceeded.

        Args:
            buffer: Optional buffer to trigger early escalation.
                   For example, buffer=2 would trigger escalation when
                   step_count >= max_steps - 2, leaving room for final steps.

        Returns:
            EscalationReason if budget exceeded, None otherwise.
        """
        if self.step_count >= self.max_steps - buffer:
            return EscalationReason.STEP_BUDGET_EXCEEDED
        if self.model_calls >= self.max_model_calls:
            return EscalationReason.MODEL_BUDGET_EXCEEDED
        if self.tool_calls >= self.max_tool_calls:
            return EscalationReason.TOOL_BUDGET_EXCEEDED
        return None

    def is_exceeded(self, buffer: int = 0) -> bool:
        """Check if any budget is exceeded.

        Args:
            buffer: Optional buffer for early escalation.

        Returns:
            True if any budget is exceeded, False otherwise.
        """
        return self.check_budget(buffer) is not None

    def get_state(self) -> dict[str, int]:
        """Return current budget state for serialisation.

        Returns:
            Dictionary containing current counts and limits.
        """
        return {
            "step_count": self.step_count,
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "max_steps": self.max_steps,
            "max_model_calls": self.max_model_calls,
            "max_tool_calls": self.max_tool_calls,
        }

    def reset(self) -> None:
        """Reset all budget counters to zero."""
        self.step_count = 0
        self.model_calls = 0
        self.tool_calls = 0

    @classmethod
    def from_config(
        cls,
        service: str,
        agent_type: str,
        max_steps: int | None = None,
        max_model_calls: int | None = None,
        max_tool_calls: int | None = None,
    ) -> "BudgetTracker":
        """Create a BudgetTracker with optional custom limits.

        Args:
            service: Service name for metrics tagging.
            agent_type: Agent type for metrics tagging.
            max_steps: Maximum steps (defaults to GOVERNANCE_DEFAULTS.max_steps).
            max_model_calls: Maximum model calls (defaults to GOVERNANCE_DEFAULTS.max_model_calls).
            max_tool_calls: Maximum tool calls (defaults to GOVERNANCE_DEFAULTS.max_tool_calls).

        Returns:
            Configured BudgetTracker instance.
        """
        return cls(
            service=service,
            agent_type=agent_type,
            max_steps=max_steps or GOVERNANCE_DEFAULTS.max_steps,
            max_model_calls=max_model_calls or GOVERNANCE_DEFAULTS.max_model_calls,
            max_tool_calls=max_tool_calls or GOVERNANCE_DEFAULTS.max_tool_calls,
        )
