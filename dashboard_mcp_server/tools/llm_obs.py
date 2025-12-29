"""LLM Observability tools for MCP server."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastmcp import FastMCP

from dashboard_mcp_server.tools import DD_API_KEY, DD_SITE


def register_llm_obs_tools(mcp: FastMCP) -> None:
    """Register LLM Observability tools with the MCP server.

    Args:
        mcp: FastMCP server instance to register tools with.
    """

    def _get_llm_obs_headers() -> dict[str, str]:
        """Get headers for LLM Obs API requests."""
        return {
            "DD-API-KEY": DD_API_KEY,
            "Content-Type": "application/json",
        }

    def _get_base_url() -> str:
        """Get base URL for LLM Obs API."""
        return f"https://api.{DD_SITE}"

    @mcp.tool()
    async def fetch_llm_obs_spans(
        ml_app: str,
        hours_back: int = 1,
        limit: int = 50,
        span_type: str | None = None,
    ) -> dict[str, Any]:
        """Fetch LLM Observability spans for evaluation.

        Args:
            ml_app: The ML application name (matches DD_LLMOBS_ML_APP).
            hours_back: How many hours back to search (default 1).
            limit: Maximum number of spans to return (default 50).
            span_type: Optional span type filter (e.g., 'llm', 'workflow').

        Returns:
            List of spans with input/output data.
        """
        now = datetime.now(timezone.utc)
        from_time = (now - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        query = f"@ml_app:{ml_app}"
        if span_type:
            query += f" @span.type:{span_type}"

        payload = {
            "filter": {
                "query": query,
                "from": from_time,
                "to": to_time,
            },
            "page": {
                "limit": limit,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_get_base_url()}/api/v2/llm-obs/v1/spans/events/search",
                headers=_get_llm_obs_headers(),
                json=payload,
            )

            if response.status_code != 200:
                return {
                    "error": f"API error: {response.status_code}",
                    "details": response.text,
                }

            data = response.json()
            spans = []

            for span in data.get("data", []):
                attrs = span.get("attributes", {})
                spans.append({
                    "span_id": span.get("id"),
                    "trace_id": attrs.get("trace_id"),
                    "name": attrs.get("name"),
                    "span_type": attrs.get("meta", {}).get("span.kind"),
                    "input": attrs.get("meta", {}).get("input", {}).get("value"),
                    "output": attrs.get("meta", {}).get("output", {}).get("value"),
                    "model": attrs.get("meta", {}).get("model_name"),
                    "duration_ns": attrs.get("duration"),
                    "timestamp": attrs.get("start"),
                    "tags": attrs.get("tags", []),
                })

            return {
                "ml_app": ml_app,
                "count": len(spans),
                "time_range": f"{from_time} to {to_time}",
                "spans": spans,
            }

    @mcp.tool()
    async def submit_evaluation(
        span_id: str,
        trace_id: str,
        ml_app: str,
        label: str,
        metric_type: str,
        value: str,
        tags_json: str | None = None,
    ) -> dict[str, Any]:
        """Submit an evaluation result for an LLM Obs span.

        Args:
            span_id: The span ID to attach evaluation to.
            trace_id: The trace ID containing the span.
            ml_app: The ML application name.
            label: Evaluation label (e.g., 'relevancy', 'syntax_valid').
            metric_type: Either 'score' or 'categorical'.
            value: Score (float as string) or category string.
            tags_json: Optional JSON object of tags.

        Returns:
            Submission confirmation.
        """
        timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        metric = {
            "join_on": {
                "span": {
                    "span_id": span_id,
                    "trace_id": trace_id,
                }
            },
            "ml_app": ml_app,
            "timestamp_ms": timestamp_ms,
            "metric_type": metric_type,
            "label": label,
        }

        if metric_type == "score":
            metric["score_value"] = float(value)
        else:
            metric["categorical_value"] = value

        if tags_json:
            metric["tags"] = json.loads(tags_json)

        payload = {
            "data": {
                "type": "evaluation_metric",
                "attributes": {
                    "metrics": [metric],
                },
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_get_base_url()}/api/intake/llm-obs/v2/eval-metric",
                headers=_get_llm_obs_headers(),
                json=payload,
            )

            if response.status_code not in (200, 202):
                return {
                    "error": f"API error: {response.status_code}",
                    "details": response.text,
                }

            return {
                "span_id": span_id,
                "trace_id": trace_id,
                "label": label,
                "value": value,
                "message": f"Evaluation '{label}' submitted successfully",
            }

    @mcp.tool()
    async def submit_evaluations_batch(
        evaluations_json: str,
    ) -> dict[str, Any]:
        """Submit multiple evaluation results in a single request.

        Args:
            evaluations_json: JSON array of evaluation objects, each with:
                - span_id, trace_id, ml_app, label, metric_type, value

        Returns:
            Batch submission results.
        """
        evaluations = json.loads(evaluations_json)
        timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        metrics = []
        for eval_item in evaluations:
            metric = {
                "join_on": {
                    "span": {
                        "span_id": eval_item["span_id"],
                        "trace_id": eval_item["trace_id"],
                    }
                },
                "ml_app": eval_item["ml_app"],
                "timestamp_ms": timestamp_ms,
                "metric_type": eval_item["metric_type"],
                "label": eval_item["label"],
            }

            if eval_item["metric_type"] == "score":
                metric["score_value"] = float(eval_item["value"])
            else:
                metric["categorical_value"] = eval_item["value"]

            metrics.append(metric)

        payload = {
            "data": {
                "type": "evaluation_metric",
                "attributes": {
                    "metrics": metrics,
                },
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_get_base_url()}/api/intake/llm-obs/v2/eval-metric",
                headers=_get_llm_obs_headers(),
                json=payload,
            )

            if response.status_code not in (200, 202):
                return {
                    "error": f"API error: {response.status_code}",
                    "details": response.text,
                }

            return {
                "submitted": len(metrics),
                "message": f"Batch of {len(metrics)} evaluations submitted successfully",
            }

    @mcp.tool()
    async def check_llm_obs_enabled(ml_app: str) -> dict[str, Any]:
        """Check if LLM Observability is enabled for a service.

        Args:
            ml_app: The ML application name to check.

        Returns:
            Status indicating if LLM Obs spans exist.
        """
        result = await fetch_llm_obs_spans(ml_app=ml_app, hours_back=24, limit=1)

        if "error" in result:
            return {
                "ml_app": ml_app,
                "enabled": False,
                "reason": result.get("error"),
            }

        has_spans = result.get("count", 0) > 0

        message = (
            "LLM Observability is active"
            if has_spans
            else "No LLM Obs spans found in last 24 hours"
        )

        return {
            "ml_app": ml_app,
            "enabled": has_spans,
            "spans_found": result.get("count", 0),
            "message": message,
        }
