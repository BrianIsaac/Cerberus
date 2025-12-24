"""MCP tools for dataset operations."""

from typing import Any

from fastmcp import FastMCP

from sas_mcp_server.data.sashelp import get_sample, get_schema, list_datasets


def register_dataset_tools(mcp: FastMCP) -> None:
    """Register dataset-related MCP tools.

    Args:
        mcp: FastMCP server instance.
    """

    @mcp.tool()
    async def get_dataset_schema(dataset_name: str) -> dict[str, Any]:
        """Get the schema definition for a SASHELP dataset.

        Args:
            dataset_name: Name of the dataset (e.g., SASHELP.CARS, SASHELP.CLASS)

        Returns:
            Dictionary containing dataset name, description, observation count,
            and column definitions with types and formats
        """
        schema = get_schema(dataset_name)
        if not schema:
            available = list_datasets()
            return {
                "error": f"Dataset '{dataset_name}' not found",
                "available_datasets": available,
            }
        return schema

    @mcp.tool()
    async def get_sample_data(
        dataset_name: str,
        n_rows: int = 5
    ) -> dict[str, Any]:
        """Get sample rows from a SASHELP dataset.

        Args:
            dataset_name: Name of the dataset (e.g., SASHELP.CARS)
            n_rows: Number of sample rows to return (max 10)

        Returns:
            Dictionary with dataset name and sample rows
        """
        n_rows = min(n_rows, 10)
        sample = get_sample(dataset_name, n_rows)
        if not sample:
            available = list_datasets()
            return {
                "error": f"Dataset '{dataset_name}' not found",
                "available_datasets": available,
            }
        return {
            "dataset": dataset_name.upper(),
            "n_rows": len(sample),
            "data": sample,
        }

    @mcp.tool()
    async def list_available_datasets() -> dict[str, Any]:
        """List all available SASHELP datasets.

        Returns:
            Dictionary with list of dataset names and brief descriptions
        """
        datasets = []
        for name in list_datasets():
            schema = get_schema(name)
            if schema:
                datasets.append({
                    "name": name,
                    "description": schema["description"],
                    "observations": schema["observations"],
                    "columns": len(schema["columns"]),
                })
        return {"datasets": datasets}
