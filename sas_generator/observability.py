"""Datadog LLM Observability for SAS Query Generator."""

from ddtrace.llmobs import LLMObs

from sas_generator.config import settings


def setup_llm_observability() -> None:
    """Initialise Datadog LLM Observability."""
    LLMObs.enable(
        ml_app=settings.dd_llmobs_ml_app,
        api_key=settings.dd_api_key,
        site=settings.dd_site,
        agentless_enabled=True,
        integrations_enabled=True,
    )
