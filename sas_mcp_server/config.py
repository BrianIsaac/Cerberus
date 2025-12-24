"""SAS MCP Server configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Datadog
    dd_api_key: str = Field(default="", alias="DD_API_KEY")
    dd_site: str = Field(default="ap1.datadoghq.com", alias="DD_SITE")
    dd_service: str = Field(default="sas-mcp-server", alias="DD_SERVICE")
    dd_env: str = Field(default="production", alias="DD_ENV")
    dd_version: str = Field(default="0.1.0", alias="DD_VERSION")

    # Application
    port: int = Field(default=8081, alias="PORT")

    class Config:
        """Pydantic settings configuration."""

        env_file = ".env"
        extra = "ignore"


settings = Settings()
