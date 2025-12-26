#!/usr/bin/env python3
"""Factory script for creating agent-specific monitors.

This script generates Datadog monitor configurations for AI agents using
standardised templates. It supports fleet-wide monitors (using team:ai-agents)
and per-agent monitors (using service:{service} filter).

Usage:
    python scripts/create_monitor.py --service sas-generator --type latency
    python scripts/create_monitor.py --service ops-assistant --type quality
    python scripts/create_monitor.py --list-types
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


TEAM_TAG = "team:ai-agents"

MONITOR_TEMPLATES: dict[str, dict[str, Any]] = {
    "latency": {
        "name": "{service} - High P95 Latency",
        "type": "metric alert",
        "query": "avg(last_5m):p95:trace.http.request.duration{{service:{service}}} > 10",
        "message": """## Summary
The P95 request latency for {service} has exceeded 10 seconds.

## Impact
- Users experiencing slow response times
- Service: {{{{service.name}}}}

## What Triggered
- Monitor: High P95 Latency
- Window: Last 5 minutes
- Threshold: P95 latency > 10 seconds
- Current value: {{{{value}}}} seconds

## Next Actions
- [ ] Check LLM API status
- [ ] Review tool latency breakdown
- [ ] Investigate slow traces

@ops-oncall""",
        "options": {
            "notify_no_data": False,
            "no_data_timeframe": 10,
            "evaluation_delay": 60,
            "thresholds": {"critical": 10, "warning": 8},
            "notify_audit": True,
            "require_full_window": False,
            "include_tags": True,
        },
        "priority": 3,
        "severity": "warning",
        "monitor_type": "latency",
    },
    "quality": {
        "name": "{service} - Quality Degradation",
        "type": "metric alert",
        "query": "avg(last_15m):avg:llmobs.evaluation.ragas_faithfulness{{service:{service}}} < 0.7",
        "message": """## Summary
LLM quality degradation detected for {service} - faithfulness score below threshold.

## Impact
- Reduced accuracy of results
- Potential hallucinations in responses
- Service: {{{{service.name}}}}

## What Triggered
- Monitor: Quality Degradation
- Window: Last 15 minutes
- Threshold: RAGAS faithfulness < 0.7
- Current score: {{{{value}}}}

## Next Actions
- [ ] Review lowest quality traces
- [ ] Compare prompts to baseline
- [ ] Check LLM model version

@ops-oncall @ml-team""",
        "options": {
            "notify_no_data": False,
            "evaluation_delay": 120,
            "thresholds": {"critical": 0.7, "warning": 0.75},
            "notify_audit": True,
            "include_tags": True,
        },
        "priority": 2,
        "severity": "high",
        "monitor_type": "quality",
    },
    "error_rate": {
        "name": "{service} - Error Rate Spike",
        "type": "metric alert",
        "query": "avg(last_5m):sum:ai_agent.request.error{{service:{service}}}.as_count() / sum:ai_agent.request.count{{service:{service}}}.as_count() * 100 > 5",
        "message": """## Summary
Request error rate exceeds 5% for {service}.

## Impact
- Users receiving errors instead of responses
- Service reliability degradation
- Service: {{{{service.name}}}}

## What Triggered
- Monitor: Error Rate Spike
- Window: Last 5 minutes
- Threshold: error rate > 5%
- Current rate: {{{{value}}}}%

## Next Actions
- [ ] Review error traces
- [ ] Check LLM API status
- [ ] Verify input validation

@ops-oncall""",
        "options": {
            "notify_no_data": False,
            "evaluation_delay": 60,
            "thresholds": {"critical": 5, "warning": 2},
            "notify_audit": True,
            "include_tags": True,
        },
        "priority": 2,
        "severity": "high",
        "monitor_type": "reliability",
    },
    "tool_errors": {
        "name": "{service} - Tool Error Rate Spike",
        "type": "metric alert",
        "query": "avg(last_5m):sum:ai_agent.tool.errors{{service:{service}}}.as_rate() > 0.1",
        "message": """## Summary
Tool reliability failure detected for {service} - error rate spike.

## Impact
- Degraded agent functionality
- Failed tool queries
- Service: {{{{service.name}}}}

## What Triggered
- Monitor: Tool Error Rate Spike
- Window: Last 5 minutes
- Threshold: error rate > 0.1 (10%)
- Current rate: {{{{value}}}}

## Next Actions
- [ ] Check MCP server logs
- [ ] Verify API credentials
- [ ] Review error distribution by tool

@ops-oncall""",
        "options": {
            "notify_no_data": False,
            "evaluation_delay": 60,
            "thresholds": {"critical": 0.1, "warning": 0.05},
            "notify_audit": True,
            "include_tags": True,
        },
        "priority": 2,
        "severity": "high",
        "monitor_type": "tool_reliability",
    },
    "step_budget": {
        "name": "{service} - Step Budget Exceeded",
        "type": "metric alert",
        "query": "sum(last_5m):sum:ai_agent.step_budget_exceeded{{service:{service}}}.as_count() > 0",
        "message": """## Summary
Agent runaway detected for {service} - step budget exceeded.

## Impact
- Requests consuming excessive compute resources
- Potential cost overruns
- Service: {{{{service.name}}}}

## What Triggered
- Monitor: Step Budget Exceeded
- Window: Last 5 minutes
- Threshold: count > 0
- Exceeded count: {{{{value}}}}

