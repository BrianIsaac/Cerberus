#!/usr/bin/env python3
"""Traffic generator for AI agents fleet.

Supports traffic generation for:
- ops-assistant: REST API (POST /ask)
- sas-generator: REST API (POST /generate)

Usage:
    # ops-assistant only (default)
    python scripts/traffic_gen.py --mode normal --rps 0.5 --duration 60

    # sas-generator only
    python scripts/traffic_gen.py --service sas --duration 60

    # Both services (fleet mode)
    python scripts/traffic_gen.py --service fleet --duration 60
"""

import argparse
import asyncio
import random
import time
from datetime import datetime
from typing import Generator

import httpx

# Service URLs
DEFAULT_OPS_URL = "https://ops-assistant-i4ney2dwya-uc.a.run.app"
DEFAULT_SAS_URL = "https://sas-generator-api-i4ney2dwya-uc.a.run.app"

# ops-assistant prompts
NORMAL_PROMPTS = [
    "What's the p95 latency for the api-gateway service in the last 15 minutes?",
    "Are there any errors in the checkout-service logs recently?",
    "Show me the error rate trend for payment-service over the last hour",
    "What changed in the user-service deployment window?",
    "Is the database connection pool healthy for order-service?",
]

LATENCY_PROMPTS = [
    """Provide a comprehensive analysis of all services in the production environment
    including latency percentiles (p50, p75, p90, p95, p99), error rates by endpoint,
    throughput trends, and correlate any anomalies with recent deployments."""
    * 2,
]

MCP_HEALTH_PROMPTS = [
    "Use the nonexistent_mcp_tool to check service health",
    "Call the invalid-tool-name with parameters {invalid: json}",
    "Execute mcp_timeout_tool with extremely_large_dataset parameter",
]

# sas-generator prompts
SAS_PROMPTS = [
    "Show me the average MSRP by vehicle type from the CARS dataset",
    "Calculate the correlation between height and weight for students in CLASS",
    "Find the top 10 most expensive cars with their MPG ratings",
    "Count the number of vehicles by origin and type",
    "What is the average horsepower by car make in SASHELP.CARS?",
    "Show age distribution of students in the CLASS dataset",
    "Calculate mean blood pressure by smoking status in HEART",
]


def get_prompts_for_mode(mode: str) -> list[str]:
    """Get prompt list for the specified mode."""
    mode_prompts = {
        "normal": NORMAL_PROMPTS,
        "latency": LATENCY_PROMPTS,
        "mcp_health": MCP_HEALTH_PROMPTS,
        "sas": SAS_PROMPTS,
    }
    return mode_prompts.get(mode, NORMAL_PROMPTS)


def generate_requests(
    mode: str,
    rps: float,
    duration: int,
    seed: int | None = None,
) -> Generator[dict, None, None]:
    """Generate request payloads at specified rate."""
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


async def send_ops_request(
    client: httpx.AsyncClient,
    base_url: str,
    payload: dict,
) -> dict:
    """Send a request to the ops assistant."""
    start_time = time.time()

    try:
        response = await client.post(
            f"{base_url}/ask",
            json=payload,
            timeout=120.0,
        )

        latency_ms = (time.time() - start_time) * 1000

        return {
            "service": "ops-assistant",
            "status": response.status_code,
            "latency_ms": latency_ms,
            "success": response.status_code == 200,
            "response": response.json() if response.status_code == 200 else None,
            "error": response.text if response.status_code != 200 else None,
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "service": "ops-assistant",
            "status": 0,
            "latency_ms": latency_ms,
            "success": False,
            "error": str(e),
        }


async def send_sas_request(
    client: httpx.AsyncClient,
    base_url: str,
    query: str,
) -> dict:
    """Send a request to the sas-generator API."""
    start_time = time.time()

    try:
        response = await client.post(
            f"{base_url}/generate",
            json={"query": query},
            timeout=120.0,
        )

        latency_ms = (time.time() - start_time) * 1000

        return {
            "service": "sas-generator",
            "status": response.status_code,
            "latency_ms": latency_ms,
            "success": response.status_code == 200,
            "response": response.json() if response.status_code == 200 else None,
            "error": response.text if response.status_code != 200 else None,
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "service": "sas-generator",
            "status": 0,
            "latency_ms": latency_ms,
            "success": False,
            "error": str(e),
        }


