# Ops Assistant: Self-Observing AI for Incident Triage

**AI Partner Catalyst: Accelerate Innovation** — Datadog LLM Observability Challenge

A production-grade observability solution demonstrating how AI agents can monitor themselves and each other. The Ops Assistant is a bounded, incident-ready AI agent that converts Datadog telemetry into actionable triage recommendations—while being fully observable through the same Datadog platform it queries.

## The Innovation: Self-Referential AI Observability

What sets this solution apart is the **closed-loop observability architecture**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATADOG OBSERVABILITY PLATFORM                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Dashboard  │  │   Monitors  │  │    SLOs     │  │ Incident Management │ │
│  │  (7 groups) │  │ (8 rules)   │  │ (4 targets) │  │   (Auto-created)    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                │                     │            │
│         └────────────────┴────────────────┴─────────────────────┘            │
│                                    ▲                                         │
│                                    │ Telemetry                               │
│                                    │                                         │
│  ┌─────────────────────────────────┴─────────────────────────────────────┐  │
│  │                        OPS ASSISTANT AI AGENT                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │  │
│  │  │   Intake    │→ │   Collect   │→ │  Synthesis  │→ │   Approval   │  │  │
│  │  │  (Gemini)   │  │ (MCP Tools) │  │  (Gemini)   │  │   (Human)    │  │  │
│  │  └─────────────┘  └──────┬──────┘  └─────────────┘  └──────────────┘  │  │
│  │                          │                                             │  │
│  │                          ▼ Queries                                     │  │
│  │                   ┌─────────────────┐                                  │  │
│  │                   │  Datadog APIs   │ ◄── The agent queries the same   │  │
│  │                   │  (via MCP)      │     platform that monitors it    │  │
│  │                   └─────────────────┘                                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

**The agent can see its own health metrics, latency, and error rates**—enabling meta-level incident response where the AI can help debug issues with itself.

## Scalable Multi-Agent Architecture

The solution is designed for horizontal scaling with multiple specialised AI agents:

```
                              ┌─────────────────────────────┐
                              │    DATADOG DASHBOARD        │
                              │  Unified view of all agents │
                              └──────────────┬──────────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
              ▼                              ▼                              ▼
   ┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
   │   OPS ASSISTANT     │      │   SAS GENERATOR     │      │   FUTURE AGENTS     │
   │   (Incident Triage) │      │   (Code Generation) │      │   (Extensible)      │
   │                     │      │                     │      │                     │
   │   • 8-node workflow │      │   • Single-shot LLM │      │   • Same patterns   │
   │   • Human approval  │      │   • User feedback   │      │   • Shared MCP      │
   │   • Bounded autonomy│      │   • Quality scoring │      │   • Common metrics  │
   └──────────┬──────────┘      └──────────┬──────────┘      └──────────┬──────────┘
              │                            │                            │
              └────────────────────────────┼────────────────────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────────┐
                              │      MCP TOOL SERVERS       │
                              │  Shared tooling infrastructure│
                              └─────────────────────────────┘
```

Each agent:
- Emits standardised telemetry (APM traces, LLM Obs spans, custom metrics)
- Shares the same MCP tool infrastructure
- Appears in the unified dashboard with service-level filtering
- Can be added without modifying existing agents

## Hard Requirements Checklist

| Requirement | Implementation |
|-------------|----------------|
| **Vertex AI / Gemini** | Google Gemini 2.0 Flash via Vertex AI |
| **Telemetry to Datadog** | APM, LLM Observability, Logs, Custom Metrics |
| **3+ Detection Rules** | 8 monitors with incident automation |
| **Actionable Records** | Auto-created incidents with context, runbooks, and signal data |
| **In-Datadog View** | 7-section dashboard with health, SLOs, and actionable items |
| **Traffic Generator** | 8-mode script demonstrating all detection rules |

## Hosted Applications

| Application | URL | Purpose |
|-------------|-----|---------|
| **Ops Assistant API** | https://ops-assistant-i4ney2dwya-uc.a.run.app | Backend triage agent |
| **Ops Assistant Frontend** | https://ops-assistant-frontend-i4ney2dwya-uc.a.run.app | Chat UI for incident triage |
| **SAS Query Generator** | https://sas-query-generator-i4ney2dwya-uc.a.run.app | Code generation demo |

## Datadog Organisation

- **Organisation Name**: AI Singapore
- **Region**: ap1 (Asia-Pacific)

### Key Datadog Resources

