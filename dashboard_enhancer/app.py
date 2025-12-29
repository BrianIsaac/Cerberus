"""Streamlit frontend for Dashboard Enhancement Agent."""

import httpx
import streamlit as st
from datadog import statsd

from dashboard_enhancer.config import settings
from dashboard_enhancer.observability import setup_llm_observability

# Page config
st.set_page_config(
    page_title="Dashboard Enhancement Agent",
    page_icon="chart_with_upwards_trend",
    layout="wide",
)

# Initialise session state
if "session_id" not in st.session_state:
    st.session_state.session_id = None
    setup_llm_observability()

if "enhancement_result" not in st.session_state:
    st.session_state.enhancement_result = None

if "history" not in st.session_state:
    st.session_state.history = []


def get_identity_token(audience: str) -> str | None:
    """Get GCP identity token for service-to-service authentication.

    Args:
        audience: The target service URL.

    Returns:
        Identity token string, or None if running locally.
    """
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        auth_req = google.auth.transport.requests.Request()
        return google.oauth2.id_token.fetch_id_token(auth_req, audience)
    except Exception:
        # Running locally without GCP credentials
        return None


def get_api_headers() -> dict[str, str]:
    """Get headers for API requests, including auth if needed.

    Returns:
        Dictionary of headers for API requests.
    """
    headers = {"Content-Type": "application/json"}
    api_url = settings.dashboard_api_url

    # Add authentication if not running locally
    if not api_url.startswith("http://localhost"):
        token = get_identity_token(api_url)
        if token:
            headers["Authorization"] = f"Bearer {token}"

    return headers


def get_api_client() -> httpx.Client:
    """Get HTTP client for backend API."""
    return httpx.Client(
        base_url=settings.dashboard_api_url,
        timeout=120.0,
        headers=get_api_headers(),
    )


def render_agent_profile(profile: dict):
    """Render agent profile information."""
    st.subheader("Agent Profile")
    cols = st.columns(3)

    with cols[0]:
        st.metric("Service", profile.get("service_name", "Unknown"))
        st.metric("Type", profile.get("agent_type", "Unknown"))

    with cols[1]:
        st.metric("Domain", profile.get("domain", "Unknown"))
        st.metric("LLM Provider", profile.get("llm_provider", "Unknown"))

    with cols[2]:
        st.metric("Framework", profile.get("framework", "Unknown"))

    if profile.get("description"):
        st.caption(profile["description"])


def render_telemetry_profile(profile: dict):
    """Render telemetry profile information."""
    st.subheader("Telemetry Discovered")

    cols = st.columns(2)
    with cols[0]:
        st.write("**Metrics Found:**")
        for metric in profile.get("metrics_found", [])[:10]:
            st.code(metric, language=None)

    with cols[1]:
        st.write("**Trace Operations:**")
        for op in profile.get("trace_operations", [])[:10]:
            st.code(op, language=None)

    flags = []
    if profile.get("has_llm_obs"):
        flags.append("LLM Observability")
    if profile.get("has_custom_metrics"):
        flags.append("Custom Metrics")
    if flags:
        st.success(f"Detected: {', '.join(flags)}")


def render_llmobs_status(status: dict):
    """Render LLM Observability status information.

    Args:
        status: LLMObs status dictionary from API response.
    """
    st.subheader("LLM Observability Status")

    if not status:
        st.info("LLMObs status not available")
        return

    cols = st.columns(3)
    with cols[0]:
        is_enabled = status.get("enabled", False)
        st.metric(
            "Status",
            "Enabled" if is_enabled else "Not Enabled",
        )
    with cols[1]:
        st.metric("ML App", status.get("ml_app", "Unknown"))
    with cols[2]:
        st.metric("Spans Found", status.get("spans_found", 0))

    message = status.get("message", "")
    if message:
        if status.get("enabled"):
            st.success(message)
        else:
            st.warning(message)


