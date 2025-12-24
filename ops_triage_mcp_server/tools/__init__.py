"""Shared configuration for Datadog API tools."""

import os

from datadog_api_client import Configuration


def get_datadog_config() -> Configuration:
    """Create Datadog API client configuration.

    Returns:
        Configuration: Datadog API client configuration with auth keys and site.
    """
    config = Configuration()
    config.api_key["apiKeyAuth"] = os.getenv("DD_API_KEY")
    config.api_key["appKeyAuth"] = os.getenv("DD_APP_KEY")
    config.server_variables["site"] = os.getenv("DD_SITE", "datadoghq.com")
    config.enable_retry = True
    config.max_retries = 3
    return config


DD_SITE = os.getenv("DD_SITE", "datadoghq.com")
