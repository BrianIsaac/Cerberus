"""Automatic span-based metrics provisioning."""

from dataclasses import dataclass, field
from typing import Any

import structlog

from ..analyzer import AgentProfile
from ..mcp_client import DashboardMCPClient

logger = structlog.get_logger()


@dataclass
class MetricDefinition:
    """Definition for a span-based metric to create.

    Attributes:
        metric_id: Unique metric identifier with {service} placeholder.
        filter_query: Span filter query with {service} placeholder.
        aggregation_type: Either 'count' or 'distribution'.
        compute_path: Path to numeric field for distribution aggregation.
        group_by: List of group_by definitions for the metric.
        description: Human-readable description of the metric.
    """

    metric_id: str
    filter_query: str
    aggregation_type: str
    compute_path: str | None = None
    group_by: list[dict] | None = None
    description: str = ""


@dataclass
class ProvisionedMetric:
    """Record of a provisioned metric.

    Attributes:
        metric_id: The metric identifier that was provisioned.
        filter_query: The filter query used for the metric.
        status: Status of provisioning ('created', 'exists', or 'failed').
        error: Error message if provisioning failed.
    """

    metric_id: str
    filter_query: str
    status: str
    error: str | None = None


class MetricsProvisioner:
    """Provisions span-based metrics for an agent.

    Creates metrics based on:
    1. Detected framework (FastAPI, LangGraph, etc.)
    2. Detected span operations
    3. Agent type and domain

    Attributes:
        agent_profile: Profile of the agent to provision metrics for.
        service: The service name derived from the agent profile.
    """

    BASE_METRICS = [
        MetricDefinition(
            metric_id="{service}.request.count",
            filter_query="service:{service}",
            aggregation_type="count",
            description="Total request count",
        ),
        MetricDefinition(
            metric_id="{service}.request.duration",
            filter_query="service:{service}",
            aggregation_type="distribution",
            compute_path="@duration",
            group_by=[{"path": "resource_name", "tag_name": "resource"}],
            description="Request duration distribution",
        ),
        MetricDefinition(
            metric_id="{service}.error.count",
            filter_query="service:{service} @error:true",
            aggregation_type="count",
            group_by=[{"path": "error.type", "tag_name": "error_type"}],
            description="Error count by type",
        ),
    ]

    LLM_METRICS = [
        MetricDefinition(
            metric_id="{service}.llm.call.count",
            filter_query="service:{service} @span.type:llm",
            aggregation_type="count",
            group_by=[{"path": "@model_name", "tag_name": "model"}],
            description="LLM call count by model",
        ),
        MetricDefinition(
            metric_id="{service}.llm.duration",
            filter_query="service:{service} @span.type:llm",
            aggregation_type="distribution",
            compute_path="@duration",
            group_by=[{"path": "@model_name", "tag_name": "model"}],
            description="LLM call duration by model",
        ),
    ]

    WORKFLOW_METRICS = [
        MetricDefinition(
            metric_id="{service}.workflow.count",
            filter_query="service:{service} @span.type:workflow",
            aggregation_type="count",
            description="Workflow execution count",
        ),
        MetricDefinition(
            metric_id="{service}.workflow.duration",
            filter_query="service:{service} @span.type:workflow",
            aggregation_type="distribution",
            compute_path="@duration",
            description="Workflow duration distribution",
        ),
    ]

    def __init__(self, agent_profile: AgentProfile) -> None:
        """Initialise provisioner with agent profile.

        Args:
            agent_profile: Profile of the agent to provision metrics for.
        """
        self.agent_profile = agent_profile
        self.service = agent_profile.service_name

    def get_metrics_to_provision(self) -> list[MetricDefinition]:
        """Determine which metrics to provision based on agent profile.

        Returns:
            List of metric definitions to create.
        """
        metrics = []

        metrics.extend(self._substitute_service(self.BASE_METRICS))

        if self.agent_profile.llmobs_enabled:
            metrics.extend(self._substitute_service(self.LLM_METRICS))

        if "workflow" in self.agent_profile.llmobs_decorators:
            metrics.extend(self._substitute_service(self.WORKFLOW_METRICS))

        for operation in self.agent_profile.span_operations:
            span_type, func_name = operation.split(":", 1)
            metric_name = func_name.replace("_", ".")

            metrics.append(
                MetricDefinition(
                    metric_id=f"{self.service}.{metric_name}.count",
                    filter_query=f"service:{self.service} @resource_name:{func_name}",
                    aggregation_type="count",
                    description=f"Count of {func_name} operations",
                )
            )

        return metrics

    def _substitute_service(
        self,
        metrics: list[MetricDefinition],
    ) -> list[MetricDefinition]:
        """Substitute service name into metric definitions.

        Args:
            metrics: List of metric definitions with {service} placeholders.

        Returns:
            List of metric definitions with service name substituted.
        """
        result = []
        for m in metrics:
            result.append(
                MetricDefinition(
                    metric_id=m.metric_id.format(service=self.service),
                    filter_query=m.filter_query.format(service=self.service),
                    aggregation_type=m.aggregation_type,
                    compute_path=m.compute_path,
                    group_by=m.group_by,
                    description=m.description,
                )
            )
        return result

    async def provision_metrics(self) -> dict[str, Any]:
        """Provision all metrics for the agent.

        Returns:
            Summary of provisioning results including counts
            and individual metric statuses.
        """
        metrics_to_create = self.get_metrics_to_provision()

        logger.info(
            "provisioning_metrics",
            service=self.service,
            metrics_count=len(metrics_to_create),
        )

        results: list[ProvisionedMetric] = []

        async with DashboardMCPClient() as mcp:
            existing = await mcp.list_spans_metrics()
            # Datadog normalises metric names (hyphens become underscores)
            existing_ids = {m["id"] for m in existing.get("metrics", [])}
            normalised_existing_ids = {m["id"].replace("-", "_") for m in existing.get("metrics", [])}

            for metric_def in metrics_to_create:
                # Check both exact match and normalised match (hyphens -> underscores)
                normalised_metric_id = metric_def.metric_id.replace("-", "_")
                if metric_def.metric_id in existing_ids or normalised_metric_id in normalised_existing_ids:
                    results.append(
                        ProvisionedMetric(
                            metric_id=metric_def.metric_id,
                            filter_query=metric_def.filter_query,
                            status="exists",
                        )
                    )
                    continue

                try:
                    result = await mcp.create_spans_metric(
                        metric_id=metric_def.metric_id,
                        filter_query=metric_def.filter_query,
                        aggregation_type=metric_def.aggregation_type,
                        compute_path=metric_def.compute_path,
                        group_by=metric_def.group_by,
                    )

                    if "error" in result:
                        results.append(
                            ProvisionedMetric(
                                metric_id=metric_def.metric_id,
                                filter_query=metric_def.filter_query,
                                status="failed",
                                error=result.get("error"),
                            )
                        )
                    else:
                        results.append(
                            ProvisionedMetric(
                                metric_id=metric_def.metric_id,
                                filter_query=metric_def.filter_query,
                                status="created",
                            )
                        )

                except Exception as e:
                    logger.error(
                        "metric_creation_failed",
                        metric_id=metric_def.metric_id,
                        error=str(e),
                    )
                    results.append(
                        ProvisionedMetric(
                            metric_id=metric_def.metric_id,
                            filter_query=metric_def.filter_query,
                            status="failed",
                            error=str(e),
                        )
                    )

        created = [r for r in results if r.status == "created"]
        existing_list = [r for r in results if r.status == "exists"]
        failed = [r for r in results if r.status == "failed"]

        logger.info(
            "metrics_provisioned",
            created=len(created),
            existing=len(existing_list),
            failed=len(failed),
        )

        return {
            "service": self.service,
            "created": len(created),
            "existing": len(existing_list),
            "failed": len(failed),
            "metrics": [
                {
                    "id": r.metric_id,
                    "status": r.status,
                    "error": r.error,
                }
                for r in results
            ],
        }

    async def cleanup_metrics(self) -> dict[str, Any]:
        """Delete all metrics created for this service.

        Returns:
            Cleanup summary with lists of deleted and failed metric IDs.
        """
        async with DashboardMCPClient() as mcp:
            existing = await mcp.list_spans_metrics()

            # Match both exact service name and normalised version (hyphens -> underscores)
            normalised_service = self.service.replace("-", "_")
            service_metrics = [
                m
                for m in existing.get("metrics", [])
                if m["id"].startswith(f"{self.service}.") or m["id"].startswith(f"{normalised_service}.")
            ]

            deleted = []
            failed = []

            for metric in service_metrics:
                try:
                    await mcp.delete_spans_metric(metric["id"])
                    deleted.append(metric["id"])
                except Exception as e:
                    failed.append({"id": metric["id"], "error": str(e)})

            return {
                "service": self.service,
                "deleted": deleted,
                "failed": failed,
            }
