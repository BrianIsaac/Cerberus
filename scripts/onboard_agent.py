#!/usr/bin/env python3
"""Automated onboarding script for new AI agents.

This script automates the process of adding a new AI agent to the observability
platform. It updates dashboard template variables, generates monitor configurations,
and creates SLO configurations using the existing factory scripts.

Usage:
    python scripts/onboard_agent.py --service my-new-agent --agent-type research
    python scripts/onboard_agent.py --service my-new-agent --agent-type code-generation --create-monitors
    python scripts/onboard_agent.py --service my-new-agent --agent-type triage --create-monitors --create-slos
    python scripts/onboard_agent.py --service my-new-agent --agent-type assistant --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TEAM_TAG = "team:ai-agents"
DEFAULT_DASHBOARD_PATH = Path("infra/datadog/dashboard.json")
DEFAULT_OUTPUT_DIR = Path("infra/datadog")

VALID_AGENT_TYPES = [
    "triage",
    "code-generation",
    "research",
    "assistant",
    "analysis",
    "automation",
]

MONITOR_TYPES = [
    "latency",
    "quality",
    "error_rate",
    "tool_errors",
    "step_budget",
    "token_budget",
    "hallucination",
]

SLO_TYPES = [
    "availability",
    "latency",
    "governance",
    "quality",
    "faithfulness",
    "tool_reliability",
]


def update_dashboard(
    service: str,
    dashboard_path: Path,
    dry_run: bool = False,
) -> bool:
    """Add service to dashboard template variables.

    Args:
        service: The service name to add.
        dashboard_path: Path to the dashboard JSON file.
        dry_run: If True, only print what would be done.

    Returns:
        True if the dashboard was updated, False if service already exists.
    """
    if not dashboard_path.exists():
        print(f"Error: Dashboard file not found at {dashboard_path}", file=sys.stderr)
        return False

    with open(dashboard_path) as f:
        dashboard = json.load(f)

    service_var = None
    for var in dashboard.get("template_variables", []):
        if var.get("name") == "service":
            service_var = var
            break

    if service_var is None:
        print("Error: No 'service' template variable found in dashboard", file=sys.stderr)
        return False

    available_values = service_var.get("available_values", [])

    if service in available_values:
        print(f"Service '{service}' already exists in dashboard template variables")
        return False

    if dry_run:
        print(f"[DRY RUN] Would add '{service}' to dashboard template variables")
        print(f"[DRY RUN] Current services: {available_values}")
        return True

    available_values.append(service)
    service_var["available_values"] = sorted(available_values)

    with open(dashboard_path, "w") as f:
        json.dump(dashboard, f, indent=2)
        f.write("\n")

    print(f"Added '{service}' to dashboard template variables")
    return True


def create_monitor_config(
    service: str,
    monitor_type: str,
) -> dict[str, Any]:
    """Create a monitor configuration for a specific service and type.

    Args:
        service: The service name.
        monitor_type: The type of monitor to create.

    Returns:
        The monitor configuration dictionary.
    """
    from create_monitor import create_monitor
    return create_monitor(service, monitor_type)


def create_monitors(
    service: str,
    output_dir: Path,
    dry_run: bool = False,
) -> Path | None:
    """Create all monitor configurations for a service.

    Args:
        service: The service name.
        output_dir: Directory to write the output file.
        dry_run: If True, only print what would be done.

    Returns:
        Path to the created file, or None if dry run.
    """
    monitors = []
    for monitor_type in MONITOR_TYPES:
        try:
            monitor = create_monitor_config(service, monitor_type)
            monitors.append(monitor)
        except Exception as e:
            print(f"Warning: Could not create {monitor_type} monitor: {e}", file=sys.stderr)

    output = {"monitors": monitors}

    if dry_run:
        print(f"[DRY RUN] Would create {len(monitors)} monitors for '{service}':")
        for m in monitors:
            print(f"  - {m['name']}")
        return None

    output_file = output_dir / f"monitors-{service}.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    print(f"Created {len(monitors)} monitors at {output_file}")
    return output_file


def create_slo_config(
    service: str,
    slo_type: str,
) -> dict[str, Any]:
    """Create an SLO configuration for a specific service and type.

    Args:
        service: The service name.
        slo_type: The type of SLO to create.

    Returns:
        The SLO configuration dictionary.
    """
    from create_slo import create_slo
    return create_slo(slo_type, scope="service", service=service)


def create_slos(
    service: str,
    output_dir: Path,
    dry_run: bool = False,
) -> Path | None:
    """Create all SLO configurations for a service.

    Args:
        service: The service name.
        output_dir: Directory to write the output file.
        dry_run: If True, only print what would be done.

    Returns:
        Path to the created file, or None if dry run.
    """
    slos = []
    for slo_type in SLO_TYPES:
        try:
            slo = create_slo_config(service, slo_type)
            slos.append(slo)
        except Exception as e:
            print(f"Warning: Could not create {slo_type} SLO: {e}", file=sys.stderr)

    output = {"slos": slos}

    if dry_run:
        print(f"[DRY RUN] Would create {len(slos)} SLOs for '{service}':")
        for s in slos:
            print(f"  - {s['name']}")
        return None

    output_file = output_dir / f"slos-{service}.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    print(f"Created {len(slos)} SLOs at {output_file}")
    return output_file


def print_next_steps(
    service: str,
    agent_type: str,
    dashboard_updated: bool,
    monitors_created: bool,
    slos_created: bool,
) -> None:
    """Print next steps after onboarding.

    Args:
        service: The service name.
        agent_type: The agent type.
        dashboard_updated: Whether the dashboard was updated.
        monitors_created: Whether monitors were created.
        slos_created: Whether SLOs were created.
    """
    print("\n" + "=" * 60)
    print(f"Onboarding Summary for '{service}'")
    print("=" * 60)

    print("\nCompleted:")
    if dashboard_updated:
        print("  [x] Added service to dashboard template variables")
    if monitors_created:
        print("  [x] Generated monitor configurations")
    if slos_created:
        print("  [x] Generated SLO configurations")

    print("\nNext Steps:")
    print("  1. Create deployment configuration files:")
    print(f"     - Dockerfile-{service}-api          # Backend API with ddtrace-run")
    print(f"     - Dockerfile-{service}-ui           # Frontend UI (optional)")
    print(f"     - infra/cloudrun/{service}-api-sidecar.yaml  # Knative + DD sidecar")
    print(f"     - cloudbuild-{service}-api.yaml     # Cloud Build config")
    print()
    print("     See AGENT_ONBOARDING.md Step 6 for templates.")
    print()
    print("  2. Integrate shared observability in your agent code:")
    print("     from shared.observability import (")
    print("         emit_request_complete,")
    print("         timed_request,")
    print("         TEAM_AI_AGENTS,")
    print("     )")
    print()
    print(f"  3. Configure your agent with the following tags:")
    print(f"     - service:{service}")
    print(f"     - team:ai-agents")
    print(f"     - agent_type:{agent_type}")
    print()
    print("  4. Deploy the backend API with Datadog sidecar:")
    print(f"     gcloud builds submit --config=cloudbuild-{service}-api.yaml \\")
    print("       --substitutions=COMMIT_SHA=$(git rev-parse --short HEAD)")
    print()

    if dashboard_updated:
        print("  5. Deploy dashboard changes:")
        print("     ./infra/datadog/apply_config.sh update-dashboard")
        print()

    if monitors_created:
        print(f"  6. Deploy monitors to Datadog:")
        print(f"     # Use Datadog API to create monitors from infra/datadog/monitors-{service}.json")
        print()

    if slos_created:
        print(f"  7. Deploy SLOs to Datadog:")
        print(f"     # Use Datadog API to create SLOs from infra/datadog/slos-{service}.json")
        print()

    print("  8. Verify using the checklist in AGENT_ONBOARDING.md")
    print()


def main() -> int:
    """Main entry point for the onboarding script.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Onboard a new AI agent to the observability platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --service my-new-agent --agent-type research
  %(prog)s --service my-new-agent --agent-type code-generation --create-monitors
  %(prog)s --service my-new-agent --agent-type triage --create-monitors --create-slos
  %(prog)s --service my-new-agent --agent-type assistant --dry-run
        """,
    )
    parser.add_argument(
        "--service",
        required=True,
        help="Unique service name for the agent (e.g., 'my-new-agent')",
    )
    parser.add_argument(
        "--agent-type",
        required=True,
        choices=VALID_AGENT_TYPES,
        help="Type of agent being onboarded",
    )
    parser.add_argument(
        "--dashboard",
        default=str(DEFAULT_DASHBOARD_PATH),
        help=f"Path to dashboard JSON file (default: {DEFAULT_DASHBOARD_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for generated configs (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--create-monitors",
        action="store_true",
        help="Generate monitor configurations for the agent",
    )
    parser.add_argument(
        "--create-slos",
        action="store_true",
        help="Generate SLO configurations for the agent",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making changes",
    )
    parser.add_argument(
        "--skip-dashboard",
        action="store_true",
        help="Skip updating the dashboard template variables",
    )

    args = parser.parse_args()

    dashboard_path = Path(args.dashboard)
    output_dir = Path(args.output_dir)

    if not output_dir.exists():
        if args.dry_run:
            print(f"[DRY RUN] Would create output directory: {output_dir}")
        else:
            output_dir.mkdir(parents=True)
            print(f"Created output directory: {output_dir}")

    print(f"\nOnboarding agent: {args.service}")
    print(f"Agent type: {args.agent_type}")
    print()

    dashboard_updated = False
    monitors_created = False
    slos_created = False

    if not args.skip_dashboard:
        dashboard_updated = update_dashboard(
            args.service,
            dashboard_path,
            args.dry_run,
        )

    if args.create_monitors:
        monitors_path = create_monitors(
            args.service,
            output_dir,
            args.dry_run,
        )
        monitors_created = monitors_path is not None or args.dry_run

    if args.create_slos:
        slos_path = create_slos(
            args.service,
            output_dir,
            args.dry_run,
        )
        slos_created = slos_path is not None or args.dry_run

    if not args.dry_run:
        print_next_steps(
            args.service,
            args.agent_type,
            dashboard_updated,
            monitors_created,
            slos_created,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
