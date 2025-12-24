"""Application configuration management."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Google Cloud
    gcp_project_id: str = Field(alias="GOOGLE_CLOUD_PROJECT")
    gcp_location: str = Field(default="us-central1", alias="VERTEX_LOCATION")
    gemini_model: str = Field(default="gemini-1.5-flash", alias="GEMINI_MODEL")

    # Datadog
    dd_api_key: str = Field(alias="DD_API_KEY")
    dd_app_key: str = Field(alias="DD_APP_KEY")
    dd_site: str = Field(default="datadoghq.com", alias="DD_SITE")
    dd_service: str = Field(default="ops-assistant", alias="DD_SERVICE")
    dd_env: str = Field(default="development", alias="DD_ENV")
    dd_version: str = Field(default="0.1.0", alias="DD_VERSION")
    dd_llmobs_enabled: bool = Field(default=True, alias="DD_LLMOBS_ENABLED")
    dd_llmobs_ml_app: str = Field(default="ops-assistant", alias="DD_LLMOBS_ML_APP")
    dd_llmobs_agentless_enabled: bool = Field(default=True, alias="DD_LLMOBS_AGENTLESS_ENABLED")
    dd_llmobs_evaluators: str = Field(
        default="ragas_faithfulness,ragas_context_precision,ragas_answer_relevancy",
        alias="DD_LLMOBS_EVALUATORS",
    )

    # MCP Server
    mcp_server_url: str = Field(alias="MCP_SERVER_URL")

    # Agent Configuration
    agent_max_steps: int = Field(default=8, alias="AGENT_MAX_STEPS")
    agent_max_model_calls: int = Field(default=5, alias="AGENT_MAX_MODEL_CALLS")
    agent_max_tool_calls: int = Field(default=6, alias="AGENT_MAX_TOOL_CALLS")
    confidence_threshold: float = Field(default=0.7, alias="CONFIDENCE_THRESHOLD")

    # Application
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    port: int = Field(default=8080, alias="PORT")

    # External APIs
    openai_api_key: str = Field(alias="OPENAI_API_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
