"""Agent-specific governance configuration for sas_generator.

This module provides factory functions for creating governance components
configured for the sas_generator, using the shared governance module.
"""

from shared.governance import (
    ApprovalGate,
    BudgetTracker,
    EscalationHandler,
    EscalationReason,
    ProposedAction,
    SecurityValidator,
)

AGENT_SERVICE = "sas-generator"
AGENT_TYPE = "code-generation"


def create_budget_tracker() -> BudgetTracker:
    """Create a BudgetTracker with agent-specific settings.

    SAS generator has a simpler workflow, so we use lower limits.

    Returns:
        BudgetTracker configured with sas_generator limits.
    """
    return BudgetTracker(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        max_steps=4,  # Simpler workflow than triage
        max_model_calls=3,  # Main generation + quality check + optional retry
        max_tool_calls=4,  # Schema + sample + validate + optional retry
    )


def create_security_validator() -> SecurityValidator:
    """Create a SecurityValidator for code generation.

    Returns:
        SecurityValidator configured for sas_generator.
    """
    return SecurityValidator(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
        block_on_pii=False,
    )


def create_escalation_handler() -> EscalationHandler:
    """Create an EscalationHandler for this agent.

    Returns:
        EscalationHandler configured for sas_generator.
    """
    return EscalationHandler(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
    )


def create_approval_gate() -> ApprovalGate:
    """Create an ApprovalGate for this agent.

    Returns:
        ApprovalGate configured for sas_generator.
    """
    return ApprovalGate(
        service=AGENT_SERVICE,
        agent_type=AGENT_TYPE,
    )


def create_code_review_action(
    query: str,
    code: str,
    explanation: str,
    quality_score: float,
) -> ProposedAction:
    """Create a ProposedAction for code review approval.

    Args:
        query: Original user query.
        code: Generated SAS code.
        explanation: Explanation of the code.
        quality_score: Quality score from LLM-as-judge.

    Returns:
        ProposedAction for human review.
    """
    return ProposedAction(
        action_type="code_execution",
        title=f"SAS Code Generation: {query[:50]}...",
        description=explanation,
        severity="low" if quality_score >= 0.8 else "medium",
        evidence=[
            f"Quality Score: {quality_score:.2f}",
            f"Code Length: {len(code)} characters",
        ],
        context={
            "query": query,
            "code_preview": code[:500] + "..." if len(code) > 500 else code,
        },
    )


__all__ = [
    "AGENT_SERVICE",
    "AGENT_TYPE",
    "create_budget_tracker",
    "create_security_validator",
    "create_escalation_handler",
    "create_approval_gate",
    "create_code_review_action",
    "EscalationReason",
]
