"""Widget templates for different agent types and domains."""

from typing import Any


def create_timeseries_widget(
    title: str,
    query: str,
    service: str,
    display_type: str = "line",
    palette: str = "dog_classic",
) -> dict[str, Any]:
    """Create a timeseries widget definition.

    Args:
        title: Widget title.
        query: Datadog query string with {service} placeholder.
        service: Service name to substitute.
        display_type: Line, bars, or area.
        palette: Colour palette name.

    Returns:
        Widget definition dictionary.
    """
    return {
        "definition": {
            "type": "timeseries",
            "title": title,
            "requests": [
                {
                    "q": query.format(service=service),
                    "display_type": display_type,
                    "style": {"palette": palette},
                }
            ],
        }
    }


def create_query_value_widget(
    title: str,
    query: str,
    service: str,
    thresholds: list[dict] | None = None,
) -> dict[str, Any]:
    """Create a query value widget definition.

    Args:
        title: Widget title.
        query: Datadog query string with {service} placeholder.
        service: Service name to substitute.
        thresholds: Optional conditional formatting rules.

    Returns:
        Widget definition dictionary.
    """
    widget: dict[str, Any] = {
        "definition": {
            "type": "query_value",
            "title": title,
            "requests": [
                {
                    "q": query.format(service=service),
                }
            ],
        }
    }

    if thresholds:
        widget["definition"]["requests"][0]["conditional_formats"] = thresholds

    return widget


def create_toplist_widget(
    title: str,
    query: str,
    service: str,
    palette: str = "dog_classic",
) -> dict[str, Any]:
    """Create a toplist widget definition.

    Args:
        title: Widget title.
        query: Datadog query string with {service} placeholder.
        service: Service name to substitute.
        palette: Colour palette name.

    Returns:
        Widget definition dictionary.
    """
    return {
        "definition": {
            "type": "toplist",
            "title": title,
            "requests": [
                {
                    "q": query.format(service=service),
                    "style": {"palette": palette},
                }
            ],
        }
    }


WIDGET_TEMPLATES: dict[str, list[dict]] = {
    "code-generation": [
        {
            "type": "query_value",
            "title": "{domain} Success Rate (%)",
            "query": (
                "(sum:ai_agent.request.count{{service:{service}}} - "
                "sum:ai_agent.request.error{{service:{service}}}) / "
                "sum:ai_agent.request.count{{service:{service}}} * 100"
            ),
            "thresholds": [
                {"comparator": ">", "value": 95, "palette": "white_on_green"},
                {"comparator": "<=", "value": 95, "palette": "white_on_yellow"},
                {"comparator": "<=", "value": 80, "palette": "white_on_red"},
            ],
        },
        {
            "type": "timeseries",
            "title": "{domain} Quality Score",
            "query": "avg:ai_agent.quality_score{{service:{service}}}",
            "display_type": "line",
        },
        {
            "type": "timeseries",
            "title": "{domain} Generation Latency",
            "query": "p95:trace.http.request.duration{{service:{service}}}",
            "display_type": "line",
        },
        {
            "type": "toplist",
            "title": "Top Error Types",
            "query": (
                "top(sum:ai_agent.request.error{{service:{service}}} "
                "by {{error_type}}.as_count(), 5, 'sum', 'desc')"
            ),
        },
    ],
    "triage": [
        {
            "type": "query_value",
            "title": "Triage Accuracy (%)",
            "query": (
                "avg:ai_agent.quality_score{{service:{service},score_type:accuracy}} * 100"
            ),
        },
        {
            "type": "timeseries",
            "title": "Time to First Hypothesis",
            "query": "avg:trace.http.request.duration{{service:{service}}}",
            "display_type": "line",
        },
        {
            "type": "timeseries",
            "title": "Escalation Rate",
            "query": (
                "sum:ai_agent.governance.escalation{{service:{service}}} "
                "by {{reason}}.as_count()"
            ),
            "display_type": "bars",
        },
        {
            "type": "toplist",
            "title": "Top Escalation Reasons",
            "query": (
                "top(sum:ai_agent.governance.escalation{{service:{service}}} "
                "by {{reason}}.as_count(), 5, 'sum', 'desc')"
            ),
        },
    ],
    "analysis": [
        {
            "type": "timeseries",
            "title": "Analysis Request Volume",
            "query": "sum:trace.http.request.hits{{service:{service}}}.as_count()",
            "display_type": "bars",
        },
        {
            "type": "timeseries",
            "title": "Analysis Duration (P95)",
            "query": "p95:trace.http.request.duration{{service:{service}}}",
            "display_type": "line",
        },
        {
            "type": "query_value",
            "title": "Error Rate (%)",
            "query": (
                "sum:trace.http.request.errors{{service:{service}}}.as_count() / "
                "sum:trace.http.request.hits{{service:{service}}}.as_count() * 100"
            ),
        },
    ],
}


def get_base_widgets(agent_type: str) -> list[dict]:
    """Get base widget templates for an agent type.

    Args:
        agent_type: Type of agent (code-generation, triage, analysis).

    Returns:
        List of widget template dictionaries.
    """
    return WIDGET_TEMPLATES.get(agent_type, WIDGET_TEMPLATES["analysis"])
