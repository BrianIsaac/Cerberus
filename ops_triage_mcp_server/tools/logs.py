"""Datadog Logs API tool for MCP server."""

from datetime import datetime, timedelta
from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_list_request import LogsListRequest
from datadog_api_client.v2.model.logs_list_request_page import LogsListRequestPage
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_sort import LogsSort
from fastmcp import FastMCP

from ops_triage_mcp_server.tools import DD_SITE, get_datadog_config


def register_logs_tools(mcp: FastMCP) -> None:
    """Register logs tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def get_logs(
        service: str,
        query: str | None = None,
        time_window: str = "last_15m",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search logs in Datadog for a service.

        Args:
            service: The service name to search logs for.
            query: Additional query string (e.g., "status:error").
            time_window: Time window (last_5m, last_15m, last_1h, last_4h).
            limit: Maximum number of logs to return.

        Returns:
            Dictionary containing log entries, summary, and logs explorer link.
        """
        window_mapping = {
            "last_5m": timedelta(minutes=5),
            "last_15m": timedelta(minutes=15),
            "last_1h": timedelta(hours=1),
            "last_4h": timedelta(hours=4),
        }
        delta = window_mapping.get(time_window, timedelta(minutes=15))

        end_time = datetime.now()
        start_time = end_time - delta

        base_query = f"service:{service}"
        full_query = f"{base_query} {query}" if query else base_query

        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api_instance = LogsApi(api_client)

            body = LogsListRequest(
                filter=LogsQueryFilter(
                    query=full_query,
                    _from=start_time.isoformat(),
                    to=end_time.isoformat(),
                ),
                sort=LogsSort.TIMESTAMP_DESCENDING,
                page=LogsListRequestPage(limit=min(limit, 100)),
            )

            response = api_instance.list_logs(body=body)

            logs = []
            for log in response.data or []:
                attrs = log.attributes
                logs.append({
                    "timestamp": str(attrs.timestamp) if attrs.timestamp else None,
                    "message": attrs.message,
                    "status": attrs.status,
                    "host": attrs.host,
                    "attributes": dict(attrs.attributes) if attrs.attributes else {},
                })

        error_count = sum(1 for log in logs if log.get("status") == "error")
        warn_count = sum(1 for log in logs if log.get("status") == "warn")

        return {
            "service": service,
            "query": full_query,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "summary": {
                "total_logs": len(logs),
                "error_count": error_count,
                "warn_count": warn_count,
            },
            "logs": logs[:20],
            "logs_link": f"https://app.{DD_SITE}/logs?query={full_query}",
        }
