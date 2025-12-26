# AI Agent Onboarding Guide

This guide explains how to add a new AI agent to the observability platform, ensuring consistent telemetry, dashboard visibility, and automated monitoring.

## Overview

The platform uses a three-layer telemetry architecture:

1. **APM Tracing** - Auto-instrumented via `ddtrace` for HTTP requests, LLM calls, and tool invocations
2. **LLM Observability** - Decorator-based spans for workflow/agent/tool hierarchy with token tracking
3. **Custom Metrics** - DogStatsD emission using standardised `ai_agent.*` prefix

All agents are tagged with `team:ai-agents` for fleet-wide aggregation.

## Prerequisites

Before onboarding a new agent, ensure:

- [ ] Agent code is written and tested locally
- [ ] Datadog API key (`DD_API_KEY`) is configured
- [ ] DogStatsD is available (via Datadog Agent sidecar on Cloud Run)
- [ ] Access to `infra/datadog/` directory for configuration updates

## Step 1: Add Dependencies

Ensure your agent includes the required dependencies in its package configuration:

```toml
# pyproject.toml
dependencies = [
    "ddtrace>=2.0.0",
    "datadog>=0.44.0",
]
```

The shared observability module is available via the `shared` package:

```python
from shared.observability import (
    emit_request_complete,
    emit_tool_error,
    emit_quality_score,
    timed_request,
    observed_workflow,
    TEAM_AI_AGENTS,
)
```

## Step 2: Configure Required Tags

Every agent must emit these tags on all metrics:

| Tag | Description | Example Values |
|-----|-------------|----------------|
| `service` | Unique agent identifier | `ops-assistant`, `sas-generator`, `my-new-agent` |
| `team` | Fleet grouping (constant) | `ai-agents` |
| `agent_type` | Category of agent | `triage`, `code-generation`, `research`, `assistant` |
| `env` | Environment | `production`, `staging`, `development` |

The shared module handles these automatically when using `build_tags()` or `emit_*()` functions.

## Step 3: Initialise Observability

Create an `observability.py` module in your agent package:

```python
"""Observability setup for my-new-agent."""

import os
from datadog import initialize as dd_initialize
from ddtrace.llmobs import LLMObs

from my_agent.config import settings

AGENT_SERVICE = "my-new-agent"
AGENT_TYPE = "my-agent-type"


def setup_llm_observability() -> None:
    """Initialise Datadog LLM Observability."""
    LLMObs.enable(
        ml_app=settings.dd_service,
        api_key=settings.dd_api_key,
        site=settings.dd_site,
        agentless_enabled=True,
        integrations_enabled=True,
    )


def setup_custom_metrics() -> None:
    """Initialise DogStatsD for custom metrics emission."""
    dd_initialize(
        statsd_host=os.getenv("DD_AGENT_HOST", "localhost"),
        statsd_port=int(os.getenv("DD_DOGSTATSD_PORT", "8125")),
    )
```

Call both functions during application startup:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from ddtrace.llmobs import LLMObs

from my_agent.observability import setup_llm_observability, setup_custom_metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_llm_observability()
    setup_custom_metrics()
    yield
    LLMObs.flush()


app = FastAPI(lifespan=lifespan)
```

## Step 4: Emit Standard Metrics

Use the shared metrics functions in your workflow:

### Option A: Using the `timed_request` Context Manager

```python
from shared.observability import timed_request

async def my_agent_workflow(query: str):
    with timed_request("my-new-agent", "my-agent-type") as metrics:
        # Your agent logic here
        result = await call_llm(query)
        metrics["llm_calls"] = 1

        if use_tools:
            tool_result = await call_tool()
            metrics["tool_calls"] = 1

        return result
```

### Option B: Using the `@observed_workflow` Decorator

```python
from shared.observability import observed_workflow

@observed_workflow("my-new-agent", "my-agent-type")
async def my_agent_workflow(query: str):
    # Metrics automatically emitted on completion
    return await do_work(query)
```

### Option C: Manual Metric Emission

```python
from shared.observability import (
    emit_request_start,
    emit_request_complete,
    emit_tool_error,
    emit_quality_score,
)

async def my_agent_workflow(query: str):
    emit_request_start("my-new-agent", "my-agent-type")
    start_time = time.perf_counter()

    try:
        result = await do_work(query)
        success = True
    except Exception as e:
        success = False
        raise
    finally:
        latency_ms = (time.perf_counter() - start_time) * 1000
        emit_request_complete(
            service="my-new-agent",
            agent_type="my-agent-type",
            latency_ms=latency_ms,
            success=success,
            llm_calls=1,
            tool_calls=0,
        )
