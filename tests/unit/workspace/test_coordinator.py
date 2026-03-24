# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Cross-Team Coordinator Agent (Task 505).

The Coordinator is a universal agent present in every team that manages
bridge interactions: routing incoming messages, requesting new bridges,
and listing active bridges.
"""

import pytest

from pact_platform.build.workspace.bridge import (
    BridgeManager,
    BridgePermission,
    BridgeStatus,
)
from pact_platform.build.workspace.coordinator import (
    CoordinatorAgent,
    CoordinatorEnvelope,
    RoutingResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bridge_manager():
    """BridgeManager with one active standing bridge."""
    mgr = BridgeManager()
    bridge = mgr.create_standing_bridge(
        source_team="dm-team",
        target_team="standards-team",
        purpose="Ongoing standards alignment",
        permissions=BridgePermission(
            read_paths=["workspaces/dm-team/content/*"],
            message_types=["status_update", "review_request"],
        ),
        created_by="dm-lead",
    )
    bridge.approve_source("dm-lead")
    bridge.approve_target("standards-lead")
    return mgr


@pytest.fixture()
def coordinator(bridge_manager):
    """Coordinator for dm-team."""
    return CoordinatorAgent(
        team_id="dm-team",
        bridge_manager=bridge_manager,
    )


# ---------------------------------------------------------------------------
# Test: Coordinator Construction
# ---------------------------------------------------------------------------


class TestCoordinatorConstruction:
    def test_coordinator_has_team_id(self, coordinator):
        """Coordinator is assigned to a specific team."""
        assert coordinator.team_id == "dm-team"

    def test_coordinator_has_agent_id(self, coordinator):
        """Coordinator has a deterministic agent ID based on team."""
        assert coordinator.agent_id == "dm-team-coordinator"

    def test_coordinator_role(self, coordinator):
        """Coordinator describes its role."""
        assert "bridge" in coordinator.role.lower() or "cross-team" in coordinator.role.lower()


# ---------------------------------------------------------------------------
# Test: Coordinator Constraint Envelope
# ---------------------------------------------------------------------------


class TestCoordinatorEnvelope:
    def test_coordinator_envelope_financial_zero(self):
        """Coordinator has $0 financial authority."""
        env = CoordinatorEnvelope()
        assert env.financial_max_spend_usd == 0.0

    def test_coordinator_envelope_communication_bridge_only(self):
        """Coordinator can only communicate through bridge channels."""
        env = CoordinatorEnvelope()
        assert env.internal_only is True
        assert "bridge" in env.allowed_channels

    def test_coordinator_envelope_no_external(self):
        """Coordinator cannot send external communications."""
        env = CoordinatorEnvelope()
        assert env.external_requires_approval is True

    def test_coordinator_envelope_operational(self):
        """Coordinator allowed actions are bridge-related only."""
        env = CoordinatorEnvelope()
        assert "bridge_messaging" in env.allowed_actions
        assert "bridge_request" in env.allowed_actions
        assert "route_message" in env.allowed_actions


# ---------------------------------------------------------------------------
# Test: handle_incoming
# ---------------------------------------------------------------------------


class TestHandleIncoming:
    def test_handle_incoming_routes_valid_message(self, coordinator, bridge_manager):
        """Valid message on an active bridge is routed successfully."""
        # Get the active bridge
        bridges = bridge_manager.get_bridges_for_team("dm-team")
        active_bridge = [b for b in bridges if b.is_active][0]

        result = coordinator.handle_incoming(
            bridge_id=active_bridge.bridge_id,
            sender_id="standards-agent-001",
            message_type="review_request",
            content={"document": "spec-v2.md"},
        )
        assert isinstance(result, RoutingResult)
        assert result.routed is True
        assert result.bridge_id == active_bridge.bridge_id

    def test_handle_incoming_rejects_inactive_bridge(self, coordinator, bridge_manager):
        """Message on a non-active bridge is rejected."""
        # Create a PENDING (not approved) bridge
        pending = bridge_manager.create_standing_bridge(
            source_team="dm-team",
            target_team="governance-team",
            purpose="Not yet approved",
            permissions=BridgePermission(
                read_paths=["workspaces/dm-team/*"],
                message_types=["info"],
            ),
            created_by="dm-lead",
        )

        result = coordinator.handle_incoming(
            bridge_id=pending.bridge_id,
            sender_id="governance-agent",
            message_type="info",
            content={"text": "Hello"},
        )
        assert result.routed is False
        assert "not active" in result.reason.lower()

    def test_handle_incoming_rejects_unknown_bridge(self, coordinator):
        """Message referencing a non-existent bridge is rejected."""
        result = coordinator.handle_incoming(
            bridge_id="br-nonexistent",
            sender_id="agent-007",
            message_type="status_update",
            content={},
        )
        assert result.routed is False
        assert "not found" in result.reason.lower()


# ---------------------------------------------------------------------------
# Test: request_bridge
# ---------------------------------------------------------------------------


class TestRequestBridge:
    def test_request_bridge_creates_pending_bridge(self, coordinator, bridge_manager):
        """request_bridge creates a new bridge in PENDING status."""
        bridge = coordinator.request_bridge(
            providing_team="governance-team",
            purpose="Need governance review for campaign",
        )
        assert bridge.status == BridgeStatus.PENDING
        assert bridge.source_team_id == "dm-team"
        assert bridge.target_team_id == "governance-team"
        assert "governance review" in bridge.purpose.lower()

    def test_request_bridge_is_stored_in_manager(self, coordinator, bridge_manager):
        """The created bridge is registered in the BridgeManager."""
        bridge = coordinator.request_bridge(
            providing_team="partnerships-team",
            purpose="Partnership inquiry",
        )
        found = bridge_manager.get_bridge(bridge.bridge_id)
        assert found is not None
        assert found.bridge_id == bridge.bridge_id


# ---------------------------------------------------------------------------
# Test: list_active_bridges
# ---------------------------------------------------------------------------


class TestListActiveBridges:
    def test_list_active_bridges_returns_active_only(self, coordinator, bridge_manager):
        """list_active_bridges() only returns ACTIVE bridges."""
        active = coordinator.list_active_bridges()
        assert len(active) >= 1
        assert all(b.is_active for b in active)

    def test_list_active_bridges_excludes_pending(self, coordinator, bridge_manager):
        """Pending bridges are not included in active list."""
        # Create a pending bridge
        bridge_manager.create_standing_bridge(
            source_team="dm-team",
            target_team="partnerships-team",
            purpose="Pending collaboration",
            permissions=BridgePermission(
                read_paths=["workspaces/dm-team/public/*"],
                message_types=["inquiry"],
            ),
            created_by="dm-lead",
        )
        active = coordinator.list_active_bridges()
        for b in active:
            assert b.status == BridgeStatus.ACTIVE

    def test_list_active_bridges_empty_when_none(self):
        """Returns empty when no bridges exist for team."""
        mgr = BridgeManager()
        coord = CoordinatorAgent(team_id="orphan-team", bridge_manager=mgr)
        active = coord.list_active_bridges()
        assert active == []