def render_provisioned_metrics(metrics: list[dict]):
    """Render provisioned metrics information.

    Args:
        metrics: List of provisioned metric dictionaries.
    """
    st.subheader("Provisioned Span-Based Metrics")

    if not metrics:
        st.info("No metrics provisioned")
        return

    created = [m for m in metrics if m.get("status") == "created"]
    existing = [m for m in metrics if m.get("status") == "exists"]
    failed = [m for m in metrics if m.get("status") == "failed"]

    cols = st.columns(3)
    with cols[0]:
        st.metric("Created", len(created))
    with cols[1]:
        st.metric("Already Existed", len(existing))
    with cols[2]:
        st.metric("Failed", len(failed))

    if created:
        with st.expander("Newly Created Metrics", expanded=True):
            for m in created:
                st.code(m.get("id", "Unknown"), language=None)

    if existing:
        with st.expander("Existing Metrics"):
            for m in existing:
                st.code(m.get("id", "Unknown"), language=None)

    if failed:
        with st.expander("Failed Metrics", expanded=True):
            for m in failed:
                st.error(f"{m.get('id')}: {m.get('error', 'Unknown error')}")


def render_evaluation_results(results: dict):
    """Render evaluation results information.

    Args:
        results: Evaluation results dictionary from API response.
    """
    st.subheader("Domain Evaluations")

    if not results:
        st.info("No evaluations run")
        return

    if not results.get("success"):
        st.warning(results.get("error", "Evaluations not available"))
        if results.get("details"):
            st.caption(results["details"])
        return

    cols = st.columns(4)
    with cols[0]:
        st.metric("Spans Evaluated", results.get("spans_evaluated", 0))
    with cols[1]:
        st.metric("Evaluations Run", results.get("evaluations_run", 0))
    with cols[2]:
        st.metric("Successful", results.get("successful", 0))
    with cols[3]:
        st.metric("Failed", results.get("failed", 0))

    eval_types = results.get("evaluation_types", [])
    if eval_types:
        st.write("**Evaluation Types Applied:**")
        for eval_type in eval_types:
            st.code(eval_type, language=None)


def render_widget_preview(widgets: list[dict], group_title: str):
    """Render widget preview."""
    st.subheader(f"Widget Group: {group_title}")

    for i, widget in enumerate(widgets):
        with st.expander(f"Widget: {widget.get('title', 'Untitled')}", expanded=i == 0):
            st.write(f"**Type:** {widget.get('type', 'unknown')}")
            st.code(widget.get("query", ""), language="sql")
            if widget.get("description"):
                st.caption(widget["description"])


# Main UI
st.title("Dashboard Enhancement Agent")
st.markdown(
    "Analyse AI agents and generate personalised dashboard widget groups."
)

# Sidebar
with st.sidebar:
    st.header("Configuration")
    dashboard_id = st.text_input(
        "Dashboard ID",
        value=settings.dashboard_id,
        help="Datadog dashboard ID to update",
    )

    st.divider()
    st.header("Health Check")
    if st.button("Check Backend"):
        try:
            with get_api_client() as client:
                response = client.get("/health")
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"Healthy: {data.get('version')}")
                else:
                    st.error(f"Error: {response.status_code}")
        except Exception as e:
            st.error(f"Connection failed: {e}")