```

## Step 5: Use LLM Obs Decorators for Span Hierarchy

For detailed tracing, use the `ddtrace.llmobs.decorators`:

```python
from ddtrace.llmobs.decorators import workflow, tool, llm

@tool(name="fetch_data")
async def fetch_data_from_source(source_id: str) -> dict:
    """Tool calls create child spans under the workflow."""
    return await external_api.fetch(source_id)


@llm(model_name="gemini-2.0-flash-exp", model_provider="google")
def call_llm(prompt: str):
    """LLM calls capture input/output and token usage."""
    return client.generate(prompt)


@workflow
async def my_agent_workflow(query: str):
    """Top-level workflow span that contains all child operations."""
    data = await fetch_data_from_source(query.source_id)
    return call_llm(build_prompt(query, data))
```

This creates a span hierarchy:
```
Workflow: my_agent_workflow
  └── Tool: fetch_data
  └── LLM: call_llm (gemini-2.0-flash-exp)
```

## Step 6: Add to Dashboard

Update `infra/datadog/dashboard.json` to include your service:

1. Find the template variables section:

```json
{
  "name": "service",
  "available_values": [
    "ops-assistant",
    "sas-generator",
    "my-new-agent"
  ]
}
```

2. Deploy the updated dashboard:

```bash
./infra/datadog/apply_config.sh update-dashboard
```

Alternatively, use the onboarding script (see Step 9).

## Step 7: Create Monitors (Optional)

Use the monitor factory script to create agent-specific monitors:

```bash
# List available monitor types
python scripts/create_monitor.py --list-types

# Create individual monitors
python scripts/create_monitor.py --service my-new-agent --type latency
python scripts/create_monitor.py --service my-new-agent --type quality
python scripts/create_monitor.py --service my-new-agent --type error_rate

# Create all monitors at once
python scripts/create_monitor.py --service my-new-agent --all -o infra/datadog/monitors-my-new-agent.json
```

Available monitor types:
- `latency` - P95 latency > 10s
- `quality` - RAGAS faithfulness < 0.7
- `error_rate` - Error rate > 5%
- `tool_errors` - Tool error rate > 10%
- `step_budget` - Step budget exceeded
- `token_budget` - Token usage > 50k
- `hallucination` - Hallucination rate > 10%

Deploy monitors using the Datadog API or `apply_config.sh`.

## Step 8: Create SLOs (Optional)

Use the SLO factory script for service-specific SLOs:

```bash
# List available SLO types
python scripts/create_slo.py --list-types

# Create individual SLOs
python scripts/create_slo.py --scope service --service my-new-agent --type availability
python scripts/create_slo.py --scope service --service my-new-agent --type latency

# Create all SLOs at once
python scripts/create_slo.py --scope service --service my-new-agent --all -o infra/datadog/slos-my-new-agent.json
```

Available SLO types:
- `availability` - 99.9% success rate
- `latency` - 95% within latency threshold (monitor-based)
- `governance` - 99% within step/tool budgets
- `quality` - 99.5% hallucination-free
- `faithfulness` - 99% RAGAS faithfulness > 0.7
- `tool_reliability` - 99% tool success rate

## Step 9: Use the Onboarding Script

For automated onboarding, use the onboarding script:

```bash
python scripts/onboard_agent.py \
    --service my-new-agent \
    --agent-type research \
    --create-monitors \
    --create-slos
```

This will:
1. Add your service to the dashboard template variables
2. Generate monitor configurations
3. Generate SLO configurations
4. Provide deployment instructions

## Verification Checklist

After onboarding, verify:

- [ ] Agent emits `team:ai-agents` tag on all metrics
- [ ] Agent emits `service:<your-service>` tag on all metrics
- [ ] Agent emits `agent_type:<category>` tag on all metrics
- [ ] Standard `ai_agent.*` metrics appear in Datadog
- [ ] Agent appears in dashboard when filtered by service
- [ ] Fleet-wide monitors include your agent in multi-alert grouping
- [ ] (Optional) Agent-specific monitors are created and active
- [ ] (Optional) Agent-specific SLOs are created and tracking

### Quick Verification Commands

```bash
# Test shared observability import
python -c "from shared.observability import emit_request_complete; print('OK')"

# Verify metrics emission (requires running agent)
curl -X POST http://localhost:8000/my-endpoint -d '{"query": "test"}'

