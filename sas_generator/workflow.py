"""Agentic workflow for SAS code generation."""

import json
import re
from typing import Any

from ddtrace.llmobs import LLMObs
from ddtrace.llmobs.decorators import llm, tool, workflow
from google import genai
from google.genai import types

from sas_generator.config import settings
from sas_generator.mcp_client import SASMCPClient
from sas_generator.prompts import SASCodeResponse

DATASET_PATTERN = re.compile(r"SASHELP\.(\w+)", re.IGNORECASE)

DATASET_KEYWORDS = {
    "cars": "SASHELP.CARS",
    "vehicle": "SASHELP.CARS",
    "automobile": "SASHELP.CARS",
    "class": "SASHELP.CLASS",
    "student": "SASHELP.CLASS",
    "heart": "SASHELP.HEART",
    "health": "SASHELP.HEART",
    "framingham": "SASHELP.HEART",
}


def extract_dataset_from_query(query: str) -> str | None:
    """Extract dataset name from user query.

    Args:
        query: User's natural language query.

    Returns:
        Dataset name if found, None otherwise.
    """
    match = DATASET_PATTERN.search(query)
    if match:
        return f"SASHELP.{match.group(1).upper()}"

    query_lower = query.lower()
    for keyword, dataset in DATASET_KEYWORDS.items():
        if keyword in query_lower:
            return dataset

    return None


@tool(name="get_schema")
async def fetch_schema_from_mcp(dataset_name: str) -> dict[str, Any]:
    """Fetch schema and sample data from MCP server.

    Args:
        dataset_name: Name of the dataset.

    Returns:
        Dictionary with schema and sample data.
    """
    async with SASMCPClient() as client:
        schema = await client.get_dataset_schema(dataset_name)
        sample = await client.get_sample_data(dataset_name, n_rows=3)
        return {"schema": schema, "sample": sample}


def build_context_prompt(
    query: str,
    schema: dict[str, Any] | None,
    sample: dict[str, Any] | None,
) -> str:
    """Build enriched prompt with schema context.

    Args:
        query: User's original query.
        schema: Dataset schema from MCP.
        sample: Sample data from MCP.

    Returns:
        Enriched prompt string.
    """
    context_parts = [query]

    if schema and "error" not in schema:
        context_parts.append(
            f"\n\n<dataset_schema>\n{json.dumps(schema, indent=2)}\n</dataset_schema>"
        )

    if sample and "error" not in sample:
        context_parts.append(
            f"\n\n<sample_data>\n{json.dumps(sample, indent=2)}\n</sample_data>"
        )

    return "".join(context_parts)


SYSTEM_PROMPT = """\
You are an expert SAS programmer specialising in generating clean, efficient SAS code.

<guidelines>
- Generate complete, runnable SAS code
- Use appropriate SAS procedures (PROC SQL, DATA step, PROC MEANS, PROC FREQ, etc.)
- Include comments explaining the approach
- Use proper SAS syntax with semicolons
- End PROC SQL with QUIT; and other procedures with RUN;
- Prefer PROC SQL for queries, DATA step for transformations
- Use CLASS instead of BY for grouping in PROC MEANS (no sorting required)
- Use the exact column names from the schema provided
- Reference the sample data to understand data types and formats
</guidelines>
"""


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


@llm(model_name="gemini-2.0-flash-exp", model_provider="google")
def call_gemini(enriched_prompt: str) -> SASCodeResponse:
    """Call Gemini with enriched prompt.

    Args:
        enriched_prompt: Query with schema and sample context.

    Returns:
        Parsed SAS code response.
    """
    client = get_genai_client()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=enriched_prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.95,
            top_k=20,
            max_output_tokens=4096,
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=SASCodeResponse,
        ),
    )

    return response.parsed


@workflow
async def generate_sas_code_agentic(query: str) -> SASCodeResponse:
    """Agentic workflow for SAS code generation.

    This workflow:
    1. Extracts dataset from query
    2. Fetches real schema from MCP server
    3. Generates code with enriched context

    Args:
        query: User's natural language query.

    Returns:
        SAS code response with code, explanation, and procedures.
    """
    LLMObs.annotate(
        input_data=query,
        metadata={
            "service": settings.dd_service,
            "workflow": "sas_generation_agentic",
        },
        tags={"interface": "streamlit", "agent_type": "code-generation"},
    )

    dataset = extract_dataset_from_query(query)

    schema = None
    sample = None
    tool_calls = 0

    if dataset:
        try:
            result = await fetch_schema_from_mcp(dataset)
            schema = result.get("schema")
            sample = result.get("sample")
            tool_calls = 2
        except Exception as e:
            LLMObs.annotate(
                metadata={"mcp_error": str(e), "fallback": True}
            )

    enriched_prompt = build_context_prompt(query, schema, sample)
    response = call_gemini(enriched_prompt)

    LLMObs.annotate(
        output_data=response.model_dump(),
        metadata={
            "dataset_detected": dataset,
            "schema_fetched": schema is not None,
            "tool_calls": tool_calls,
        },
    )

    return response
