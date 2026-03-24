# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Slack webhook adapter — governance events as Block Kit messages.

Formats PACT governance events into Slack's Block Kit structure:
- HELD: orange warning with action details and approve/reject action buttons
- BLOCKED: red alert with reason and constraint details
- COMPLETED: green success with cost summary
- Other events: neutral grey informational message

Supports per-event-type channel routing via ``channel_map``.

Usage:
    from pact_platform.integrations.slack_adapter import SlackAdapter

    adapter = SlackAdapter(
        webhook_url=os.environ["SLACK_WEBHOOK_URL"],
        secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
        channel_map={"HELD": "#approvals", "BLOCKED": "#alerts"},
    )
    await adapter.send("HELD", {
        "agent_id": "agent-001",
        "action": "deploy_production",
        "reason": "Budget limit exceeded",
    })
"""

from __future__ import annotations

import logging
from typing import Any

from pact_platform.integrations.notification_base import WebhookAdapterBase

logger = logging.getLogger(__name__)

__all__ = ["SlackAdapter"]

# ---------------------------------------------------------------------------
# Colour palette for governance event types (Slack uses hex colour strings)
# ---------------------------------------------------------------------------
_COLOURS: dict[str, str] = {
    "HELD": "#FFA500",  # orange — needs human attention
    "BLOCKED": "#FF0000",  # red — action denied
    "COMPLETED": "#2ECC71",  # green — success
    "FLAGGED": "#FFA500",  # orange — elevated risk
    "AUTO_APPROVED": "#2ECC71",  # green — normal flow
}

_DEFAULT_COLOUR = "#808080"  # grey — informational


class SlackAdapter(WebhookAdapterBase):
    """Slack webhook adapter with Block Kit message formatting.

    Inherits retry, rate limiting, and HMAC signing from ``WebhookAdapterBase``.
    Override ``_format_payload`` to produce Slack Block Kit structures.

    Args:
        webhook_url: Slack incoming webhook URL.
        secret: Shared secret for HMAC-SHA256 signing. Empty to disable.
        max_retries: Maximum delivery attempts (>= 1).
        rate_limit_per_minute: Max deliveries per minute (>= 1).
        channel_map: Maps event types to Slack channel names. When set,
            overrides the webhook's default channel.
        default_channel: Fallback channel for unmapped event types. Empty
            string means no override (use webhook default).
    """

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        max_retries: int = 3,
        rate_limit_per_minute: int = 60,
        channel_map: dict[str, str] | None = None,
        default_channel: str = "",
    ) -> None:
        super().__init__(
            webhook_url=webhook_url,
            secret=secret,
            max_retries=max_retries,
            rate_limit_per_minute=rate_limit_per_minute,
        )
        self._channel_map: dict[str, str] = channel_map or {}
        self._default_channel = default_channel

    def _format_payload(self, event_type: str, payload: dict) -> dict:
        """Format governance event as a Slack Block Kit message.

        Produces an ``attachments``-style message with colour coding and
        structured blocks. HELD events include interactive approve/reject
        buttons (requires Slack app with interactivity configured).

        Args:
            event_type: Governance event category (HELD, BLOCKED, COMPLETED, etc.).
            payload: Event details dict.

        Returns:
            Slack-compatible webhook payload dict.
        """
        colour = _COLOURS.get(event_type.upper(), _DEFAULT_COLOUR)
        title = self._make_title(event_type, payload)
        blocks = self._build_blocks(event_type, payload)

        message: dict[str, Any] = {
            "attachments": [
                {
                    "color": colour,
                    "blocks": blocks,
                }
            ],
        }

        # Channel override
        channel = self._channel_map.get(event_type.upper(), self._default_channel)
        if channel:
            message["channel"] = channel

        # Fallback text for notifications/previews
        message["text"] = title

        return message

    # ------------------------------------------------------------------
    # Block builders
    # ------------------------------------------------------------------

    @staticmethod
    def _make_title(event_type: str, payload: dict) -> str:
        """Build a plain-text title line for the event.

        Args:
            event_type: The event category.
            payload: Event details.

        Returns:
            Human-readable title string.
        """
        agent = payload.get("agent_id", "unknown")
        action = payload.get("action", "")
        upper = event_type.upper()

        if upper == "HELD":
            return f":warning: Action HELD — {action} by {agent}"
        if upper == "BLOCKED":
            return f":no_entry: Action BLOCKED — {action} by {agent}"
        if upper == "COMPLETED":
            return f":white_check_mark: Action COMPLETED — {action} by {agent}"
        if upper == "FLAGGED":
            return f":warning: Action FLAGGED — {action} by {agent}"
        return f":information_source: [{upper}] {action} by {agent}"

    @staticmethod
    def _build_blocks(event_type: str, payload: dict) -> list[dict[str, Any]]:
        """Build Slack Block Kit blocks for the event.

        Args:
            event_type: The event category.
            payload: Event details.

        Returns:
            List of Block Kit block dicts.
        """
        blocks: list[dict[str, Any]] = []
        upper = event_type.upper()
        agent = payload.get("agent_id", "unknown")
        action = payload.get("action", "")
        reason = payload.get("reason", "")

        # Header
        if upper == "HELD":
            header_text = ":warning: Action Held — Approval Required"
        elif upper == "BLOCKED":
            header_text = ":no_entry: Action Blocked"
        elif upper == "COMPLETED":
            header_text = ":white_check_mark: Action Completed"
        elif upper == "FLAGGED":
            header_text = ":warning: Action Flagged"
        else:
            header_text = f":information_source: Governance Event: {upper}"

        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header_text},
            }
        )

        # Details section
        fields: list[dict[str, str]] = [
            {"type": "mrkdwn", "text": f"*Agent:*\n`{agent}`"},
        ]
        if action:
            fields.append({"type": "mrkdwn", "text": f"*Action:*\n`{action}`"})
        if reason:
            fields.append({"type": "mrkdwn", "text": f"*Reason:*\n{reason}"})

        # Cost summary for COMPLETED events
        if upper == "COMPLETED":
            cost = payload.get("cost_usd")
            if cost is not None:
                fields.append({"type": "mrkdwn", "text": f"*Cost:*\n${cost:.4f} USD"})
            tokens_in = payload.get("input_tokens")
            tokens_out = payload.get("output_tokens")
            if tokens_in is not None or tokens_out is not None:
                token_text = f"In: {tokens_in or 0:,} / Out: {tokens_out or 0:,}"
                fields.append({"type": "mrkdwn", "text": f"*Tokens:*\n{token_text}"})

        # Constraint dimension for HELD/BLOCKED
        if upper in ("HELD", "BLOCKED"):
            dimension = payload.get("constraint_dimension", "")
            if dimension:
                fields.append(
                    {
                        "type": "mrkdwn",
                        "text": f"*Constraint:*\n{dimension}",
                    }
                )

        blocks.append({"type": "section", "fields": fields})

        # Additional context (timestamp, action_id)
        context_elements: list[dict[str, str]] = []
        action_id = payload.get("action_id", "")
        if action_id:
            context_elements.append({"type": "mrkdwn", "text": f"Action ID: `{action_id}`"})
        timestamp = payload.get("timestamp", "")
        if timestamp:
            context_elements.append({"type": "mrkdwn", "text": f"Time: {timestamp}"})
        if context_elements:
            blocks.append({"type": "context", "elements": context_elements})

        # Approve/Reject buttons for HELD events
        if upper == "HELD":
            blocks.append({"type": "divider"})
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Approve",
                            },
                            "style": "primary",
                            "action_id": "pact_approve",
                            "value": action_id or action,
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Reject",
                            },
                            "style": "danger",
                            "action_id": "pact_reject",
                            "value": action_id or action,
                        },
                    ],
                }
            )

        return blocks
