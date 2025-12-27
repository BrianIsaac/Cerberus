"""Agent-specific governance configuration for ops_triage_agent.

This module provides factory functions for creating governance components
configured for the ops_triage_agent, using the shared governance module.
"""

from typing import Tuple

from ops_triage_agent.config import settings
from shared.governance import (
    ApprovalGate,
    BudgetTracker,
    EscalationHandler,
    EscalationReason,
    SecurityValidator,
)

AGENT_SERVICE = "ops-assistant"
AGENT_TYPE = "triage"


def create_budget_tracker() -> BudgetTracker:
    """Create a BudgetTracker with agent-specific settings.

    Returns:
        BudgetTracker configured with ops_triage_agent limits.
    """
    return BudgetTracker(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        max_steps=settings.agent_max_steps,
        max_model_calls=settings.agent_max_model_calls,
        max_tool_calls=settings.agent_max_tool_calls,
    )


def create_security_validator() -> SecurityValidator:
    """Create a SecurityValidator for this agent.

    Returns:
        SecurityValidator configured for ops_triage_agent.
        PII detection is set to warn but not block.
    """
    return SecurityValidator(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        block_on_pii=False,  # Log but don't block - rely on Datadog Sensitive Data Scanner
    )


def create_escalation_handler() -> EscalationHandler:
    """Create an EscalationHandler for this agent.

    Returns:
        EscalationHandler configured for ops_triage_agent.
    """
    return EscalationHandler(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
    )


def create_approval_gate() -> ApprovalGate:
    """Create an ApprovalGate for this agent.

    Returns:
        ApprovalGate configured for ops_triage_agent.
    """
    return ApprovalGate(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
    )


def validate_input(text: str) -> Tuple[bool, str | None]:
    """Validate user input using shared security validator.

    This is a convenience function that maintains backward compatibility
    with the original security.validate_input() function signature.

    Args:
        text: User input text to validate.

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    validator = create_security_validator()
    result = validator.validate_input(text)
    return result.is_valid, result.message


# Re-export EscalationReason for use in nodes.py
__all__ = [
    "AGENT_SERVICE",
    "AGENT_TYPE",
    "create_budget_tracker",
    "create_security_validator",
    "create_escalation_handler",
    "create_approval_gate",
    "validate_input",
    "EscalationReason",
]
