"""Ops Assistant Frontend Streamlit Application."""

import uuid
from typing import Any

import streamlit as st

from ops_assistant_frontend.api_client import OpsAssistantClient
from ops_assistant_frontend.observability import setup_llm_observability

st.set_page_config(
    page_title="Ops Assistant",
    page_icon="",
    layout="wide",
)

if "llmobs_initialised" not in st.session_state:
    setup_llm_observability()
    st.session_state.llmobs_initialised = True

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None


def get_client() -> OpsAssistantClient:
    """Get or create the API client instance.

    Returns:
        Shared OpsAssistantClient instance
    """
    if "api_client" not in st.session_state:
        st.session_state.api_client = OpsAssistantClient()
    return st.session_state.api_client


def render_hypothesis(hypothesis: dict[str, Any], index: int) -> None:
    """Render a single hypothesis with expander.

    Args:
        hypothesis: Hypothesis data from API
        index: Index for unique key generation
    """
    rank = hypothesis.get("rank", index + 1)
    description = hypothesis.get("description", "")
    confidence = hypothesis.get("confidence", 0)
    evidence = hypothesis.get("evidence", [])

    preview = description[:60] + "..." if len(description) > 60 else description
    with st.expander(f"#{rank}: {preview} ({confidence:.0%})"):
        st.markdown(description)
        if evidence:
            st.markdown("**Evidence:**")
            for item in evidence:
                st.markdown(f"- {item}")


def render_response(data: dict[str, Any]) -> None:
    """Render a complete API response.

    Args:
        data: Response data from API
    """
    summary = data.get("summary", "")
    confidence = data.get("confidence", 0)
    hypotheses = data.get("hypotheses", [])
    next_steps = data.get("next_steps", [])

    if summary:
        st.markdown(f"**Summary:** {summary}")

    st.progress(confidence, text=f"Confidence: {confidence:.0%}")

    if hypotheses:
        st.markdown("**Hypotheses:**")
        for i, h in enumerate(hypotheses):
            render_hypothesis(h, i)

    if next_steps:
        st.markdown("**Recommended Next Steps:**")
        for step in next_steps:
            st.markdown(f"- {step}")


st.title("Ops Assistant")
st.markdown("AI-powered incident triage and investigation")

with st.sidebar:
    st.header("Configuration")

    target_service = st.text_input(
        "Target Service",
        placeholder="e.g., payment-api",
        help="Service to investigate",
    )

    environment = st.selectbox(
        "Environment",
        ["production", "staging", "development"],
        index=0,
    )

    time_window = st.selectbox(
        "Time Window",
        ["last_5m", "last_15m", "last_30m", "last_1h", "last_4h"],
        index=1,
    )

    st.divider()

    if st.button("Check Backend Health"):
        client = get_client()
        try:
            health = client.health()
            version = health.get("version", "unknown")
            st.success(f"Backend healthy: {version}")
        except Exception as e:
            st.error(f"Backend error: {str(e)}")

    st.divider()
    st.caption(f"Session: {st.session_state.session_id[:8]}...")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            data = msg.get("data", {})
            if data:
                render_response(data)
            else:
                st.markdown(msg.get("content", ""))

if st.session_state.pending_approval:
    approval_data = st.session_state.pending_approval
    st.warning("Action requires approval")

    proposed = approval_data.get("proposed_incident", {})
    if proposed:
        st.markdown("**Proposed Incident:**")
        st.markdown(f"- **Title:** {proposed.get('title', 'N/A')}")
        st.markdown(f"- **Service:** {proposed.get('service', 'N/A')}")
        st.markdown(f"- **Severity:** {proposed.get('severity', 'N/A')}")

    col1, col2, col3 = st.columns(3)
    client = get_client()

    with col1:
        if st.button("Approve", type="primary"):
            try:
                result = client.review(
                    trace_id=approval_data["trace_id"],
                    outcome="approve",
                )
                incident_id = result.get("incident_id", "N/A")
                st.success(f"Approved! Incident ID: {incident_id}")
                st.session_state.pending_approval = None
                st.rerun()
            except Exception as e:
                st.error(f"Approval failed: {str(e)}")

    with col2:
        if st.button("Reject"):
            try:
                client.review(
                    trace_id=approval_data["trace_id"],
                    outcome="reject",
                )
                st.info("Rejected")
                st.session_state.pending_approval = None
                st.rerun()
            except Exception as e:
                st.error(f"Rejection failed: {str(e)}")

    with col3:
        if st.button("Edit"):
            st.session_state.show_edit = True

    if st.session_state.get("show_edit"):
        modifications = st.text_area("Modifications", key="edit_modifications")
        if st.button("Submit Edit"):
            try:
                client.review(
                    trace_id=approval_data["trace_id"],
                    outcome="edit",
                    modifications=modifications,
                )
                st.success("Edit submitted")
                st.session_state.pending_approval = None
                st.session_state.show_edit = False
                st.rerun()
            except Exception as e:
                st.error(f"Edit failed: {str(e)}")

if query := st.chat_input("Describe the issue or ask a triage question..."):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    client = get_client()
    with st.chat_message("assistant"):
        with st.spinner("Analysing..."):
            try:
                result = client.ask(
                    question=query,
                    service=target_service or None,
                    time_window=time_window,
                )

                render_response(result)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result.get("summary", ""),
                        "data": result,
                    }
                )

                if result.get("requires_approval"):
                    st.session_state.pending_approval = {
                        "trace_id": result["trace_id"],
                        "proposed_incident": result.get("proposed_incident"),
                    }

            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"Error: {str(e)}",
                        "data": {},
                    }
                )

if not st.session_state.messages:
    st.markdown("### Example Questions")
    examples = [
        "Why is my API responding slowly?",
        "What's causing the spike in error rates?",
        "Investigate high latency on the payment service",
        "Are there any anomalies in the last hour?",
    ]
    for example in examples:
        if st.button(example, key=f"example_{hash(example)}"):
            st.session_state.example_query = example
            st.rerun()
