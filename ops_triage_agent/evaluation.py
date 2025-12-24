"""Custom quality evaluation submission for LLM Observability.

This module provides functions to submit custom evaluations to Datadog
LLM Observability, complementing the managed RAGAS evaluations configured
via DD_LLMOBS_EVALUATORS environment variable.
"""

import structlog
from ddtrace.llmobs import LLMObs

from app.observability import emit_quality_metric

logger = structlog.get_logger()


def submit_hypothesis_quality_evaluation(
    span_context: dict,
    hypothesis_count: int,
    avg_confidence: float,
    evidence_coverage: float,
) -> None:
    """Submit quality evaluations for hypothesis generation.

    Args:
        span_context: LLMObs span context from the synthesis node
        hypothesis_count: Number of hypotheses generated
        avg_confidence: Average confidence across hypotheses (0.0-1.0)
        evidence_coverage: Ratio of hypotheses with evidence citations (0.0-1.0)
    """
    quality_score = avg_confidence * evidence_coverage

    LLMObs.submit_evaluation(
        span=span_context,
        ml_app="ops-assistant",
        label="hypothesis_quality",
        metric_type="score",
        value=quality_score,
        tags={
            "hypothesis_count": str(hypothesis_count),
            "evaluator": "custom",
        },
    )

    LLMObs.submit_evaluation(
        span=span_context,
        ml_app="ops-assistant",
        label="evidence_coverage",
        metric_type="score",
        value=evidence_coverage,
        tags={"evaluator": "custom"},
    )

    emit_quality_metric("hypothesis_confidence", avg_confidence)
    emit_quality_metric("evidence_coverage", evidence_coverage)

    logger.info(
        "quality_evaluation_submitted",
        evaluation_type="hypothesis_quality",
        avg_confidence=avg_confidence,
        evidence_coverage=evidence_coverage,
        quality_score=round(quality_score, 3),
    )


def submit_intake_quality_evaluation(
    span_context: dict,
    confidence: float,
    extracted_params: int,
    required_clarification: bool,
) -> None:
    """Submit quality evaluations for intake classification.

    Args:
        span_context: LLMObs span context from the intake node
        confidence: Classification confidence (0.0-1.0)
        extracted_params: Number of parameters extracted from input
        required_clarification: Whether clarification was needed from user
    """
    LLMObs.submit_evaluation(
        span=span_context,
        ml_app="ops-assistant",
        label="intake_quality",
        metric_type="score",
        value=confidence,
        tags={
            "extracted_params": str(extracted_params),
            "required_clarification": str(required_clarification).lower(),
            "evaluator": "custom",
        },
    )

    LLMObs.submit_evaluation(
        span=span_context,
        ml_app="ops-assistant",
        label="first_pass_success",
        metric_type="categorical",
        value="yes" if not required_clarification else "no",
        tags={"evaluator": "custom"},
    )

    emit_quality_metric("intake_confidence", confidence)

    logger.info(
        "quality_evaluation_submitted",
        evaluation_type="intake_quality",
        confidence=confidence,
        extracted_params=extracted_params,
        required_clarification=required_clarification,
    )


def submit_escalation_evaluation(
    span_context: dict,
    reason: str,
    step_count: int,
) -> None:
    """Submit evaluation when escalation occurs.

    Args:
        span_context: LLMObs span context from the workflow
        reason: Reason for escalation (e.g., low_confidence, budget_exceeded)
        step_count: Steps taken before escalation
    """
    LLMObs.submit_evaluation(
        span=span_context,
        ml_app="ops-assistant",
        label="escalation",
        metric_type="categorical",
        value=reason,
        tags={
            "step_count": str(step_count),
            "evaluator": "custom",
        },
    )

    logger.info(
        "quality_evaluation_submitted",
        evaluation_type="escalation",
        reason=reason,
        step_count=step_count,
    )
