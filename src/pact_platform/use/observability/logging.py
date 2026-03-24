# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Structured logging with structlog and correlation IDs — M23/2308, 5024.

Provides:
- structlog as the default logging library for the PACT
- JSON output for production (PACT_LOG_FORMAT=json)
- Human-readable console output for development (PACT_LOG_FORMAT=console, default)
- Correlation ID generation and propagation via context managers
- Agent context propagation for per-agent log enrichment
- CareLogProcessor for structlog integration

Usage:
    from pact_platform.use.observability.logging import (
        configure_logging,
        correlation_context,
        agent_context,
        get_correlation_id,
    )

    logger = configure_logging(log_format="json")

    with correlation_context("request-abc-123"):
        with agent_context("agent-42"):
            logger.info("Processing action", action="read_data")
"""

from __future__ import annotations

import contextvars
import logging
import sys
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import structlog

# Module-level stdlib logger for internal use within this module
logger = logging.getLogger(__name__)

# Valid log formats — reject anything else explicitly
_VALID_LOG_FORMATS = {"json", "console"}

# Context variables for correlation and agent tracking
_correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
_agent_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("agent_id", default=None)


def generate_correlation_id() -> str:
    """Generate a unique correlation ID.

    Returns:
        A UUID-based correlation ID string.
    """
    return f"corr-{uuid.uuid4().hex[:16]}"


def get_correlation_id() -> str | None:
    """Get the current correlation ID from context.

    Returns:
        The current correlation ID, or None if not in a correlation context.
    """
    return _correlation_id_var.get()


def get_agent_id() -> str | None:
    """Get the current agent ID from context.

    Returns:
        The current agent ID, or None if not in an agent context.
    """
    return _agent_id_var.get()


@contextmanager
def correlation_context(correlation_id: str) -> Generator[None, None, None]:
    """Context manager for propagating a correlation ID.

    All log messages within this context will include the correlation ID.

    Args:
        correlation_id: The correlation ID to set.
    """
    token = _correlation_id_var.set(correlation_id)
    try:
        yield
    finally:
        _correlation_id_var.reset(token)


@contextmanager
def agent_context(agent_id: str) -> Generator[None, None, None]:
    """Context manager for propagating an agent ID.

    All log messages within this context will include the agent ID.

    Args:
        agent_id: The agent ID to set.
    """
    token = _agent_id_var.set(agent_id)
    try:
        yield
    finally:
        _agent_id_var.reset(token)


class CareLogProcessor:
    """Structlog-compatible processor that enriches log events.

    Adds:
    - timestamp (ISO 8601 with timezone)
    - correlation_id (from context)
    - agent_id (from context, when available)
    """

    def __call__(
        self,
        logger_obj: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> tuple[Any, str, dict[str, Any]]:
        """Process a log event, adding correlation and context fields.

        Args:
            logger_obj: The logger instance (unused).
            method_name: The log level method name.
            event_dict: The log event dictionary to enrich.

        Returns:
            Tuple of (logger, method_name, enriched event_dict).
        """
        event_dict["timestamp"] = datetime.now(UTC).isoformat()
        event_dict["correlation_id"] = get_correlation_id()

        agent_id = get_agent_id()
        if agent_id is not None:
            event_dict["agent_id"] = agent_id

        return logger_obj, method_name, event_dict


def _add_care_context(
    logger_obj: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor that injects CARE context (correlation ID, agent ID).

    This is a proper structlog processor (returns event_dict only).
    Used in the structlog processor chain.
    """
    event_dict["correlation_id"] = get_correlation_id()

    agent_id = get_agent_id()
    if agent_id is not None:
        event_dict["agent_id"] = agent_id

    return event_dict


def configure_logging(
    *,
    log_format: str = "console",
    json_output: bool | None = None,
    level: str = "INFO",
) -> structlog.stdlib.BoundLogger:
    """Configure structured logging for the PACT using structlog.

    Sets up structlog with the appropriate renderer (JSON for production,
    human-readable console for development) and configures the stdlib
    logging integration so all loggers benefit from structured output.

    Args:
        log_format: Output format — "json" for production or "console" for
            development. Read from PACT_LOG_FORMAT env var at the call site.
            Defaults to "console".
        json_output: Deprecated — use log_format="json" instead. When provided,
            True maps to log_format="json", False maps to log_format="console".
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        A structlog BoundLogger configured for the pact namespace.

    Raises:
        ValueError: If log_format is not one of "json" or "console".
    """
    # Handle backward-compatible json_output parameter
    if json_output is not None:
        log_format = "json" if json_output else "console"

    if log_format not in _VALID_LOG_FORMATS:
        raise ValueError(
            f"Invalid log_format={log_format!r}. "
            f"Must be one of: {sorted(_VALID_LOG_FORMATS)}. "
            f"Set PACT_LOG_FORMAT environment variable to 'json' or 'console'."
        )

    # Choose renderer based on format
    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # Configure structlog globally
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _add_care_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    # Configure stdlib logging to match the level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Set up the root handler for stdlib logging
    root_logger = logging.getLogger()
    # Configure pact logger level
    pact_logger = logging.getLogger("pact")
    pact_logger.setLevel(log_level)

    # Add a handler if none exists on the root
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(log_level)
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)

    return structlog.get_logger("pact")
