"""Metrics provisioner for personalised observability."""

from dataclasses import dataclass
from typing import Any

import structlog
from ddtrace.llmobs.decorators import task

from ..mcp_client import DashboardMCPClient
from ..proposer import ProposedMetric

logger = structlog.get_logger()


@dataclass
class ProvisionedMetric:
    """Result of metric provisioning.

    Attributes:
        metric_id: The metric identifier.
        status: 'created', 'exists', or 'failed'.
        metric_type: 'count' or 'distribution'.
        queries: Generated Datadog query templates.
        widget_config: Suggested widget configuration.
        error: Error message if failed.
    """

    metric_id: str
    status: str
    metric_type: str
    queries: dict[str, str]
    widget_config: dict[str, str]
    error: str | None = None


class MetricsProvisioner:
    """Provisions span-based metrics from proposed metrics."""

    def __init__(self, service: str) -> None:
        """Initialise provisioner.

        Args:
            service: Service name for metrics.
        """
        self.service = service

    @task
    async def provision_metrics(
        self,
        proposed_metrics: list[ProposedMetric],
    ) -> dict[str, Any]:
        """Provision proposed metrics in Datadog.

        Args:
            proposed_metrics: Metrics proposed by LLM.

        Returns:
            Provisioning results with query templates.
        """
        logger.info(
            "provisioning_metrics",
            service=self.service,
            count=len(proposed_metrics),
        )

        results: list[ProvisionedMetric] = []

        async with DashboardMCPClient() as mcp:
            existing = await mcp.list_spans_metrics()
            existing_ids = {m["id"] for m in existing.get("metrics", [])}
            normalised_existing = {
                m["id"].replace("-", "_") for m in existing.get("metrics", [])
            }

            for proposed in proposed_metrics:
                queries = proposed.generate_queries(self.service)
                widget_config = {
                    "title": proposed.widget_title,
                    "type": proposed.widget_type,
                    "description": proposed.description,
                    "rationale": proposed.rationale,
                }

                normalised_id = proposed.metric_id.replace("-", "_")
                if proposed.metric_id in existing_ids or normalised_id in normalised_existing:
                    results.append(
                        ProvisionedMetric(
                            metric_id=proposed.metric_id,
                            status="exists",
                            metric_type=proposed.aggregation_type,
                            queries=queries,
                            widget_config=widget_config,
                        )
                    )
                    continue

                try:
                    result = await mcp.create_spans_metric(
                        metric_id=proposed.metric_id,
                        filter_query=proposed.filter_query,
                        aggregation_type=proposed.aggregation_type,
                        compute_path="@duration" if proposed.aggregation_type == "distribution" else None,
                        group_by=proposed.group_by,
                    )

                    if "error" in result:
                        results.append(
                            ProvisionedMetric(
                                metric_id=proposed.metric_id,
                                status="failed",
                                metric_type=proposed.aggregation_type,
                                queries=queries,
                                widget_config=widget_config,
                                error=result.get("error"),
                            )
                        )
                    else:
                        results.append(
                            ProvisionedMetric(
                                metric_id=proposed.metric_id,
                                status="created",
                                metric_type=proposed.aggregation_type,
                                queries=queries,
                                widget_config=widget_config,
                            )
                        )

                except Exception as e:
                    logger.error(
                        "metric_creation_failed",
                        metric_id=proposed.metric_id,
                        error=str(e),
                    )
                    results.append(
                        ProvisionedMetric(
                            metric_id=proposed.metric_id,
                            status="failed",
                            metric_type=proposed.aggregation_type,
                            queries=queries,
                            widget_config=widget_config,
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
                    "metric_type": r.metric_type,
                    "queries": r.queries,
                    "widget_config": r.widget_config,
                    "error": r.error,
                }
                for r in results
            ],
        }

    async def cleanup_metrics(
        self,
        metric_ids: list[str],
    ) -> dict[str, Any]:
        """Delete provisioned metrics.

        Args:
            metric_ids: List of metric IDs to delete.

        Returns:
            Cleanup results.
        """
        logger.info("cleaning_up_metrics", count=len(metric_ids))

        deleted = []
        failed = []

        async with DashboardMCPClient() as mcp:
            for metric_id in metric_ids:
                try:
                    await mcp.delete_spans_metric(metric_id)
                    deleted.append(metric_id)
                except Exception as e:
                    failed.append({"id": metric_id, "error": str(e)})

        return {
            "deleted": deleted,
            "failed": failed,
        }
