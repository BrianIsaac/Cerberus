"""Shared Datadog API configuration for Dashboard MCP Server tools."""

import os

from datadog_api_client import Configuration

DD_API_KEY = os.getenv("DD_API_KEY")
DD_APP_KEY = os.getenv("DD_APP_KEY")
DD_SITE = os.getenv("DD_SITE", "ap1.datadoghq.com")


def get_datadog_config() -> Configuration:
    """Get Datadog API configuration with retry enabled.

    Returns:
        Configuration: Datadog API client configuration with auth keys and site.
    """
    config = Configuration()
    config.api_key["apiKeyAuth"] = DD_API_KEY
    config.api_key["appKeyAuth"] = DD_APP_KEY
    config.server_variables["site"] = DD_SITE
    config.enable_retry = True
    config.max_retries = 3
    return config
