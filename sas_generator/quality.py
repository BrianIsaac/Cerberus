"""LLM-as-judge quality evaluation for SAS code generation.

This module provides quality evaluation for generated SAS code using
an LLM to assess correctness, syntax, best practices, and safety.
"""

import json

import structlog
from google import genai
from google.genai import types

from sas_generator.config import settings
from shared.observability import emit_quality_score

logger = structlog.get_logger()

QUALITY_JUDGE_PROMPT = """\
You are an expert SAS programmer reviewing generated code.

Evaluate the following SAS code on these criteria:
1. **Correctness**: Does the code address the user's request?
2. **Syntax**: Is the SAS syntax valid?
3. **Best Practices**: Does it follow SAS coding standards?
4. **Completeness**: Does it include necessary statements (RUN;, QUIT;)?
5. **Safety**: Does it avoid dangerous operations?

User Query: {query}

Generated Code:
```sas
{code}
```

Respond with a JSON object:
{{
    "overall_score": 0.0-1.0,
    "correctness_score": 0.0-1.0,
    "syntax_score": 0.0-1.0,
    "best_practices_score": 0.0-1.0,
    "completeness_score": 0.0-1.0,
    "safety_score": 0.0-1.0,
    "issues": ["list of specific issues found"],
    "suggestions": ["list of improvement suggestions"],
    "approved": true/false
}}
"""


async def evaluate_code_quality(
    query: str,
    code: str,
    service: str = "sas-generator",
    agent_type: str = "code-generation",
) -> dict:
    """Evaluate generated SAS code quality using LLM-as-judge.

    This function uses Gemini to evaluate the quality of generated SAS code
    across multiple dimensions and emits quality metrics to Datadog.

    Args:
        query: Original user query.
        code: Generated SAS code.
        service: Service name for metrics.
        agent_type: Agent type for metrics.

    Returns:
        Quality evaluation dictionary with scores and feedback.
    """
    try:
        client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )

        prompt = QUALITY_JUDGE_PROMPT.format(query=query, code=code)

        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,  # Low temperature for consistent evaluation
                response_mime_type="application/json",
            ),
        )

        result = json.loads(response.text)

        # Emit quality metrics
        emit_quality_score(
            service, agent_type, result.get("overall_score", 0.0), "code_quality"
        )
        emit_quality_score(
            service, agent_type, result.get("syntax_score", 0.0), "syntax_quality"
        )
        emit_quality_score(
            service, agent_type, result.get("safety_score", 0.0), "safety_score"
        )
        emit_quality_score(
            service,
            agent_type,
            result.get("correctness_score", 0.0),
            "correctness_score",
        )
        emit_quality_score(
            service,
            agent_type,
            result.get("best_practices_score", 0.0),
            "best_practices_score",
        )

        logger.info(
            "Code quality evaluation complete",
            overall_score=result.get("overall_score"),
            approved=result.get("approved"),
            issues_count=len(result.get("issues", [])),
        )

        return result

    except Exception as e:
        logger.error("Code quality evaluation failed", error=str(e))
        # Return a safe default that requires review
        return {
            "overall_score": 0.0,
            "correctness_score": 0.0,
            "syntax_score": 0.0,
            "best_practices_score": 0.0,
            "completeness_score": 0.0,
            "safety_score": 0.0,
            "approved": False,
            "issues": [f"Quality evaluation failed: {str(e)}"],
            "suggestions": ["Manual review required"],
        }


def quick_syntax_check(code: str) -> dict:
    """Perform quick heuristic syntax checks on SAS code.

    This is a fast check that doesn't require an LLM call.

    Args:
        code: SAS code to check.

    Returns:
        Dictionary with syntax check results.
    """
    issues = []
    score = 1.0

    # Check for missing semicolons (basic heuristic)
    lines = code.strip().split("\n")
    for i, line in enumerate(lines):
        line = line.strip()
        if line and not line.startswith("/*") and not line.startswith("*"):
            # Skip empty lines, comments
            if line and not line.endswith(";") and not line.endswith("*/"):
                # Check if it's a continuation or block
                if not any(
                    line.upper().startswith(kw)
                    for kw in ["DO", "IF", "ELSE", "SELECT", "WHEN", "OTHERWISE"]
                ):
                    issues.append(f"Line {i+1}: Possibly missing semicolon")
                    score -= 0.1

    # Check for RUN/QUIT statements
    code_upper = code.upper()
    if "PROC " in code_upper:
        if "PROC SQL" in code_upper and "QUIT;" not in code_upper:
            issues.append("PROC SQL should end with QUIT;")
            score -= 0.2
        elif "PROC SQL" not in code_upper and "RUN;" not in code_upper:
            issues.append("PROC statement should end with RUN;")
            score -= 0.2

    if "DATA " in code_upper and "RUN;" not in code_upper:
        issues.append("DATA step should end with RUN;")
        score -= 0.2

    return {
        "syntax_score": max(0.0, score),
        "issues": issues,
        "passed": len(issues) == 0,
    }
