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


def get_api_client() -> httpx.Client:
    """Get HTTP client for backend API."""
    return httpx.Client(
        base_url="http://localhost:8083",
        timeout=120.0,
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
            "Agent Directory",
            placeholder="e.g., sas_generator",
            help="Path to agent source code directory",
        )

    submitted = st.form_submit_button("Analyse & Generate", type="primary")

    if submitted and service and agent_dir:
        with st.spinner("Analysing agent and generating widgets..."):
            try:
                with get_api_client() as client:
                    response = client.post(
                        "/enhance",
                        json={
                            "service": service,
                            "agent_dir": agent_dir,
                            "dashboard_id": dashboard_id,
                        },
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
    tab1, tab2, tab3 = st.tabs(["Summary", "Widgets", "Raw Data"])

    with tab1:
        render_agent_profile(result.get("agent_profile", {}))
        st.divider()
        render_telemetry_profile(result.get("telemetry_profile", {}))

    with tab2:
        render_widget_preview(
            result.get("widgets", []),
            result.get("group_title", "New Widgets"),
        )

    with tab3:
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
