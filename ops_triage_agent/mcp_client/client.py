"""MCP client wrapper for invoking Datadog tools."""

import json
from typing import Any

import httpx
import structlog
from fastmcp import Client

from app.config import settings

logger = structlog.get_logger()


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


class DatadogMCPClient:
    """Wrapper for MCP client to invoke Datadog tools."""

    def __init__(self) -> None:
        """Initialise MCP client with server URL from settings."""
        self.server_url = settings.mcp_server_url
        self._client: Client | None = None

    async def __aenter__(self) -> "DatadogMCPClient":
        """Enter async context and connect to MCP server.

        Returns:
            DatadogMCPClient: The connected client instance.
        """
        base_url = self.server_url.rsplit("/mcp", 1)[0]
        id_token = await _get_identity_token(base_url)

        if id_token:
            self._client = Client(self.server_url, auth=id_token)
            logger.info("mcp_client_connected_with_auth", server_url=self.server_url)
        else:
            self._client = Client(self.server_url)
            logger.info("mcp_client_connected", server_url=self.server_url)

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
            logger.info("mcp_client_disconnected")

    async def get_metrics(
        self,
        service: str,
        time_window: str = "last_15m",
        metrics: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch metrics from Datadog via MCP.

        Args:
            service: The service name to query metrics for.
            time_window: Time window (last_5m, last_15m, last_1h, last_4h).
            metrics: Specific metric queries (defaults to standard APM metrics).

        Returns:
            Dictionary containing metric data, time range, and dashboard link.
        """
        result = await self._client.call_tool(
            "get_metrics",
            {"service": service, "time_window": time_window, "metrics": metrics},
        )
        return _extract_result(result)

    async def get_logs(
        self,
        service: str,
        query: str | None = None,
        time_window: str = "last_15m",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Fetch logs from Datadog via MCP.

        Args:
            service: The service name to search logs for.
            query: Additional query string (e.g., "status:error").
            time_window: Time window (last_5m, last_15m, last_1h, last_4h).
            limit: Maximum number of logs to return.

        Returns:
            Dictionary containing log entries, summary, and logs explorer link.
        """
        result = await self._client.call_tool(
            "get_logs",
            {"service": service, "query": query, "time_window": time_window, "limit": limit},
        )
        return _extract_result(result)

    async def list_spans(
        self,
        service: str,
        query: str | None = None,
        time_window: str = "last_15m",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Fetch traces from Datadog via MCP.

        Args:
            service: The service name to search traces for.
            query: Additional query string (e.g., "status:error").
            time_window: Time window (last_5m, last_15m, last_1h, last_4h).
            limit: Maximum number of spans to return.

        Returns:
            Dictionary containing span data, summary, and traces explorer link.
        """
        result = await self._client.call_tool(
            "list_spans",
            {"service": service, "query": query, "time_window": time_window, "limit": limit},
        )
        return _extract_result(result)

    async def get_trace(self, trace_id: str) -> dict[str, Any]:
        """Fetch a single trace by ID from Datadog via MCP.

        Args:
            trace_id: The trace ID to retrieve.

        Returns:
            Dictionary containing trace details including all spans.
        """
        result = await self._client.call_tool(
            "get_trace",
            {"trace_id": trace_id},
        )
        return _extract_result(result)

    async def create_incident(
        self,
        title: str,
        summary: str,
        severity: str = "SEV-2",
        evidence_links: list[str] | None = None,
        hypotheses: list[str] | None = None,
        next_steps: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a Datadog incident via MCP.

        Args:
            title: Incident title (max 100 chars).
            summary: Brief description of the incident.
            severity: Severity level (SEV-1, SEV-2, SEV-3, SEV-4).
            evidence_links: Links to dashboards, traces, logs.
            hypotheses: Ranked hypotheses from triage.
            next_steps: Recommended actions.

        Returns:
            Dictionary containing incident ID, link, and creation timestamp.
        """
        result = await self._client.call_tool(
            "create_incident",
            {
                "title": title,
                "summary": summary,
                "severity": severity,
                "evidence_links": evidence_links,
                "hypotheses": hypotheses,
                "next_steps": next_steps,
            },
        )
        return _extract_result(result)

    async def create_case(
        self,
        title: str,
        description: str,
        priority: str = "P2",
        evidence_links: list[str] | None = None,
        hypotheses: list[str] | None = None,
        next_steps: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a Datadog case via MCP.

        Args:
            title: Case title.
            description: Brief description of the issue.
            priority: Priority level (P1, P2, P3, P4).
            evidence_links: Links to dashboards, traces, logs.
            hypotheses: Ranked hypotheses from triage.
            next_steps: Recommended actions.

        Returns:
            Dictionary containing case ID, key, link, and creation timestamp.
        """
        result = await self._client.call_tool(
            "create_case",
            {
                "title": title,
                "description": description,
                "priority": priority,
                "evidence_links": evidence_links,
                "hypotheses": hypotheses,
                "next_steps": next_steps,
            },
        )
        return _extract_result(result)

    async def list_incidents(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List Datadog incidents via MCP.

        Args:
            status: Filter by status (active, stable, resolved, completed).
            limit: Maximum number of incidents to return.

        Returns:
            Dictionary containing list of incidents and summary.
        """
        result = await self._client.call_tool(
            "list_incidents",
            {"status": status, "limit": limit},
        )
        return _extract_result(result)

    async def get_incident(self, incident_id: str) -> dict[str, Any]:
        """Get incident details via MCP.

        Args:
            incident_id: The incident ID to retrieve.

        Returns:
            Dictionary containing full incident details.
        """
        result = await self._client.call_tool(
            "get_incident",
            {"incident_id": incident_id},
        )
        return _extract_result(result)

    async def list_monitors(
        self,
        state: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List Datadog monitors via MCP.

        Args:
            state: Filter by state (all, alert, warn, no data, ok).
            tags: Filter by tags (e.g., ["env:prod", "service:api"]).
            limit: Maximum number of monitors to return.

        Returns:
            Dictionary containing list of monitors and summary by state.
        """
        result = await self._client.call_tool(
            "list_monitors",
            {"state": state, "tags": tags, "limit": limit},
        )
        return _extract_result(result)

    async def list_dashboards(
        self,
        query: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List Datadog dashboards via MCP.

        Args:
            query: Search query to filter dashboards by title.
            limit: Maximum number of dashboards to return.

        Returns:
            Dictionary containing list of dashboards.
        """
        result = await self._client.call_tool(
            "list_dashboards",
            {"query": query, "limit": limit},
        )
        return _extract_result(result)
