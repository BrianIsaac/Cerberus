"""SAS Query Generator Streamlit Application."""

import uuid

import streamlit as st
from datadog import statsd

from sas_generator.generator import generate_sas_code
from sas_generator.observability import setup_llm_observability

st.set_page_config(
    page_title="SAS Query Generator",
    page_icon="",
    layout="wide"
)

if "llmobs_initialised" not in st.session_state:
    setup_llm_observability()
    st.session_state.llmobs_initialised = True

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
                result = generate_sas_code(query)

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
