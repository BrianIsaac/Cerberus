"""Shared governance module for bounded autonomy across all agents.

This module provides reusable components for implementing bounded autonomy
following the "Measuring Agents in Production" paper recommendations:
- Budget tracking and enforcement
- Security validation (prompt injection, PII)
- Human approval gates
- Escalation handling

Example usage:
    from shared.governance import (
        BudgetTracker,
        SecurityValidator,
        EscalationHandler,
        ApprovalGate,
        GOVERNANCE_DEFAULTS,
    )

    # Create components for your agent
    tracker = BudgetTracker.from_config("my-agent", "my-type")
    validator = SecurityValidator("my-agent", "my-type")
    escalation = EscalationHandler("my-agent", "my-type")
    approval = ApprovalGate("my-agent", "my-type")

    # Use in workflow
    tracker.increment_step()
    if tracker.is_exceeded():
        return escalation.escalate_from_budget(tracker)
"""

from shared.governance.approval import (
    ApprovalDecision,
    ApprovalGate,
    ProposedAction,
)
from shared.governance.budget import BudgetTracker
from shared.governance.constants import (
    GOVERNANCE_DEFAULTS,
    ApprovalStatus,
    EscalationReason,
    GovernanceDefaults,
    GovernanceMetrics,
    GovernanceTags,
)
from shared.governance.escalation import (
    EscalationHandler,
    EscalationResult,
)
from shared.governance.security import (
    PII_PATTERNS,
    PROMPT_INJECTION_PATTERNS,
    SecurityValidator,
    ValidationResult,
)

__all__ = [
    # Constants
    "GOVERNANCE_DEFAULTS",
    "GovernanceDefaults",
    "EscalationReason",
    "ApprovalStatus",
    "GovernanceMetrics",
    "GovernanceTags",
    # Budget tracking
    "BudgetTracker",
    # Security
    "SecurityValidator",
    "ValidationResult",
    "PROMPT_INJECTION_PATTERNS",
    "PII_PATTERNS",
    # Escalation
    "EscalationHandler",
    "EscalationResult",
    # Approval
    "ApprovalGate",
    "ProposedAction",
    "ApprovalDecision",
]
