"""Domain-specific evaluation prompts for LLM-as-judge."""

from dataclasses import dataclass


@dataclass
class EvaluationPrompt:
    """Configuration for a domain-specific evaluation.

    Attributes:
        label: Unique identifier for the evaluation metric.
        metric_type: Either 'score' or 'categorical'.
        description: Human-readable description of what is evaluated.
        prompt_template: Template string with {domain}, {input}, {output} placeholders.
        score_range: Valid range for score metrics (min, max).
        categories: Valid categories for categorical metrics.
    """

    label: str
    metric_type: str
    description: str
    prompt_template: str
    score_range: tuple[float, float] | None = None
    categories: list[str] | None = None


CODE_GENERATION_EVALUATIONS = [
    EvaluationPrompt(
        label="syntax_validity",
        metric_type="categorical",
        description="Check if generated code is syntactically valid",
        categories=["valid", "invalid", "partial"],
        prompt_template="""Analyse the following generated code for syntax validity.

Domain: {domain}
Input Request: {input}
Generated Code:
```
{output}
```

Evaluate ONLY the syntax, not the logic or correctness.
Respond with exactly one of: valid, invalid, partial

- valid: Code has no syntax errors and would parse correctly
- invalid: Code has clear syntax errors that would prevent parsing
- partial: Code is incomplete but what exists is syntactically correct

Response:""",
    ),
    EvaluationPrompt(
        label="output_quality",
        metric_type="score",
        description="Rate overall quality of generated output",
        score_range=(0.0, 1.0),
        prompt_template="""Rate the quality of this generated output.

Domain: {domain}
User Request: {input}
Generated Output:
```
{output}
```

Consider:
1. Does it address the user's request?
2. Is it complete and well-structured?
3. Does it follow best practices for this domain?

Respond with ONLY a decimal number between 0.0 and 1.0:
- 0.0-0.3: Poor quality, doesn't meet requirements
- 0.4-0.6: Acceptable but has issues
- 0.7-0.8: Good quality, meets requirements
- 0.9-1.0: Excellent quality, exceeds expectations

Score:""",
    ),
]


ASSISTANT_EVALUATIONS = [
    EvaluationPrompt(
        label="relevancy",
        metric_type="score",
        description="Rate how relevant the response is to the query",
        score_range=(0.0, 1.0),
        prompt_template="""Rate the relevancy of this response to the user's query.

User Query: {input}
Response: {output}

How well does the response address what the user asked?

Respond with ONLY a decimal number between 0.0 and 1.0:
- 0.0-0.3: Not relevant, off-topic
- 0.4-0.6: Partially relevant
- 0.7-0.8: Mostly relevant
- 0.9-1.0: Highly relevant, directly addresses the query

Score:""",
    ),
    EvaluationPrompt(
        label="helpfulness",
        metric_type="score",
        description="Rate how helpful the response is",
        score_range=(0.0, 1.0),
        prompt_template="""Rate how helpful this response is.

User Query: {input}
Response: {output}

Consider:
1. Does it provide actionable information?
2. Is it clear and understandable?
3. Does it solve the user's problem?

Respond with ONLY a decimal number between 0.0 and 1.0:

Score:""",
    ),
]


TRIAGE_EVALUATIONS = [
    EvaluationPrompt(
        label="accuracy",
        metric_type="score",
        description="Rate the accuracy of the analysis",
        score_range=(0.0, 1.0),
        prompt_template="""Rate the accuracy of this triage/analysis.

Input Data: {input}
Analysis Output: {output}

Consider:
1. Are the conclusions supported by the input data?
2. Are there any obvious errors or misinterpretations?
3. Is the analysis thorough?

Respond with ONLY a decimal number between 0.0 and 1.0:

Score:""",
    ),
    EvaluationPrompt(
        label="completeness",
        metric_type="categorical",
        description="Check if analysis covers all relevant aspects",
        categories=["complete", "partial", "incomplete"],
        prompt_template="""Evaluate the completeness of this analysis.

Input: {input}
Analysis: {output}

Respond with exactly one of: complete, partial, incomplete

- complete: All relevant aspects are covered
- partial: Some aspects are missing but core analysis is present
- incomplete: Major aspects are missing

Response:""",
    ),
]


def get_evaluations_for_agent_type(agent_type: str, domain: str) -> list[EvaluationPrompt]:
    """Get appropriate evaluations based on agent type.

    Args:
        agent_type: Type of agent (e.g., 'code-generation', 'assistant').
        domain: Agent's domain.

    Returns:
        List of evaluation prompts for this agent type.
    """
    agent_type_lower = agent_type.lower()

    if "code" in agent_type_lower or "generator" in agent_type_lower:
        return CODE_GENERATION_EVALUATIONS
    elif "triage" in agent_type_lower or "analysis" in agent_type_lower:
        return TRIAGE_EVALUATIONS
    else:
        return ASSISTANT_EVALUATIONS
