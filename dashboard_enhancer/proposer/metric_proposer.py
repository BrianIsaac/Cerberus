"""LLM-driven metric proposal for personalised observability."""

import json
import re
from dataclasses import dataclass

import structlog
from ddtrace.llmobs.decorators import llm
from google import genai
from google.genai.types import GenerateContentConfig

from ..config import settings
from ..discovery import ServiceDiscovery

logger = structlog.get_logger()


@dataclass
class ProposedMetric:
    """A metric proposed by the LLM.

    Attributes:
        metric_id: Proposed metric identifier.
        description: What this metric measures.
        aggregation_type: Either 'count' or 'distribution'.
        filter_query: Span filter for this metric.
        group_by: Optional grouping tags.
        widget_title: Suggested widget title.
        widget_type: Suggested widget type.
        rationale: Why this metric is useful for this service.
    """

    metric_id: str
    description: str
    aggregation_type: str
    filter_query: str
    group_by: list[dict] | None = None
    widget_title: str = ""
    widget_type: str = "timeseries"
    rationale: str = ""

    def generate_queries(self, service: str) -> dict[str, str]:
        """Generate valid Datadog query templates.

        Args:
            service: Service name for filter.

        Returns:
            Dict of query templates keyed by aggregation.
        """
        service_filter = f"service:{service}"
        queries = {}

        if self.aggregation_type == "count":
            queries["sum"] = f"sum:{self.metric_id}{{{service_filter}}}"
            queries["avg"] = f"avg:{self.metric_id}{{{service_filter}}}"
            if self.group_by:
                tag = self.group_by[0].get("tag_name", "")
                queries["sum_by"] = f"sum:{self.metric_id}{{{service_filter}}} by {{{tag}}}"
        else:  # distribution
            queries["avg"] = f"avg:{self.metric_id}{{{service_filter}}}"
            queries["p50"] = f"p50:{self.metric_id}{{{service_filter}}}"
            queries["p95"] = f"p95:{self.metric_id}{{{service_filter}}}"
            queries["p99"] = f"p99:{self.metric_id}{{{service_filter}}}"
            if self.group_by:
                tag = self.group_by[0].get("tag_name", "")
                queries["p95_by"] = f"p95:{self.metric_id}{{{service_filter}}} by {{{tag}}}"

        return queries


class MetricProposer:
    """Proposes personalised metrics using LLM analysis."""

    PROPOSAL_PROMPT = '''You are designing personalised observability metrics for an AI agent service.

## Service Discovery Results

**Service**: {service}
**Domain**: {domain}
**Agent Type**: {agent_type}
**LLM Provider**: {llm_provider}
**Framework**: {framework}

**Discovered Operations** (from code/traces):
{operations}

**Existing Metrics** (already being collected):
{existing_metrics}

**LLMObs Span Types**:
{span_types}

## Your Task

Propose 3-6 PERSONALISED metrics that are UNIQUE to this service's business logic and domain.

**DO NOT propose generic metrics like**:
- Request count/latency (already in shared dashboard)
- LLM call count/duration (already in shared dashboard)
- Error rates (already in shared dashboard)
- Token usage (already in shared dashboard)

**DO propose domain-specific metrics like**:
- For SAS generator: code_generation.success, syntax_validation.failures, template.usage
- For Ops assistant: ticket.classification.accuracy, runbook.execution.success
- For Dashboard enhancer: widget.generation.count, metric.provisioning.success

## Output Format

Return a JSON array of proposed metrics. Each metric must have:
- metric_id: Snake_case identifier starting with service name (e.g., "sas_generator.code.success")
- description: What this metric measures
- aggregation_type: "count" or "distribution"
- filter_query: Span filter (e.g., "service:{service} @operation:generate_code")
- group_by: Optional array of {{"path": "@field", "tag_name": "tag"}}
- widget_title: Human-readable title for dashboard widget
- widget_type: "timeseries", "query_value", or "toplist"
- rationale: Why this metric is valuable for this specific service

Return ONLY the JSON array, no explanation.'''

    def __init__(self) -> None:
        """Initialise Gemini client."""
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.vertex_location,
        )
        self.model = settings.gemini_model

    @llm(model_name="gemini-2.0-flash", model_provider="google")
    async def propose_metrics(
        self,
        discovery: ServiceDiscovery,
    ) -> list[ProposedMetric]:
        """Propose personalised metrics based on discovery.

        Args:
            discovery: Service discovery results.

        Returns:
            List of proposed metrics.
        """
        logger.info(
            "proposing_metrics",
            service=discovery.service_name,
            domain=discovery.domain,
        )

        prompt = self.PROPOSAL_PROMPT.format(
            service=discovery.service_name,
            domain=discovery.domain,
            agent_type=discovery.agent_type,
            llm_provider=discovery.llm_provider,
            framework=discovery.framework,
            operations="\n".join(f"- {op}" for op in discovery.discovered_operations) or "None discovered",
            existing_metrics="\n".join(f"- {m}" for m in discovery.discovered_metrics) or "None found",
            span_types=", ".join(discovery.llmobs_span_types) or "None found",
        )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )

        return self._parse_response(response.text or "", discovery.service_name)

    def _parse_response(
        self,
        response_text: str,
        service: str,
    ) -> list[ProposedMetric]:
        """Parse LLM response into ProposedMetric objects.

        Args:
            response_text: Raw LLM response.
            service: Service name for validation.

        Returns:
            List of ProposedMetric objects.
        """
        text = response_text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        try:
            metrics_data = json.loads(text)
            if not isinstance(metrics_data, list):
                metrics_data = [metrics_data]
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e))
            return []

        proposed = []
        for m in metrics_data:
            metric_id = m.get("metric_id", "")
            if not metric_id or not self._validate_metric_id(metric_id, service):
                continue

            proposed.append(
                ProposedMetric(
                    metric_id=metric_id,
                    description=m.get("description", ""),
                    aggregation_type=m.get("aggregation_type", "count"),
                    filter_query=m.get("filter_query", f"service:{service}"),
                    group_by=m.get("group_by"),
                    widget_title=m.get("widget_title", metric_id),
                    widget_type=m.get("widget_type", "timeseries"),
                    rationale=m.get("rationale", ""),
                )
            )

        logger.info("metrics_proposed", count=len(proposed))
        return proposed

    def _validate_metric_id(self, metric_id: str, service: str) -> bool:
        """Validate metric ID format.

        Args:
            metric_id: Proposed metric ID.
            service: Expected service name.

        Returns:
            True if valid.
        """
        if not re.match(r"^[a-z][a-z0-9_.]+$", metric_id):
            return False

        normalised_service = service.replace("-", "_")
        if not metric_id.startswith(normalised_service):
            return False

        return True
