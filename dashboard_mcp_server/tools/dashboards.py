"""Dashboard management tools for MCP server."""

import asyncio
import json
from functools import partial
from pathlib import Path
from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v1.api.dashboards_api import DashboardsApi
from fastmcp import FastMCP

from dashboard_mcp_server.tools import DD_SITE, get_datadog_config

# Read-only fields that must be removed before updating a dashboard
READ_ONLY_FIELDS = [
    "author_handle",
    "author_name",
    "created_at",
    "modified_at",
    "url",
    "id",
]


def _strip_read_only_fields(dashboard_dict: dict[str, Any]) -> dict[str, Any]:
    """Remove read-only fields from dashboard dict before API update.

    Args:
        dashboard_dict: Dashboard definition from API response.

    Returns:
        Dashboard dict with read-only fields removed.
    """
    for field in READ_ONLY_FIELDS:
        dashboard_dict.pop(field, None)
    return dashboard_dict


def _sync_get_dashboard(dashboard_id: str) -> dict[str, Any]:
    """Synchronously fetch a dashboard from Datadog API.

    Args:
        dashboard_id: The dashboard ID to retrieve.

    Returns:
        Dashboard definition as dictionary.
    """
    config = get_datadog_config()
    with ApiClient(config) as api_client:
        api = DashboardsApi(api_client)
        response = api.get_dashboard(dashboard_id=dashboard_id)
        return response.to_dict()


def _sync_update_dashboard(
    dashboard_id: str,
    dashboard_body: dict[str, Any],
) -> dict[str, Any]:
    """Synchronously update a dashboard via Datadog API.

    Args:
        dashboard_id: The dashboard ID to update.
        dashboard_body: Dashboard definition (read-only fields stripped).

    Returns:
        Updated dashboard info.
    """
    config = get_datadog_config()
    with ApiClient(config) as api_client:
        api = DashboardsApi(api_client)
        response = api.update_dashboard(
            dashboard_id=dashboard_id,
            body=dashboard_body,
        )
        return {
            "id": response.id,
            "title": response.title,
        }


def _sync_add_widget_group(
    dashboard_id: str,
    group_title: str,
    widgets: list[dict[str, Any]],
    service: str,
) -> dict[str, Any]:
    """Synchronously add a widget group to a dashboard.

    Args:
        dashboard_id: The dashboard ID to update.
        group_title: Title for the new widget group.
        widgets: List of widget definitions.
        service: Service name for the widget group.

    Returns:
        Result with dashboard ID, group ID, and URL.
    """
    config = get_datadog_config()
    with ApiClient(config) as api_client:
        api = DashboardsApi(api_client)

        # Get current dashboard
        dashboard = api.get_dashboard(dashboard_id=dashboard_id)
        dashboard_dict = dashboard.to_dict()
        dashboard_dict = _strip_read_only_fields(dashboard_dict)

        # Generate new group ID (find max existing + 10)
        existing_ids = [w.get("id", 0) for w in dashboard_dict.get("widgets", [])]
        new_group_id = max(existing_ids, default=0) + 10

        # Create new group
        new_group = {
            "id": new_group_id,
            "definition": {
                "type": "group",
                "title": group_title,
                "layout_type": "ordered",
                "widgets": widgets,
            },
        }

        # Find insertion point (before "Operations & Actionable Items" if exists)
        insert_index = len(dashboard_dict["widgets"])
        for i, w in enumerate(dashboard_dict["widgets"]):
            if w.get("definition", {}).get("title") == "Operations & Actionable Items":
                insert_index = i
                break

        dashboard_dict["widgets"].insert(insert_index, new_group)

        # Update template variables to include new service
        for tv in dashboard_dict.get("template_variables", []):
            if tv.get("name") == "service":
                if service not in tv.get("available_values", []):
                    tv["available_values"].append(service)
                    tv["available_values"].sort()

        # Update dashboard
        response = api.update_dashboard(
            dashboard_id=dashboard_id,
            body=dashboard_dict,
        )

        return {
            "id": response.id,
            "group_id": new_group_id,
            "group_title": group_title,
            "widgets_added": len(widgets),
        }


def register_dashboard_tools(mcp: FastMCP) -> None:
    """Register dashboard management tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def get_dashboard(dashboard_id: str) -> dict[str, Any]:
        """Get a dashboard by ID.

        Args:
            dashboard_id: The dashboard ID to retrieve.

        Returns:
            Dashboard definition as JSON.
        """
        return await asyncio.to_thread(_sync_get_dashboard, dashboard_id)

    @mcp.tool()
    async def update_dashboard(
        dashboard_id: str,
        dashboard_json: str,
    ) -> dict[str, Any]:
        """Update an existing dashboard.

        Args:
            dashboard_id: The dashboard ID to update.
            dashboard_json: Complete dashboard definition as JSON string.

        Returns:
            Updated dashboard with ID and URL.
        """
        dashboard_body = json.loads(dashboard_json)
        dashboard_body = _strip_read_only_fields(dashboard_body)

        result = await asyncio.to_thread(
            _sync_update_dashboard, dashboard_id, dashboard_body
        )
        return {
            **result,
            "url": f"https://app.{DD_SITE}/dashboard/{result['id']}",
            "message": "Dashboard updated successfully",
        }

    @mcp.tool()
    async def add_widget_group_to_dashboard(
        dashboard_id: str,
        group_title: str,
        widgets_json: str,
        service: str,
    ) -> dict[str, Any]:
        """Add a new widget group to an existing dashboard.

        Args:
            dashboard_id: The dashboard ID to update.
            group_title: Title for the new widget group.
            widgets_json: JSON array of widget definitions.
            service: Service name for the widget group.

        Returns:
            Updated dashboard info including new group ID.
        """
        widgets = json.loads(widgets_json)

        result = await asyncio.to_thread(
            _sync_add_widget_group,
            dashboard_id,
            group_title,
            widgets,
            service,
        )

        return {
            **result,
            "url": f"https://app.{DD_SITE}/dashboard/{result['id']}",
            "message": f"Added widget group '{group_title}' with {result['widgets_added']} widgets",
        }

    @mcp.tool()
    async def read_local_dashboard(
        dashboard_path: str = "infra/datadog/dashboard.json",
    ) -> dict[str, Any]:
        """Read dashboard JSON from local file.

        Args:
            dashboard_path: Path to dashboard JSON file.

        Returns:
            Dashboard definition.
        """
        path = Path(dashboard_path)
        if not path.exists():
            return {"error": f"Dashboard file not found: {dashboard_path}"}

        with open(path) as f:
            return json.load(f)

    @mcp.tool()
    async def write_local_dashboard(
        dashboard_json: str,
        dashboard_path: str = "infra/datadog/dashboard.json",
    ) -> dict[str, Any]:
        """Write dashboard JSON to local file.

        Args:
            dashboard_json: Dashboard definition as JSON string.
            dashboard_path: Path to dashboard JSON file.

        Returns:
            Success message.
        """
        path = Path(dashboard_path)
        dashboard = json.loads(dashboard_json)

        with open(path, "w") as f:
            json.dump(dashboard, f, indent=2)
            f.write("\n")

        return {
            "path": str(path),
            "message": "Dashboard written successfully",
        }
