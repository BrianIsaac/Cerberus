#!/usr/bin/env python3
"""Factory script for creating AI agent SLOs.

This script generates Datadog SLO configurations for AI agents using
standardised templates. It supports fleet-wide SLOs (using team:ai-agents)
and per-service SLOs (using service:{service} filter).

Usage:
    python scripts/create_slo.py --scope fleet --type availability
    python scripts/create_slo.py --scope service --service ops-assistant --type latency
    python scripts/create_slo.py --list-types
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


TEAM_TAG = "team:ai-agents"

SLO_TEMPLATES: dict[str, dict[str, Any]] = {
    "availability": {
        "name": "{scope} - Availability SLO",
        "description": "99.9% of requests should complete successfully without errors",
        "type": "metric",
        "thresholds": [
            {"target": 99.9, "timeframe": "30d", "warning": 99.95},
            {"target": 99.5, "timeframe": "7d", "warning": 99.7},
        ],
        "query": {
            "numerator": "sum:trace.http.request.hits{{{filter}}}.as_count() - sum:trace.http.request.errors{{{filter}}}.as_count()",
            "denominator": "sum:trace.http.request.hits{{{filter}}}.as_count()",
        },
        "slo_type": "availability",
    },
    "latency": {
        "name": "{scope} - Latency SLO",
        "description": "95% of the time, P95 latency should be under 10 seconds",
        "type": "monitor",
        "thresholds": [
            {"target": 95.0, "timeframe": "30d", "warning": 97.0},
            {"target": 90.0, "timeframe": "7d", "warning": 92.0},
        ],
        "slo_type": "latency",
        "requires_monitor_ids": True,
    },
    "governance": {
        "name": "{scope} - Governance SLO",
        "description": "99% of requests should stay within step budgets and have no tool failures",
        "type": "metric",
        "thresholds": [
            {"target": 99.0, "timeframe": "30d", "warning": 99.5},
            {"target": 95.0, "timeframe": "7d", "warning": 97.0},
        ],
        "query": {
            "numerator": "sum:trace.http.request.hits{{{filter}}}.as_count() - sum:ai_agent.step_budget_exceeded{{{filter}}}.as_count() - sum:ai_agent.tool.errors{{{filter}}}.as_count()",
            "denominator": "sum:trace.http.request.hits{{{filter}}}.as_count()",
        },
        "slo_type": "governance",
    },
    "quality": {
        "name": "{scope} - Quality SLO (Hallucination-Free)",
        "description": "99.5% of requests should not produce hallucinated responses",
        "type": "metric",
        "thresholds": [
            {"target": 99.5, "timeframe": "30d", "warning": 99.7},
            {"target": 98.0, "timeframe": "7d", "warning": 99.0},
        ],
        "query": {
            "numerator": "sum:llmobs.evaluation.hallucination.total{{{filter}}}.as_count() - sum:llmobs.evaluation.hallucination.fail{{{filter}}}.as_count()",
            "denominator": "sum:llmobs.evaluation.hallucination.total{{{filter}}}.as_count()",
        },
        "slo_type": "quality",
    },
    "faithfulness": {
        "name": "{scope} - Faithfulness SLO",
        "description": "99% of responses should have RAGAS faithfulness score above 0.7",
        "type": "metric",
        "thresholds": [
            {"target": 99.0, "timeframe": "30d", "warning": 99.5},
            {"target": 95.0, "timeframe": "7d", "warning": 97.0},
        ],
        "query": {
            "numerator": "count:llmobs.evaluation.ragas_faithfulness{{{filter},value:>=0.7}}.as_count()",
            "denominator": "count:llmobs.evaluation.ragas_faithfulness{{{filter}}}.as_count()",
        },
        "slo_type": "quality",
    },
    "tool_reliability": {
        "name": "{scope} - Tool Reliability SLO",
        "description": "99% of tool calls should complete successfully",
        "type": "metric",
        "thresholds": [
            {"target": 99.0, "timeframe": "30d", "warning": 99.5},
            {"target": 95.0, "timeframe": "7d", "warning": 97.0},
        ],
        "query": {
            "numerator": "sum:ai_agent.tool.calls{{{filter}}}.as_count() - sum:ai_agent.tool.errors{{{filter}}}.as_count()",
            "denominator": "sum:ai_agent.tool.calls{{{filter}}}.as_count()",
        },
        "slo_type": "reliability",
    },
}


def create_slo(
    slo_type: str,
    scope: str = "fleet",
    service: str | None = None,
    monitor_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Create an SLO configuration for the AI agent fleet or a specific service.

    Args:
        slo_type: The type of SLO to create (e.g., 'availability', 'latency').
        scope: Either 'fleet' for team-wide or 'service' for per-service SLO.
        service: The service name (required if scope is 'service').
        monitor_ids: Optional list of monitor IDs for monitor-based SLOs.

    Returns:
        A dictionary containing the complete SLO configuration.

    Raises:
        ValueError: If the slo_type is not recognised or service is missing.
    """
    if slo_type not in SLO_TEMPLATES:
        raise ValueError(
            f"Unknown SLO type: {slo_type}. "
            f"Available types: {', '.join(SLO_TEMPLATES.keys())}"
        )

    if scope == "service" and not service:
        raise ValueError("Service name is required when scope is 'service'")

    template = SLO_TEMPLATES[slo_type].copy()
    template_slo_type = template.pop("slo_type")
    requires_monitor_ids = template.pop("requires_monitor_ids", False)

    if requires_monitor_ids and not monitor_ids:
        import sys
        print(
            f"Warning: {slo_type} SLO requires monitor_ids. "
            "Use --monitor-ids to specify the latency monitor ID.",
            file=sys.stderr
        )

    if scope == "fleet":
        scope_name = "AI Agents"
        # Use service tag for metrics filtering (team tag not indexed on trace metrics)
        filter_tag = "service:ops-assistant"
        tags = [TEAM_TAG, f"slo_type:{template_slo_type}"]
    else:
        scope_name = service
        filter_tag = f"service:{service}"
        tags = [f"service:{service}", TEAM_TAG, f"slo_type:{template_slo_type}"]

    slo = {
        "name": template["name"].format(scope=scope_name),
        "description": template["description"],
        "type": template["type"],
        "thresholds": template["thresholds"],
        "tags": tags,
        "monitor_ids": monitor_ids or [],
    }

    if "query" in template:
        slo["query"] = {
            "numerator": template["query"]["numerator"].format(filter=filter_tag),
            "denominator": template["query"]["denominator"].format(filter=filter_tag),
        }

    if slo_type == "quality":
        slo["tags"].append("evaluation:hallucination")
    elif slo_type == "faithfulness":
        slo["tags"].append("evaluation:faithfulness")

    return slo


