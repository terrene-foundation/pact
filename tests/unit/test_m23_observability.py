# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""M23 Security Hardening — tests for tasks 2308 and 2309.

Tests structured logging and alerting.
- 2308: Structured logging with correlation IDs
- 2309: Error reporting and alerting via webhooks
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# 2308: Structured Logging with Correlation IDs (I1)
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    """Structured logging with JSON output and correlation IDs."""

    def test_configure_structured_logging(self):
        """Should be able to configure structured logging."""
        from pact_platform.use.observability.logging import configure_logging

        logger = configure_logging(json_output=True)
        assert logger is not None

    def test_generate_correlation_id(self):
        """Should generate unique correlation IDs."""
        from pact_platform.use.observability.logging import generate_correlation_id

        id1 = generate_correlation_id()
        id2 = generate_correlation_id()
        assert id1 != id2
        assert len(id1) > 0

    def test_correlation_context_manager(self):
        """Should provide a context manager for correlation ID propagation."""
        from pact_platform.use.observability.logging import correlation_context, get_correlation_id

        with correlation_context("test-corr-123"):
            assert get_correlation_id() == "test-corr-123"

        # Outside context, should return None or empty
        assert get_correlation_id() is None

    def test_log_includes_required_fields(self):
        """Log messages should include timestamp, level, correlation_id."""
        from pact_platform.use.observability.logging import (
            CareLogProcessor,
            correlation_context,
        )

        processor = CareLogProcessor()

        with correlation_context("corr-abc"):
            _, _, event_dict = processor(None, "info", {"event": "test"})

        assert "timestamp" in event_dict
        assert "correlation_id" in event_dict
        assert event_dict["correlation_id"] == "corr-abc"

    def test_log_includes_agent_id_when_available(self):
        """Log messages should include agent_id when set in context."""
        from pact_platform.use.observability.logging import (
            CareLogProcessor,
            agent_context,
        )

        processor = CareLogProcessor()

        with agent_context("agent-42"):
            _, _, event_dict = processor(None, "info", {"event": "test"})

        assert "agent_id" in event_dict
        assert event_dict["agent_id"] == "agent-42"

    def test_log_without_context_has_none_correlation_id(self):
        """Without correlation context, correlation_id should be None."""
        from pact_platform.use.observability.logging import CareLogProcessor

        processor = CareLogProcessor()
        _, _, event_dict = processor(None, "info", {"event": "test"})

        assert "correlation_id" in event_dict
        assert event_dict["correlation_id"] is None


# ---------------------------------------------------------------------------
# 2309: Error Reporting and Alerting via Webhooks (I10)
# ---------------------------------------------------------------------------


class TestAlertSeverity:
    """Alert severity levels."""

    def test_severity_levels_exist(self):
        """Should define CRITICAL, HIGH, MEDIUM, LOW severity levels."""
        from pact_platform.use.observability.alerting import AlertSeverity

        assert AlertSeverity.CRITICAL is not None
        assert AlertSeverity.HIGH is not None
        assert AlertSeverity.MEDIUM is not None
        assert AlertSeverity.LOW is not None

    def test_severity_ordering(self):
        """CRITICAL > HIGH > MEDIUM > LOW."""
        from pact_platform.use.observability.alerting import AlertSeverity

        assert AlertSeverity.CRITICAL.value > AlertSeverity.HIGH.value
        assert AlertSeverity.HIGH.value > AlertSeverity.MEDIUM.value
        assert AlertSeverity.MEDIUM.value > AlertSeverity.LOW.value


class TestAlertManager:
    """AlertManager sends alerts via configurable webhooks."""

    def test_create_alert_manager(self):
        """Should be able to create an AlertManager with webhook URLs."""
        from pact_platform.use.observability.alerting import AlertManager

        mgr = AlertManager(webhook_urls=["https://hooks.example.com/alert"])
        assert mgr is not None

    def test_alert_manager_raises_without_webhooks(self):
        """Should raise ValueError if no webhook URLs are provided."""
        from pact_platform.use.observability.alerting import AlertManager

        with pytest.raises(ValueError, match="webhook"):
            AlertManager(webhook_urls=[])

    def test_send_alert(self):
        """Should be able to send an alert."""
        from pact_platform.use.observability.alerting import AlertManager, AlertSeverity

        mgr = AlertManager(webhook_urls=["https://hooks.example.com/alert"])

        # Mock the actual HTTP call
        with patch.object(mgr, "_send_webhook") as mock_send:
            mock_send.return_value = True
            mgr.send_alert(
                severity=AlertSeverity.HIGH,
                title="Test Alert",
                message="Something happened",
                source="test",
            )
            mock_send.assert_called_once()

    def test_rate_limits_alerts(self):
        """Should rate-limit alerts to prevent flooding."""
        from pact_platform.use.observability.alerting import AlertManager, AlertSeverity

        mgr = AlertManager(
            webhook_urls=["https://hooks.example.com/alert"],
            rate_limit_seconds=60,
        )

        with patch.object(mgr, "_send_webhook") as mock_send:
            mock_send.return_value = True

            # First alert should go through
            mgr.send_alert(
                severity=AlertSeverity.HIGH,
                title="Test Alert",
                message="First",
                source="test",
            )
            assert mock_send.call_count == 1

            # Second alert with same title within window should be suppressed
            mgr.send_alert(
                severity=AlertSeverity.HIGH,
                title="Test Alert",
                message="Second",
                source="test",
            )
            assert mock_send.call_count == 1  # Still 1, second was rate-limited

    def test_critical_alerts_bypass_rate_limit(self):
        """CRITICAL alerts should bypass rate limiting."""
        from pact_platform.use.observability.alerting import AlertManager, AlertSeverity

        mgr = AlertManager(
            webhook_urls=["https://hooks.example.com/alert"],
            rate_limit_seconds=60,
        )

        with patch.object(mgr, "_send_webhook") as mock_send:
            mock_send.return_value = True

            mgr.send_alert(
                severity=AlertSeverity.CRITICAL,
                title="Critical Alert",
                message="First",
                source="test",
            )
            mgr.send_alert(
                severity=AlertSeverity.CRITICAL,
                title="Critical Alert",
                message="Second",
                source="test",
            )
            assert mock_send.call_count == 2  # Both should go through

    def test_alert_on_blocked_action(self):
        """Should alert when constraint middleware returns BLOCKED."""
        from pact_platform.use.observability.alerting import AlertManager

        mgr = AlertManager(webhook_urls=["https://hooks.example.com/alert"])

        with patch.object(mgr, "_send_webhook") as mock_send:
            mock_send.return_value = True

            mgr.alert_on_blocked_action(
                agent_id="agent-1",
                action="dangerous_action",
                reason="Budget exceeded",
            )
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            payload = call_args[0][1]  # second positional arg
            assert "agent-1" in str(payload)
            assert "dangerous_action" in str(payload)

    def test_alert_on_trust_store_health_failure(self):
        """Should alert when trust store health check fails."""
        from pact_platform.use.observability.alerting import AlertManager

        mgr = AlertManager(webhook_urls=["https://hooks.example.com/alert"])

        with patch.object(mgr, "_send_webhook") as mock_send:
            mock_send.return_value = True

            mgr.alert_on_trust_store_failure(error="Connection refused")
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            payload = call_args[0][1]
            assert "trust store" in str(payload).lower() or "Connection refused" in str(payload)
