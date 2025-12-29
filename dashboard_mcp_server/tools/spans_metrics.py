"""Span-based metrics management tools for MCP server."""

import json
from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v2.api.spans_metrics_api import SpansMetricsApi
from datadog_api_client.v2.model.spans_metric_compute import SpansMetricCompute
from datadog_api_client.v2.model.spans_metric_create_attributes import (
    SpansMetricCreateAttributes,
)
from datadog_api_client.v2.model.spans_metric_create_data import SpansMetricCreateData
from datadog_api_client.v2.model.spans_metric_create_request import (
    SpansMetricCreateRequest,
)
from datadog_api_client.v2.model.spans_metric_filter import SpansMetricFilter
from datadog_api_client.v2.model.spans_metric_group_by import SpansMetricGroupBy
from datadog_api_client.v2.model.spans_metric_update_attributes import (
    SpansMetricUpdateAttributes,
)
from datadog_api_client.v2.model.spans_metric_update_data import SpansMetricUpdateData
from datadog_api_client.v2.model.spans_metric_update_request import (
    SpansMetricUpdateRequest,
)
from fastmcp import FastMCP

from dashboard_mcp_server.tools import get_datadog_config


def register_spans_metrics_tools(mcp: FastMCP) -> None:
    """Register span-based metrics tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def create_spans_metric(
        metric_id: str,
        filter_query: str,
        aggregation_type: str = "count",
        compute_path: str | None = None,
        include_percentiles: bool = False,
        group_by_json: str | None = None,
    ) -> dict[str, Any]:
        """Create a new span-based metric.

        Args:
            metric_id: Unique metric name (e.g., 'sas_generator.llm.duration').
            filter_query: Span filter query (e.g., 'service:sas-generator @span.type:llm').
            aggregation_type: 'count' or 'distribution'.
            compute_path: Path to numeric field for distribution (e.g., '@duration').
            include_percentiles: Whether to include percentile aggregations.
            group_by_json: JSON array of group_by definitions.

        Returns:
            Created metric details.
        """
        config = get_datadog_config()

        compute = SpansMetricCompute(aggregation_type=aggregation_type)
        if aggregation_type == "distribution" and compute_path:
            compute.path = compute_path
            compute.include_percentiles = include_percentiles

        attributes = SpansMetricCreateAttributes(
            compute=compute,
            filter=SpansMetricFilter(query=filter_query),
        )

        if group_by_json:
            group_by_list = json.loads(group_by_json)
            attributes.group_by = [
                SpansMetricGroupBy(
                    path=g["path"],
                    tag_name=g.get("tag_name", g["path"]),
                )
                for g in group_by_list
            ]

        body = SpansMetricCreateRequest(
            data=SpansMetricCreateData(
                id=metric_id,
                type="spans_metrics",
                attributes=attributes,
            )
        )

        with ApiClient(config) as api_client:
            api = SpansMetricsApi(api_client)
            response = api.create_spans_metric(body=body)

            return {
                "id": response.data.id,
                "type": response.data.type,
                "aggregation_type": aggregation_type,
                "filter_query": filter_query,
                "message": f"Span metric '{metric_id}' created successfully",
            }

    @mcp.tool()
    async def list_spans_metrics() -> dict[str, Any]:
        """List all span-based metrics.

        Returns:
            List of all configured span metrics.
        """
        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api = SpansMetricsApi(api_client)
            response = api.list_spans_metrics()

            metrics = []
            for metric in response.data or []:
                attrs = metric.attributes
                metrics.append({
                    "id": metric.id,
                    "filter_query": attrs.filter.query if attrs.filter else None,
                    "aggregation_type": attrs.compute.aggregation_type if attrs.compute else None,
                })

            return {
                "count": len(metrics),
                "metrics": metrics,
            }

    @mcp.tool()
    async def get_spans_metric(metric_id: str) -> dict[str, Any]:
        """Get details of a specific span-based metric.

        Args:
            metric_id: The metric ID to retrieve.

        Returns:
            Metric configuration details.
        """
        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api = SpansMetricsApi(api_client)
            response = api.get_spans_metric(metric_id=metric_id)

            attrs = response.data.attributes
            result = {
                "id": response.data.id,
                "type": response.data.type,
            }

            if attrs:
                if attrs.filter:
                    result["filter_query"] = attrs.filter.query
                if attrs.compute:
                    result["aggregation_type"] = attrs.compute.aggregation_type
                    result["compute_path"] = getattr(attrs.compute, "path", None)
                    result["include_percentiles"] = getattr(
                        attrs.compute, "include_percentiles", False
                    )
                if attrs.group_by:
                    result["group_by"] = [
                        {"path": g.path, "tag_name": g.tag_name}
                        for g in attrs.group_by
                    ]

            return result

    @mcp.tool()
    async def update_spans_metric(
        metric_id: str,
        filter_query: str | None = None,
        group_by_json: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing span-based metric.

        Note: aggregation_type cannot be changed after creation.

        Args:
            metric_id: The metric ID to update.
            filter_query: New filter query (optional).
            group_by_json: New group_by definitions as JSON (optional).

        Returns:
            Updated metric details.
        """
        config = get_datadog_config()

        attributes = SpansMetricUpdateAttributes()

        if filter_query:
            attributes.filter = SpansMetricFilter(query=filter_query)

        if group_by_json:
            group_by_list = json.loads(group_by_json)
            attributes.group_by = [
                SpansMetricGroupBy(
                    path=g["path"],
                    tag_name=g.get("tag_name", g["path"]),
                )
                for g in group_by_list
            ]

        body = SpansMetricUpdateRequest(
            data=SpansMetricUpdateData(
                id=metric_id,
                type="spans_metrics",
                attributes=attributes,
            )
        )

        with ApiClient(config) as api_client:
            api = SpansMetricsApi(api_client)
            response = api.update_spans_metric(metric_id=metric_id, body=body)

            return {
                "id": response.data.id,
                "message": f"Span metric '{metric_id}' updated successfully",
            }

    @mcp.tool()
    async def delete_spans_metric(metric_id: str) -> dict[str, Any]:
        """Delete a span-based metric.

        Args:
            metric_id: The metric ID to delete.

        Returns:
            Deletion confirmation.
        """
        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api = SpansMetricsApi(api_client)
            api.delete_spans_metric(metric_id=metric_id)

            return {
                "id": metric_id,
                "message": f"Span metric '{metric_id}' deleted successfully",
            }