def create_all_slos(
    scope: str = "fleet",
    service: str | None = None,
) -> list[dict[str, Any]]:
    """Create all SLO types for the fleet or a specific service.

    Args:
        scope: Either 'fleet' for team-wide or 'service' for per-service SLOs.
        service: The service name (required if scope is 'service').

    Returns:
        A list of SLO configurations.
    """
    return [create_slo(st, scope, service) for st in SLO_TEMPLATES]


def create_fleet_slos() -> dict[str, Any]:
    """Create the standard fleet-wide SLO configuration.

    Returns:
        A dictionary containing all fleet SLOs with metadata.
    """
    slos = [
        create_slo("availability", scope="fleet"),
        create_slo("latency", scope="fleet"),
        create_slo("governance", scope="fleet"),
        create_slo("quality", scope="fleet"),
    ]

    return {
        "slos": slos,
        "slo_metadata": {
            "created_by": "ai-agents-fleet-deployment",
            "purpose": "Track fleet-wide health, performance, governance, and LLM quality metrics across all AI agents tagged with team:ai-agents",
            "alert_configuration": {
                "availability_slo": {
                    "error_budget_alerts": [
                        {
                            "threshold": 50,
                            "message": "50% of availability error budget consumed. Review recent errors across AI agent fleet.",
                        },
                        {
                            "threshold": 90,
                            "message": "90% of availability error budget consumed. CRITICAL - immediate action required.",
                        },
                    ]
                },
                "latency_slo": {
                    "error_budget_alerts": [
                        {
                            "threshold": 50,
                            "message": "50% of latency error budget consumed. Review slow traces across AI agent fleet.",
                        },
                        {
                            "threshold": 90,
                            "message": "90% of latency error budget consumed. CRITICAL - performance degradation.",
                        },
                    ]
                },
                "governance_slo": {
                    "error_budget_alerts": [
                        {
                            "threshold": 50,
                            "message": "50% of governance error budget consumed. Review agent behaviour across fleet.",
                        },
                        {
                            "threshold": 90,
                            "message": "90% of governance error budget consumed. CRITICAL - agent reliability issues.",
                        },
                    ]
                },
                "quality_slo": {
                    "error_budget_alerts": [
                        {
                            "threshold": 25,
                            "message": "25% of quality error budget consumed. Review hallucination rates across fleet.",
                        },
                        {
                            "threshold": 75,
                            "message": "75% of quality error budget consumed. CRITICAL - LLM quality degradation.",
                        },
                    ]
                },
            },
        },
    }


def list_slo_types() -> None:
    """Print available SLO types and their descriptions."""
    print("Available SLO types:")
    print("-" * 60)
    for name, template in SLO_TEMPLATES.items():
        print(f"  {name:<18} - {template['description'][:50]}...")
    print()
    print(f"Total: {len(SLO_TEMPLATES)} SLO types available")


def main() -> int:
    """Main entry point for the SLO factory script.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Create Datadog SLO configurations for AI agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scope fleet --type availability
  %(prog)s --scope service --service ops-assistant --type latency
  %(prog)s --scope fleet --all
  %(prog)s --fleet-config
  %(prog)s --list-types
        """,
    )
    parser.add_argument(
        "--scope",
        choices=["fleet", "service"],
        default="fleet",
        help="Scope of the SLO: 'fleet' for team-wide or 'service' for per-service",
    )
    parser.add_argument(
        "--service",
        help="Service name (required when scope is 'service')",
    )
    parser.add_argument(
        "--type",
        dest="slo_type",
        choices=list(SLO_TEMPLATES.keys()),
        help="Type of SLO to create",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Create all SLO types for the specified scope",
    )
    parser.add_argument(
        "--fleet-config",
        action="store_true",
        help="Generate the standard fleet SLO configuration with metadata",
    )
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="List available SLO types",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--monitor-ids",
        type=int,
        nargs="*",
        help="Monitor IDs for monitor-based SLOs",
    )

    args = parser.parse_args()

    if args.list_types:
        list_slo_types()
        return 0

    if args.fleet_config:
        output = create_fleet_slos()
    elif args.all:
        slos = create_all_slos(args.scope, args.service)
        output = {"slos": slos}
    elif args.slo_type:
        output = create_slo(
            args.slo_type,
            args.scope,
            args.service,
            args.monitor_ids,
        )
    else:
        parser.error("Either --type, --all, --fleet-config, or --list-types is required")

    result = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(result)
        print(f"SLO configuration written to {args.output}")
    else:
        print(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