| Resource | Link |
|----------|------|
| **LLM Obs Traces** | https://ap1.datadoghq.com/llm/traces?query=%40ml_app%3Aops-assistant |
| **Dashboard** | https://ap1.datadoghq.com/dashboard/vy8-sk9-yxg |
| **Monitors** | https://ap1.datadoghq.com/monitors/manage?q=service%3Aops-assistant |
| **SLOs** | https://ap1.datadoghq.com/slo/manage |

## Observability Strategy

### Three-Layer Telemetry

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: APM Tracing                                            │
│ • Full request traces with span hierarchy                       │
│ • Service map and dependency visualisation                      │
│ • Latency breakdown by component                                │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: LLM Observability                                      │
│ • Workflow → Agent → Tool span hierarchy                        │
│ • Input/output capture for debugging                            │
│ • Token usage and cost tracking                                 │
│ • RAGAS quality evaluations (faithfulness, relevancy)           │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: Custom Metrics                                         │
│ • Governance metrics (steps, tool calls, model calls)           │
│ • Quality scores (confidence, hallucination rate)               │
│ • Security events (PII detection, prompt injection)             │
│ • Business metrics (escalations, approvals, feedback)           │
└─────────────────────────────────────────────────────────────────┘
```

### Dashboard (7 Widget Groups)

| Section | Signals Monitored |
|---------|-------------------|
| **Application Health** | Request volume, P95 latency, error rate, Gemini LLM latency |
| **Governance & Autonomy** | LLM calls, workflow executions, step budgets, tool limits |
| **MCP Tools Performance** | Tool invocations, latency (avg/P95), error rate, Apdex score |
| **Quality Evaluations** | RAGAS faithfulness/relevancy, confidence scores, hallucination rate |
| **Operations** | Monitor status panel, incidents/cases, worst traces |
| **SAS Query Generator** | Query volume, generation latency, user feedback, error rate |
| **Ops Assistant Frontend** | Request volume, latency, backend connectivity, sessions |

### Detection Rules (8 Monitors)

| Monitor | Threshold | Severity | Rationale |
|---------|-----------|----------|-----------|
| **High P95 Latency** | >10s | P3 | User experience degradation |
| **Agent Step Budget Exceeded** | >0 events | P3 | Runaway agent detection |
| **Tool Error Rate Spike** | >10% | P2 | MCP/Datadog API issues |
| **Quality Degradation** | faithfulness <0.7 | P2 | Model output quality drop |
| **Hallucination Rate High** | >10% | P1 | Critical accuracy issue |
| **PII Detection Alert** | any PII detected | P1 | Data privacy violation |
| **MCP Server Connection Issues** | >5 errors | P1 | Infrastructure failure |
| **Token Budget Spike** | >50k tokens | P3 | Cost anomaly detection |

**Each monitor automatically creates an incident with:**
- Signal data (metric values, timestamps, affected services)
- Runbook link for remediation steps
- Context tags for filtering and correlation
- Severity-based notification routing

### SLOs (4 Targets)

| SLO | Target (30d) | Target (7d) | Error Budget |
|-----|--------------|-------------|--------------|
| **Availability** | 99.9% | 99.5% | 43.2 min/month |
| **Latency** | 95% <10s | 90% <10s | 5% slow requests |
| **Governance** | 99% within budgets | 95% | 1% budget violations |
| **Quality** | 99.5% hallucination-free | 99% | 0.5% hallucinations |

## Bounded Autonomy: Governance as Observability

Rather than treating governance as an afterthought, this solution treats **governance constraints as measurable SLOs**:

| Control | Limit | Observable As |
|---------|-------|---------------|
| Max Agent Steps | 8 (hard cap: 10) | `ops_assistant.agent.steps` gauge |
| Max Model Calls | 5 | `ops_assistant.model.calls` counter |
| Max Tool Calls | 6 | `ops_assistant.tool.calls` counter |
| Confidence Threshold | 0.7 | `ops_assistant.synthesis.confidence` gauge |
| Human Approval | Required for incidents | `ops_assistant.approval.*` metrics |

This makes AI agent behaviour **predictable, debuggable, and continuously improvable** through standard SRE practices.

## Tech Stack

| Component | Technology |
|-----------|------------|
| **LLM** | Google Gemini 2.0 Flash via Vertex AI |
| **Agent Framework** | LangGraph (structured multi-step workflows) |
| **Tool Interface** | Model Context Protocol (MCP) via FastMCP |
| **Backend API** | FastAPI + Uvicorn |
| **Frontend** | Streamlit |
| **Observability** | Datadog (APM, LLM Obs, Logs, Metrics, Incidents) |
| **Quality Evaluation** | RAGAS (faithfulness, answer relevancy) |
| **Deployment** | Google Cloud Run with Datadog Agent sidecar |
| **Package Management** | uv |

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Datadog account with API and App keys
- Google Cloud project with Vertex AI enabled

### Installation

```bash
# Clone the repository
git clone https://github.com/BrianIsaac/AI-Partner-Catalyst.git
cd AI-Partner-Catalyst/ops-assistant

