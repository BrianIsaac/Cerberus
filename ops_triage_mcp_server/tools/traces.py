"""Datadog Traces/APM API tool for MCP server."""

from datetime import datetime, timedelta, timezone
from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v2.api.spans_api import SpansApi
from datadog_api_client.v2.model.spans_list_request import SpansListRequest
from datadog_api_client.v2.model.spans_list_request_page import SpansListRequestPage
from datadog_api_client.v2.model.spans_query_filter import SpansQueryFilter
from datadog_api_client.v2.model.spans_sort import SpansSort
from fastmcp import FastMCP

from mcp_server.tools import DD_SITE, get_datadog_config


def register_traces_tools(mcp: FastMCP) -> None:
    """Register traces tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def list_spans(
        service: str,
        query: str | None = None,
        time_window: str = "last_15m",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search APM traces for a service.

        Args:
            service: The service name to search traces for.
            query: Additional query string (e.g., "status:error").
            time_window: Time window (last_5m, last_15m, last_1h, last_4h).
            limit: Maximum number of spans to return.

        Returns:
            Dictionary containing span data, summary, and traces explorer link.
        """
        window_mapping = {
            "last_5m": timedelta(minutes=5),
            "last_15m": timedelta(minutes=15),
            "last_1h": timedelta(hours=1),
            "last_4h": timedelta(hours=4),
        }
        delta = window_mapping.get(time_window, timedelta(minutes=15))

        end_time = datetime.now(timezone.utc)
        start_time = end_time - delta

        base_query = f"service:{service}"
        full_query = f"{base_query} {query}" if query else base_query

        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api_instance = SpansApi(api_client)

            body = SpansListRequest(
                data={
                    "type": "search_request",
                    "attributes": {
                        "filter": SpansQueryFilter(
                            query=full_query,
                            _from=start_time.isoformat(),
                            to=end_time.isoformat(),
                        ),
                        "sort": SpansSort.TIMESTAMP_DESCENDING,
                        "page": SpansListRequestPage(limit=min(limit, 50)),
                    },
                }
            )

            response = api_instance.list_spans(body=body)

            spans = []
            error_spans = []

            for span in response.data or []:
                attrs = span.attributes
                span_data = {
                    "trace_id": getattr(attrs, "trace_id", None),
                    "span_id": getattr(attrs, "span_id", None),
                    "resource_name": getattr(attrs, "resource_name", None),
                    "duration_ns": getattr(attrs, "duration", None),
                    "status": getattr(attrs, "status", None),
                    "error": getattr(attrs, "error", 0),
                }
                spans.append(span_data)

                if span_data.get("error"):
                    error_spans.append(span_data)

        durations = [s["duration_ns"] for s in spans if s.get("duration_ns")]
        avg_duration_ms = (sum(durations) / len(durations) / 1_000_000) if durations else 0

        return {
            "service": service,
            "query": full_query,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "summary": {
                "total_spans": len(spans),
                "error_spans": len(error_spans),
                "avg_duration_ms": round(avg_duration_ms, 2),
            },
            "error_traces": error_spans[:5],
            "traces_link": f"https://app.{DD_SITE}/apm/traces?query={full_query}",
        }

    @mcp.tool()
    async def get_trace(trace_id: str) -> dict[str, Any]:
        """Get full trace details by trace ID.

        Args:
            trace_id: The trace ID to retrieve.

        Returns:
            Dictionary containing trace details including all spans.
        """
        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api_instance = SpansApi(api_client)

            body = SpansListRequest(
                data={
                    "type": "search_request",
                    "attributes": {
                        "filter": SpansQueryFilter(
                            query=f"trace_id:{trace_id}",
                            _from=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
                            to=datetime.now(timezone.utc).isoformat(),
                        ),
                        "sort": SpansSort.TIMESTAMP_ASCENDING,
                        "page": SpansListRequestPage(limit=100),
                    },
                }
            )

            response = api_instance.list_spans(body=body)

            spans = []
            for span in response.data or []:
                attrs = span.attributes
                start_time = getattr(attrs, "start", None)
                tags_attr = getattr(attrs, "tags", None)

                span_data = {
                    "trace_id": getattr(attrs, "trace_id", None),
                    "span_id": getattr(attrs, "span_id", None),
                    "parent_id": getattr(attrs, "parent_id", None),
                    "service": getattr(attrs, "service", None),
                    "resource_name": getattr(attrs, "resource_name", None),
                    "operation_name": getattr(attrs, "name", None),
                    "start_timestamp": str(start_time) if start_time else None,
                    "duration_ns": getattr(attrs, "duration", None),
                    "status": getattr(attrs, "status", None),
                    "error": getattr(attrs, "error", 0),
                    "tags": dict(tags_attr) if tags_attr else {},
                }
                spans.append(span_data)

        if not spans:
            return {
                "trace_id": trace_id,
                "found": False,
                "message": "Trace not found or no spans available",
            }

        root_span = next((s for s in spans if not s.get("parent_id")), spans[0])
        error_spans = [s for s in spans if s.get("error")]

        return {
            "trace_id": trace_id,
            "found": True,
            "total_spans": len(spans),
            "root_service": root_span.get("service"),
            "root_resource": root_span.get("resource_name"),
            "total_duration_ns": root_span.get("duration_ns"),
            "error_count": len(error_spans),
            "spans": spans,
            "trace_link": f"https://app.{DD_SITE}/apm/trace/{trace_id}",
        }
