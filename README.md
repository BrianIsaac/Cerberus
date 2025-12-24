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
- **Streamlit Frontends**: Chat UIs for ops triage and SAS code generation

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
# 1. Start MCP server (terminal 1)
uv run python -m ops_triage_mcp_server.server

# 2. Start backend API (terminal 2)
uv run uvicorn ops_triage_agent.main:app --host 0.0.0.0 --port 8080

# 3. Start Ops Assistant Frontend (terminal 3)
OPS_TRIAGE_AGENT_URL=http://localhost:8080 uv run streamlit run ops_assistant_frontend/app.py

# 4. Start SAS Query Generator (terminal 4)
uv run streamlit run sas_generator/app.py --server.port=8502

# Test the API endpoint directly
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why is api-gateway slow?", "service": "api-gateway"}'
```

### Running with Docker

```bash
# Build and run Ops Assistant Frontend
docker build -f Dockerfile-ops-frontend -t ops-frontend .
docker run -p 8501:8080 -e OPS_TRIAGE_AGENT_URL=http://host.docker.internal:8080 ops-frontend

# Build and run SAS Generator
docker build -f Dockerfile-sas-generator -t sas-generator .
docker run -p 8502:8080 sas-generator
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
├── ops_triage_agent/           # Backend API for incident triage
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Settings management
│   ├── observability.py        # LLM Obs and custom metrics
│   ├── agent/                  # LangGraph workflow
│   └── mcp_client/             # MCP client wrapper
├── ops_triage_mcp_server/      # MCP server for Datadog tools
│   ├── server.py               # FastMCP server entry point
│   └── tools/                  # Datadog API tools (metrics, logs, traces, etc.)
├── ops_assistant_frontend/     # Streamlit chat UI for triage
│   ├── app.py                  # Streamlit application
│   ├── config.py               # Settings
│   ├── api_client.py           # Backend API client
│   └── observability.py        # LLM Obs setup
├── sas_generator/              # Streamlit app for SAS code generation
│   ├── app.py                  # Streamlit application
│   ├── generator.py            # Gemini code generation
│   ├── prompts.py              # System prompts and schemas
│   └── sashelp_schemas.py      # SASHELP dataset definitions
├── sas_mcp_server/             # MCP server for SAS data tools
│   ├── server.py               # FastMCP server entry point
│   └── tools/                  # Dataset and procedure tools
├── scripts/
│   └── traffic_gen.py          # Traffic generator for demo/testing
├── infra/
│   ├── cloudrun/               # Cloud Run deployment configs
│   └── datadog/                # Dashboard, monitors, SLOs
├── tests/                      # Test suite
├── Dockerfile-ops-triage-agent       # Ops triage agent
├── Dockerfile-ops-triage-mcp-server  # Ops triage MCP server
├── Dockerfile-sas-generator    # SAS generator Streamlit
├── Dockerfile-sas-mcp-server   # SAS MCP server
├── Dockerfile-ops-frontend     # Ops assistant frontend Streamlit
└── pyproject.toml              # Project dependencies
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

**Dashboard** (7 widget groups with multi-service filtering):
- Application Health: request volume, P95 latency, error rate, Gemini LLM latency
- Governance & Autonomy: Gemini LLM calls, LangGraph workflow calls, latency, errors
- MCP Tools Performance: tool invocations, latency (avg/P95), error rate, Apdex score
- Quality Evaluations: RAGAS faithfulness/relevancy scores, evaluation calls, confidence scores
- Operations: monitor status panel, incidents/cases, worst traces
- SAS Query Generator: query volume, generation latency, feedback rate, error rate
- Ops Assistant Frontend: request volume, latency, backend connectivity, session metrics

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
   - Included files: `ops_triage_mcp_server/**`, `Dockerfile-ops-triage-mcp-server`, `cloudbuild-mcp.yaml`, `pyproject.toml`, `uv.lock`
   - Config: `cloudbuild-mcp.yaml`

3. **Create Main App trigger:**
   - Name: `deploy-ops-assistant`
   - Event: Push to branch `^main$`
   - Included files: `ops_triage_agent/**`, `Dockerfile-ops-triage-agent`, `cloudbuild-app.yaml`, `pyproject.toml`, `uv.lock`
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
- **Dashboard**: https://ap1.datadoghq.com/dashboard/vy8-sk9-yxg
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
