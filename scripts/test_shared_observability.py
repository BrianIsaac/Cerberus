#!/usr/bin/env python3
"""Test script to emit metrics using the shared observability module.

This script demonstrates the shared observability module by emitting
test metrics that can be verified in Datadog.
"""

import os
import time
from datetime import datetime

from dotenv import load_dotenv
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.metrics_api import MetricsApi
from datadog_api_client.v2.model.metric_intake_type import MetricIntakeType
from datadog_api_client.v2.model.metric_payload import MetricPayload
from datadog_api_client.v2.model.metric_point import MetricPoint
from datadog_api_client.v2.model.metric_resource import MetricResource
from datadog_api_client.v2.model.metric_series import MetricSeries

# Load environment variables
load_dotenv()


def submit_test_metrics():
    """Submit test metrics directly via Datadog API."""
    configuration = Configuration()
    configuration.api_key["apiKeyAuth"] = os.getenv("DD_API_KEY")
    configuration.server_variables["site"] = os.getenv("DD_SITE", "datadoghq.com")

    current_time = int(time.time())

    # Create test metrics for both agents with team:ai-agents tag
    metrics = []

    # SAS Generator metrics
    metrics.append(
        MetricSeries(
            metric="ai_agent.request.count",
            type=MetricIntakeType.COUNT,
            points=[MetricPoint(timestamp=current_time, value=1.0)],
            resources=[MetricResource(name="host", type="test-host")],
            tags=[
                "service:sas-generator",
                "team:ai-agents",
                "agent_type:code-generation",
                "env:development",
                "test:phase2_verification",
            ],
        )
    )
    metrics.append(
        MetricSeries(
            metric="ai_agent.request.latency",
            type=MetricIntakeType.GAUGE,
            points=[MetricPoint(timestamp=current_time, value=250.5)],
            resources=[MetricResource(name="host", type="test-host")],
            tags=[
                "service:sas-generator",
                "team:ai-agents",
                "agent_type:code-generation",
                "env:development",
                "test:phase2_verification",
            ],
        )
    )
    metrics.append(
        MetricSeries(
            metric="ai_agent.quality.score",
            type=MetricIntakeType.GAUGE,
            points=[MetricPoint(timestamp=current_time, value=0.85)],
            resources=[MetricResource(name="host", type="test-host")],
            tags=[
                "service:sas-generator",
                "team:ai-agents",
                "agent_type:code-generation",
                "env:development",
                "metric_name:faithfulness",
                "test:phase2_verification",
            ],
        )
    )

    # Ops Assistant metrics
    metrics.append(
        MetricSeries(
            metric="ai_agent.request.count",
            type=MetricIntakeType.COUNT,
            points=[MetricPoint(timestamp=current_time, value=1.0)],
            resources=[MetricResource(name="host", type="test-host")],
            tags=[
                "service:ops-assistant",
                "team:ai-agents",
                "agent_type:triage",
                "env:development",
                "test:phase2_verification",
            ],
        )
    )
    metrics.append(
        MetricSeries(
            metric="ai_agent.request.latency",
            type=MetricIntakeType.GAUGE,
            points=[MetricPoint(timestamp=current_time, value=1500.0)],
            resources=[MetricResource(name="host", type="test-host")],
            tags=[
                "service:ops-assistant",
                "team:ai-agents",
                "agent_type:triage",
                "env:development",
                "test:phase2_verification",
            ],
        )
    )
    metrics.append(
        MetricSeries(
            metric="ai_agent.quality.score",
            type=MetricIntakeType.GAUGE,
            points=[MetricPoint(timestamp=current_time, value=0.92)],
            resources=[MetricResource(name="host", type="test-host")],
            tags=[
                "service:ops-assistant",
                "team:ai-agents",
                "agent_type:triage",
                "env:development",
                "metric_name:answer_relevancy",
                "test:phase2_verification",
            ],
        )
    )

    body = MetricPayload(series=metrics)

    with ApiClient(configuration) as api_client:
        api_instance = MetricsApi(api_client)
        response = api_instance.submit_metrics(body=body)
        print(f"Submitted {len(metrics)} metrics at {datetime.now()}")
        print(f"Response: {response}")
        return response


if __name__ == "__main__":
    print("Testing shared observability module...")
    print(f"Datadog Site: {os.getenv('DD_SITE')}")
    print()

    response = submit_test_metrics()

    print()
    print("Metrics submitted with tags:")
    print("  - team:ai-agents (common tag)")
    print("  - service:sas-generator | service:ops-assistant")
    print("  - agent_type:code-generation | agent_type:triage")
    print("  - test:phase2_verification (for filtering)")
    print()
    print("To verify in Datadog:")
    print(f"  1. Go to https://{os.getenv('DD_SITE')}/metric/summary")
    print("  2. Search for 'ai_agent.request.count'")
    print("  3. Verify tags include 'team:ai-agents'")
