#!/usr/bin/env python3
"""Traffic generator for ops assistant demo.

Usage:
    python scripts/traffic_gen.py --mode normal --rps 0.5 --duration 300
    python scripts/traffic_gen.py --mode latency --rps 1.0 --duration 60
    python scripts/traffic_gen.py --mode hallucination --rps 0.2 --duration 120
    python scripts/traffic_gen.py --mode mcp_health --rps 0.5 --duration 120
"""

import argparse
import asyncio
import random
import time
from datetime import datetime
from typing import Generator

import httpx

# Normal traffic prompts
NORMAL_PROMPTS = [
    "What's the p95 latency for the api-gateway service in the last 15 minutes?",
    "Are there any errors in the checkout-service logs recently?",
    "Show me the error rate trend for payment-service over the last hour",
    "What changed in the user-service deployment window?",
    "Is the database connection pool healthy for order-service?",
]

# Latency-inducing prompts (long, complex)
LATENCY_PROMPTS = [
    """Provide a comprehensive analysis of all services in the production environment
    including latency percentiles (p50, p75, p90, p95, p99), error rates by endpoint,
    throughput trends, and correlate any anomalies with recent deployments.
    Also check for database connection issues, cache hit rates, and external API
    dependencies. Include recommendations for each issue found."""
    * 2,
]

# Runaway prompts (missing identifiers, vague)
RUNAWAY_PROMPTS = [
    "Check the thing",
    "Why is it broken?",
    "Fix the production issue",
    "What happened?",
    "Something is wrong with the app",
]

# Tool error prompts (target non-existent services)
TOOL_ERROR_PROMPTS = [
    "Check metrics for nonexistent-service-12345",
    "Get logs from fake-microservice-xyz",
    "Show traces for undefined-api-000",
]

# Hallucination prompts
HALLUCINATION_PROMPTS = [
    "Show me metrics for the unicorn-service in production",
    "What was the deployment time for service-xyz-fake yesterday?",
    "Retrieve logs for the nonexistent-app from last week",
    "Analyse the quantum-computing-service latency",
    "Check the blockchain-validator-service for errors",
]

# PII test prompts
PII_TEST_PROMPTS = [
    "Create incident for user test-user@example.com with card 4532-1234-5678-9010",
    "Check logs mentioning SSN 123-45-6789",
    "Find requests from user john.doe@company.com",
    "Search for customer with phone 555-123-4567",
]

# Low confidence prompts
LOW_CONFIDENCE_PROMPTS = [
    "Something's wrong, can you check?",
    "Why is it slow?",
    "Fix the thing from earlier",
    "Is everything okay?",
    "Help me with the issue",
]

# MCP health test prompts (trigger MCP connection issues)
MCP_HEALTH_PROMPTS = [
    "Use the nonexistent_mcp_tool to check service health",
    "Call the invalid-tool-name with parameters {invalid: json}",
    "Execute mcp_timeout_tool with extremely_large_dataset parameter",
    "Invoke undefined_datadog_tool for metrics retrieval",
    "Run broken-mcp-service tool with malformed arguments",
    "Access disconnected_mcp_server to fetch logs",
    "Call mcp_tool_that_doesnt_exist for trace analysis",
    "Use fake_monitoring_tool with null parameters",
]


def get_prompts_for_mode(mode: str) -> list[str]:
    """Get prompt list for the specified mode.

    Args:
        mode: Traffic mode name.

    Returns:
        List of prompts for the mode.
    """
    mode_prompts = {
        "normal": NORMAL_PROMPTS,
        "latency": LATENCY_PROMPTS,
        "runaway": RUNAWAY_PROMPTS,
        "tool_error": TOOL_ERROR_PROMPTS,
        "hallucination": HALLUCINATION_PROMPTS,
        "pii_test": PII_TEST_PROMPTS,
        "low_confidence": LOW_CONFIDENCE_PROMPTS,
        "mcp_health": MCP_HEALTH_PROMPTS,
    }
    return mode_prompts.get(mode, NORMAL_PROMPTS)


