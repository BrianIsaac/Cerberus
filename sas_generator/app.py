"""SAS Query Generator Streamlit Application.

This is the frontend UI that calls the SAS Generator backend API.
"""

import uuid
from dataclasses import dataclass

import httpx
import streamlit as st
from datadog import statsd

from sas_generator.config import settings


@dataclass
class GenerateResult:
    """Result from the backend API."""

    code: str
    explanation: str
    procedures_used: list[str]
    trace_id: str
    latency_ms: float


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


def call_backend_api(query: str) -> GenerateResult:
    """Call the SAS Generator backend API.

    Args:
        query: Natural language query for SAS code generation.

    Returns:
        GenerateResult with code, explanation, and procedures.

    Raises:
        Exception: If the API call fails.
    """
    api_url = settings.sas_api_url

    headers = {"Content-Type": "application/json"}

    # Add authentication if not running locally
    if not api_url.startswith("http://localhost"):
        token = get_identity_token(api_url)
        if token:
            headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{api_url}/generate",
            json={"query": query},
            headers=headers,
        )

        if response.status_code != 200:
            error_detail = response.json().get("detail", {})
            error_msg = error_detail.get("error", response.text)
            raise Exception(f"API error: {error_msg}")

        data = response.json()
        return GenerateResult(
            code=data["code"],
            explanation=data["explanation"],
            procedures_used=data["procedures_used"],
            trace_id=data["trace_id"],
            latency_ms=data["latency_ms"],
        )


st.set_page_config(
    page_title="SAS Query Generator",
    page_icon="",
    layout="wide"
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "history" not in st.session_state:
    st.session_state.history = []

st.title("SAS Query Generator")
st.markdown("Generate SAS code from natural language using AI")

with st.sidebar:
    st.header("Available Datasets")
    st.markdown("""
    **SASHELP.CARS** - Vehicle data (428 rows)
    - Make, Model, Type, Origin, MSRP, Horsepower, MPG...

    **SASHELP.CLASS** - Student data (19 rows)
    - Name, Sex, Age, Height, Weight

    **SASHELP.HEART** - Heart study (5209 rows)
    - Blood pressure, cholesterol, smoking status...
    """)

    st.divider()
    st.caption(f"Session: {st.session_state.session_id[:8]}...")

for i, item in enumerate(st.session_state.history):
    with st.chat_message("user"):
        st.markdown(item["query"])

    with st.chat_message("assistant"):
        st.markdown(f"**{item['explanation']}**")
        st.markdown(f"*Procedures: {', '.join(item['procedures_used'])}*")
        st.code(item["code"], language="sas")

        col1, col2, col3 = st.columns([1, 1, 8])
        with col1:
            if st.button("Good", key=f"up_{i}"):
                statsd.increment("sas_generator.feedback.positive")
                st.toast("Thanks for the feedback!")
        with col2:
            if st.button("Bad", key=f"down_{i}"):
                statsd.increment("sas_generator.feedback.negative")
                st.toast("We'll try to improve!")

if query := st.chat_input("Describe the data analysis you need..."):
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Generating SAS code..."):
            try:
                result = call_backend_api(query)

                st.markdown(f"**{result.explanation}**")
                st.markdown(f"*Procedures: {', '.join(result.procedures_used)}*")
                st.code(result.code, language="sas")

                st.session_state.history.append({
                    "query": query,
                    "code": result.code,
                    "explanation": result.explanation,
                    "procedures_used": result.procedures_used
                })

                statsd.increment("sas_generator.queries.success")

            except Exception as e:
                st.error(f"Error generating code: {str(e)}")
                statsd.increment("sas_generator.queries.error")

if not st.session_state.history:
    st.markdown("### Example Queries")
    examples = [
        "Show me the average MSRP by vehicle type from the CARS dataset",
        "Calculate the correlation between height and weight for students in CLASS",
        "Find the top 10 most expensive cars with their MPG ratings",
        "Count the number of vehicles by origin and type",
    ]
    for example in examples:
        if st.button(example, key=f"example_{hash(example)}"):
            st.session_state.example_query = example
            st.rerun()
