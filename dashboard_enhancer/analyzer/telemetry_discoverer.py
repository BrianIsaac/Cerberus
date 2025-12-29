"""Discover existing telemetry for an agent from Datadog."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import structlog
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.metrics_api import MetricsApi
from datadog_api_client.v2.api.spans_api import SpansApi
from datadog_api_client.v2.model.spans_list_request import SpansListRequest
from datadog_api_client.v2.model.spans_list_request_attributes import (
    SpansListRequestAttributes,
)
from datadog_api_client.v2.model.spans_list_request_data import SpansListRequestData
from datadog_api_client.v2.model.spans_list_request_page import SpansListRequestPage
from datadog_api_client.v2.model.spans_query_filter import SpansQueryFilter

from ..config import settings

logger = structlog.get_logger()


def get_datadog_config() -> Configuration:
    """Get Datadog API configuration.

    Returns:
        Configured Datadog API Configuration object.
    """
    config = Configuration()
    config.api_key["apiKeyAuth"] = settings.dd_api_key
    config.api_key["appKeyAuth"] = settings.dd_app_key
    config.server_variables["site"] = settings.dd_site
    config.enable_retry = True
    config.max_retries = 3
    return config


@dataclass
class TelemetryProfile:
    """Profile of existing telemetry for a service."""

    service: str
    metrics_found: list[str] = field(default_factory=list)
    trace_operations: list[str] = field(default_factory=list)
    tags_in_use: list[str] = field(default_factory=list)
    has_llm_obs: bool = False
    has_custom_metrics: bool = False
    sample_trace_ids: list[str] = field(default_factory=list)
    time_range: str = "last_1h"


class TelemetryDiscoverer:
    """Discovers existing telemetry from Datadog APIs."""

    METRIC_PREFIXES = [
        "ai_agent.",
        "trace.http.request.",
        "trace.google_genai.",
        "trace.langgraph.",
        "trace.mcp.",
        "llmobs.",
    ]

    def __init__(self, service: str):
        """Initialise discoverer for a service.

        Args:
            service: Service name to discover telemetry for.
        """
        self.service = service

    async def discover(self) -> TelemetryProfile:
        """Query Datadog to discover existing telemetry.

        Returns:
            TelemetryProfile with discovered information.
        """
        logger.info("discovering_telemetry", service=self.service)

        profile = TelemetryProfile(service=self.service)

        metrics = await self._discover_metrics()
        profile.metrics_found = metrics
        profile.has_custom_metrics = any(m.startswith("ai_agent.") for m in metrics)

        traces = await self._discover_traces()
        profile.trace_operations = traces.get("operations", [])
        profile.sample_trace_ids = traces.get("trace_ids", [])
        profile.tags_in_use = traces.get("tags", [])

        profile.has_llm_obs = any(m.startswith("llmobs.") for m in metrics)

        logger.info(
            "telemetry_discovered",
            service=self.service,
            metrics_count=len(profile.metrics_found),
            operations_count=len(profile.trace_operations),
            has_llm_obs=profile.has_llm_obs,
        )

        return profile

    async def _discover_metrics(self) -> list[str]:
        """Query Datadog for active metrics.

        Returns:
            List of discovered metric names.
        """
        config = get_datadog_config()
        found_metrics: list[str] = []

        now = datetime.now()
        from_time = int((now - timedelta(hours=1)).timestamp())
        to_time = int(now.timestamp())

        with ApiClient(config) as api_client:
            api = MetricsApi(api_client)

            for prefix in self.METRIC_PREFIXES:
                test_queries = [
                    f"avg:{prefix}*{{service:{self.service}}}",
                    f"sum:{prefix}*{{service:{self.service}}}.as_count()",
                ]

                for query in test_queries:
                    try:
                        response = api.query_metrics(
                            _from=from_time,
                            to=to_time,
                            query=query,
                        )
                        if response.series:
                            for series in response.series:
                                metric_name = getattr(series, "metric", None)
                                if metric_name and metric_name not in found_metrics:
                                    found_metrics.append(metric_name)
                    except Exception as e:
                        logger.debug("metric_query_failed", query=query, error=str(e))

        return found_metrics

    async def _discover_traces(self) -> dict:
        """Query Datadog for traces and extract operations.

        Returns:
            Dictionary with operations, trace_ids, and tags.
        """
        config = get_datadog_config()

        now = datetime.now(timezone.utc)
        from_time = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        operations: set[str] = set()
        trace_ids: list[str] = []
        tags: set[str] = set()

        with ApiClient(config) as api_client:
            api = SpansApi(api_client)

            try:
                body = SpansListRequest(
                    data=SpansListRequestData(
                        type="search_request",
                        attributes=SpansListRequestAttributes(
                            filter=SpansQueryFilter(
                                query=f"service:{self.service}",
                                _from=from_time,
                                to=to_time,
                            ),
                            page=SpansListRequestPage(limit=50),
                        ),
                    )
                )

                response = api.list_spans(body=body)

                for span in response.data or []:
                    attrs = getattr(span, "attributes", None)
                    if attrs:
                        resource = getattr(attrs, "resource_name", None)
                        if resource:
                            operations.add(resource)

                        trace_id = getattr(attrs, "trace_id", None)
                        if trace_id and len(trace_ids) < 5:
                            trace_ids.append(str(trace_id))

                        span_tags = getattr(attrs, "tags", None)
                        if span_tags and isinstance(span_tags, list):
                            for tag in span_tags:
                                if ":" in tag:
                                    tags.add(tag.split(":")[0])

            except Exception as e:
                logger.warning("trace_discovery_failed", error=str(e))

        return {
            "operations": list(operations),
            "trace_ids": trace_ids,
            "tags": list(tags),
        }