def generate_requests(
    mode: str,
    rps: float,
    duration: int,
    seed: int | None = None,
) -> Generator[dict, None, None]:
    """Generate request payloads at specified rate.

    Args:
        mode: Traffic mode.
        rps: Requests per second.
        duration: Duration in seconds.
        seed: Random seed for reproducibility.

    Yields:
        Request payload dictionaries.
    """
    if seed:
        random.seed(seed)

    prompts = get_prompts_for_mode(mode)
    interval = 1.0 / rps if rps > 0 else 1.0
    end_time = time.time() + duration

    while time.time() < end_time:
        prompt = random.choice(prompts)

        service = None
        if mode == "normal":
            service = random.choice([
                "api-gateway",
                "checkout-service",
                "payment-service",
                "user-service",
                "order-service",
            ])

        yield {
            "question": prompt,
            "service": service,
            "time_window": random.choice(["last_5m", "last_15m", "last_1h"]),
        }

        time.sleep(interval)


async def send_request(
    client: httpx.AsyncClient,
    base_url: str,
    payload: dict,
) -> dict:
    """Send a request to the ops assistant.

    Args:
        client: HTTP client.
        base_url: Base URL of the service.
        payload: Request payload.

    Returns:
        Response data.
    """
    start_time = time.time()

    try:
        response = await client.post(
            f"{base_url}/ask",
            json=payload,
            timeout=120.0,
        )

        latency_ms = (time.time() - start_time) * 1000

        return {
            "status": response.status_code,
            "latency_ms": latency_ms,
            "success": response.status_code == 200,
            "response": response.json() if response.status_code == 200 else None,
            "error": response.text if response.status_code != 200 else None,
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "status": 0,
            "latency_ms": latency_ms,
            "success": False,
            "error": str(e),
        }


async def run_traffic(
    base_url: str,
    mode: str,
    rps: float,
    duration: int,
    seed: int | None = None,
) -> None:
    """Run traffic generation.

    Args:
        base_url: Base URL of the service.
        mode: Traffic mode.
        rps: Requests per second.
        duration: Duration in seconds.
        seed: Random seed.
    """
    print("Starting traffic generation:")
    print(f"  Mode: {mode}")
    print(f"  RPS: {rps}")
    print(f"  Duration: {duration}s")
    print(f"  Base URL: {base_url}")
    print("-" * 50)

    stats = {
        "total": 0,
        "success": 0,
        "errors": 0,
        "latencies": [],
    }

    async with httpx.AsyncClient() as client:
        for payload in generate_requests(mode, rps, duration, seed):
            result = await send_request(client, base_url, payload)

            stats["total"] += 1
            stats["latencies"].append(result["latency_ms"])

            if result["success"]:
                stats["success"] += 1
                status = "OK"
            else:
                stats["errors"] += 1
                status = f"ERR({result['status']})"

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"{status} {result['latency_ms']:.0f}ms - "
                f"{payload['question'][:50]}..."
            )

    print("-" * 50)
    print("Summary:")
    print(f"  Total requests: {stats['total']}")
    print(f"  Successful: {stats['success']}")
    print(f"  Errors: {stats['errors']}")

    if stats["latencies"]:
        avg_latency = sum(stats["latencies"]) / len(stats["latencies"])
        sorted_latencies = sorted(stats["latencies"])
        p95_idx = int(len(sorted_latencies) * 0.95)
        p95_latency = (
            sorted_latencies[p95_idx]
            if p95_idx < len(sorted_latencies)
            else sorted_latencies[-1]
        )

        print(f"  Avg latency: {avg_latency:.0f}ms")
        print(f"  P95 latency: {p95_latency:.0f}ms")


def main() -> None:
    """Parse arguments and run traffic generation."""
    parser = argparse.ArgumentParser(description="Traffic generator for ops assistant")
    parser.add_argument(
        "--mode",
        choices=[
            "normal",
            "latency",
            "runaway",
            "tool_error",
            "hallucination",
            "pii_test",
            "low_confidence",
            "mcp_health",
        ],
        default="normal",
        help="Traffic mode",
    )
    parser.add_argument("--rps", type=float, default=0.5, help="Requests per second")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the ops assistant",
    )

    args = parser.parse_args()

    asyncio.run(
        run_traffic(
            base_url=args.base_url,
            mode=args.mode,
            rps=args.rps,
            duration=args.duration,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()
