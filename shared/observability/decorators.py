"""Reusable observability decorators for AI agents.

This module provides decorators that add automatic metrics emission
to workflow functions without requiring boilerplate code.
"""

import asyncio
import functools
import time
from typing import Callable, ParamSpec, TypeVar

from shared.observability.metrics import emit_request_complete

P = ParamSpec("P")
R = TypeVar("R")


def observed_workflow(
    service: str,
    agent_type: str,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to add observability to workflow functions.

    Automatically emits request completion metrics including latency
    and success status. Works with both sync and async functions.

    Args:
        service: Service name for metrics.
        agent_type: Type of agent.

    Returns:
        Decorated function with automatic metrics emission.

    Example:
        @observed_workflow("sas-generator", "code-generation")
        async def generate_code(query: str) -> CodeResponse:
            return await do_generation(query)
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                start_time = time.perf_counter()
                success = True

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception:
                    success = False
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    emit_request_complete(
                        service=service,
                        agent_type=agent_type,
                        latency_ms=latency_ms,
                        success=success,
                    )

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start_time = time.perf_counter()
            success = True

            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                success = False
                raise
            finally:
                latency_ms = (time.perf_counter() - start_time) * 1000
                emit_request_complete(
                    service=service,
                    agent_type=agent_type,
                    latency_ms=latency_ms,
                    success=success,
                )

        return sync_wrapper  # type: ignore[return-value]

    return decorator
