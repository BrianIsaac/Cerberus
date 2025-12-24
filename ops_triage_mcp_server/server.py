"""FastMCP server exposing Datadog tools."""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

# Load .env from project root (must happen before importing tools which read env vars)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from mcp_server.tools.dashboards import register_dashboards_tools  # noqa: E402
from mcp_server.tools.incidents import register_incidents_tools  # noqa: E402
from mcp_server.tools.logs import register_logs_tools  # noqa: E402
from mcp_server.tools.metrics import register_metrics_tools  # noqa: E402
from mcp_server.tools.monitors import register_monitors_tools  # noqa: E402
from mcp_server.tools.traces import register_traces_tools  # noqa: E402

mcp = FastMCP(
    name="Datadog MCP Server",
    version="0.1.0",
)

register_metrics_tools(mcp)
register_logs_tools(mcp)
register_traces_tools(mcp)
register_incidents_tools(mcp)
register_monitors_tools(mcp)
register_dashboards_tools(mcp)


if __name__ == "__main__":
    asyncio.run(
        mcp.run_async(
            transport="streamable-http",
            host="0.0.0.0",
            port=int(os.getenv("PORT", 8080)),
        )
    )
