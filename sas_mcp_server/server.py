"""SAS MCP Server - FastMCP server for SAS data tools."""

import asyncio
import os

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from sas_mcp_server.tools.datasets import register_dataset_tools
from sas_mcp_server.tools.procedures import register_procedure_tools

mcp = FastMCP(
    name="SAS Data Tools MCP Server",
    version="0.1.0",
    stateless_http=True,
    json_response=True,
)

register_dataset_tools(mcp)
register_procedure_tools(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Cloud Run.

    Args:
        request: Starlette request object.

    Returns:
        JSON response with health status.
    """
    return JSONResponse({
        "status": "healthy",
        "service": "sas-mcp-server",
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8081))
    asyncio.run(mcp.run_async(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
    ))
