"""Prompt templates for ops assistant LLM interactions."""

from app.prompts.incident_v1 import (
    INCIDENT_DRAFT_SYSTEM_PROMPT,
    INCIDENT_DRAFT_USER_TEMPLATE,
)
from app.prompts.intake_v1 import (
    CLARIFICATION_PROMPT,
    INTAKE_SYSTEM_PROMPT,
    INTAKE_USER_TEMPLATE,
)
from app.prompts.synthesis_v1 import (
    SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_USER_TEMPLATE,
)

__all__ = [
    "INTAKE_SYSTEM_PROMPT",
    "INTAKE_USER_TEMPLATE",
    "CLARIFICATION_PROMPT",
    "SYNTHESIS_SYSTEM_PROMPT",
    "SYNTHESIS_USER_TEMPLATE",
    "INCIDENT_DRAFT_SYSTEM_PROMPT",
    "INCIDENT_DRAFT_USER_TEMPLATE",
]
