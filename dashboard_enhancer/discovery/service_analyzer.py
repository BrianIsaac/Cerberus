"""Service discovery for personalised metrics."""

from dataclasses import dataclass, field
from pathlib import Path

import structlog
from ddtrace.llmobs.decorators import task

from ..analyzer import CodeAnalyzer, TelemetryDiscoverer
from ..config import settings
from ..mcp_client import DashboardMCPClient

logger = structlog.get_logger()


@dataclass
class CategorisedOperation:
    """An operation categorised by its type.

    Attributes:
        name: The operation/function name.
        operation_type: Type of operation (workflow, llm, tool, task, or general).
        description: Optional description from docstring.
    """

    name: str
    operation_type: str
    description: str = ""


@dataclass
class ServiceDiscovery:
    """Discovery results for a service.

    Attributes:
        service_name: The service identifier.
        domain: Service domain (sas, ops, analytics, etc.).
        agent_type: Type of agent (generator, assistant, etc.).
        llm_provider: LLM provider used.
        framework: Agent framework.
        discovered_operations: Operations found in code/spans.
        categorised_operations: Operations categorised by type (workflow, llm, tool, etc.).
        workflow_operations: Main workflow entry points (highest priority for metrics).
        llm_operations: LLM call operations.
        tool_operations: Tool/MCP operations.
        discovered_metrics: Existing custom metrics.
        llmobs_span_types: Types of LLMObs spans found.
        sample_inputs: Sample input patterns (sanitised).
        sample_outputs: Sample output patterns (sanitised).
    """

    service_name: str
    domain: str
    agent_type: str
    llm_provider: str = "unknown"
    framework: str = "unknown"
    discovered_operations: list[str] = field(default_factory=list)
    categorised_operations: list[CategorisedOperation] = field(default_factory=list)
    workflow_operations: list[str] = field(default_factory=list)
    llm_operations: list[str] = field(default_factory=list)
    tool_operations: list[str] = field(default_factory=list)
    discovered_metrics: list[str] = field(default_factory=list)
    llmobs_span_types: list[str] = field(default_factory=list)
    sample_inputs: list[str] = field(default_factory=list)
    sample_outputs: list[str] = field(default_factory=list)


class ServiceDiscoveryAnalyzer:
    """Analyses a service using hybrid approach.

    Combines:
    - Code analysis (if source available)
    - Existing telemetry in Datadog
    - User-provided hints
    """

    def __init__(
        self,
        service: str,
        domain: str,
        agent_type: str,
        agent_source: Path | str | None = None,
        llm_provider: str = "unknown",
        framework: str = "unknown",
    ) -> None:
        """Initialise the discovery analyser.

        Args:
            service: Service name in Datadog.
            domain: Service domain from user input.
            agent_type: Agent type from user input.
            agent_source: Optional path or GitHub URL to source code.
            llm_provider: LLM provider from user input.
            framework: Framework from user input.
        """
        self.service = service
        self.domain = domain
        self.agent_type = agent_type
        self.agent_source = agent_source
        self.llm_provider = llm_provider
        self.framework = framework

    @task
    async def discover(self) -> ServiceDiscovery:
        """Run hybrid discovery on the service.

        Returns:
            ServiceDiscovery with all discovered information.
        """
        discovery = ServiceDiscovery(
            service_name=self.service,
            domain=self.domain,
            agent_type=self.agent_type,
            llm_provider=self.llm_provider,
            framework=self.framework,
        )

        # 1. Code analysis (if source available)
        if self.agent_source:
            await self._discover_from_code(discovery)

        # 2. Telemetry discovery
        await self._discover_from_telemetry(discovery)

        # 3. LLMObs span analysis
        await self._discover_from_llmobs(discovery)

        logger.info(
            "discovery_complete",
            service=self.service,
            operations=len(discovery.discovered_operations),
            metrics=len(discovery.discovered_metrics),
            span_types=len(discovery.llmobs_span_types),
        )

        return discovery

    async def _discover_from_code(self, discovery: ServiceDiscovery) -> None:
        """Discover operations from source code.

        Args:
            discovery: Discovery object to populate.
        """
        if not self.agent_source:
            return

        try:
            analyzer = CodeAnalyzer(
                self.agent_source,
                github_token=settings.github_token,
            )
            profile = analyzer.analyze()

            discovery.discovered_operations.extend(profile.span_operations)

            # Categorise operations by type
            for op in profile.span_operations:
                if ":" in op:
                    op_type, op_name = op.split(":", 1)
                    categorised = CategorisedOperation(
                        name=op_name,
                        operation_type=op_type,
                    )
                    discovery.categorised_operations.append(categorised)

                    # Also populate type-specific lists
                    if op_type == "workflow":
                        discovery.workflow_operations.append(op_name)
                    elif op_type == "llm":
                        discovery.llm_operations.append(op_name)
                    elif op_type == "tool":
                        discovery.tool_operations.append(op_name)
                else:
                    discovery.categorised_operations.append(
                        CategorisedOperation(name=op, operation_type="general")
                    )

            if profile.llm_provider != "unknown":
                discovery.llm_provider = profile.llm_provider
            if profile.framework != "unknown":
                discovery.framework = profile.framework

            logger.info(
                "code_analysis_complete",
                operations=len(profile.span_operations),
                workflows=len(discovery.workflow_operations),
                llm_calls=len(discovery.llm_operations),
                tools=len(discovery.tool_operations),
            )
        except Exception as e:
            logger.warning("code_analysis_failed", error=str(e))

    async def _discover_from_telemetry(self, discovery: ServiceDiscovery) -> None:
        """Discover existing metrics and traces.

        Args:
            discovery: Discovery object to populate.
        """
        try:
            discoverer = TelemetryDiscoverer(self.service)
            telemetry = await discoverer.discover()

            discovery.discovered_metrics.extend(telemetry.metrics_found)

            for op in telemetry.trace_operations:
                if op not in discovery.discovered_operations:
                    discovery.discovered_operations.append(op)

            logger.info(
                "telemetry_discovery_complete",
                metrics=len(telemetry.metrics_found),
                operations=len(telemetry.trace_operations),
            )
        except Exception as e:
            logger.warning("telemetry_discovery_failed", error=str(e))

    async def _discover_from_llmobs(self, discovery: ServiceDiscovery) -> None:
        """Discover LLMObs span patterns.

        Args:
            discovery: Discovery object to populate.
        """
        try:
            async with DashboardMCPClient() as mcp:
                status = await mcp.check_llm_obs_enabled(self.service)

                if status.get("enabled"):
                    spans = await mcp.fetch_llm_obs_spans(
                        ml_app=self.service,
                        hours_back=24,
                        limit=50,
                    )

                    span_types = set()
                    for span in spans.get("spans", []):
                        span_type = span.get("meta", {}).get("span.kind", "unknown")
                        span_types.add(span_type)

                        name = span.get("name", "")
                        if name and name not in discovery.discovered_operations:
                            discovery.discovered_operations.append(name)

                    discovery.llmobs_span_types = list(span_types)

                    logger.info(
                        "llmobs_discovery_complete",
                        span_types=len(span_types),
                        spans_analysed=len(spans.get("spans", [])),
                    )
        except Exception as e:
            logger.warning("llmobs_discovery_failed", error=str(e))
