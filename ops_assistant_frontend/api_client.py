"""Client for ops-triage-agent backend API."""

from typing import Any

import httpx
from ddtrace.llmobs.decorators import workflow

from ops_assistant_frontend.config import settings


class OpsAssistantClient:
    """Client for the ops-triage-agent backend API.

    Uses synchronous httpx client for compatibility with Streamlit's
    execution model.
    """

    def __init__(self) -> None:
        """Initialise the API client."""
        self.base_url = settings.backend_url.rstrip("/")
        self.timeout = 120.0

    def _get_client(self) -> httpx.Client:
        """Create a fresh HTTP client for each request."""
        return httpx.Client(timeout=self.timeout)

    @workflow
    def ask(
        self,
        question: str,
        service: str | None = None,
        time_window: str = "last_15m",
    ) -> dict[str, Any]:
        """Send a triage question to the backend.

        Args:
            question: Free-form triage question
            service: Optional service to focus on
            time_window: Time window for analysis

        Returns:
            API response with hypotheses and analysis
        """
        payload: dict[str, Any] = {
            "question": question,
            "time_window": time_window,
        }
        if service:
            payload["service"] = service

        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/ask",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    @workflow
    def triage(
        self,
        service: str,
        environment: str = "production",
        severity: str | None = None,
        symptoms: str | None = None,
    ) -> dict[str, Any]:
        """Send a structured triage request.

        Args:
            service: Target service name
            environment: Target environment
            severity: Optional severity level (SEV-1 to SEV-4)
            symptoms: Optional symptom description

        Returns:
            API response with hypotheses and proposed incident
        """
        payload: dict[str, Any] = {
            "service": service,
            "environment": environment,
            "time_window": "last_15m",
        }
        if severity:
            payload["severity"] = severity
        if symptoms:
            payload["symptoms"] = symptoms

        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/triage",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    @workflow
    def review(
        self,
        trace_id: str,
        outcome: str,
        modifications: str | None = None,
    ) -> dict[str, Any]:
        """Submit a review decision.

        Args:
            trace_id: Trace ID from previous response
            outcome: Review outcome (approve, edit, reject)
            modifications: Optional modifications for edit outcome

        Returns:
            Review confirmation with incident/case IDs
        """
        payload: dict[str, Any] = {
            "trace_id": trace_id,
            "outcome": outcome,
        }
        if modifications:
            payload["modifications"] = modifications

        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/review",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def health(self) -> dict[str, Any]:
        """Check backend health.

        Returns:
            Health status with version and service info
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
