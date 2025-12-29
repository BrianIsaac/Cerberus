"""Monitor management tools for MCP server."""

import json
from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from datadog_api_client.v1.model.monitor import Monitor
from fastmcp import FastMCP

from dashboard_mcp_server.tools import DD_SITE, get_datadog_config


def register_monitor_tools(mcp: FastMCP) -> None:
    """Register monitor management tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def create_monitor(monitor_json: str) -> dict[str, Any]:
        """Create a new monitor in Datadog.

        Args:
            monitor_json: Monitor definition as JSON string.

        Returns:
            Created monitor with ID and URL.
        """
        config = get_datadog_config()
        monitor_body = json.loads(monitor_json)

        with ApiClient(config) as api_client:
            api = MonitorsApi(api_client)
            response = api.create_monitor(body=Monitor(**monitor_body))

            return {
                "id": response.id,
                "name": response.name,
                "url": f"https://app.{DD_SITE}/monitors/{response.id}",
                "message": "Monitor created successfully",
            }

    @mcp.tool()
    async def create_monitors_batch(monitors_json: str) -> dict[str, Any]:
        """Create multiple monitors in Datadog.

        Args:
            monitors_json: JSON array of monitor definitions.

        Returns:
            Summary of created monitors.
        """
        config = get_datadog_config()
        monitors = json.loads(monitors_json)
        results = []
        errors = []

        with ApiClient(config) as api_client:
            api = MonitorsApi(api_client)

            for monitor_body in monitors:
                try:
                    response = api.create_monitor(body=Monitor(**monitor_body))
                    results.append({
                        "id": response.id,
                        "name": response.name,
                        "status": "created",
                    })
                except Exception as e:
                    errors.append({
                        "name": monitor_body.get("name", "unknown"),
                        "error": str(e),
                    })

        return {
            "created": len(results),
            "failed": len(errors),
            "monitors": results,
            "errors": errors,
        }
