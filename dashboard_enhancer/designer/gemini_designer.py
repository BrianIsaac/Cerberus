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
from .templates import get_base_widgets

logger = structlog.get_logger()


class GeminiWidgetDesigner:
    """Uses Vertex AI Gemini to design domain-specific widgets."""

    SYSTEM_PROMPT = """You are a Datadog dashboard expert specialising in AI/LLM observability.
Your task is to design dashboard widgets that are SPECIFIC to the agent's domain, not generic health metrics.

Guidelines:
1. Widget titles should reflect the agent's domain (e.g., "SAS Query Complexity" not "Request Count")
2. Use metrics that already exist in Datadog (provided in telemetry profile)
3. Focus on domain-specific insights, not just standard APM metrics
4. Each widget should tell a story about the agent's performance in its specific domain
5. Use appropriate widget types: timeseries for trends, query_value for KPIs, toplist for rankings

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
    ) -> list[dict[str, Any]]:
        """Design domain-specific widgets using Gemini.

        Args:
            agent_profile: Profile of the agent being enhanced.
            telemetry_profile: Available telemetry from Datadog.

        Returns:
            List of widget definitions.
        """
        logger.info(
            "designing_widgets",
            service=agent_profile.service_name,
            domain=agent_profile.domain,
        )

        base_widgets = get_base_widgets(agent_profile.agent_type)
        prompt = self._build_prompt(agent_profile, telemetry_profile, base_widgets)

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4096,
                ),
            )

            widgets = self._parse_response(response.text)

            logger.info(
                "widgets_designed",
                count=len(widgets),
                service=agent_profile.service_name,
            )

            return widgets

        except Exception as e:
            logger.error("widget_design_failed", error=str(e))
            return self._apply_base_widgets(base_widgets, agent_profile)

    def _build_prompt(
        self,
        agent_profile: AgentProfile,
        telemetry_profile: TelemetryProfile,
        base_widgets: list[dict],
    ) -> str:
        """Build the prompt for Gemini.

        Args:
            agent_profile: Profile of the agent.
            telemetry_profile: Available telemetry.
            base_widgets: Base widget templates.

        Returns:
            Formatted prompt string.
        """
        return f"""Design 4-6 dashboard widgets for this AI agent:

## Agent Profile
- Service: {agent_profile.service_name}
- Type: {agent_profile.agent_type}
- Domain: {agent_profile.domain}
- Description: {agent_profile.description}
- Primary Actions: {', '.join(agent_profile.primary_actions)}
- Output Types: {', '.join(agent_profile.output_types)}
- LLM Provider: {agent_profile.llm_provider}
- Framework: {agent_profile.framework}

## Available Telemetry
- Metrics: {', '.join(telemetry_profile.metrics_found)}
- Trace Operations: {', '.join(telemetry_profile.trace_operations)}
- Has LLM Observability: {telemetry_profile.has_llm_obs}
- Has Custom Metrics: {telemetry_profile.has_custom_metrics}

## Base Widgets (customise these for the domain)
{json.dumps(base_widgets, indent=2)}

## Requirements
1. Generate 4-6 widgets as a JSON array
2. Each widget must have: type, title, query
3. Titles must be domain-specific (e.g., "SAS Query Complexity" not "Request Latency")
4. Queries must use the {{service:{agent_profile.service_name}}} filter
5. Use only metrics from the Available Telemetry list
6. Focus on insights unique to this agent's domain

Return ONLY a JSON array of widget definitions, no other text."""

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
                return widgets
            elif isinstance(widgets, dict) and "widgets" in widgets:
                return widgets["widgets"]
            else:
                return [widgets]
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e), text=text[:200])
            return []

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
