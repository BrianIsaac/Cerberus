"""SLO management tools for MCP server."""

import json
from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v1.api.service_level_objectives_api import (
    ServiceLevelObjectivesApi,
)
from fastmcp import FastMCP

from dashboard_mcp_server.tools import DD_SITE, get_datadog_config


def register_slo_tools(mcp: FastMCP) -> None:
    """Register SLO management tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def create_slo(slo_json: str) -> dict[str, Any]:
        """Create a new SLO in Datadog.

        Args:
            slo_json: SLO definition as JSON string.

        Returns:
            Created SLO with ID and URL.
        """
        config = get_datadog_config()
        slo_body = json.loads(slo_json)

        with ApiClient(config) as api_client:
            api = ServiceLevelObjectivesApi(api_client)
            response = api.create_slo(body=slo_body)

            slo_data = response.data[0] if response.data else {}
            slo_id = getattr(slo_data, "id", None)
            slo_name = getattr(slo_data, "name", None)

            return {
                "id": slo_id,
                "name": slo_name,
                "url": f"https://app.{DD_SITE}/slo?slo_id={slo_id}",
                "message": "SLO created successfully",
            }

    @mcp.tool()
    async def create_slos_batch(slos_json: str) -> dict[str, Any]:
        """Create multiple SLOs in Datadog.

        Args:
            slos_json: JSON array of SLO definitions.

        Returns:
            Summary of created SLOs.
        """
        config = get_datadog_config()
        slos = json.loads(slos_json)
        results = []
        errors = []

        with ApiClient(config) as api_client:
            api = ServiceLevelObjectivesApi(api_client)

            for slo_body in slos:
                try:
                    response = api.create_slo(body=slo_body)
                    slo_data = response.data[0] if response.data else {}
                    slo_id = getattr(slo_data, "id", None)
                    slo_name = getattr(slo_data, "name", None)

                    results.append({
                        "id": slo_id,
                        "name": slo_name,
                        "status": "created",
                    })
                except Exception as e:
                    errors.append({
                        "name": slo_body.get("name", "unknown"),
                        "error": str(e),
                    })

        return {
            "created": len(results),
            "failed": len(errors),
            "slos": results,
            "errors": errors,
        }
