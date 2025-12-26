"""SAS Query Generator configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Google Cloud
    gcp_project_id: str = Field(alias="GOOGLE_CLOUD_PROJECT")
    gcp_location: str = Field(default="us-central1", alias="VERTEX_LOCATION")
    gemini_model: str = Field(default="gemini-2.0-flash-exp", alias="GEMINI_MODEL")

    # Datadog
    dd_api_key: str = Field(alias="DD_API_KEY")
    dd_site: str = Field(default="ap1.datadoghq.com", alias="DD_SITE")
    dd_service: str = Field(default="sas-query-generator", alias="DD_SERVICE")
    dd_env: str = Field(default="production", alias="DD_ENV")
    dd_version: str = Field(default="0.1.0", alias="DD_VERSION")
    dd_llmobs_ml_app: str = Field(default="sas-query-generator", alias="DD_LLMOBS_ML_APP")

    # MCP Server
    sas_mcp_server_url: str = Field(
        default="http://localhost:8081/mcp",
        alias="SAS_MCP_SERVER_URL",
    )

    # Application
    port: int = Field(default=8080, alias="PORT")

    class Config:
        """Pydantic settings configuration."""

        env_file = ".env"
        extra = "ignore"


settings = Settings()