## Next Actions
- [ ] Review traces hitting step cap
- [ ] Analyse LLM response quality
- [ ] Check tool error rates

@ops-oncall""",
        "options": {
            "notify_no_data": False,
            "evaluation_delay": 60,
            "thresholds": {"critical": 0},
            "notify_audit": True,
            "include_tags": True,
        },
        "priority": 3,
        "severity": "warning",
        "monitor_type": "governance",
    },
    "token_budget": {
        "name": "{service} - Token Budget Spike",
        "type": "metric alert",
        "query": "avg(last_15m):avg:llmobs.tokens.total{{service:{service}}} > 50000",
        "message": """## Summary
Token usage spike detected for {service} - potential cost overrun.

## Impact
- Higher than expected API costs
- Service: {{{{service.name}}}}

## What Triggered
- Monitor: Token Budget Spike
- Window: Last 15 minutes
- Threshold: average tokens > 50,000 per request
- Current average: {{{{value}}}} tokens

## Next Actions
- [ ] Review high-token traces
- [ ] Check prompt template lengths
- [ ] Analyse tool output sizes

@ops-oncall""",
        "options": {
            "notify_no_data": False,
            "evaluation_delay": 120,
            "thresholds": {"critical": 50000, "warning": 30000},
            "include_tags": True,
        },
        "priority": 3,
        "severity": "warning",
        "monitor_type": "cost",
    },
    "hallucination": {
        "name": "{service} - Hallucination Rate High",
        "type": "metric alert",
        "query": "avg(last_15m):sum:llmobs.evaluation.hallucination.fail{{service:{service}}}.as_count() / sum:llmobs.evaluation.hallucination.total{{service:{service}}}.as_count() * 100 > 10",
        "message": """## Summary
Hallucination rate exceeds 10% for {service}.

## Impact
- Users receiving inaccurate information
- Service credibility at risk
- Service: {{{{service.name}}}}

## What Triggered
- Monitor: Hallucination Rate High
- Window: Last 15 minutes
- Threshold: hallucination rate > 10%
- Current rate: {{{{value}}}}%

## Next Actions
- [ ] Review hallucinated traces
- [ ] Check context retrieval quality
- [ ] Verify prompt grounding instructions

@ops-oncall @ml-team""",
        "options": {
            "notify_no_data": False,
            "evaluation_delay": 120,
            "thresholds": {"critical": 10, "warning": 5},
            "include_tags": True,
        },
        "priority": 1,
        "severity": "critical",
        "monitor_type": "quality",
    },
}


def create_monitor(service: str, monitor_type: str) -> dict[str, Any]:
    """Create a monitor configuration for a specific service.

    Args:
        service: The service name (e.g., 'ops-assistant', 'sas-generator').
        monitor_type: The type of monitor to create (e.g., 'latency', 'quality').

    Returns:
        A dictionary containing the complete monitor configuration.

    Raises:
        ValueError: If the monitor_type is not recognised.
    """
    if monitor_type not in MONITOR_TEMPLATES:
        raise ValueError(
            f"Unknown monitor type: {monitor_type}. "
            f"Available types: {', '.join(MONITOR_TEMPLATES.keys())}"
        )

    template = MONITOR_TEMPLATES[monitor_type].copy()
    severity = template.pop("severity")
    template_monitor_type = template.pop("monitor_type")

    monitor = {
        "name": template["name"].format(service=service),
        "type": template["type"],
        "query": template["query"].format(service=service),
        "message": template["message"].format(service=service),
        "tags": [
            f"service:{service}",
            TEAM_TAG,
            f"monitor_type:{template_monitor_type}",
            f"severity:{severity}",
        ],
        "options": template["options"],
        "priority": template["priority"],
    }

    return monitor


def create_all_monitors(service: str) -> list[dict[str, Any]]:
    """Create all monitor types for a specific service.

    Args:
        service: The service name.

    Returns:
        A list of monitor configurations.
    """
    return [create_monitor(service, mt) for mt in MONITOR_TEMPLATES]


def list_monitor_types() -> None:
    """Print available monitor types and their descriptions."""
    print("Available monitor types:")
    print("-" * 50)
    for name, template in MONITOR_TEMPLATES.items():
        print(f"  {name:<15} - {template['name'].format(service='<service>')}")
    print()
    print(f"Total: {len(MONITOR_TEMPLATES)} monitor types available")


def main() -> int:
    """Main entry point for the monitor factory script.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Create Datadog monitor configurations for AI agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --service sas-generator --type latency
  %(prog)s --service ops-assistant --type quality
  %(prog)s --service ops-assistant --all
  %(prog)s --list-types
        """,
    )
    parser.add_argument(
        "--service",
        help="Service name for the monitor (e.g., 'ops-assistant', 'sas-generator')",
    )
    parser.add_argument(
        "--type",
        dest="monitor_type",
        choices=list(MONITOR_TEMPLATES.keys()),
        help="Type of monitor to create",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Create all monitor types for the specified service",
    )
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="List available monitor types",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args()

    if args.list_types:
        list_monitor_types()
        return 0

    if not args.service:
        parser.error("--service is required unless using --list-types")

    if args.all:
        monitors = create_all_monitors(args.service)
        output = {"monitors": monitors}
    elif args.monitor_type:
        output = create_monitor(args.service, args.monitor_type)
    else:
        parser.error("Either --type or --all is required")

    result = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(result)
        print(f"Monitor configuration written to {args.output}")
    else:
        print(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
