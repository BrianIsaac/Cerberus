"""Gemini-based SAS code generation with MCP integration."""

import asyncio

from sas_generator.prompts import SASCodeResponse
from sas_generator.workflow import generate_sas_code_agentic


def generate_sas_code(query: str) -> SASCodeResponse:
    """Generate SAS code from natural language query.

    This is the synchronous entry point that wraps the async agentic workflow.

    Args:
        query: Natural language description of desired data analysis.

    Returns:
        SASCodeResponse with code, explanation, and procedures used.
    """
    return asyncio.run(generate_sas_code_agentic(query))
