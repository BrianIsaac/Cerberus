"""FastMCP server for Datadog dashboard write operations."""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# Load .env from project root (must happen before importing tools which read env vars)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from dashboard_mcp_server.config import settings  # noqa: E402
from dashboard_mcp_server.tools.dashboards import register_dashboard_tools  # noqa: E402
from dashboard_mcp_server.tools.monitors import register_monitor_tools  # noqa: E402
from dashboard_mcp_server.tools.slos import register_slo_tools  # noqa: E402

mcp = FastMCP(
    name="Dashboard MCP Server",
    version=settings.dd_version,
)

register_dashboard_tools(mcp)
register_monitor_tools(mcp)
register_slo_tools(mcp)


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
        "service": settings.dd_service,
        "version": settings.dd_version,
    })


# Create ASGI app for uvicorn (after all routes registered)
app = mcp.http_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8084))
    asyncio.run(mcp.run_async(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        stateless_http=True,
        json_response=True,
    ))
