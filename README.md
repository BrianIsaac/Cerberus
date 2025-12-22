# Ops Assistant

A bounded, incident-ready ops assistant that converts Datadog telemetry into actionable triage recommendations. Built with Gemini on Vertex AI, deployed on Google Cloud Run, with comprehensive Datadog observability.

## Features

- Natural language triage questions for services and time windows
- Evidence pulling from Datadog (metrics, logs, traces, incidents)
- Ranked hypotheses with citations and confidence scores
- Human approval required before creating incidents/cases
- Bounded autonomy with step budgets and tool limits
- Full observability via Datadog APM, LLM Observability, and custom metrics

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Client/CLI    │────▶│  Ops Assistant  │────▶│   MCP Server    │
│                 │     │   (FastAPI)     │     │   (FastMCP)     │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 ▼                       ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Gemini 1.5     │     │  Datadog APIs   │
                        │  (Vertex AI)    │     │                 │
                        └─────────────────┘     └─────────────────┘
```

## Tech Stack

- **LLM**: Google Gemini 1.5 Flash via Vertex AI
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
# Start Datadog agent (for local development)
docker run -d --name dd-agent \
  --network host \
  -e DD_API_KEY=your-api-key \
  -e DD_SITE=datadoghq.com \
  -e DD_HOSTNAME=ops-assistant-local \
  -e DD_APM_ENABLED=true \
  datadog/agent:latest

# Run the application
export DD_SERVICE=ops-assistant DD_ENV=development DD_VERSION=0.1.0
uv run ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port 8080
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
├── scripts/                 # Utility scripts
├── tests/                   # Test suite
├── Dockerfile               # Multi-stage build for Cloud Run
└── pyproject.toml           # Project dependencies
```

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
- [ ] Phase 4: LangGraph agent workflow
- [ ] Phase 5: RAGAS quality evaluation and production hardening

## License

See [LICENSE](LICENSE) for details.
