"""Shared modules for AI agent fleet.

This package provides common utilities for all AI agents, including:
- observability: Standardised telemetry patterns
- governance: Bounded autonomy components
"""

# Re-export observability for convenience
from shared.observability import *  # noqa: F401, F403

# Re-export governance for convenience
from shared.governance import *  # noqa: F401, F403
