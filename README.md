# Ops Assistant

A bounded, incident-ready ops assistant that converts Datadog telemetry into actionable triage recommendations. Built with Gemini on Vertex AI, deployed on Google Cloud Run, with comprehensive Datadog observability.

## Features

- Natural language triage questions for services and time windows
- Evidence pulling from Datadog (metrics, logs, traces, incidents)
- Ranked hypotheses with citations and confidence scores
- Human approval required before creating incidents/cases
- Bounded autonomy with step budgets and tool limits
- Full observability via Datadog APM, LLM Observability, and custom metrics
- Security hardening: prompt injection detection, PII detection and redaction
- Quality evaluation: RAGAS integration (faithfulness, answer relevancy)

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Client/CLI    │────▶│  Ops Assistant  │────▶│   MCP Server    │
│                 │     │   (FastAPI)     │     │   (FastMCP)     │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 ▼                       ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Gemini 2.0     │     │  Datadog APIs   │
                        │  (Vertex AI)    │     │                 │
                        └─────────────────┘     └─────────────────┘
```

## Tech Stack

- **LLM**: Google Gemini 2.0 Flash via Vertex AI
- **Agent Framework**: LangGraph for structured workflows
- **Tool Interface**: Model Context Protocol (MCP) via FastMCP
- **Observability**: Datadog LLM Observability, APM, Logs, Custom Metrics
- **Quality Evaluation**: RAGAS (faithfulness, context precision, answer relevancy)
- **Deployment**: Google Cloud Run

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Datadog account with API and App keys
- Google Cloud project with Vertex AI enabled

### Installation

```bash
# Clone the repository
git clone https://github.com/BrianIsaac/ops-assistant.git
cd ops-assistant

# Install dependencies
uv sync
```

### Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your API keys
```

### Running Locally

```bash
# 1. Start Datadog agent (for metrics/traces)
sudo docker run -d --name dd-agent \
  --network host \
  -e DD_API_KEY=your-api-key \
  -e DD_SITE=datadoghq.com \
  -e DD_HOSTNAME=ops-assistant-local \
  -e DD_APM_ENABLED=true \
  datadog/agent:latest

# 2. Start MCP server (terminal 1)
uv run python mcp_server/server.py

# 3. Start main app with tracing (terminal 2)
uv run ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. Test the endpoint
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why is api-gateway slow?", "service": "api-gateway"}'

# Stop agent when done
sudo docker stop dd-agent && sudo docker rm dd-agent
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ask` | POST | Free-form triage question |
| `/triage` | POST | Structured triage payload |
| `/review` | POST | Human review outcome |

## Project Structure

```
ops-assistant/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings management
│   ├── logging_config.py    # Structured logging with Datadog correlation
│   ├── observability.py     # LLM Obs and custom metrics
│   ├── security.py          # Prompt injection and PII detection
│   ├── evaluation.py        # Custom quality evaluation submission
│   ├── agent/
│   │   ├── state.py         # LangGraph state schema
│   │   ├── nodes.py         # Workflow nodes (intake, collect, synthesis)
│   │   └── workflow.py      # LangGraph workflow graph
│   ├── prompts/             # LLM prompt templates
│   ├── mcp_client/
│   │   └── client.py        # MCP client wrapper
│   └── models/
│       └── schemas.py       # Pydantic request/response models
├── mcp_server/
│   ├── server.py            # FastMCP server entry point
│   └── tools/               # Datadog API tools
│       ├── metrics.py       # get_metrics
│       ├── logs.py          # get_logs
│       ├── traces.py        # list_spans, get_trace
│       ├── incidents.py     # create_incident, create_case, list/get
│       ├── monitors.py      # list_monitors
│       └── dashboards.py    # list_dashboards
├── scripts/
│   └── traffic_gen.py       # Traffic generator for demo/testing
├── tests/                   # Test suite
├── Dockerfile               # Multi-stage build for Cloud Run
└── pyproject.toml           # Project dependencies
```

## Traffic Generator

Generate test traffic to verify observability and trigger monitors:

```bash
# Normal triage questions
uv run python scripts/traffic_gen.py --mode normal --rps 0.5 --duration 60

# Trigger latency alerts
uv run python scripts/traffic_gen.py --mode latency --rps 1.0 --duration 30

# Test quality monitoring (fictional services)
uv run python scripts/traffic_gen.py --mode hallucination --rps 0.5 --duration 30
```

**Available Modes:**
| Mode | Purpose |
|------|---------|
| `normal` | Standard triage questions |
| `latency` | Long prompts for latency testing |
| `hallucination` | Fictional services for quality monitoring |
| `pii_test` | PII detection testing |
| `low_confidence` | Trigger clarification/escalation |
| `runaway` | Vague prompts (missing identifiers) |
| `tool_error` | Non-existent services |
| `mcp_health` | Invalid MCP tool calls |

## Governance Controls

The assistant enforces bounded autonomy:

| Control | Default | Description |
|---------|---------|-------------|
| Max Steps | 8 | Maximum agent steps per request |
| Max Model Calls | 5 | Maximum LLM invocations |
| Max Tool Calls | 6 | Maximum tool invocations |
| Confidence Threshold | 0.7 | Minimum confidence for auto-approval |

## Observability

All requests emit:
- APM traces with span correlation
- Structured JSON logs with trace IDs
- Custom metrics (step counts, tool calls, latency)
- LLM Observability spans for Gemini calls

## Development Status

- [x] Phase 1: Project structure and core infrastructure
- [x] Phase 2: Datadog observability setup
- [x] Phase 3: MCP server with Datadog tools (10 tools, auto-instrumented)
- [x] Phase 4: LangGraph agent workflow (verified in Datadog LLM Obs)
- [x] Phase 5: Security hardening and quality evaluation (prompt injection, PII, RAGAS)
- [x] Phase 6: Traffic generator and demo preparation (8 modes, APM + LLM Obs verified)
- [ ] Phase 7: Cloud Run deployment and Datadog dashboards/monitors

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
