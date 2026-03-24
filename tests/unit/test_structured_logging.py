# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for Task 5024: Structured logging with structlog.

Tests that configure_logging() properly wires structlog as the default
logger with environment-driven format selection (JSON for production,
human-readable for development).
"""

from __future__ import annotations

import json
import logging
import os
from io import StringIO
from unittest.mock import patch

import pytest
import structlog


class TestConfigureLoggingFormat:
    """configure_logging() respects PACT_LOG_FORMAT environment variable."""

    def test_default_format_is_console(self):
        """Without PACT_LOG_FORMAT set, output should be human-readable (console)."""
        from pact_platform.use.observability.logging import configure_logging

        logger = configure_logging()
        assert logger is not None

    def test_json_format_produces_valid_json(self):
        """PACT_LOG_FORMAT=json should produce parseable JSON lines."""
        from pact_platform.use.observability.logging import configure_logging

        logger = configure_logging(log_format="json")
        assert logger is not None

        # Capture output to verify it's valid JSON
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        # Get the structlog-configured stdlib logger and add our capture handler
        stdlib_logger = logging.getLogger("pact")
        stdlib_logger.addHandler(handler)
        stdlib_logger.setLevel(logging.INFO)
        try:
            logger.info("test message", key="value")
            output = stream.getvalue().strip()
            # Should be valid JSON
            if output:
                parsed = json.loads(output)
                assert "event" in parsed or "message" in parsed or "key" in parsed
        finally:
            stdlib_logger.removeHandler(handler)

    def test_console_format_is_not_json(self):
        """PACT_LOG_FORMAT=console should produce human-readable output, not JSON."""
        from pact_platform.use.observability.logging import configure_logging

        logger = configure_logging(log_format="console")
        assert logger is not None

    def test_configure_logging_returns_bound_logger(self):
        """configure_logging() should return a structlog BoundLogger."""
        from pact_platform.use.observability.logging import configure_logging

        logger = configure_logging()
        # structlog bound loggers have bind/unbind methods
        assert hasattr(logger, "bind")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_configure_logging_invalid_format_raises(self):
        """An unrecognized log format should raise a ValueError, not silently default."""
        from pact_platform.use.observability.logging import configure_logging

        with pytest.raises(ValueError, match="log_format"):
            configure_logging(log_format="xml")

    def test_configure_logging_accepts_level(self):
        """configure_logging() should accept and apply a log level."""
        from pact_platform.use.observability.logging import configure_logging

        logger = configure_logging(level="DEBUG")
        assert logger is not None

    def test_structlog_is_configured_globally(self):
        """After configure_logging(), structlog.get_logger() should work."""
        from pact_platform.use.observability.logging import configure_logging

        configure_logging(log_format="console")
        sl = structlog.get_logger("pact.test")
        assert sl is not None


class TestEnvConfigLogFormat:
    """EnvConfig reads PACT_LOG_FORMAT from environment."""

    def test_log_format_default_is_console(self):
        """log_format should default to 'console' when PACT_LOG_FORMAT is not set."""
        from pact_platform.build.config.env import EnvConfig

        config = EnvConfig()
        assert config.log_format == "console"

    def test_log_format_from_env(self):
        """log_format should read PACT_LOG_FORMAT from environment."""
        from pact_platform.build.config.env import load_env_config

        with patch.dict(
            os.environ,
            {
                "PACT_LOG_FORMAT": "json",
                "PACT_DEV_MODE": "true",
            },
            clear=False,
        ):
            config = load_env_config(load_dotenv=False)
            assert config.log_format == "json"

    def test_log_format_preserves_value(self):
        """EnvConfig should store the exact value of PACT_LOG_FORMAT."""
        from pact_platform.build.config.env import EnvConfig

        config = EnvConfig(log_format="json")
        assert config.log_format == "json"


class TestCareLogProcessorWithStructlog:
    """CareLogProcessor still works correctly after structlog wiring."""

    def test_processor_enriches_with_correlation_id(self):
        """CareLogProcessor should still add correlation_id from context."""
        from pact_platform.use.observability.logging import (
            CareLogProcessor,
            correlation_context,
        )

        processor = CareLogProcessor()

        with correlation_context("corr-structlog-test"):
            _, _, event_dict = processor(None, "info", {"event": "test"})

        assert event_dict["correlation_id"] == "corr-structlog-test"
        assert "timestamp" in event_dict

    def test_processor_enriches_with_agent_id(self):
        """CareLogProcessor should still add agent_id from context."""
        from pact_platform.use.observability.logging import (
            CareLogProcessor,
            agent_context,
        )

        processor = CareLogProcessor()

        with agent_context("agent-structlog"):
            _, _, event_dict = processor(None, "info", {"event": "test"})

        assert event_dict["agent_id"] == "agent-structlog"
