"""Streamlit frontend for Dashboard Enhancement Agent.

Implements a two-phase workflow:
1. Analyse: Discovers service operations and proposes metrics/widgets (no resources created)
2. Provision: Creates metrics and adds widget group to dashboard (after user approval)
"""

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

if "stage" not in st.session_state:
    st.session_state.stage = "input"

if "preview_result" not in st.session_state:
    st.session_state.preview_result = None

if "provision_result" not in st.session_state:
    st.session_state.provision_result = None

if "trace_id" not in st.session_state:
    st.session_state.trace_id = None


def set_stage(stage: str) -> None:
    """Set the current workflow stage.

    Args:
        stage: The stage to transition to ('input', 'preview', 'provisioned').
    """
    st.session_state.stage = stage


def reset_workflow() -> None:
    """Reset the workflow to initial state."""
    st.session_state.stage = "input"
    st.session_state.preview_result = None
    st.session_state.provision_result = None
    st.session_state.trace_id = None


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
        return None


def get_api_headers() -> dict[str, str]:
    """Get headers for API requests, including auth if needed.

    Returns:
        Dictionary of headers for API requests.
    """
    headers = {"Content-Type": "application/json"}
    api_url = settings.dashboard_api_url

    if not api_url.startswith("http://localhost"):
        token = get_identity_token(api_url)
        if token:
            headers["Authorization"] = f"Bearer {token}"

    return headers


def get_api_client() -> httpx.Client:
    """Get HTTP client for backend API.

    Returns:
        Configured httpx Client instance.
    """
    return httpx.Client(
        base_url=settings.dashboard_api_url,
        timeout=300.0,
        headers=get_api_headers(),
    )


def render_discovery_info(discovery: dict) -> None:
    """Render service discovery information.

    Args:
        discovery: Discovery results from the analyse endpoint.
    """
    st.subheader("Service Discovery")
    cols = st.columns(4)

    with cols[0]:
        st.metric("Domain", discovery.get("domain", "Unknown"))
    with cols[1]:
        st.metric("Agent Type", discovery.get("agent_type", "Unknown"))
    with cols[2]:
        st.metric("LLM Provider", discovery.get("llm_provider", "Unknown"))
    with cols[3]:
        st.metric("Framework", discovery.get("framework", "Unknown"))

    info_cols = st.columns(2)
    with info_cols[0]:
        st.metric("Operations Found", discovery.get("operations_found", 0))
    with info_cols[1]:
        st.metric("Existing Metrics", discovery.get("existing_metrics", 0))


def render_llmobs_status(status: dict) -> None:
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


def render_proposed_metrics(metrics: list[dict]) -> None:
    """Render proposed metrics with pending status.

    Args:
        metrics: List of proposed metric dictionaries.
    """
    st.subheader("Proposed Metrics")

    if not metrics:
        st.info("No metrics proposed")
        return

    st.info(
        "These metrics will be created when you click 'Provision & Apply'. "
        "No resources have been created yet."
    )

    for metric in metrics:
        status = metric.get("status", "pending")
        status_colour = "orange" if status == "pending" else "green"

        with st.expander(
            f":{status_colour}[{status.upper()}] {metric.get('id', 'Unknown')}",
            expanded=False,
        ):
            st.write(f"**Description:** {metric.get('description', 'N/A')}")
            st.write(f"**Type:** {metric.get('metric_type', 'count')}")

            widget_config = metric.get("widget_config", {})
            if widget_config.get("rationale"):
                st.write(f"**Rationale:** {widget_config['rationale']}")

            st.write("**Query Templates:**")
            queries = metric.get("queries", {})
            for query_type, query in queries.items():
                st.code(f"{query_type}: {query}", language=None)


def render_provisioned_metrics(metrics: list[dict]) -> None:
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
                st.success(m.get("id", "Unknown"))

    if existing:
        with st.expander("Existing Metrics"):
            for m in existing:
                st.info(m.get("id", "Unknown"))

    if failed:
        with st.expander("Failed Metrics", expanded=True):
            for m in failed:
                st.error(f"{m.get('id')}: {m.get('error', 'Unknown error')}")