# Install dependencies
uv sync
```

### Configuration

```bash
# Copy environment template
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Datadog
DD_API_KEY=your_datadog_api_key
DD_APP_KEY=your_datadog_app_key
DD_SITE=ap1.datadoghq.com  # or your region

# Google Cloud
GOOGLE_CLOUD_PROJECT=your_project_id
VERTEX_LOCATION=us-central1
GEMINI_MODEL=gemini-2.0-flash-001

# Service Configuration
DD_SERVICE=ops-assistant
DD_ENV=development
```

### Running Locally

```bash
# Terminal 1: Start MCP server
uv run python -m ops_triage_mcp_server.server

# Terminal 2: Start backend API
uv run uvicorn ops_triage_agent.main:app --host 0.0.0.0 --port 8080

# Terminal 3: Start Ops Assistant Frontend
OPS_TRIAGE_AGENT_URL=http://localhost:8080 uv run streamlit run ops_assistant_frontend/app.py

# Terminal 4: Start SAS Query Generator
uv run streamlit run sas_generator/app.py --server.port=8502
```

### Running with Docker

```bash
# Build all images
docker build -f Dockerfile-ops-triage-mcp-server -t ops-mcp-server .
docker build -f Dockerfile-ops-triage-agent -t ops-agent .
docker build -f Dockerfile-ops-frontend -t ops-frontend .
docker build -f Dockerfile-sas-generator -t sas-generator .

# Run with environment variables
docker run -p 8081:8080 --env-file .env ops-mcp-server
docker run -p 8080:8080 --env-file .env -e MCP_SERVER_URL=http://host.docker.internal:8081 ops-agent
docker run -p 8501:8080 -e OPS_TRIAGE_AGENT_URL=http://host.docker.internal:8080 ops-frontend
```

### Deploy to Cloud Run

```bash
# Deploy MCP server
gcloud builds submit --config cloudbuild-mcp.yaml

# Deploy main app with Datadog sidecar
gcloud run services replace infra/cloudrun/service-with-sidecar.yaml --region us-central1

# Deploy frontends
gcloud builds submit --config cloudbuild-ops-frontend.yaml
gcloud builds submit --config cloudbuild-sas-generator.yaml
```

## Traffic Generator

Generate test traffic to verify observability and trigger detection rules:

```bash
# Normal triage questions
uv run python scripts/traffic_gen.py --mode normal --rps 0.5 --duration 60

# Trigger latency alerts
uv run python scripts/traffic_gen.py --mode latency --rps 1.0 --duration 30

# Test quality monitoring (fictional services trigger hallucination detection)
uv run python scripts/traffic_gen.py --mode hallucination --rps 0.5 --duration 30

# Test PII detection
uv run python scripts/traffic_gen.py --mode pii_test --rps 0.5 --duration 30

