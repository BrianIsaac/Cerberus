"""Agentic workflow for SAS code generation with governance."""

import json
import re
from typing import Any

import structlog
from datadog import statsd
from ddtrace.llmobs import LLMObs
from ddtrace.llmobs.decorators import llm, tool, workflow
from google import genai
from google.genai import types

from sas_generator.config import settings
from sas_generator.governance import (
    AGENT_SERVICE,
    AGENT_TYPE,
    create_budget_tracker,
    create_escalation_handler,
    create_security_validator,
)
from shared.governance.constants import GovernanceMetrics
from sas_generator.mcp_client import SASMCPClient
from sas_generator.prompts import SASCodeResponse
from sas_generator.quality import evaluate_code_quality, quick_syntax_check

logger = structlog.get_logger()

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
async def generate_sas_code_agentic(query: str) -> dict[str, Any]:
    """Agentic workflow for SAS code generation with full governance.

    This workflow:
    1. Validates input for security concerns
    2. Extracts dataset from query
    3. Fetches real schema from MCP server (with budget tracking)
    4. Generates code with enriched context
    5. Evaluates code quality using LLM-as-judge
    6. Returns result with governance metadata

    Args:
        query: User's natural language query.

    Returns:
        Dictionary with code, explanation, procedures, quality scores,
        and governance metadata.
    """
    # Initialise governance components
    tracker = create_budget_tracker()
    validator = create_security_validator()
    escalation = create_escalation_handler()

    tracker.increment_step()

    # Security validation
    validation_result = validator.validate_input(query)
    if not validation_result.is_valid:
        logger.warning(
            "Security validation failed",
            reason=validation_result.reason.value if validation_result.reason else None,
            message=validation_result.message,
        )
        result = escalation.escalate(
            reason=validation_result.reason,
            message=validation_result.message,
        )
        return {
            "error": result.message,
            "escalated": True,
            "reason": result.reason.value,
        }

    # LLM Obs annotation
    LLMObs.annotate(
        input_data=query,
        metadata={
            "service": settings.dd_service,
            "workflow": "sas_generation_agentic",
        },
        tags={"interface": "streamlit", "agent_type": "code-generation"},
    )

    tracker.increment_step()

    # Dataset detection
    dataset = extract_dataset_from_query(query)
    schema = None
    sample = None

    # MCP tool calls with budget tracking
    if dataset:
        tracker.increment_tool_call()

        # Check budget before MCP call
        if tracker.is_exceeded():
            result = escalation.escalate_from_budget(tracker)
            return {"error": result.message, "escalated": True, "reason": result.reason.value}

        try:
            mcp_result = await fetch_schema_from_mcp(dataset)
            schema = mcp_result.get("schema")
            sample = mcp_result.get("sample")
            tracker.increment_tool_call()
        except Exception as e:
            logger.warning("MCP fetch failed, continuing without schema", error=str(e))
            LLMObs.annotate(metadata={"mcp_error": str(e), "fallback": True})

    tracker.increment_step()

    # Check budget before LLM call
    tracker.increment_model_call()
    if tracker.is_exceeded():
        result = escalation.escalate_from_budget(tracker)
        return {"error": result.message, "escalated": True, "reason": result.reason.value}

    # Build context and call Gemini
    enriched_prompt = build_context_prompt(query, schema, sample)
    response = call_gemini(enriched_prompt)

    code = response.code
    explanation = response.explanation
    procedures = response.procedures_used

    tracker.increment_step()

    # Quick syntax check (no LLM call needed)
    syntax_result = quick_syntax_check(code)

    # Quality evaluation (LLM-as-judge) - only if syntax looks ok
    quality_result = {"overall_score": syntax_result["syntax_score"], "approved": True}
    if syntax_result["passed"]:
        tracker.increment_model_call()
        if not tracker.is_exceeded():
            quality_result = await evaluate_code_quality(query, code)

    quality_score = quality_result.get("overall_score", 0.0)

    # Determine if approval would be required (for API response)
    requires_approval = quality_score < 0.7

    # Emit approval pending metric for dashboard visibility when approval would be required
    if requires_approval:
        tags = [
            f"service:{AGENT_SERVICE}",
            f"agent_type:{AGENT_TYPE}",
            "action_type:code_generation",
        ]
        statsd.increment(GovernanceMetrics.APPROVAL_REQUESTED, tags=tags)

    # Output annotation
    LLMObs.annotate(
        output_data={
            "code": code,
            "explanation": explanation,
            "procedures": procedures,
        },
        metadata={
            "dataset_detected": dataset,
            "schema_fetched": schema is not None,
            "quality_score": quality_score,
            "requires_approval": requires_approval,
            "tool_calls": tracker.tool_calls,
            "model_calls": tracker.model_calls,
        },
    )

    return {
        "code": code,
        "explanation": explanation,
        "procedures_used": procedures,
        "quality_score": quality_score,
        "quality_issues": quality_result.get("issues", []),
        "quality_suggestions": quality_result.get("suggestions", []),
        "syntax_issues": syntax_result.get("issues", []),
        "requires_approval": requires_approval,
        "governance": tracker.get_state(),
    }
