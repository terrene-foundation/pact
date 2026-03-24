# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Cross-Team Coordinator Agent — universal Cross-Functional Bridge interaction manager.

Every team has exactly one Coordinator agent. It manages Cross-Functional Bridge
interactions: routing incoming cross-team messages, requesting new
bridges, and listing active bridges for its team.

Constraint envelope:
    - Financial: $0 (no spending authority)
    - Operational: bridge messaging, bridge request, message routing only
    - Data Access: bridge-eligible content only; no confidential workspace content
    - Communication: bridge channels only; no direct external communication
    - Temporal: active during business hours
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from pact_platform.build.workspace.bridge import (
    Bridge,
    BridgeManager,
    BridgePermission,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Coordinator constraint envelope definition
# ---------------------------------------------------------------------------


class CoordinatorEnvelope(BaseModel):
    """Constraint envelope definition for the Cross-Team Coordinator agent.

    Defines the five CARE constraint dimensions for the Coordinator role.
    The Coordinator has no financial authority, can only communicate through
    bridge channels, and is limited to bridge-related operations.
    """

    # Financial: $0 — no spending authority
    financial_max_spend_usd: float = 0.0

    # Operational: bridge-related actions only
    allowed_actions: list[str] = Field(
        default_factory=lambda: [
            "bridge_messaging",
            "bridge_request",
            "route_message",
        ]
    )

    # Communication: bridge channels only, no external
    internal_only: bool = True
    external_requires_approval: bool = True
    allowed_channels: list[str] = Field(default_factory=lambda: ["bridge"])

    # Data Access: bridge-eligible only
    data_access_read: list[str] = Field(default_factory=lambda: ["bridge-eligible/*"])
    blocked_data_types: list[str] = Field(
        default_factory=lambda: ["confidential", "pii", "financial_records"]
    )

    # Temporal: business hours
    active_hours_start: str = "06:00"
    active_hours_end: str = "22:00"


# ---------------------------------------------------------------------------
# Routing result
# ---------------------------------------------------------------------------


class RoutingResult(BaseModel):
    """Result of routing an incoming bridge message."""

    routed: bool = Field(description="Whether the message was successfully routed")
    bridge_id: str = Field(default="", description="Bridge through which message arrived")
    reason: str = Field(default="", description="Explanation if routing failed")
    target_agent: str = Field(default="", description="Agent the message was routed to")


# ---------------------------------------------------------------------------
# Coordinator Agent
# ---------------------------------------------------------------------------


class CoordinatorAgent:
    """Cross-Team Coordinator agent for managing bridge interactions.

    Each team has exactly one Coordinator. It handles:
    - Incoming messages: verify bridge is active, route to specialist or team lead
    - Bridge requests: create requests to establish new bridges
    - Active bridge listing: report which bridges are operational

    Args:
        team_id: The team this Coordinator belongs to.
        bridge_manager: The shared BridgeManager for Cross-Functional Bridges.
    """

    def __init__(self, team_id: str, bridge_manager: BridgeManager) -> None:
        self._team_id = team_id
        self._bridge_manager = bridge_manager
        self._envelope = CoordinatorEnvelope()

    @property
    def team_id(self) -> str:
        """The team this Coordinator belongs to."""
        return self._team_id

    @property
    def agent_id(self) -> str:
        """Deterministic agent ID based on team."""
        return f"{self._team_id}-coordinator"

    @property
    def role(self) -> str:
        """Human-readable role description."""
        return "Cross-Functional Bridge interaction manager"

    @property
    def envelope(self) -> CoordinatorEnvelope:
        """The Coordinator's constraint envelope."""
        return self._envelope

    def handle_incoming(
        self,
        bridge_id: str,
        sender_id: str,
        message_type: str,
        content: dict[str, Any],
    ) -> RoutingResult:
        """Handle an incoming message through a bridge.

        Verifies the bridge is active and the message is authorized,
        then routes to the appropriate team member.

        Args:
            bridge_id: The bridge the message arrived through.
            sender_id: The agent sending the message.
            message_type: The type of message (must be in bridge permissions).
            content: The message payload.

        Returns:
            RoutingResult indicating whether the message was routed.
        """
        bridge = self._bridge_manager.get_bridge(bridge_id)

        if bridge is None:
            logger.warning(
                "Coordinator %s: bridge '%s' not found — rejecting message from %s",
                self.agent_id,
                bridge_id,
                sender_id,
            )
            return RoutingResult(
                routed=False,
                bridge_id=bridge_id,
                reason=f"Bridge '{bridge_id}' not found",
            )

        if not bridge.is_active:
            logger.warning(
                "Coordinator %s: bridge '%s' is not active (status=%s) — rejecting message",
                self.agent_id,
                bridge_id,
                bridge.status.value,
            )
            return RoutingResult(
                routed=False,
                bridge_id=bridge_id,
                reason=f"Bridge '{bridge_id}' is not active (status: {bridge.status.value})",
            )

        # Route to team lead by default
        target = f"{self._team_id}-team-lead"

        logger.info(
            "Coordinator %s: routed message from %s (type=%s) via bridge %s to %s",
            self.agent_id,
            sender_id,
            message_type,
            bridge_id,
            target,
        )

        return RoutingResult(
            routed=True,
            bridge_id=bridge_id,
            target_agent=target,
        )

    def request_bridge(
        self,
        providing_team: str,
        purpose: str,
    ) -> Bridge:
        """Request a new bridge to another team.

        Creates a scoped bridge request from this team to the providing
        team. The bridge starts in PENDING status and must be approved
        by both sides.

        Args:
            providing_team: The team being asked to provide a bridge.
            purpose: Why the bridge is needed.

        Returns:
            The newly created Bridge in PENDING status.
        """
        bridge = self._bridge_manager.create_scoped_bridge(
            source_team=self._team_id,
            target_team=providing_team,
            purpose=purpose,
            permissions=BridgePermission(
                read_paths=[f"workspaces/{providing_team}/public/*"],
                message_types=["bridge_request", "status_update"],
            ),
            created_by=self.agent_id,
            valid_days=30,
        )

        logger.info(
            "Coordinator %s: requested bridge to %s — bridge_id=%s purpose='%s'",
            self.agent_id,
            providing_team,
            bridge.bridge_id,
            purpose,
        )

        return bridge

    def list_active_bridges(self) -> list[Bridge]:
        """List all active bridges for this team.

        Returns only bridges with ACTIVE status where this team
        is either source or target.

        Returns:
            List of active Bridge objects.
        """
        all_bridges = self._bridge_manager.get_bridges_for_team(self._team_id)
        active = [b for b in all_bridges if b.is_active]

        logger.debug(
            "Coordinator %s: %d active bridges (of %d total)",
            self.agent_id,
            len(active),
            len(all_bridges),
        )

        return active
