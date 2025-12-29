"""Configuration for Dashboard Enhancement Agent."""

from pydantic import Field
from pydantic_settings import BaseSettings

from shared.governance import GOVERNANCE_DEFAULTS


class Settings(BaseSettings):
    """Dashboard Enhancement Agent settings."""

    # Google Cloud
    gcp_project_id: str = Field(alias="GOOGLE_CLOUD_PROJECT")
    vertex_location: str = Field(default="us-central1", alias="VERTEX_LOCATION")
    gemini_model: str = Field(default="gemini-2.0-flash-001", alias="GEMINI_MODEL")

    # Datadog
    dd_api_key: str = Field(alias="DD_API_KEY")
    dd_app_key: str = Field(alias="DD_APP_KEY")
    dd_site: str = Field(default="ap1.datadoghq.com", alias="DD_SITE")
    dd_service: str = Field(default="dashboard-enhancer", alias="DD_SERVICE")
    dd_env: str = Field(default="development", alias="DD_ENV")
    dd_version: str = Field(default="0.1.0", alias="DD_VERSION")

    # LLM Observability
    dd_llmobs_enabled: bool = Field(default=True, alias="DD_LLMOBS_ENABLED")
    dd_llmobs_ml_app: str = Field(default="dashboard-enhancer", alias="DD_LLMOBS_ML_APP")

    # MCP Servers
    dashboard_mcp_url: str = Field(
        default="http://localhost:8084/mcp",
        alias="DASHBOARD_MCP_SERVER_URL",
    )
    ops_mcp_url: str = Field(
        default="http://localhost:8081/mcp",
        alias="OPS_MCP_SERVER_URL",
    )

    # Backend API (for frontend to call)
    dashboard_api_url: str = Field(
        default="http://localhost:8083",
        alias="DASHBOARD_ENHANCER_API_URL",
        description="URL of the Dashboard Enhancer backend API",
    )

    # Governance
    agent_max_steps: int = Field(
        default=GOVERNANCE_DEFAULTS.max_steps,
        alias="AGENT_MAX_STEPS",
    )
    agent_max_model_calls: int = Field(
        default=GOVERNANCE_DEFAULTS.max_model_calls,
        alias="AGENT_MAX_MODEL_CALLS",
    )
    agent_max_tool_calls: int = Field(
        default=GOVERNANCE_DEFAULTS.max_tool_calls,
        alias="AGENT_MAX_TOOL_CALLS",
    )

    # Dashboard
    dashboard_id: str = Field(
        default="k3b-pcm-45c",
        alias="DATADOG_DASHBOARD_ID",
    )

    # GitHub (optional, for private repo code analysis)
    github_token: str | None = Field(
        default=None,
        alias="GITHUB_TOKEN",
        description="GitHub token for private repo access",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
