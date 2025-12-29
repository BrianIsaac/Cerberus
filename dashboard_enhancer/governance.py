"""Governance factories for Dashboard Enhancement Agent."""

from shared.governance import (
    BudgetTracker,
    EscalationHandler,
    SecurityValidator,
)

from .config import settings

AGENT_SERVICE = "dashboard-enhancer"
AGENT_TYPE = "analysis"


def create_budget_tracker() -> BudgetTracker:
    """Create a budget tracker for the enhancement workflow.

    Returns:
        Configured BudgetTracker instance.
    """
    return BudgetTracker(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        max_steps=settings.agent_max_steps,
        max_model_calls=settings.agent_max_model_calls,
        max_tool_calls=settings.agent_max_tool_calls,
    )


def create_security_validator() -> SecurityValidator:
    """Create a security validator for input validation.

    Returns:
        Configured SecurityValidator instance.
    """
    return SecurityValidator(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        max_input_length=50000,
        block_on_pii=False,
    )


def create_escalation_handler() -> EscalationHandler:
    """Create an escalation handler for the agent.

    Returns:
        Configured EscalationHandler instance.
    """
    return EscalationHandler(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
    )
