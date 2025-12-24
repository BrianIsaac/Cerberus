"""Gemini-based SAS code generation."""

from ddtrace.llmobs import LLMObs
from ddtrace.llmobs.decorators import llm, workflow
from google import genai
from google.genai import types

from sas_generator.config import settings
from sas_generator.prompts import SYSTEM_PROMPT, SASCodeResponse


def get_genai_client() -> genai.Client:
    """Get configured Google GenAI client for Vertex AI.

    Returns:
        Configured genai.Client instance.
    """
    return genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )


@workflow
def generate_sas_code(query: str) -> SASCodeResponse:
    """Generate SAS code from natural language query.

    Args:
        query: Natural language description of desired data analysis.

    Returns:
        SASCodeResponse with code, explanation, and procedures used.
    """
    LLMObs.annotate(
        input_data=query,
        metadata={"service": settings.dd_service},
        tags={"interface": "streamlit", "task": "sas_generation"}
    )

    response = call_gemini(query)

    LLMObs.annotate(output_data=response.model_dump())
    return response


@llm(model_name="gemini-2.0-flash-exp", model_provider="google")
def call_gemini(query: str) -> SASCodeResponse:
    """Call Gemini to generate SAS code.

    Args:
        query: User's natural language query.

    Returns:
        Parsed SASCodeResponse (Pydantic model).
    """
    client = get_genai_client()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=query,
        config=types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.95,
            top_k=20,
            max_output_tokens=4096,
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=SASCodeResponse,
        )
    )

    return response.parsed
