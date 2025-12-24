"""Datadog Incident and Case Management tools for MCP server."""

from datetime import datetime
from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v2.api.case_management_api import CaseManagementApi
from datadog_api_client.v2.api.incidents_api import IncidentsApi
from datadog_api_client.v2.model.case_create import CaseCreate
from datadog_api_client.v2.model.case_create_attributes import CaseCreateAttributes
from datadog_api_client.v2.model.case_create_request import CaseCreateRequest
from datadog_api_client.v2.model.case_priority import CasePriority
from datadog_api_client.v2.model.case_type import CaseType
from datadog_api_client.v2.model.incident_create_attributes import IncidentCreateAttributes
from datadog_api_client.v2.model.incident_create_data import IncidentCreateData
from datadog_api_client.v2.model.incident_create_request import IncidentCreateRequest
from datadog_api_client.v2.model.incident_type import IncidentType
from fastmcp import FastMCP

from mcp_server.tools import DD_SITE, get_datadog_config


def register_incidents_tools(mcp: FastMCP) -> None:
    """Register incident and case tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def create_incident(
        title: str,
        summary: str,
        severity: str = "SEV-2",
        evidence_links: list[str] | None = None,
        hypotheses: list[str] | None = None,
        next_steps: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a Datadog incident with full context.

        Args:
            title: Incident title (max 100 chars).
            summary: Brief description of the incident.
            severity: Severity level (SEV-1, SEV-2, SEV-3, SEV-4).
            evidence_links: Links to dashboards, traces, logs.
            hypotheses: Ranked hypotheses from triage.
            next_steps: Recommended actions.

        Returns:
            Dictionary containing incident ID, link, and creation timestamp.
        """
        description_parts = [f"## Summary\n{summary}", ""]

        if hypotheses:
            description_parts.append("## Hypotheses (Ranked)")
            for i, hyp in enumerate(hypotheses, 1):
                description_parts.append(f"{i}. {hyp}")
            description_parts.append("")

        if evidence_links:
            description_parts.append("## Evidence")
            for link in evidence_links:
                description_parts.append(f"- {link}")
            description_parts.append("")

        if next_steps:
            description_parts.append("## Next Steps")
            for step in next_steps:
                description_parts.append(f"- [ ] {step}")
            description_parts.append("")

        description_parts.append(
            f"\n---\n*Created by Ops Assistant at {datetime.now().isoformat()}*"
        )

        config = get_datadog_config()
        config.unstable_operations["create_incident"] = True

        with ApiClient(config) as api_client:
            api_instance = IncidentsApi(api_client)

            body = IncidentCreateRequest(
                data=IncidentCreateData(
                    type=IncidentType.INCIDENTS,
                    attributes=IncidentCreateAttributes(
                        title=title,
                        customer_impacted=severity in ["SEV-1", "SEV-2"],
                    ),
                ),
            )

            response = api_instance.create_incident(body=body)

            incident_id = response.data.id
            public_id = response.data.attributes.public_id

        return {
            "incident_id": incident_id,
            "public_id": public_id,
            "title": title,
            "severity": severity,
            "incident_link": f"https://app.{DD_SITE}/incidents/{incident_id}",
            "created_at": datetime.now().isoformat(),
        }

    @mcp.tool()
    async def create_case(
        title: str,
        description: str,
        priority: str = "P2",
        evidence_links: list[str] | None = None,
        hypotheses: list[str] | None = None,
        next_steps: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a Datadog case with full context.

        Args:
            title: Case title.
            description: Brief description of the issue.
            priority: Priority level (P1, P2, P3, P4).
            evidence_links: Links to dashboards, traces, logs.
            hypotheses: Ranked hypotheses from triage.
            next_steps: Recommended actions.

        Returns:
            Dictionary containing case ID, key, link, and creation timestamp.
        """
        description_parts = [f"## Summary\n{description}", ""]

        if hypotheses:
            description_parts.append("## Hypotheses (Ranked)")
            for i, hyp in enumerate(hypotheses, 1):
                description_parts.append(f"{i}. {hyp}")
            description_parts.append("")

        if evidence_links:
            description_parts.append("## Evidence")
            for link in evidence_links:
                description_parts.append(f"- {link}")
            description_parts.append("")

        if next_steps:
            description_parts.append("## Next Steps")
            for step in next_steps:
                description_parts.append(f"- [ ] {step}")
            description_parts.append("")

        description_parts.append(
            f"\n---\n*Created by Ops Assistant at {datetime.now().isoformat()}*"
        )
        full_description = "\n".join(description_parts)

        priority_mapping = {
            "P1": CasePriority.P1,
            "P2": CasePriority.P2,
            "P3": CasePriority.P3,
            "P4": CasePriority.P4,
        }
        case_priority = priority_mapping.get(priority, CasePriority.P2)

        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api_instance = CaseManagementApi(api_client)

            body = CaseCreateRequest(
                data=CaseCreate(
                    type=CaseType.CASE,
                    attributes=CaseCreateAttributes(
                        title=title,
                        description=full_description,
                        priority=case_priority,
                    ),
                ),
            )

            response = api_instance.create_case(body=body)

            case_id = response.data.id
            case_key = response.data.attributes.key

        return {
            "case_id": case_id,
            "case_key": case_key,
            "title": title,
            "priority": priority,
            "case_link": f"https://app.{DD_SITE}/cases/{case_id}",
            "created_at": datetime.now().isoformat(),
        }

    @mcp.tool()
    async def list_incidents(
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List Datadog incidents with optional status filter.

        Args:
            status: Filter by status (active, stable, resolved, completed).
            limit: Maximum number of incidents to return.

        Returns:
            Dictionary containing list of incidents and summary.
        """
        config = get_datadog_config()
        config.unstable_operations["list_incidents"] = True

        with ApiClient(config) as api_client:
            api_instance = IncidentsApi(api_client)

            kwargs = {}
            if limit:
                kwargs["page_size"] = min(limit, 100)

            response = api_instance.list_incidents(**kwargs)

            incidents = []
            for incident in response.data or []:
                attrs = incident.attributes
                created = getattr(attrs, "created", None)
                modified = getattr(attrs, "modified", None)
                resolved = getattr(attrs, "resolved", None)

                incident_data = {
                    "id": incident.id,
                    "public_id": getattr(attrs, "public_id", None),
                    "title": getattr(attrs, "title", None),
                    "created": str(created) if created else None,
                    "modified": str(modified) if modified else None,
                    "customer_impacted": getattr(attrs, "customer_impacted", None),
                    "resolved": str(resolved) if resolved else None,
                }

                if status:
                    incident_status = "resolved" if incident_data.get("resolved") else "active"
                    if incident_status == status or status.lower() == "all":
                        incidents.append(incident_data)
                else:
                    incidents.append(incident_data)

        active_count = sum(1 for i in incidents if not i.get("resolved"))
        resolved_count = sum(1 for i in incidents if i.get("resolved"))

        return {
            "total_incidents": len(incidents),
            "active_count": active_count,
            "resolved_count": resolved_count,
            "incidents": incidents[:limit],
            "incidents_link": f"https://app.{DD_SITE}/incidents",
        }

    @mcp.tool()
    async def get_incident(incident_id: str) -> dict[str, Any]:
        """Get detailed information about a specific incident.

        Args:
            incident_id: The incident ID to retrieve.

        Returns:
            Dictionary containing full incident details.
        """
        config = get_datadog_config()
        config.unstable_operations["get_incident"] = True

        with ApiClient(config) as api_client:
            api_instance = IncidentsApi(api_client)

            response = api_instance.get_incident(incident_id=incident_id)

            if not response.data:
                return {
                    "incident_id": incident_id,
                    "found": False,
                    "message": "Incident not found",
                }

            incident = response.data
            attrs = incident.attributes

            created = getattr(attrs, "created", None)
            modified = getattr(attrs, "modified", None)
            resolved = getattr(attrs, "resolved", None)
            impact_start = getattr(attrs, "customer_impact_start", None)
            impact_end = getattr(attrs, "customer_impact_end", None)
            fields = getattr(attrs, "fields", None)

            return {
                "incident_id": incident.id,
                "found": True,
                "public_id": getattr(attrs, "public_id", None),
                "title": getattr(attrs, "title", None),
                "created": str(created) if created else None,
                "modified": str(modified) if modified else None,
                "resolved": str(resolved) if resolved else None,
                "customer_impacted": getattr(attrs, "customer_impacted", None),
                "customer_impact_scope": getattr(attrs, "customer_impact_scope", None),
                "customer_impact_start": str(impact_start) if impact_start else None,
                "customer_impact_end": str(impact_end) if impact_end else None,
                "fields": dict(fields) if fields else {},
                "incident_link": f"https://app.{DD_SITE}/incidents/{incident.id}",
            }
