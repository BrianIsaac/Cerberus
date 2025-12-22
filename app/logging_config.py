"""Structured logging configuration with Datadog trace correlation."""

import logging

import structlog
from ddtrace import tracer

from app.config import settings


def add_datadog_trace_context(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Inject Datadog trace correlation context into logs.

    Args:
        logger: The wrapped logger instance.
        method_name: Name of the logging method called.
        event_dict: Dictionary containing the log event data.

    Returns:
        The event dictionary with trace context added.
    """
    trace_context = tracer.get_log_correlation_context()
    event_dict.update(trace_context)
    return event_dict


def add_service_context(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Add service metadata to all log entries.

    Args:
        logger: The wrapped logger instance.
        method_name: Name of the logging method called.
        event_dict: Dictionary containing the log event data.

    Returns:
        The event dictionary with service context added.
    """
    event_dict["service"] = settings.dd_service
    event_dict["env"] = settings.dd_env
    event_dict["version"] = settings.dd_version
    return event_dict


def configure_logging() -> None:
    """Configure structlog with Datadog integration.

    Sets up structured JSON logging with:
    - Context variable merging for request-scoped data
    - Log level and logger name inclusion
    - ISO timestamp formatting
    - Service metadata injection
    - Datadog trace correlation IDs
    - Stack info and exception formatting
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_service_context,
        add_datadog_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper()),
    )
