"""Test MCP client with Datadog LLM Observability."""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env first
load_dotenv(Path(__file__).parent.parent / ".env")

# Remove RAGAS evaluators (version incompatibility with ddtrace)
os.environ.pop("DD_LLMOBS_EVALUATORS", None)

# Enable LLM Observability
os.environ["DD_LLMOBS_ENABLED"] = "1"
os.environ["DD_LLMOBS_AGENTLESS_ENABLED"] = "1"
os.environ["DD_LLMOBS_ML_APP"] = "ops-assistant"

from ddtrace.llmobs import LLMObs

# Initialize LLMObs
LLMObs.enable(
    ml_app="ops-assistant",
    api_key=os.getenv("DD_API_KEY"),
    site=os.getenv("DD_SITE", "datadoghq.com"),
    agentless_enabled=True,
)

from ops_triage_agent.mcp_client.client import DatadogMCPClient


async def main():
    """Test MCP client calls."""
    print("Testing MCP client with LLM Observability...")

    async with DatadogMCPClient() as client:
        # Test list_monitors
        print("\n1. Testing list_monitors...")
        result = await client.list_monitors(limit=3)
        print(f"   Found {result} monitors")

        # Test list_dashboards
        print("\n2. Testing list_dashboards...")
        result = await client.list_dashboards(limit=3)
        print(f"   Found {result} dashboards")

        # Test get_logs
        print("\n3. Testing get_logs...")
        result = await client.get_logs(service="ops-assistant", limit=3)
        print(f"   Result: {result}")

    print("\n Flushing LLMObs traces...")
    LLMObs.flush()
    print("Done! Check Datadog LLM Observability in ~2 minutes.")


if __name__ == "__main__":
    asyncio.run(main())