def render_widget_preview(widget_preview: dict, is_provisioned: bool = False) -> None:
    """Render widget group preview.

    Args:
        widget_preview: Widget preview dictionary with group_title and widgets.
        is_provisioned: Whether the widgets have been provisioned to the dashboard.
    """
    group_title = widget_preview.get("group_title", "New Widget Group")
    widgets = widget_preview.get("widgets", [])

    status_text = "Added to Dashboard" if is_provisioned else "Preview - Not Yet Applied"
    status_icon = "white_check_mark" if is_provisioned else "hourglass_flowing_sand"

    st.subheader(f"Widget Group: {group_title}")
    st.caption(f":{status_icon}: {status_text}")

    if not widgets:
        st.info("No widgets designed")
        return

    for i, widget in enumerate(widgets):
        with st.expander(
            f"Widget: {widget.get('title', 'Untitled')}", expanded=i == 0
        ):
            st.write(f"**Type:** {widget.get('type', 'unknown')}")
            st.write("**Query:**")
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

    st.divider()
    st.header("Workflow")
    current_stage = st.session_state.stage
    st.write(f"**Current Stage:** {current_stage.title()}")

    if current_stage != "input":
        if st.button("Start New Analysis"):
            reset_workflow()
            st.rerun()


# Stage: Input Form
if st.session_state.stage == "input":
    with st.form("analyse_form"):
        st.subheader("Agent to Analyse")

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

        with st.expander("Agent Profile", expanded=True):
            st.caption("Provide agent details for personalised metric proposals")
            profile_cols = st.columns(2)
            with profile_cols[0]:
                domain = st.selectbox(
                    "Domain",
                    options=["sas", "ops", "analytics", "dashboard", "data", "other"],
                    help="Agent's primary domain",
                )
                agent_type = st.selectbox(
                    "Agent Type",
                    options=[
                        "generator",
                        "assistant",
                        "triage",
                        "enhancer",
                        "analyzer",
                    ],
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

        submitted = st.form_submit_button("Analyse Service", type="primary")

        if submitted and service:
            with st.spinner("Analysing service and proposing metrics..."):
                try:
                    payload = {
                        "service": service,
                        "dashboard_id": dashboard_id,
                        "agent_profile": {
                            "domain": domain,
                            "agent_type": agent_type,
                            "llm_provider": llm_provider,
                            "framework": framework,
                        },
                    }
                    if agent_dir:
                        payload["agent_dir"] = agent_dir
                    if github_url:
                        payload["github_url"] = github_url

                    with get_api_client() as client:
                        response = client.post("/analyze", json=payload)

                        if response.status_code == 200:
                            result = response.json()
                            st.session_state.preview_result = result
                            st.session_state.trace_id = result.get("trace_id")
                            st.session_state.stage = "preview"
                            statsd.increment("dashboard_enhancer.analyse.success")
                            st.rerun()
                        else:
                            error = response.json()
                            st.error(
                                f"Error: {error.get('detail', {}).get('error', str(error))}"
                            )
                            statsd.increment("dashboard_enhancer.analyse.error")

                except Exception as e:
                    st.error(f"Request failed: {e}")
                    statsd.increment("dashboard_enhancer.analyse.error")


# Stage: Preview (Analysis Complete, Awaiting Approval)
elif st.session_state.stage == "preview":
    result: dict = st.session_state.preview_result or {}

    st.success(
        "Analysis complete. Review the proposed metrics and widgets below. "
        "No resources have been created yet."
    )

    service_name = result.get("service", "Unknown")
    trace_id_display = st.session_state.trace_id or "N/A"
    st.info(f"Service: **{service_name}** | Trace ID: `{trace_id_display}`")

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Discovery", "Proposed Metrics", "Widget Preview", "Raw Data"]
    )

    with tab1:
        render_discovery_info(result.get("discovery", {}))
        st.divider()
        render_llmobs_status(result.get("llmobs_status", {}))

    with tab2:
        render_proposed_metrics(result.get("proposed_metrics", []))

    with tab3:
        render_widget_preview(result.get("widget_preview", {}), is_provisioned=False)

    with tab4:
        st.json(result)

    # Action buttons
    st.divider()
    st.subheader("Actions")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Provision & Apply", type="primary"):
            with st.spinner("Creating metrics and adding widgets to dashboard..."):
                try:
                    trace_id = st.session_state.trace_id
                    with get_api_client() as client:
                        response = client.post(f"/provision/{trace_id}")

                        if response.status_code == 200:
                            provision_result = response.json()
                            st.session_state.provision_result = provision_result
                            st.session_state.stage = "provisioned"
                            statsd.increment("dashboard_enhancer.provision.success")
                            st.rerun()
                        else:
                            error = response.json()
                            st.error(
                                f"Provisioning failed: {error.get('detail', {}).get('error', str(error))}"
                            )
                            statsd.increment("dashboard_enhancer.provision.error")

                except Exception as e:
                    st.error(f"Request failed: {e}")
                    statsd.increment("dashboard_enhancer.provision.error")

    with col2:
        if st.button("Cancel"):
            reset_workflow()
            st.info("Analysis cancelled. No resources were created.")
            st.rerun()