# Main form
with st.form("enhance_form"):
    st.subheader("Agent to Enhance")

    col1, col2 = st.columns(2)
    with col1:
        service = st.text_input(
            "Service Name",
            placeholder="e.g., sas-generator",
            help="Service name as it appears in Datadog",
        )
    with col2:
        agent_dir = st.text_input(
            "Agent Directory (optional)",
            placeholder="e.g., sas_generator",
            help="Path to agent source code (leave empty for Cloud Run)",
        )

    github_url = st.text_input(
        "GitHub URL (optional)",
        placeholder="e.g., https://github.com/owner/repo/tree/main/agent_dir",
        help="GitHub URL to agent source code for remote analysis",
    )

    # Agent profile section (used when agent_dir is not available)
    with st.expander("Agent Profile (for Cloud Run deployments)", expanded=True):
        st.caption("Provide agent details when local code is not accessible")
        profile_cols = st.columns(2)
        with profile_cols[0]:
            domain = st.selectbox(
                "Domain",
                options=["sas", "ops", "analytics", "dashboard", "data", "other"],
                help="Agent's primary domain",
            )
            agent_type = st.selectbox(
                "Agent Type",
                options=["generator", "assistant", "triage", "enhancer", "analyzer"],
                help="Type of agent",
            )
        with profile_cols[1]:
            llm_provider = st.selectbox(
                "LLM Provider",
                options=["gemini", "openai", "anthropic", "other"],
                help="LLM provider used by the agent",
            )
            framework = st.selectbox(
                "Framework",
                options=["langgraph", "langchain", "custom", "other"],
                help="Agent framework",
            )

    # Observability provisioning options
    st.subheader("Observability Provisioning")
    st.caption("Configure automatic observability infrastructure setup")
    prov_cols = st.columns(2)
    with prov_cols[0]:
        provision_metrics = st.checkbox(
            "Provision Span-Based Metrics",
            value=True,
            help="Automatically create span-based metrics in Datadog for this service",
        )
    with prov_cols[1]:
        run_evaluations = st.checkbox(
            "Run Domain Evaluations",
            value=True,
            help="Run LLM-as-judge evaluations on recent spans using Gemini",
        )

    submitted = st.form_submit_button("Analyse & Generate", type="primary")

    if submitted and service:
        with st.spinner("Analysing agent and provisioning observability..."):
            try:
                # Build request payload
                payload = {
                    "service": service,
                    "dashboard_id": dashboard_id,
                    "agent_profile": {
                        "domain": domain,
                        "agent_type": agent_type,
                        "llm_provider": llm_provider,
                        "framework": framework,
                    },
                    "provision_metrics": provision_metrics,
                    "run_evaluations": run_evaluations,
                }
                # Include agent_dir or github_url if provided
                if agent_dir:
                    payload["agent_dir"] = agent_dir
                if github_url:
                    payload["github_url"] = github_url

                with get_api_client() as client:
                    response = client.post(
                        "/enhance",
                        json=payload,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        st.session_state.enhancement_result = result
                        statsd.increment("dashboard_enhancer.analysis.success")
                    else:
                        error = response.json()
                        st.error(f"Error: {error.get('detail', {}).get('error', 'Unknown')}")
                        statsd.increment("dashboard_enhancer.analysis.error")

            except Exception as e:
                st.error(f"Request failed: {e}")
                statsd.increment("dashboard_enhancer.analysis.error")

# Display results
if st.session_state.enhancement_result:
    result = st.session_state.enhancement_result

    st.divider()
    st.header("Enhancement Recommendations")

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Summary", "Observability", "Widgets", "Raw Data"]
    )

    with tab1:
        render_agent_profile(result.get("agent_profile", {}))
        st.divider()
        render_telemetry_profile(result.get("telemetry_profile", {}))

    with tab2:
        render_llmobs_status(result.get("llmobs_status", {}))
        st.divider()
        render_provisioned_metrics(result.get("provisioned_metrics", []))
        st.divider()
        render_evaluation_results(result.get("evaluation_results", {}))

    with tab3:
        render_widget_preview(
            result.get("widgets", []),
            result.get("group_title", "New Widgets"),
        )

    with tab4:
        st.json(result)

    # Approval buttons
    st.divider()
    st.subheader("Apply Enhancement")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve & Apply", type="primary"):
            with st.spinner("Applying enhancement to dashboard..."):
                try:
                    with get_api_client() as client:
                        response = client.post(
                            "/approve",
                            json={
                                "trace_id": result.get("trace_id"),
                                "outcome": "approved",
                            },
                        )

                        if response.status_code == 200:
                            apply_result = response.json()
                            st.success(apply_result.get("message"))
                            if apply_result.get("dashboard_url"):
                                st.markdown(
                                    f"[View Dashboard]({apply_result['dashboard_url']})"
                                )
                            st.session_state.enhancement_result = None
                            statsd.increment("dashboard_enhancer.apply.success")
                        else:
                            error = response.json()
                            st.error(f"Error: {error.get('detail', {}).get('error')}")
                            statsd.increment("dashboard_enhancer.apply.error")

                except Exception as e:
                    st.error(f"Request failed: {e}")

    with col2:
        if st.button("Reject"):
            try:
                with get_api_client() as client:
                    response = client.post(
                        "/approve",
                        json={
                            "trace_id": result.get("trace_id"),
                            "outcome": "rejected",
                        },
                    )
                    st.session_state.enhancement_result = None
                    st.info("Enhancement rejected. No changes made.")
                    statsd.increment("dashboard_enhancer.reject")
            except Exception as e:
                st.error(f"Request failed: {e}")
