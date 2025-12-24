"""Datadog Metrics API tool for MCP server."""

from datetime import datetime, timedelta
from typing import Any

from datadog_api_client import ApiClient
from datadog_api_client.v1.api.metrics_api import MetricsApi
from fastmcp import FastMCP

from mcp_server.tools import DD_SITE, get_datadog_config


def register_metrics_tools(mcp: FastMCP) -> None:
    """Register metrics tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    @mcp.tool()
    async def get_metrics(
        service: str,
        time_window: str = "last_15m",
        metrics: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch key metrics from Datadog for a service.

        Args:
            service: The service name to query metrics for.
            time_window: Time window (last_5m, last_15m, last_1h, last_4h).
            metrics: Specific metric queries (defaults to standard APM metrics).

        Returns:
            Dictionary containing metric data, time range, and dashboard link.
        """
        window_mapping = {
            "last_5m": timedelta(minutes=5),
            "last_15m": timedelta(minutes=15),
            "last_1h": timedelta(hours=1),
            "last_4h": timedelta(hours=4),
        }
        delta = window_mapping.get(time_window, timedelta(minutes=15))

        end_time = datetime.now()
        start_time = end_time - delta

        default_metrics = [
            f"avg:trace.http.request.duration{{service:{service}}}",
            f"sum:trace.http.request.errors{{service:{service}}}.as_count()",
            f"sum:trace.http.request.hits{{service:{service}}}.as_count()",
        ]
        query_metrics = metrics or default_metrics

        config = get_datadog_config()

        with ApiClient(config) as api_client:
            api_instance = MetricsApi(api_client)

            results = {}
            for metric_query in query_metrics:
                response = api_instance.query_metrics(
                    _from=int(start_time.timestamp()),
                    to=int(end_time.timestamp()),
                    query=metric_query,
                )

                if response.series:
                    series = response.series[0]
                    points = (
                        [(p[0], p[1]) for p in series.pointlist]
                        if series.pointlist
                        else []
                    )
                    results[metric_query] = {
                        "points": points[-10:],
                        "scope": series.scope,
                        "unit": getattr(series, "unit", None),
                    }
                else:
                    results[metric_query] = {"points": [], "scope": None}

        return {
            "service": service,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "metrics": results,
            "dashboard_link": f"https://app.{DD_SITE}/apm/services/{service}",
        }
