# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Error reporting and alerting via webhooks — M23/2309.

Provides:
- AlertSeverity levels (CRITICAL, HIGH, MEDIUM, LOW)
- AlertManager for sending alerts via configurable webhooks
- Rate limiting to prevent alert flooding
- Integration hooks for constraint middleware (BLOCKED actions)
  and trust store health failures

Usage:
    from pact_platform.use.observability.alerting import AlertManager, AlertSeverity

    mgr = AlertManager(
        webhook_urls=["https://hooks.example.com/alert"],
        rate_limit_seconds=60,
    )
    mgr.send_alert(
        severity=AlertSeverity.HIGH,
        title="Budget Exceeded",
        message="Agent agent-1 exceeded API budget",
        source="constraint_middleware",
    )
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)


class AlertSeverity(IntEnum):
    """Alert severity levels, ordered by importance.

    Higher numeric value = higher severity.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AlertManager:
    """Sends alerts via configurable webhooks with rate limiting.

    Rate limiting prevents alert flooding: duplicate alerts with the same
    title within the rate_limit_seconds window are suppressed. CRITICAL
    alerts bypass rate limiting entirely.

    Args:
        webhook_urls: List of webhook URLs to send alerts to.
        rate_limit_seconds: Minimum interval between duplicate alerts.

    Raises:
        ValueError: If no webhook URLs are provided.
    """

    def __init__(
        self,
        webhook_urls: list[str],
        rate_limit_seconds: float = 60.0,
    ) -> None:
        if not webhook_urls:
            raise ValueError(
                "At least one webhook URL is required. "
                "AlertManager cannot function without a delivery target."
            )
        self._webhook_urls = list(webhook_urls)
        self._rate_limit_seconds = rate_limit_seconds
        # Maps alert title -> last send timestamp (monotonic)
        self._last_sent: dict[str, float] = {}

    def send_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send an alert to all configured webhooks.

        CRITICAL alerts bypass rate limiting. Other alerts are
        rate-limited by title.

        Args:
            severity: The alert severity level.
            title: Short alert title (used for rate limiting key).
            message: Detailed alert message.
            source: Source component that generated the alert.
            metadata: Optional additional context.

        Returns:
            True if the alert was sent, False if rate-limited.
        """
        # Rate limiting (CRITICAL bypasses)
        if severity != AlertSeverity.CRITICAL:
            now = time.monotonic()
            last = self._last_sent.get(title)
            if last is not None and (now - last) < self._rate_limit_seconds:
                logger.debug(
                    "Alert rate-limited: title='%s' (last sent %.1fs ago)",
                    title,
                    now - last,
                )
                return False

        payload = {
            "severity": severity.name,
            "title": title,
            "message": message,
            "source": source,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": metadata or {},
        }

        sent = False
        for url in self._webhook_urls:
            try:
                if self._send_webhook(url, payload):
                    sent = True
            except Exception as exc:
                logger.error(
                    "Failed to send alert to webhook '%s': %s",
                    url,
                    exc,
                )

        if sent:
            self._last_sent[title] = time.monotonic()

        return sent

    def _send_webhook(self, url: str, payload: dict[str, Any]) -> bool:
        """Send a payload to a webhook URL.

        Args:
            url: The webhook URL.
            payload: The alert payload dictionary.

        Returns:
            True if the webhook accepted the payload.
        """
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status < 400
        except Exception as exc:
            logger.warning("Webhook delivery failed for '%s': %s", url, exc)
            return False

    # --- Integration hooks ---

    def alert_on_blocked_action(
        self,
        agent_id: str,
        action: str,
        reason: str,
    ) -> bool:
        """Send an alert when a constraint middleware BLOCKS an action.

        Args:
            agent_id: The agent whose action was blocked.
            action: The action that was blocked.
            reason: Why the action was blocked.

        Returns:
            True if the alert was sent.
        """
        return self.send_alert(
            severity=AlertSeverity.HIGH,
            title=f"Action BLOCKED: {action}",
            message=(f"Agent '{agent_id}' action '{action}' was BLOCKED. Reason: {reason}"),
            source="constraint_middleware",
            metadata={
                "agent_id": agent_id,
                "action": action,
                "reason": reason,
            },
        )

    def alert_on_trust_store_failure(
        self,
        error: str,
    ) -> bool:
        """Send an alert when the trust store health check fails.

        Args:
            error: The error message from the health check.

        Returns:
            True if the alert was sent.
        """
        return self.send_alert(
            severity=AlertSeverity.CRITICAL,
            title="Trust Store Health Failure",
            message=(
                f"Trust store is unreachable — all actions will be BLOCKED "
                f"(fail-closed). Error: {error}"
            ),
            source="trust_store_health",
            metadata={
                "error": error,
            },
        )
