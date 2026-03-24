# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Microsoft Teams webhook adapter — governance events as MessageCard format.

Formats PACT governance events into Teams MessageCard schema with:
- Colour-coded theme (orange=warning, red=error, green=success)
- Structured sections with facts for action details
- Potential action buttons for HELD events

Usage:
    from pact_platform.integrations.teams_adapter import TeamsAdapter

    adapter = TeamsAdapter(
        webhook_url=os.environ["TEAMS_WEBHOOK_URL"],
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

__all__ = ["TeamsAdapter"]

# ---------------------------------------------------------------------------
# Teams MessageCard theme colours (hex strings without #)
# ---------------------------------------------------------------------------
_COLOURS: dict[str, str] = {
    "HELD": "FFA500",  # orange
    "BLOCKED": "FF0000",  # red
    "COMPLETED": "2ECC71",  # green
    "FLAGGED": "FFA500",  # orange
    "AUTO_APPROVED": "2ECC71",  # green
}

_DEFAULT_COLOUR = "808080"  # grey


class TeamsAdapter(WebhookAdapterBase):
    """Microsoft Teams webhook adapter with MessageCard formatting.

    Inherits retry, rate limiting, and HMAC signing from ``WebhookAdapterBase``.

    Uses the Office 365 Connector ``MessageCard`` schema. For organisations
    migrating to Adaptive Cards via Workflows, the card structure is compatible
    with the ``message`` action type.

    Args:
        webhook_url: Teams incoming webhook URL.
        secret: Shared secret for HMAC-SHA256 signing. Empty to disable.
        max_retries: Maximum delivery attempts (>= 1).
        rate_limit_per_minute: Max deliveries per minute (>= 1).
        dashboard_url: Optional base URL for the PACT dashboard. When set,
            HELD events include an "Open Dashboard" action button.
    """

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        max_retries: int = 3,
        rate_limit_per_minute: int = 60,
        dashboard_url: str = "",
    ) -> None:
        super().__init__(
            webhook_url=webhook_url,
            secret=secret,
            max_retries=max_retries,
            rate_limit_per_minute=rate_limit_per_minute,
        )
        self._dashboard_url = dashboard_url

    def _format_payload(self, event_type: str, payload: dict) -> dict:
        """Format governance event as a Teams MessageCard.

        Produces an Office 365 Connector MessageCard with:
        - ``themeColor``: hex colour based on event type
        - ``summary``: plain-text fallback
        - ``sections``: structured facts for event details
        - ``potentialAction``: dashboard link for HELD events

        Args:
            event_type: Governance event category.
            payload: Event details dict.

        Returns:
            Teams MessageCard dict.
        """
        upper = event_type.upper()
        colour = _COLOURS.get(upper, _DEFAULT_COLOUR)
        title = self._make_title(upper, payload)
        sections = self._build_sections(upper, payload)

        card: dict[str, Any] = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": colour,
            "summary": title,
            "title": title,
            "sections": sections,
        }

        # Add dashboard action for HELD events
        actions = self._build_actions(upper, payload)
        if actions:
            card["potentialAction"] = actions

        return card

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    @staticmethod
    def _make_title(event_type: str, payload: dict) -> str:
        """Build a plain-text title.

        Args:
            event_type: Upper-cased event category.
            payload: Event details.

        Returns:
            Human-readable title string.
        """
        agent = payload.get("agent_id", "unknown")
        action = payload.get("action", "")

        if event_type == "HELD":
            return f"Action HELD — {action} by {agent}"
        if event_type == "BLOCKED":
            return f"Action BLOCKED — {action} by {agent}"
        if event_type == "COMPLETED":
            return f"Action COMPLETED — {action} by {agent}"
        if event_type == "FLAGGED":
            return f"Action FLAGGED — {action} by {agent}"
        return f"[{event_type}] {action} by {agent}"

    @staticmethod
    def _build_sections(
        event_type: str,
        payload: dict,
    ) -> list[dict[str, Any]]:
        """Build MessageCard sections with facts.

        Args:
            event_type: Upper-cased event category.
            payload: Event details.

        Returns:
            List of MessageCard section dicts.
        """
        agent = payload.get("agent_id", "unknown")
        action = payload.get("action", "")
        reason = payload.get("reason", "")

        # Activity section
        if event_type == "HELD":
            activity_title = "Action Held — Approval Required"
            activity_text = (
                f"Agent **{agent}** requested **{action}** but it requires "
                f"human approval before proceeding."
            )
        elif event_type == "BLOCKED":
            activity_title = "Action Blocked"
            activity_text = (
                f"Agent **{agent}** attempted **{action}** but it was denied "
                f"by governance constraints."
            )
        elif event_type == "COMPLETED":
            activity_title = "Action Completed"
            activity_text = f"Agent **{agent}** successfully completed **{action}**."
        elif event_type == "FLAGGED":
            activity_title = "Action Flagged"
            activity_text = (
                f"Agent **{agent}** action **{action}** has been flagged "
                f"for elevated monitoring."
            )
        else:
            activity_title = f"Governance Event: {event_type}"
            activity_text = f"Agent **{agent}** — **{action}**" if action else f"Agent **{agent}**"

        # Facts (key-value pairs rendered as a table)
        facts: list[dict[str, str]] = [
            {"name": "Agent", "value": agent},
        ]
        if action:
            facts.append({"name": "Action", "value": action})
        if reason:
            facts.append({"name": "Reason", "value": reason})

        # Constraint details for HELD/BLOCKED
        dimension = payload.get("constraint_dimension", "")
        if dimension:
            facts.append({"name": "Constraint Dimension", "value": dimension})

        # Cost info for COMPLETED
        if event_type == "COMPLETED":
            cost = payload.get("cost_usd")
            if cost is not None:
                facts.append({"name": "Cost", "value": f"${cost:.4f} USD"})
            tokens_in = payload.get("input_tokens")
            tokens_out = payload.get("output_tokens")
            if tokens_in is not None or tokens_out is not None:
                facts.append(
                    {
                        "name": "Tokens",
                        "value": f"In: {tokens_in or 0:,} / Out: {tokens_out or 0:,}",
                    }
                )
            provider = payload.get("provider", "")
            model = payload.get("model", "")
            if provider or model:
                facts.append(
                    {
                        "name": "Provider/Model",
                        "value": f"{provider} / {model}" if model else provider,
                    }
                )

        # Action ID and timestamp
        action_id = payload.get("action_id", "")
        if action_id:
            facts.append({"name": "Action ID", "value": action_id})
        timestamp = payload.get("timestamp", "")
        if timestamp:
            facts.append({"name": "Timestamp", "value": timestamp})

        # Team context
        team_id = payload.get("team_id", "")
        if team_id:
            facts.append({"name": "Team", "value": team_id})

        section: dict[str, Any] = {
            "activityTitle": activity_title,
            "text": activity_text,
            "facts": facts,
        }

        return [section]

    def _build_actions(
        self,
        event_type: str,
        payload: dict,
    ) -> list[dict[str, Any]]:
        """Build MessageCard potential actions.

        For HELD events with a dashboard URL, adds an "Open Dashboard" button.

        Args:
            event_type: Upper-cased event category.
            payload: Event details.

        Returns:
            List of potentialAction dicts (may be empty).
        """
        actions: list[dict[str, Any]] = []

        if event_type == "HELD" and self._dashboard_url:
            action_id = payload.get("action_id", "")
            url = self._dashboard_url
            if action_id:
                url = f"{self._dashboard_url.rstrip('/')}/decisions/{action_id}"

            actions.append(
                {
                    "@type": "OpenUri",
                    "name": "Open Dashboard",
                    "targets": [{"os": "default", "uri": url}],
                }
            )

        return actions
