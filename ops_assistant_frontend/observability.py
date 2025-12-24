"""Datadog LLM Observability for Ops Assistant Frontend."""

from ddtrace.llmobs import LLMObs

from ops_assistant_frontend.config import settings


def setup_llm_observability() -> None:
    """Initialise Datadog LLM Observability."""
    if not settings.dd_api_key:
        return

    LLMObs.enable(
        ml_app=settings.dd_llmobs_ml_app,
        api_key=settings.dd_api_key,
        site=settings.dd_site,
        agentless_enabled=True,
        integrations_enabled=True,
    )
