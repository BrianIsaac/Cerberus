"""Datadog Dashboards API tool for MCP server."""

from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v1.api.dashboards_api import DashboardsApi
from fastmcp import FastMCP

from mcp_server.tools import DD_SITE, get_datadog_config


def register_dashboards_tools(mcp: FastMCP) -> None:
    """Register dashboards tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def list_dashboards(
        query: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List Datadog dashboards with optional search query.

        Args:
            query: Search query to filter dashboards by title.
            limit: Maximum number of dashboards to return.

        Returns:
            Dictionary containing list of dashboards.
        """
        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api_instance = DashboardsApi(api_client)

            response = api_instance.list_dashboards()

            dashboards = []
            for dashboard in response.dashboards or []:
                created = getattr(dashboard, "created_at", None)
                modified = getattr(dashboard, "modified_at", None)
                layout = getattr(dashboard, "layout_type", None)

                dashboard_data = {
                    "id": dashboard.id,
                    "title": getattr(dashboard, "title", None),
                    "description": getattr(dashboard, "description", None),
                    "layout_type": layout.value if layout else None,
                    "url": getattr(dashboard, "url", None),
                    "created_at": str(created) if created else None,
                    "modified_at": str(modified) if modified else None,
                    "author_handle": getattr(dashboard, "author_handle", None),
                    "is_read_only": getattr(dashboard, "is_read_only", False),
                }

                if query:
                    title = (dashboard_data.get("title") or "").lower()
                    description = (dashboard_data.get("description") or "").lower()
                    if query.lower() in title or query.lower() in description:
                        dashboards.append(dashboard_data)
                else:
                    dashboards.append(dashboard_data)

            dashboards = dashboards[:limit]

        return {
            "total_dashboards": len(dashboards),
            "dashboards": dashboards,
            "dashboards_link": f"https://app.{DD_SITE}/dashboard/lists",
        }
