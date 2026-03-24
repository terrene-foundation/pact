# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Discord webhook adapter — governance events as Discord embeds.

Formats PACT governance events into Discord webhook embeds with:
- Colour-coded sidebars (orange=warning, red=error, green=success)
- Structured embed fields for action details, constraints, and costs
- Footer with action ID and timestamp

Usage:
    from pact_platform.integrations.discord_adapter import DiscordAdapter

    adapter = DiscordAdapter(
        webhook_url=os.environ["DISCORD_WEBHOOK_URL"],
        bot_name="PACT Governance",
    )
    await adapter.send("BLOCKED", {
        "agent_id": "agent-001",
        "action": "deploy_production",
        "reason": "Exceeds financial constraint",
    })
"""

from __future__ import annotations

import logging
from typing import Any

from pact_platform.integrations.notification_base import WebhookAdapterBase

logger = logging.getLogger(__name__)

__all__ = ["DiscordAdapter"]

# ---------------------------------------------------------------------------
# Discord embed colours (decimal integer format per Discord API)
# ---------------------------------------------------------------------------
_COLOURS: dict[str, int] = {
    "HELD": 0xFFA500,  # orange
    "BLOCKED": 0xFF0000,  # red
    "COMPLETED": 0x2ECC71,  # green
    "FLAGGED": 0xFFA500,  # orange
    "AUTO_APPROVED": 0x2ECC71,  # green
}

_DEFAULT_COLOUR = 0x808080  # grey


class DiscordAdapter(WebhookAdapterBase):
    """Discord webhook adapter with embed message formatting.

    Inherits retry, rate limiting, and HMAC signing from ``WebhookAdapterBase``.

    Args:
        webhook_url: Discord webhook URL.
        secret: Shared secret for HMAC-SHA256 signing. Empty to disable.
        max_retries: Maximum delivery attempts (>= 1).
        rate_limit_per_minute: Max deliveries per minute (>= 1).
        bot_name: Display name for the webhook bot in Discord.
        avatar_url: Optional avatar URL for the webhook bot.
    """

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        max_retries: int = 3,
        rate_limit_per_minute: int = 60,
        bot_name: str = "PACT Governance",
        avatar_url: str = "",
    ) -> None:
        super().__init__(
            webhook_url=webhook_url,
            secret=secret,
            max_retries=max_retries,
            rate_limit_per_minute=rate_limit_per_minute,
        )
        self._bot_name = bot_name
        self._avatar_url = avatar_url

    def _format_payload(self, event_type: str, payload: dict) -> dict:
        """Format governance event as a Discord webhook message with embeds.

        Produces a Discord webhook JSON body with:
        - ``username``: bot display name
        - ``embeds``: list containing one embed with colour, title, fields, and footer

        Args:
            event_type: Governance event category.
            payload: Event details dict.

        Returns:
            Discord webhook payload dict.
        """
        upper = event_type.upper()
        colour = _COLOURS.get(upper, _DEFAULT_COLOUR)
        embed = self._build_embed(upper, payload, colour)

        message: dict[str, Any] = {
            "username": self._bot_name,
            "embeds": [embed],
        }

        if self._avatar_url:
            message["avatar_url"] = self._avatar_url

        return message

    # ------------------------------------------------------------------
    # Embed builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_embed(
        event_type: str,
        payload: dict,
        colour: int,
    ) -> dict[str, Any]:
        """Build a Discord embed dict for the governance event.

        Args:
            event_type: Upper-cased event category.
            payload: Event details.
            colour: Decimal integer colour value.

        Returns:
            Discord embed dict.
        """
        agent = payload.get("agent_id", "unknown")
        action = payload.get("action", "")
        reason = payload.get("reason", "")

        # Title
        if event_type == "HELD":
            title = "Action Held — Approval Required"
            description = (
                f"Agent `{agent}` requested `{action}` but it was held " f"for human approval."
            )
        elif event_type == "BLOCKED":
            title = "Action Blocked"
            description = f"Agent `{agent}` attempted `{action}` but it was blocked."
        elif event_type == "COMPLETED":
            title = "Action Completed"
            description = f"Agent `{agent}` successfully completed `{action}`."
        elif event_type == "FLAGGED":
            title = "Action Flagged"
            description = (
                f"Agent `{agent}` action `{action}` has been flagged " f"for elevated monitoring."
            )
        else:
            title = f"Governance Event: {event_type}"
            description = f"Agent `{agent}` — `{action}`" if action else f"Agent `{agent}`"

        embed: dict[str, Any] = {
            "title": title,
            "description": description,
            "color": colour,
            "fields": [],
        }

        # Standard fields
        if reason:
            embed["fields"].append({"name": "Reason", "value": reason, "inline": False})

        # Constraint dimension
        dimension = payload.get("constraint_dimension", "")
        if dimension:
            embed["fields"].append({"name": "Constraint", "value": dimension, "inline": True})

        # Cost info for COMPLETED events
        if event_type == "COMPLETED":
            cost = payload.get("cost_usd")
            if cost is not None:
                embed["fields"].append(
                    {
                        "name": "Cost",
                        "value": f"${cost:.4f} USD",
                        "inline": True,
                    }
                )
            tokens_in = payload.get("input_tokens")
            tokens_out = payload.get("output_tokens")
            if tokens_in is not None or tokens_out is not None:
                embed["fields"].append(
                    {
                        "name": "Tokens",
                        "value": f"In: {tokens_in or 0:,} / Out: {tokens_out or 0:,}",
                        "inline": True,
                    }
                )
            provider = payload.get("provider", "")
            model = payload.get("model", "")
            if provider or model:
                embed["fields"].append(
                    {
                        "name": "Provider",
                        "value": f"{provider} / {model}" if model else provider,
                        "inline": True,
                    }
                )

        # Team/org context
        team_id = payload.get("team_id", "")
        if team_id:
            embed["fields"].append({"name": "Team", "value": f"`{team_id}`", "inline": True})

        # Footer with action ID and timestamp
        footer_parts: list[str] = []
        action_id = payload.get("action_id", "")
        if action_id:
            footer_parts.append(f"Action ID: {action_id}")
        timestamp = payload.get("timestamp", "")
        if timestamp:
            footer_parts.append(f"Time: {timestamp}")
        if footer_parts:
            embed["footer"] = {"text": " | ".join(footer_parts)}

        return embed