# Test all modes sequentially
uv run python scripts/traffic_gen.py --mode all --rps 0.5 --duration 120
```

### Available Modes

| Mode | Purpose | Triggers |
|------|---------|----------|
| `normal` | Standard triage questions | Baseline metrics |
| `latency` | Long prompts | High P95 Latency monitor |
| `hallucination` | Fictional services | Quality Degradation, Hallucination Rate monitors |
| `pii_test` | PII in queries | PII Detection Alert |
| `low_confidence` | Vague questions | Escalation metrics |
| `runaway` | Missing identifiers | Step Budget Exceeded |
| `tool_error` | Non-existent services | Tool Error Rate Spike |
| `mcp_health` | Invalid tool calls | MCP Connection Issues |

## Project Structure

```
ops-assistant/
├── ops_triage_agent/           # Backend API for incident triage
│   ├── main.py                 # FastAPI application with /ask, /triage, /review
│   ├── config.py               # Pydantic settings management
│   ├── observability.py        # LLM Obs + DogStatsD metrics
│   ├── security.py             # Prompt injection & PII detection
│   ├── evaluation.py           # Custom quality evaluations
│   ├── agent/                  # LangGraph workflow
│   │   ├── workflow.py         # 8-node state machine
│   │   ├── state.py            # TypedDict state schema
│   │   └── nodes.py            # Node implementations
│   ├── mcp_client/             # MCP client wrapper
│   ├── models/                 # Pydantic request/response schemas
│   └── prompts/                # System prompts (intake, synthesis, incident)
│
├── ops_triage_mcp_server/      # MCP server for Datadog tools
│   ├── server.py               # FastMCP entry point
│   └── tools/                  # 6 tool modules
│       ├── metrics.py          # APM metrics query
│       ├── logs.py             # Log search
│       ├── traces.py           # Span query
│       ├── incidents.py        # Incident management
│       ├── monitors.py         # Monitor status
│       └── dashboards.py       # Dashboard listing
│
├── ops_assistant_frontend/     # Streamlit chat UI
├── sas_generator/              # SAS code generation demo
├── sas_mcp_server/             # SAS data tools
│
├── scripts/
│   └── traffic_gen.py          # 8-mode traffic generator
│
├── infra/
│   ├── cloudrun/               # Cloud Run deployment configs
│   │   ├── service-with-sidecar.yaml  # Datadog Agent sidecar
│   │   └── deploy.sh           # Deployment scripts
│   └── datadog/                # Datadog configuration
│       ├── dashboard.json      # 7-section dashboard
│       ├── monitors.json       # 8 detection rules
│       ├── slos.json           # 4 SLO definitions
│       └── apply_config.sh     # Configuration deployment
│
├── submission/                 # Hackathon submission artifacts
│   ├── dashboard.json          # Dashboard export
│   ├── monitors.json           # Monitors export
│   ├── slos.json               # SLOs export
│   └── screenshots/            # Evidence screenshots
│
├── Dockerfile-*                # Container definitions (5 total)
├── cloudbuild-*.yaml           # Cloud Build configs (4 total)
└── pyproject.toml              # Project dependencies (uv)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with dependency status |
| `/ask` | POST | Free-form triage question |
| `/triage` | POST | Structured triage with service/environment |
| `/review` | POST | Human approval decision for pending incidents |

### Example Request

```bash
curl -X POST https://ops-assistant-i4ney2dwya-uc.a.run.app/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Why is api-gateway experiencing high latency?",
    "service": "api-gateway",
    "time_window": "last_15m"
  }'
```

### Example Response

```json
{
  "summary": "API Gateway latency spike correlated with database connection pool exhaustion",
  "hypotheses": [
    {
      "rank": 1,
      "hypothesis": "Database connection pool exhausted",
      "confidence": 0.85,
      "evidence": ["Error logs showing 'connection pool exhausted'", "DB latency P99 at 2.3s"],
      "next_steps": ["Scale connection pool", "Check for connection leaks"]
    }
  ],
  "confidence": 0.85,
  "requires_approval": false,
  "governance": {
    "steps_used": 4,
    "tool_calls": 3,
    "model_calls": 2
  }
}
```

## Extending with New Agents

To add a new AI agent to the platform:

1. **Create agent module** following the pattern in `ops_triage_agent/` or `sas_generator/`

2. **Implement observability** using the shared patterns:
   ```python
   from ddtrace.llmobs import LLMObs
   from ddtrace.llmobs.decorators import workflow, agent, llm

   @workflow
   def my_agent_workflow(request):
       # Your agent logic
       pass
   ```

3. **Emit standard metrics**:
   ```python
   statsd.gauge("my_agent.steps", step_count, tags=["service:my-agent"])
   ```

4. **Add to dashboard** by extending the service filter variable

5. **Deploy** using the existing Cloud Build patterns

The dashboard automatically aggregates metrics from all agents tagged with the appropriate service name.

## Submission Artifacts

All required Datadog configuration exports are in `submission/`:

| File | Contents |
|------|----------|
| `dashboard.json` | 7-section dashboard with multi-service filtering |
| `monitors.json` | 8 detection rules with incident automation |
| `slos.json` | 4 SLO definitions (availability, latency, governance, quality) |
| `screenshots/` | Evidence of functioning observability |

## Video Walkthrough

[Link to 3-minute video walkthrough]

Topics covered:
1. Observability strategy and three-layer telemetry approach
2. Detection rules rationale and threshold selection
3. Innovation: self-referential monitoring and multi-agent scalability
4. Challenges faced and solutions implemented

## Challenges and Solutions

| Challenge | Solution |
|-----------|----------|
| **Cloud Run + Datadog Agent** | Used Gen2 sidecar pattern with `gcr.io/datadoghq/serverless-init` |
| **LLM Obs + Custom Metrics** | Combined auto-instrumentation with manual DogStatsD emission |
| **Service-to-service auth** | GCP identity tokens for internal Cloud Run communication |
| **Bounded autonomy tracking** | Governance metrics as first-class observability signals |

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.

---

**Built for the Datadog LLM Observability Challenge** — demonstrating that AI agents deserve the same rigorous observability we give to any production system.