async def run_ops_traffic(
    base_url: str,
    mode: str,
    rps: float,
    duration: int,
    seed: int | None = None,
) -> dict:
    """Run traffic generation for ops-assistant."""
    print(f"Starting ops-assistant traffic: mode={mode}, rps={rps}, duration={duration}s")
    print("-" * 50)

    stats = {"total": 0, "success": 0, "errors": 0, "latencies": []}

    async with httpx.AsyncClient() as client:
        for payload in generate_requests(mode, rps, duration, seed):
            result = await send_ops_request(client, base_url, payload)

            stats["total"] += 1
            stats["latencies"].append(result["latency_ms"])

            if result["success"]:
                stats["success"] += 1
                status = "OK"
            else:
                stats["errors"] += 1
                status = f"ERR({result['status']})"

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] ops-assistant "
                f"{status} {result['latency_ms']:.0f}ms - "
                f"{payload['question'][:40]}..."
            )

    return stats


async def run_sas_traffic(
    base_url: str,
    rps: float,
    duration: int,
    seed: int | None = None,
) -> dict:
    """Run traffic generation for sas-generator."""
    print(f"Starting sas-generator traffic: rps={rps}, duration={duration}s")
    print("-" * 50)

    if seed:
        random.seed(seed)

    stats = {"total": 0, "success": 0, "errors": 0, "latencies": []}
    interval = 1.0 / rps if rps > 0 else 1.0
    end_time = time.time() + duration

    async with httpx.AsyncClient() as client:
        while time.time() < end_time:
            query = random.choice(SAS_PROMPTS)
            result = await send_sas_request(client, base_url, query)

            stats["total"] += 1
            stats["latencies"].append(result["latency_ms"])

            if result["success"]:
                stats["success"] += 1
                status = "OK"
            else:
                stats["errors"] += 1
                status = f"ERR({result['status']})"

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] sas-generator "
                f"{status} {result['latency_ms']:.0f}ms - {query[:40]}..."
            )

            await asyncio.sleep(interval)

    return stats


async def run_fleet_traffic(
    ops_url: str,
    sas_url: str,
    mode: str,
    rps: float,
    duration: int,
    seed: int | None = None,
) -> None:
    """Run traffic for both services concurrently."""
    print("Starting fleet traffic generation:")
    print(f"  ops-assistant: {ops_url}")
    print(f"  sas-generator: {sas_url}")
    print(f"  Mode: {mode}, RPS: {rps}, Duration: {duration}s")
    print("=" * 50)

    ops_task = asyncio.create_task(
        run_ops_traffic(ops_url, mode, rps / 2, duration, seed)
    )
    sas_task = asyncio.create_task(
        run_sas_traffic(sas_url, rps / 2, duration, seed)
    )

    ops_stats, sas_stats = await asyncio.gather(ops_task, sas_task)

    print("=" * 50)
    print("Fleet Summary:")
    print(f"  ops-assistant: {ops_stats['success']}/{ops_stats['total']} successful")
    print(f"  sas-generator: {sas_stats['success']}/{sas_stats['total']} successful")


def print_stats(stats: dict) -> None:
    """Print traffic statistics."""
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
    parser = argparse.ArgumentParser(description="Traffic generator for AI agents fleet")
    parser.add_argument(
        "--service",
        choices=["ops", "sas", "fleet"],
        default="ops",
        help="Target service(s): ops=ops-assistant, sas=sas-generator, fleet=both",
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "latency", "mcp_health"],
        default="normal",
        help="Traffic mode for ops-assistant",
    )
    parser.add_argument("--rps", type=float, default=0.5, help="Requests per second")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument(
        "--ops-url",
        default=DEFAULT_OPS_URL,
        help="Base URL of ops-assistant",
    )
    parser.add_argument(
        "--sas-url",
        default=DEFAULT_SAS_URL,
        help="Base URL of sas-generator API",
    )

    args = parser.parse_args()

    if args.service == "ops":
        stats = asyncio.run(
            run_ops_traffic(
                base_url=args.ops_url,
                mode=args.mode,
                rps=args.rps,
                duration=args.duration,
                seed=args.seed,
            )
        )
        print_stats(stats)

    elif args.service == "sas":
        stats = asyncio.run(
            run_sas_traffic(
                base_url=args.sas_url,
                rps=args.rps,
                duration=args.duration,
                seed=args.seed,
            )
        )
        print_stats(stats)

    elif args.service == "fleet":
        asyncio.run(
            run_fleet_traffic(
                ops_url=args.ops_url,
                sas_url=args.sas_url,
                mode=args.mode,
                rps=args.rps,
                duration=args.duration,
                seed=args.seed,
            )
        )


if __name__ == "__main__":
    main()
