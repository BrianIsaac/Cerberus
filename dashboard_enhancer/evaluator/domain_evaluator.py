"""Domain-specific evaluator using Gemini as LLM-as-judge."""

import re
from dataclasses import dataclass
from typing import Any

import structlog
from ddtrace.llmobs.decorators import llm, workflow
from google import genai
from google.genai.types import GenerateContentConfig

from ..analyzer import AgentProfile
from ..config import settings
from ..mcp_client import DashboardMCPClient
from .evaluation_prompts import EvaluationPrompt, get_evaluations_for_agent_type

logger = structlog.get_logger()


@dataclass
class EvaluationResult:
    """Result of a single evaluation.

    Attributes:
        span_id: ID of the span that was evaluated.
        trace_id: ID of the trace containing the span.
        label: Evaluation label (e.g., 'syntax_validity', 'relevancy').
        metric_type: Type of metric ('score' or 'categorical').
        value: The evaluation value (float for score, string for categorical).
        success: Whether the evaluation completed successfully.
        error: Error message if evaluation failed.
    """

    span_id: str
    trace_id: str
    label: str
    metric_type: str
    value: str | float
    success: bool
    error: str | None = None


class DomainEvaluator:
    """Runs domain-specific evaluations on LLM Obs spans using Gemini.

    This evaluator:
    1. Fetches LLM Obs spans from Datadog
    2. Runs evaluations using Gemini as LLM-as-judge
    3. Submits evaluation results back to Datadog
    """

    def __init__(self, agent_profile: AgentProfile):
        """Initialise evaluator with agent profile.

        Args:
            agent_profile: Profile of the agent being evaluated.
        """
        self.agent_profile = agent_profile
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.vertex_location,
        )
        self.model = settings.gemini_model
        self.evaluations = get_evaluations_for_agent_type(
            agent_profile.agent_type,
            agent_profile.domain,
        )

    @workflow
    async def run_evaluations(
        self,
        hours_back: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Fetch spans and run all evaluations.

        Args:
            hours_back: Hours of spans to evaluate.
            limit: Maximum spans to evaluate.

        Returns:
            Summary of evaluation results.
        """
        logger.info(
            "starting_evaluations",
            service=self.agent_profile.service_name,
            evaluations_count=len(self.evaluations),
        )

        async with DashboardMCPClient() as mcp:
            status = await mcp.check_llm_obs_enabled(self.agent_profile.service_name)
            if not status.get("enabled"):
                return {
                    "success": False,
                    "error": "LLM Observability not enabled for this service",
                    "details": status.get("message"),
                }

            spans_result = await mcp.fetch_llm_obs_spans(
                ml_app=self.agent_profile.service_name,
                hours_back=hours_back,
                limit=limit,
                span_type="llm",
            )

            if "error" in spans_result:
                return {
                    "success": False,
                    "error": "Failed to fetch spans",
                    "details": spans_result.get("error"),
                }

            spans = spans_result.get("spans", [])
            if not spans:
                return {
                    "success": True,
                    "spans_evaluated": 0,
                    "message": "No spans found to evaluate",
                }

            all_results: list[EvaluationResult] = []

            for span in spans:
                if not span.get("input") or not span.get("output"):
                    continue

                span_results = await self._evaluate_span(span)
                all_results.extend(span_results)

            successful_results = [r for r in all_results if r.success]
            if successful_results:
                evaluations_to_submit = [
                    {
                        "span_id": r.span_id,
                        "trace_id": r.trace_id,
                        "ml_app": self.agent_profile.service_name,
                        "label": r.label,
                        "metric_type": r.metric_type,
                        "value": r.value,
                    }
                    for r in successful_results
                ]

                submit_result = await mcp.submit_evaluations_batch(evaluations_to_submit)

                if "error" in submit_result:
                    logger.error(
                        "evaluation_submit_failed", error=submit_result.get("error")
                    )

            logger.info(
                "evaluations_complete",
                spans_evaluated=len(spans),
                evaluations_run=len(all_results),
                successful=len(successful_results),
            )

            return {
                "success": True,
                "spans_evaluated": len(spans),
                "evaluations_run": len(all_results),
                "successful": len(successful_results),
                "failed": len(all_results) - len(successful_results),
                "evaluation_types": [e.label for e in self.evaluations],
            }

    async def _evaluate_span(self, span: dict) -> list[EvaluationResult]:
        """Run all evaluations on a single span.

        Args:
            span: Span data with input/output.

        Returns:
            List of evaluation results.
        """
        results = []

        for eval_prompt in self.evaluations:
            result = await self._run_single_evaluation(span, eval_prompt)
            results.append(result)

        return results

    @llm(model_name="gemini-2.0-flash", model_provider="google")
    async def _run_single_evaluation(
        self,
        span: dict,
        eval_prompt: EvaluationPrompt,
    ) -> EvaluationResult:
        """Run a single evaluation on a span.

        Args:
            span: Span data.
            eval_prompt: Evaluation configuration.

        Returns:
            Evaluation result.
        """
        try:
            prompt = eval_prompt.prompt_template.format(
                domain=self.agent_profile.domain,
                input=span.get("input", ""),
                output=span.get("output", ""),
            )

            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=50,
                ),
            )

            raw_value = (response.text or "").strip().lower()

            if eval_prompt.metric_type == "score":
                value = self._parse_score(raw_value, eval_prompt.score_range)
            else:
                value = self._parse_category(raw_value, eval_prompt.categories)

            return EvaluationResult(
                span_id=span.get("span_id", ""),
                trace_id=span.get("trace_id", ""),
                label=eval_prompt.label,
                metric_type=eval_prompt.metric_type,
                value=value,
                success=True,
            )

        except Exception as e:
            logger.warning(
                "evaluation_failed",
                label=eval_prompt.label,
                error=str(e),
            )
            return EvaluationResult(
                span_id=span.get("span_id", ""),
                trace_id=span.get("trace_id", ""),
                label=eval_prompt.label,
                metric_type=eval_prompt.metric_type,
                value=0 if eval_prompt.metric_type == "score" else "error",
                success=False,
                error=str(e),
            )

    def _parse_score(
        self,
        raw_value: str,
        score_range: tuple[float, float] | None,
    ) -> float:
        """Parse score from LLM response.

        Args:
            raw_value: Raw response text.
            score_range: Valid score range.

        Returns:
            Parsed score value.
        """
        match = re.search(r"(\d+\.?\d*)", raw_value)
        if match:
            score = float(match.group(1))
            if score_range:
                score = max(score_range[0], min(score_range[1], score))
            return score
        return 0.5

    def _parse_category(
        self,
        raw_value: str,
        categories: list[str] | None,
    ) -> str:
        """Parse category from LLM response.

        Args:
            raw_value: Raw response text.
            categories: Valid categories.

        Returns:
            Parsed category value.
        """
        if not categories:
            return raw_value

        for category in categories:
            if category.lower() in raw_value:
                return category

        return categories[0]
