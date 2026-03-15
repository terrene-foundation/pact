# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Structured logging with correlation IDs — M23/2308.

Provides:
- JSON-formatted structured logging for production
- Correlation ID generation and propagation via context managers
- Agent context propagation for per-agent log enrichment
- CareLogProcessor for structlog integration

Usage:
    from care_platform.observability.logging import (
        configure_logging,
        correlation_context,
        agent_context,
        get_correlation_id,
    )

    logger = configure_logging(json_output=True)

    with correlation_context("request-abc-123"):
        with agent_context("agent-42"):
            logger.info("Processing action", action="read_data")
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Generator

logger = logging.getLogger(__name__)

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


def configure_logging(
    *,
    json_output: bool = False,
    level: str = "INFO",
) -> logging.Logger:
    """Configure structured logging for the CARE Platform.

    Args:
        json_output: When True, configure JSON-formatted output (production).
            When False, use human-readable format (development).
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        A configured root logger for the care_platform package.
    """
    care_logger = logging.getLogger("care_platform")
    care_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not care_logger.handlers:
        handler = logging.StreamHandler()
        if json_output:
            # JSON format for production
            handler.setFormatter(_JsonFormatter())
        else:
            # Human-readable for development
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
        care_logger.addHandler(handler)

    return care_logger


class _JsonFormatter(logging.Formatter):
    """JSON log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        agent_id = get_agent_id()
        if agent_id is not None:
            log_entry["agent_id"] = agent_id

        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = str(record.exc_info[1])

        return json.dumps(log_entry, default=str)
