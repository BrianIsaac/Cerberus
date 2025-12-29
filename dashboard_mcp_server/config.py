"""Configuration for Dashboard MCP Server."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Dashboard MCP Server settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Datadog configuration
    dd_api_key: str = Field(default="", alias="DD_API_KEY")
    dd_app_key: str = Field(default="", alias="DD_APP_KEY")
    dd_site: str = Field(default="ap1.datadoghq.com", alias="DD_SITE")

    # Service identity
    dd_service: str = Field(default="dashboard-mcp-server", alias="DD_SERVICE")
    dd_env: str = Field(default="development", alias="DD_ENV")
    dd_version: str = Field(default="0.1.0", alias="DD_VERSION")


settings = Settings()
