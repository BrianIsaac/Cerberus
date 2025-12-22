"""MCP client wrapper for invoking Datadog tools."""

from typing import Any

import structlog
from fastmcp import Client

from app.config import settings

logger = structlog.get_logger()


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
        self._client = Client(self.server_url)
        await self._client.__aenter__()
        logger.info("mcp_client_connected", server_url=self.server_url)
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
        return await self._client.call_tool(
            "get_metrics",
            {"service": service, "time_window": time_window, "metrics": metrics},
        )

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
        return await self._client.call_tool(
            "get_logs",
            {"service": service, "query": query, "time_window": time_window, "limit": limit},
        )

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
        return await self._client.call_tool(
            "list_spans",
            {"service": service, "query": query, "time_window": time_window, "limit": limit},
        )

    async def get_trace(self, trace_id: str) -> dict[str, Any]:
        """Fetch a single trace by ID from Datadog via MCP.

        Args:
            trace_id: The trace ID to retrieve.

        Returns:
            Dictionary containing trace details including all spans.
        """
        return await self._client.call_tool(
            "get_trace",
            {"trace_id": trace_id},
        )

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
        return await self._client.call_tool(
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
        return await self._client.call_tool(
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
        return await self._client.call_tool(
            "list_incidents",
            {"status": status, "limit": limit},
        )

    async def get_incident(self, incident_id: str) -> dict[str, Any]:
        """Get incident details via MCP.

        Args:
            incident_id: The incident ID to retrieve.

        Returns:
            Dictionary containing full incident details.
        """
        return await self._client.call_tool(
            "get_incident",
            {"incident_id": incident_id},
        )

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
        return await self._client.call_tool(
            "list_monitors",
            {"state": state, "tags": tags, "limit": limit},
        )

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
        return await self._client.call_tool(
            "list_dashboards",
            {"query": query, "limit": limit},
        )