# Check Datadog for metrics (requires API key)
export DD_API_KEY=your-api-key
curl "https://ap1.datadoghq.com/api/v1/query?from=$(date -d '5 minutes ago' +%s)&to=$(date +%s)&query=sum:ai_agent.request.count{service:my-new-agent}"
```

## Troubleshooting

### Metrics Not Appearing

1. **Check DD_API_KEY is set correctly**
   ```bash
   echo $DD_API_KEY | head -c 10  # Should show first 10 chars
   ```

2. **Verify DogStatsD is running**
   ```bash
   # Local development
   docker ps | grep datadog-agent

   # Cloud Run - check sidecar container logs
   gcloud run services logs read my-service --region us-central1
   ```

3. **Check metric namespace**
   - All custom metrics should use `ai_agent.*` prefix
   - Verify with: `statsd.increment("ai_agent.test")`

4. **Verify tag format**
   - Tags must be lowercase
   - Use colons for key:value pairs (e.g., `service:my-agent`)

### Agent Not in Dashboard

1. **Verify service name matches exactly**
   - Check `DD_SERVICE` environment variable
   - Compare with dashboard template variable values

2. **Check template variable includes your service**
   - Open `infra/datadog/dashboard.json`
   - Find `template_variables` section
   - Ensure your service is in `available_values`

3. **Ensure metrics have correct tags**
   - Use Datadog Metric Explorer to check tag values
   - Query: `sum:ai_agent.request.count{*} by {service}`

### LLM Obs Spans Not Appearing

1. **Verify LLMObs is enabled**
   ```python
   from ddtrace.llmobs import LLMObs
   print(LLMObs.enabled)  # Should be True
   ```

2. **Check decorator usage**
   - `@workflow` must be the outermost decorator
   - `@tool` and `@llm` should be on actual tool/LLM functions

3. **Flush pending spans**
   ```python
   LLMObs.flush()  # Call on shutdown
   ```

### Fleet Monitors Not Triggering for Your Agent

1. **Verify `team:ai-agents` tag is present**
   - Check metric tags in Datadog Metric Explorer
   - Query: `sum:ai_agent.request.count{team:ai-agents} by {service}`

2. **Check monitor query uses `by {service}`**
   - Fleet monitors should use multi-alert with `by {service}` grouping
   - This creates separate alerts per agent

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `DD_API_KEY` | Datadog API key | Yes |
| `DD_APP_KEY` | Datadog App key (for API calls) | For API operations |
| `DD_SITE` | Datadog site (e.g., `ap1.datadoghq.com`) | Yes |
| `DD_SERVICE` | Service name | Yes |
| `DD_ENV` | Environment name | Yes |
| `DD_AGENT_HOST` | DogStatsD host | Default: `localhost` |
| `DD_DOGSTATSD_PORT` | DogStatsD port | Default: `8125` |
| `DD_LLMOBS_ENABLED` | Enable LLM Observability | Default: `1` |
| `DD_LLMOBS_ML_APP` | LLM Obs application name | Same as `DD_SERVICE` |

## Standard Metrics Reference

| Metric | Type | Description |
|--------|------|-------------|
| `ai_agent.request.count` | Counter | Total requests |
| `ai_agent.request.latency` | Histogram | End-to-end latency (ms) |
| `ai_agent.request.error` | Counter | Failed requests |
| `ai_agent.llm.calls` | Counter | LLM invocations |
| `ai_agent.llm.latency` | Histogram | LLM response time (ms) |
| `ai_agent.llm.tokens.input` | Gauge | Input tokens |
| `ai_agent.llm.tokens.output` | Gauge | Output tokens |
| `ai_agent.tool.calls` | Counter | Tool invocations |
| `ai_agent.tool.errors` | Counter | Tool failures |
| `ai_agent.tool.latency` | Histogram | Tool execution time (ms) |
| `ai_agent.quality.score` | Gauge | Quality evaluation score (0-1) |
| `ai_agent.step_budget_exceeded` | Counter | Runaway agent events |
| `ai_agent.handoff_required` | Counter | Human escalation events |

## Related Files

- **Shared Observability Module**: `shared/observability/`
- **Dashboard Configuration**: `infra/datadog/dashboard.json`
- **Monitor Templates**: `infra/datadog/monitors.json`
- **SLO Templates**: `infra/datadog/slos.json`
- **Monitor Factory**: `scripts/create_monitor.py`
- **SLO Factory**: `scripts/create_slo.py`
- **Onboarding Script**: `scripts/onboard_agent.py`
- **Traffic Generator**: `scripts/traffic_gen.py`

## Further Reading

- [Datadog LLM Observability SDK](https://docs.datadoghq.com/llm_observability/setup/sdk/python/)
- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Datadog Dashboard Template Variables](https://docs.datadoghq.com/dashboards/template_variables/)
- [Datadog Monitor Best Practices](https://docs.datadoghq.com/monitors/guide/monitor_best_practices/)
