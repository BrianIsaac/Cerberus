"""MCP client for SAS data tools."""

import json
from typing import Any

import httpx
from fastmcp import Client

from sas_generator.config import settings


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


class SASMCPClient:
    """Client for interacting with SAS MCP Server tools."""

    def __init__(self, server_url: str | None = None) -> None:
        """Initialise the MCP client.

        Args:
            server_url: URL of the SAS MCP server. Defaults to settings.
        """
        self.server_url = server_url or settings.sas_mcp_server_url
        self._client: Client | None = None

    async def __aenter__(self) -> "SASMCPClient":
        """Enter async context and connect to MCP server.

        Returns:
            SASMCPClient: The connected client instance.
        """
        base_url = self.server_url.rsplit("/mcp", 1)[0]
        id_token = await _get_identity_token(base_url)

        if id_token:
            self._client = Client(self.server_url, auth=id_token)
        else:
            self._client = Client(self.server_url)

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

    async def get_dataset_schema(self, dataset_name: str) -> dict[str, Any]:
        """Get schema for a SASHELP dataset.

        Args:
            dataset_name: Name of the dataset (e.g., SASHELP.CARS).

        Returns:
            Schema dictionary with columns and metadata.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._client:
            raise RuntimeError("Not connected. Use 'async with client:'")

        result = await self._client.call_tool(
            "get_dataset_schema",
            {"dataset_name": dataset_name},
        )
        return _extract_result(result)

    async def get_sample_data(
        self,
        dataset_name: str,
        n_rows: int = 3,
    ) -> dict[str, Any]:
        """Get sample rows from a dataset.

        Args:
            dataset_name: Name of the dataset.
            n_rows: Number of sample rows (max 10).

        Returns:
            Sample data dictionary.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._client:
            raise RuntimeError("Not connected. Use 'async with client:'")

        result = await self._client.call_tool(
            "get_sample_data",
            {"dataset_name": dataset_name, "n_rows": n_rows},
        )
        return _extract_result(result)

    async def list_available_datasets(self) -> dict[str, Any]:
        """List all available datasets.

        Returns:
            Dictionary containing list of dataset information.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._client:
            raise RuntimeError("Not connected. Use 'async with client:'")

        result = await self._client.call_tool("list_available_datasets", {})
        return _extract_result(result)
