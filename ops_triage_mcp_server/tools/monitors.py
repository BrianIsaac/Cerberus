"""Datadog Monitors API tool for MCP server."""

from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from fastmcp import FastMCP

from ops_triage_mcp_server.tools import DD_SITE, get_datadog_config


def register_monitors_tools(mcp: FastMCP) -> None:
    """Register monitors tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def list_monitors(
        state: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List Datadog monitors with optional filters.

        Args:
            state: Filter by state (all, alert, warn, no data, ok).
            tags: Filter by tags (e.g., ["env:prod", "service:api"]).
            limit: Maximum number of monitors to return.

        Returns:
            Dictionary containing list of monitors and summary by state.
        """
        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api_instance = MonitorsApi(api_client)

            kwargs = {}
            if tags:
                kwargs["tags"] = ",".join(tags)
            if state and state.lower() != "all":
                kwargs["monitor_tags"] = f"state:{state}"

            response = api_instance.list_monitors(**kwargs)

            monitors = []
            state_counts = {
                "alert": 0,
                "warn": 0,
                "no_data": 0,
                "ok": 0,
                "unknown": 0,
            }

            for monitor in (response or [])[:limit]:
                monitor_state = (
                    monitor.overall_state.value
                    if hasattr(monitor, "overall_state") and monitor.overall_state
                    else "unknown"
                )

                created = getattr(monitor, "created", None)
                modified = getattr(monitor, "modified", None)

                monitor_data = {
                    "id": monitor.id,
                    "name": getattr(monitor, "name", None),
                    "type": monitor.type.value if hasattr(monitor, "type") else None,
                    "query": getattr(monitor, "query", None),
                    "state": monitor_state,
                    "tags": getattr(monitor, "tags", []),
                    "created": str(created) if created else None,
                    "modified": str(modified) if modified else None,
                }
                monitors.append(monitor_data)

                if monitor_state in state_counts:
                    state_counts[monitor_state] += 1
                else:
                    state_counts["unknown"] += 1

        return {
            "total_monitors": len(monitors),
            "state_summary": state_counts,
            "monitors": monitors,
            "monitors_link": f"https://app.{DD_SITE}/monitors/manage",
        }
