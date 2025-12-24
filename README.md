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
uv run python -m ops_triage_mcp_server.server

# 3. Start main app with tracing (terminal 2)
uv run ddtrace-run uvicorn ops_triage_agent.main:app --host 0.0.0.0 --port 8000

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
├── ops_triage_agent/
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
├── ops_triage_mcp_server/
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
├── infra/
│   ├── cloudrun/            # Cloud Run deployment configs
│   │   ├── service-with-sidecar.yaml # Cloud Run + Datadog Agent sidecar
│   │   ├── setup_secrets.sh      # Secret Manager setup
│   │   ├── deploy_mcp_server.sh  # Deploy MCP server
│   │   ├── configure_iam.sh      # Service-to-service IAM
│   │   └── deploy.sh             # Deploy main app
│   └── datadog/             # Datadog configuration
│       ├── dashboard.json   # Dashboard with 5 widget groups
│       ├── monitors.json    # 8 monitors with incident automation
│       ├── slos.json        # 4 SLOs (availability, latency, governance, quality)
│       └── apply_config.sh  # Deploy script (auto-loads .env)
├── tests/                   # Test suite
├── Dockerfile-app           # Multi-stage build for main app (Cloud Run)
├── Dockerfile-mcp           # Multi-stage build for MCP server (Cloud Run)
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

### Datadog Configuration

Deploy dashboard, monitors, and SLOs:

```bash
cd infra/datadog
./apply_config.sh  # Reads DD_API_KEY and DD_APP_KEY from .env
```

**Dashboard** (5 widget groups):
- Application Health: request volume, P95 latency, error rate, Gemini LLM latency
- Governance & Autonomy: Gemini LLM calls, LangGraph workflow calls, latency, errors
- MCP Tools Performance: tool invocations, latency (avg/P95), error rate, Apdex score
- Quality Evaluations: RAGAS faithfulness/relevancy scores, evaluation calls, confidence scores
- Operations: monitor status panel, incidents/cases, worst traces

**Monitors** (8 total):
- High P95 Latency (>10s)
- Agent Step Budget Exceeded
- Tool Error Rate Spike (>10%)
- Quality Degradation (faithfulness <0.7)
- Hallucination Rate High (>10%)
- PII Detection Alert
- MCP Server Connection Issues
- Token Budget Spike

**SLOs** (4 total):
- Availability: 99.9% (30d), 99.5% (7d)
- Latency: 95% <10s (30d), 90% (7d)
- Governance: 99% within budgets (30d)
- Quality: 99.5% hallucination-free (30d)

## Development Status

- [x] Phase 1: Project structure and core infrastructure
- [x] Phase 2: Datadog observability setup
- [x] Phase 3: MCP server with Datadog tools (10 tools, auto-instrumented)
- [x] Phase 4: LangGraph agent workflow (verified in Datadog LLM Obs)
- [x] Phase 5: Security hardening and quality evaluation (prompt injection, PII, RAGAS)
- [x] Phase 6: Traffic generator and demo preparation (8 modes, APM + LLM Obs verified)
- [x] Phase 7: Datadog configuration (dashboard, 8 monitors, 4 SLOs deployed)
- [x] Phase 8: Cloud Run deployment (MCP server, main app, service-to-service auth)

## CI/CD with Cloud Build

The project includes Cloud Build configs for automated deployments.

### Setup Triggers

1. **Connect your repository** in Cloud Console > Cloud Build > Triggers > Connect Repository

2. **Create MCP Server trigger:**
   - Name: `deploy-mcp-server`
   - Event: Push to branch `^main$`
   - Included files: `ops_triage_mcp_server/**`, `Dockerfile-mcp`, `cloudbuild-mcp.yaml`, `pyproject.toml`, `uv.lock`
   - Config: `cloudbuild-mcp.yaml`

3. **Create Main App trigger:**
   - Name: `deploy-ops-assistant`
   - Event: Push to branch `^main$`
   - Included files: `ops_triage_agent/**`, `Dockerfile-app`, `cloudbuild-app.yaml`, `pyproject.toml`, `uv.lock`
   - Config: `cloudbuild-app.yaml`

### Manual Deployment

```bash
# Deploy MCP server
gcloud builds submit --config cloudbuild-mcp.yaml

# Deploy main app (via Cloud Build)
gcloud builds submit --config cloudbuild-app.yaml

# Deploy main app with Datadog sidecar (recommended)
gcloud run services replace infra/cloudrun/service-with-sidecar.yaml --region us-central1
```

## Hackathon Submission

**AI Partner Catalyst: Accelerate Innovation** - Datadog LLM Observability Challenge

### Hosted Application
- **URL**: https://ops-assistant-118887195862.us-central1.run.app

### Datadog Organisation
- **Organisation Name**: AI Singapore
- **Region**: ap1 (Asia-Pacific)

### Key Datadog Resources
- **LLM Obs Traces** (Primary): https://ap1.datadoghq.com/llm/traces?query=%40ml_app%3Aops-assistant
- **Dashboard**: https://ap1.datadoghq.com/dashboard/k3b-pcm-45c
- **Monitors**: https://ap1.datadoghq.com/monitors/manage?q=service%3Aops-assistant

### Cloud Run Observability with Datadog Agent Sidecar
This application runs on Google Cloud Run Gen2 with a Datadog Agent sidecar container. This enables full observability:
- **APM Traces**: Fully functional via `gcr.io/datadoghq/serverless-init:latest` sidecar
- **LLM Observability**: Fully functional with traces, spans, and evaluations
- **DogStatsD Metrics**: Custom metrics via the sidecar agent
- **Dashboard**: All sections populated with real-time data

The sidecar configuration is defined in `infra/cloudrun/service-with-sidecar.yaml`.

### Submission Artifacts
All Datadog JSON exports are in the `submission/` directory:
- `submission/dashboard.json` - Dashboard configuration
- `submission/monitors.json` - 8 monitors with incident automation
- `submission/slos.json` - 4 SLOs (availability, latency, governance, quality)
- `submission/screenshots/` - Evidence screenshots

### Detection Rules (Monitors)
| Monitor | Threshold | Severity |
|---------|-----------|----------|
| High P95 Latency | >10s | P3 |
| Agent Step Budget Exceeded | >0 | P3 |
| Tool Error Rate Spike | >10% | P2 |
| Quality Degradation | faithfulness <0.7 | P2 |
| Hallucination Rate High | >10% | P1 |
| PII Detection Alert | any PII detected | P1 |
| MCP Server Connection Issues | >5 errors | P1 |
| Token Budget Spike | >50k tokens | P3 |

### Observability Strategy
This application demonstrates comprehensive LLM observability:
1. **Trace Visibility**: Full LLM workflow traces with span hierarchy (workflow → agent → tool)
2. **Quality Evaluation**: RAGAS faithfulness and answer relevancy scores
3. **Security Monitoring**: PII detection, prompt injection detection
4. **Governance**: Step budgets, tool limits, confidence thresholds
5. **Incident Automation**: Workflow triggers incidents on monitor alerts

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
