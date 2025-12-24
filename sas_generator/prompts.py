"""System prompts and response schemas for SAS code generation."""

from pydantic import BaseModel, Field

from sas_generator.sashelp_schemas import ALL_SCHEMAS


class SASCodeResponse(BaseModel):
    """Structured response schema for SAS code generation."""

    code: str = Field(description="Complete, runnable SAS code")
    explanation: str = Field(description="Brief explanation of the approach")
    procedures_used: list[str] = Field(description="List of SAS procedures used")


SYSTEM_PROMPT = f"""You are an expert SAS programmer specialising in generating clean, efficient SAS code.

<available_datasets>
{ALL_SCHEMAS}
</available_datasets>

<guidelines>
- Generate complete, runnable SAS code
- Use appropriate SAS procedures (PROC SQL, DATA step, PROC MEANS, PROC FREQ, etc.)
- Include comments explaining the approach
- Use proper SAS syntax with semicolons
- End PROC SQL with QUIT; and other procedures with RUN;
- Prefer PROC SQL for queries, DATA step for transformations
- Use CLASS instead of BY for grouping in PROC MEANS (no sorting required)
</guidelines>
"""
