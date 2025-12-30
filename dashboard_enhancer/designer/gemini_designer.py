"""Gemini-powered widget design for domain-specific dashboards."""

import json
import re
from typing import Any

import structlog
from ddtrace.llmobs.decorators import llm
from google import genai
from google.genai.types import GenerateContentConfig

from ..analyzer import AgentProfile, TelemetryProfile
from ..config import settings
from ..discovery import ServiceDiscovery
from .templates import get_base_widgets

logger = structlog.get_logger()


class GeminiWidgetDesigner:
    """Uses Vertex AI Gemini to design domain-specific widgets."""

    SYSTEM_PROMPT = """You are a Datadog dashboard expert specialising in AI/LLM observability.
Your task is to design dashboard widgets using REAL metrics that have been provisioned.

Guidelines:
1. Use ONLY the metrics provided in the "Provisioned Metrics" section
2. Use ONLY the evaluation labels provided in the "Available Evaluations" section
3. For evaluation metrics, use query format: avg:llmobs.evaluation.<label>{ml_app:<service>}
4. For span-based metrics, use the exact metric ID provided
5. Widget titles should reflect the agent's domain
6. Each widget should tell a story about the agent's performance
7. Use appropriate widget types: timeseries for trends, query_value for KPIs, toplist for rankings

Output valid JSON only. No markdown, no explanation."""

    def __init__(self) -> None:
        """Initialise Gemini client."""
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.vertex_location,
        )
        self.model = settings.gemini_model

    @llm(model_name="gemini-2.0-flash", model_provider="google")
    async def design_widgets(
        self,
        agent_profile: AgentProfile,
        telemetry_profile: TelemetryProfile,
        provisioned_metrics: list[dict] | None = None,
        evaluation_labels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Design domain-specific widgets using Gemini.

        Args:
            agent_profile: Profile of the agent being enhanced.
            telemetry_profile: Available telemetry from Datadog.
            provisioned_metrics: Metrics provisioned for this agent.
            evaluation_labels: Evaluation labels configured for this agent.

        Returns:
            List of widget definitions.
        """
        logger.info(
            "designing_widgets",
            service=agent_profile.service_name,
            domain=agent_profile.domain,
            provisioned_metrics_count=len(provisioned_metrics or []),
            evaluation_labels_count=len(evaluation_labels or []),
        )

        prompt = self._build_prompt(
            agent_profile,
            telemetry_profile,
            provisioned_metrics or [],
            evaluation_labels or [],
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4096,
                ),
            )

            widgets = self._parse_response(response.text or "")

            logger.info(
                "widgets_designed",
                count=len(widgets),
                service=agent_profile.service_name,
            )

            return widgets

        except Exception as e:
            logger.error("widget_design_failed", error=str(e))
            base_widgets = get_base_widgets(agent_profile.agent_type)
            return self._apply_base_widgets(base_widgets, agent_profile)

    def _build_prompt(
        self,
        agent_profile: AgentProfile,
        telemetry_profile: TelemetryProfile,
        provisioned_metrics: list[dict],
        evaluation_labels: list[str],
    ) -> str:
        """Build the prompt for Gemini.

        Args:
            agent_profile: Profile of the agent.
            telemetry_profile: Available telemetry.
            provisioned_metrics: Metrics that were provisioned.
            evaluation_labels: Available evaluation labels.

        Returns:
            Formatted prompt string.
        """
        return f"""Design 4-8 dashboard widgets for this AI agent:

## Agent Profile
- Service: {agent_profile.service_name}
- Type: {agent_profile.agent_type}
- Domain: {agent_profile.domain}
- Description: {agent_profile.description}
- LLM Provider: {agent_profile.llm_provider}
- Framework: {agent_profile.framework}

## Provisioned Metrics (use these exact metric IDs)
{json.dumps(provisioned_metrics, indent=2)}

## Available Evaluations (query as: avg:llmobs.evaluation.<label>{{ml_app:{agent_profile.service_name}}})
{json.dumps(evaluation_labels, indent=2)}

## Automatic Trace Metrics (always available)
- trace.{agent_profile.framework.lower()}.request.hits{{service:{agent_profile.service_name}}}
- trace.{agent_profile.framework.lower()}.request.errors{{service:{agent_profile.service_name}}}
- p95:trace.{agent_profile.framework.lower()}.request{{service:{agent_profile.service_name}}}

## Requirements
1. Generate 4-8 widgets as a JSON array
2. Each widget must have: type, title, query, description
3. Include at least one widget for each evaluation label
4. Include widgets for LLM-specific metrics if available
5. Titles must be domain-specific
6. Use formulas where useful (e.g., error rate = errors / hits * 100)

Return ONLY a JSON array of widget definitions."""

    def _parse_response(self, response_text: str) -> list[dict]:
        """Parse Gemini response to extract widgets.

        Args:
            response_text: Raw response from Gemini.

        Returns:
            List of widget definitions.
        """
        text = response_text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        try:
            widgets = json.loads(text)
            if isinstance(widgets, list):
                widgets = self._fix_widget_queries(widgets)
                return widgets
            elif isinstance(widgets, dict) and "widgets" in widgets:
                widgets = self._fix_widget_queries(widgets["widgets"])
                return widgets
            else:
                return self._fix_widget_queries([widgets])
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e), text=text[:200])
            return []

    def _fix_widget_queries(self, widgets: list[dict]) -> list[dict]:
        """Fix common issues in widget queries from LLM output.

        Args:
            widgets: List of widget definitions.

        Returns:
            List of widgets with fixed queries.
        """
        for widget in widgets:
            if "query" in widget and isinstance(widget["query"], str):
                # Fix double braces - LLM sometimes outputs {{tag:value}} instead of {tag:value}
                widget["query"] = re.sub(r"\{\{([^}]+)\}\}", r"{\1}", widget["query"])
        return widgets

    def _apply_base_widgets(
        self,
        base_widgets: list[dict],
        agent_profile: AgentProfile,
    ) -> list[dict]:
        """Apply base widgets with simple substitution as fallback.

        Args:
            base_widgets: Base widget templates.
            agent_profile: Agent profile for substitution.

        Returns:
            List of widget definitions with substituted values.
        """
        result = []
        for template in base_widgets:
            widget = template.copy()
            widget["title"] = widget["title"].format(domain=agent_profile.domain)
            widget["query"] = widget["query"].format(service=agent_profile.service_name)
            result.append(widget)
        return result


class PersonalisedWidgetDesigner:
    """Designs personalised widget group for a service."""

    DESIGN_PROMPT = '''You are designing a personalised dashboard widget group for an AI agent.

## Service Context

**Service**: {service}
**Domain**: {domain}
**Agent Type**: {agent_type}

## Available Metrics (with valid queries)

These metrics have been provisioned. Each has pre-generated Datadog queries:

{metrics_json}

## Your Task

Design a widget group that tells a story about this service's unique operations.

1. Select the most valuable 4-6 widgets from the available metrics
2. Write compelling, domain-specific titles (e.g., "SAS Code Generation Success" not "Count Metric")
3. Add brief descriptions explaining business value
4. Choose the best query for each widget (usually "sum" for counts, "p95" for latency)
5. Order widgets logically (overview first, then details)

## Output Format

Return JSON with:
- group_title: Title for the widget group (e.g., "SAS Generator Analytics")
- widgets: Array of widget definitions

Each widget must have:
- title: Domain-specific title
- type: Keep the suggested type (timeseries, query_value, toplist)
- query: Copy EXACTLY from the available queries (do NOT modify!)
- description: Brief business value explanation

CRITICAL: Copy the query field EXACTLY as provided. Do not modify queries.

Return ONLY the JSON, no explanation.'''

    def __init__(self) -> None:
        """Initialise Gemini client."""
        self.client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.vertex_location,
        )
        self.model = settings.gemini_model

    @llm(model_name="gemini-2.0-flash", model_provider="google")
    async def design_widget_group(
        self,
        discovery: ServiceDiscovery,
        provisioned_metrics: list[dict],
    ) -> dict[str, Any]:
        """Design personalised widget group.

        Args:
            discovery: Service discovery results.
            provisioned_metrics: Provisioned metrics with queries.

        Returns:
            Widget group definition with title and widgets.
        """
        valid_metrics = [
            m for m in provisioned_metrics
            if m.get("status") in ("created", "exists", "pending")
        ]

        if not valid_metrics:
            logger.warning("no_valid_metrics", service=discovery.service_name)
            return {
                "group_title": f"{discovery.domain.title()} Analytics",
                "widgets": [],
            }

        metrics_json = json.dumps(
            [
                {
                    "metric_id": m["id"],
                    "description": m.get("widget_config", {}).get("description", ""),
                    "type": m.get("widget_config", {}).get("type", "timeseries"),
                    "queries": m.get("queries", {}),
                    "rationale": m.get("widget_config", {}).get("rationale", ""),
                }
                for m in valid_metrics
            ],
            indent=2,
        )

        prompt = self.DESIGN_PROMPT.format(
            service=discovery.service_name,
            domain=discovery.domain,
            agent_type=discovery.agent_type,
            metrics_json=metrics_json,
        )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )

        return self._parse_response(
            response.text or "",
            discovery,
            valid_metrics,
        )

    def _parse_response(
        self,
        response_text: str,
        discovery: ServiceDiscovery,
        valid_metrics: list[dict],
    ) -> dict[str, Any]:
        """Parse LLM response and validate queries.

        Args:
            response_text: Raw LLM response.
            discovery: Service discovery for fallback.
            valid_metrics: Valid metrics for query validation.

        Returns:
            Widget group definition.
        """
        text = response_text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e))
            return self._fallback_design(discovery, valid_metrics)

        valid_queries = set()
        for m in valid_metrics:
            for query in m.get("queries", {}).values():
                valid_queries.add(query)

        widgets = []
        for w in data.get("widgets", []):
            query = w.get("query", "")

            if query not in valid_queries:
                for m in valid_metrics:
                    if m["id"] in w.get("title", "").lower().replace(" ", "_"):
                        queries = m.get("queries", {})
                        query = queries.get("sum") or queries.get("p95") or list(queries.values())[0]
                        break

            if query in valid_queries:
                widgets.append({
                    "title": w.get("title", "Untitled"),
                    "type": w.get("type", "timeseries"),
                    "query": query,
                    "description": w.get("description", ""),
                })

        return {
            "group_title": data.get("group_title", f"{discovery.domain.title()} Analytics"),
            "widgets": widgets,
        }

    def _fallback_design(
        self,
        discovery: ServiceDiscovery,
        valid_metrics: list[dict],
    ) -> dict[str, Any]:
        """Create fallback widget design if LLM fails.

        Args:
            discovery: Service discovery.
            valid_metrics: Valid metrics to use.

        Returns:
            Basic widget group.
        """
        widgets = []
        for m in valid_metrics[:6]:
            queries = m.get("queries", {})
            primary_query = queries.get("sum") or queries.get("p95") or list(queries.values())[0] if queries else ""

            widgets.append({
                "title": m.get("widget_config", {}).get("title", m["id"]),
                "type": m.get("widget_config", {}).get("type", "timeseries"),
                "query": primary_query,
                "description": m.get("widget_config", {}).get("description", ""),
            })

        return {
            "group_title": f"{discovery.domain.title()} Analytics",
            "widgets": widgets,
        }
