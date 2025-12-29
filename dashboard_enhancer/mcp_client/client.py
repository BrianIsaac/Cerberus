"""Dashboard MCP client wrapper."""

import json
from typing import Any

import httpx
import structlog
from fastmcp import Client

from ..config import settings

logger = structlog.get_logger()


def _call_tool_sync(client: Client, tool_name: str, params: dict) -> Any:
    """Wrapper to call tools synchronously for internal use."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        client.call_tool(tool_name, params)
    )


async def _get_identity_token(audience: str) -> str | None:
    """Fetch identity token from GCP metadata server for service-to-service auth.

    Args:
        audience: The target audience URL (the MCP server URL).

    Returns:
        Identity token string if on GCP, None otherwise.
    """
    metadata_url = (
        f"http://metadata.google.internal/computeMetadata/v1/"
        f"instance/service-accounts/default/identity?audience={audience}"
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                metadata_url,
                headers={"Metadata-Flavor": "Google"},
                timeout=5.0,
            )
            if response.status_code == 200:
                return response.text
    except httpx.RequestError:
        pass
    return None


def _extract_result(result: Any) -> dict[str, Any]:
    """Extract dictionary from CallToolResult.

    Args:
        result: The CallToolResult from MCP call_tool.

    Returns:
        Dictionary extracted from the result content.
    """
    if hasattr(result, "content") and result.content:
        for item in result.content:
            if hasattr(item, "text"):
                try:
                    return json.loads(item.text)
                except json.JSONDecodeError:
                    return {"raw_text": item.text}
    if isinstance(result, dict):
        return result
    return {"error": "Could not extract result", "raw": str(result)}


class DashboardMCPClient:
    """Client for Dashboard MCP Server operations."""

    def __init__(self) -> None:
        """Initialise MCP client with server URL from settings."""
        self.server_url = settings.dashboard_mcp_url
        self._client: Client | None = None

    async def __aenter__(self) -> "DashboardMCPClient":
        """Enter async context and connect to MCP server.

        Returns:
            DashboardMCPClient: The connected client instance.
        """
        base_url = self.server_url.rsplit("/mcp", 1)[0]
        id_token = await _get_identity_token(base_url)

        if id_token:
            self._client = Client(self.server_url, auth=id_token)
            logger.info("dashboard_mcp_client_connected_with_auth", server_url=self.server_url)
        else:
            self._client = Client(self.server_url)
            logger.info("dashboard_mcp_client_connected", server_url=self.server_url)

        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context and disconnect from MCP server.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.
        """
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            logger.info("dashboard_mcp_client_disconnected")

    async def add_widget_group(
        self,
        dashboard_id: str,
        group_title: str,
        widgets: list[dict],
        service: str,
    ) -> dict[str, Any]:
        """Add a widget group to the dashboard.

        Args:
            dashboard_id: Dashboard ID to update.
            group_title: Title for the new group.
            widgets: List of widget definitions.
            service: Service name.

        Returns:
            Result from MCP server.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        logger.info(
            "adding_widget_group",
            dashboard_id=dashboard_id,
            group_title=group_title,
            widgets_count=len(widgets),
        )

        result = await self._client.call_tool(
            "add_widget_group_to_dashboard",
            {
                "dashboard_id": dashboard_id,
                "group_title": group_title,
                "widgets_json": json.dumps(widgets),
                "service": service,
            },
        )

        return _extract_result(result)

    async def get_dashboard(self, dashboard_id: str) -> dict[str, Any]:
        """Get a dashboard by ID.

        Args:
            dashboard_id: The dashboard ID to retrieve.

        Returns:
            Dashboard definition.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        result = await self._client.call_tool(
            "get_dashboard",
            {"dashboard_id": dashboard_id},
        )

        return _extract_result(result)

    async def update_dashboard(
        self,
        dashboard_id: str,
        dashboard_json: str,
    ) -> dict[str, Any]:
        """Update an existing dashboard.

        Args:
            dashboard_id: The dashboard ID to update.
            dashboard_json: Complete dashboard definition as JSON string.

        Returns:
            Updated dashboard info.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        result = await self._client.call_tool(
            "update_dashboard",
            {
                "dashboard_id": dashboard_id,
                "dashboard_json": dashboard_json,
            },
        )

        return _extract_result(result)

    async def create_spans_metric(
        self,
        metric_id: str,
        filter_query: str,
        aggregation_type: str = "count",
        compute_path: str | None = None,
        group_by: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Create a span-based metric via MCP server.

        Args:
            metric_id: Unique metric name.
            filter_query: Span filter query.
            aggregation_type: 'count' or 'distribution'.
            compute_path: Path for distribution aggregation.
            group_by: List of group_by definitions.

        Returns:
            Created metric details.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        params: dict[str, Any] = {
            "metric_id": metric_id,
            "filter_query": filter_query,
            "aggregation_type": aggregation_type,
        }
        if compute_path:
            params["compute_path"] = compute_path
        if group_by:
            params["group_by_json"] = json.dumps(group_by)

        result = await self._client.call_tool("create_spans_metric", params)
        return _extract_result(result)

    async def list_spans_metrics(self) -> dict[str, Any]:
        """List all span-based metrics.

        Returns:
            List of all configured span metrics.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        result = await self._client.call_tool("list_spans_metrics", {})
        return _extract_result(result)

    async def delete_spans_metric(self, metric_id: str) -> dict[str, Any]:
        """Delete a span-based metric.

        Args:
            metric_id: The metric ID to delete.

        Returns:
            Deletion confirmation.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        result = await self._client.call_tool(
            "delete_spans_metric",
            {"metric_id": metric_id},
        )
        return _extract_result(result)

    async def fetch_llm_obs_spans(
        self,
        ml_app: str,
        hours_back: int = 1,
        limit: int = 50,
        span_type: str | None = None,
    ) -> dict[str, Any]:
        """Fetch LLM Obs spans for evaluation.

        Args:
            ml_app: ML application name.
            hours_back: Hours to look back.
            limit: Max spans to return.
            span_type: Optional span type filter.

        Returns:
            Spans with input/output data.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        params: dict[str, Any] = {
            "ml_app": ml_app,
            "hours_back": hours_back,
            "limit": limit,
        }
        if span_type:
            params["span_type"] = span_type

        result = await self._client.call_tool("fetch_llm_obs_spans", params)
        return _extract_result(result)

    async def submit_evaluation(
        self,
        span_id: str,
        trace_id: str,
        ml_app: str,
        label: str,
        metric_type: str,
        value: str | float,
        tags: dict | None = None,
    ) -> dict[str, Any]:
        """Submit an evaluation result.

        Args:
            span_id: Span ID to attach evaluation to.
            trace_id: Trace ID containing the span.
            ml_app: ML application name.
            label: Evaluation label.
            metric_type: 'score' or 'categorical'.
            value: Score or category value.
            tags: Optional tags.

        Returns:
            Submission confirmation.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        params: dict[str, Any] = {
            "span_id": span_id,
            "trace_id": trace_id,
            "ml_app": ml_app,
            "label": label,
            "metric_type": metric_type,
            "value": str(value),
        }
        if tags:
            params["tags_json"] = json.dumps(tags)

        result = await self._client.call_tool("submit_evaluation", params)
        return _extract_result(result)

    async def submit_evaluations_batch(self, evaluations: list[dict]) -> dict[str, Any]:
        """Submit multiple evaluations in batch.

        Args:
            evaluations: List of evaluation objects.

        Returns:
            Batch submission results.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        result = await self._client.call_tool(
            "submit_evaluations_batch",
            {"evaluations_json": json.dumps(evaluations)},
        )
        return _extract_result(result)

    async def check_llm_obs_enabled(self, ml_app: str) -> dict[str, Any]:
        """Check if LLM Obs is enabled for a service.

        Args:
            ml_app: ML application name.

        Returns:
            Status dict with enabled flag.
        """
        if not self._client:
            raise RuntimeError("Client not connected")

        result = await self._client.call_tool(
            "check_llm_obs_enabled",
            {"ml_app": ml_app},
        )
        return _extract_result(result)