# Stage: Provisioned (Resources Created)
elif st.session_state.stage == "provisioned":
    result: dict = st.session_state.provision_result or {}
    preview: dict = st.session_state.preview_result or {}

    metrics_created = result.get("metrics_created", 0)
    widgets_added = result.get("widgets_added", 0)
    st.success(
        f"Provisioning complete! Created {metrics_created} metrics "
        f"and added {widgets_added} widgets to dashboard."
    )

    dashboard_url = result.get("dashboard_url")
    if dashboard_url:
        st.markdown(f"[View Dashboard]({dashboard_url})")

    service_name = result.get("service", "Unknown")
    trace_id_display = st.session_state.trace_id or "N/A"
    st.info(f"Service: **{service_name}** | Trace ID: `{trace_id_display}`")

    # Tabs for results
    tab1, tab2, tab3 = st.tabs(["Provisioned Metrics", "Widget Group", "Raw Data"])

    with tab1:
        provisioned_metrics = result.get("provisioned_metrics")
        if provisioned_metrics:
            render_provisioned_metrics(provisioned_metrics)
        else:
            render_provisioned_metrics(preview.get("proposed_metrics", []))

    with tab2:
        widget_group = result.get("widget_group") or preview.get("widget_preview", {})
        render_widget_preview(widget_group, is_provisioned=True)

    with tab3:
        st.json(result)

    # Rollback option
    st.divider()
    st.subheader("Rollback")
    st.warning(
        "If you want to undo the provisioning, you can rollback the created metrics. "
        "Note: This will delete the metrics but will NOT remove widgets from the dashboard."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Rollback Metrics", type="secondary"):
            with st.spinner("Rolling back created metrics..."):
                try:
                    trace_id = st.session_state.trace_id
                    with get_api_client() as client:
                        response = client.delete(f"/rollback/{trace_id}")

                        if response.status_code == 200:
                            rollback_result = response.json()
                            deleted_count = len(rollback_result.get("deleted", []))
                            st.success(f"Rolled back {deleted_count} metrics.")
                            statsd.increment("dashboard_enhancer.rollback.success")
                            reset_workflow()
                            st.rerun()
                        else:
                            error = response.json()
                            st.error(
                                f"Rollback failed: {error.get('detail', {}).get('error', str(error))}"
                            )
                            statsd.increment("dashboard_enhancer.rollback.error")

                except Exception as e:
                    st.error(f"Request failed: {e}")
                    statsd.increment("dashboard_enhancer.rollback.error")

    with col2:
        if st.button("Start New Analysis"):
            reset_workflow()
            st.rerun()
