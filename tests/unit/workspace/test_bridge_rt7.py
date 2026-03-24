# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""RT7 red team tests for Cross-Functional Bridges.

RT7-07: Enforce bridge directionality in access_through_bridge.
RT7-12: resume_bridge must check valid_until before reactivation.
"""

from datetime import UTC, datetime, timedelta

import pytest

from pact_platform.build.workspace.bridge import (
    BridgeManager,
    BridgePermission,
    BridgeStatus,
)


@pytest.fixture()
def permissions_docs():
    """Permissions granting read access to docs paths."""
    return BridgePermission(
        read_paths=["docs/*", "reports/*"],
        write_paths=["drafts/*"],
        message_types=["status_update"],
    )


@pytest.fixture()
def manager():
    """Fresh BridgeManager instance."""
    return BridgeManager()


def _make_active_bridge(mgr: BridgeManager, perms: BridgePermission) -> str:
    """Helper: create and activate a standing bridge source-team -> target-team."""
    bridge = mgr.create_standing_bridge(
        source_team="source-team",
        target_team="target-team",
        purpose="RT7 test bridge",
        permissions=perms,
        created_by="admin",
    )
    bridge.approve_source("source-lead")
    bridge.approve_target("target-lead")
    assert bridge.status == BridgeStatus.ACTIVE
    return bridge.bridge_id


# ===========================================================================
# RT7-07: Enforce bridge directionality
# ===========================================================================


class TestBridgeDirectionality:
    """RT7-07: Bridge permissions flow source -> target only.

    read_paths/write_paths grant the SOURCE team access to the TARGET team's data.
    Target team agents must NOT use the same bridge to access source team data.
    """

    def test_source_team_agent_read_allowed(self, manager, permissions_docs):
        """Agent from source team can read through bridge (source->target direction)."""
        bridge_id = _make_active_bridge(manager, permissions_docs)
        assert manager.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="source-agent-1",
            path="docs/readme.md",
            access_type="read",
            agent_team_id="source-team",
        )

    def test_source_team_agent_write_allowed(self, manager, permissions_docs):
        """Agent from source team can write through bridge (source->target direction)."""
        bridge_id = _make_active_bridge(manager, permissions_docs)
        assert manager.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="source-agent-1",
            path="drafts/doc.md",
            access_type="write",
            agent_team_id="source-team",
        )

    def test_target_team_agent_read_denied(self, manager, permissions_docs):
        """Agent from target team CANNOT read through bridge (wrong direction)."""
        bridge_id = _make_active_bridge(manager, permissions_docs)
        assert not manager.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="target-agent-1",
            path="docs/readme.md",
            access_type="read",
            agent_team_id="target-team",
        )

    def test_target_team_agent_write_denied(self, manager, permissions_docs):
        """Agent from target team CANNOT write through bridge (wrong direction)."""
        bridge_id = _make_active_bridge(manager, permissions_docs)
        assert not manager.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="target-agent-1",
            path="drafts/doc.md",
            access_type="write",
            agent_team_id="target-team",
        )

    def test_no_team_id_denied_fail_closed(self, manager, permissions_docs):
        """RT8-05: When agent_team_id is None, access is DENIED (fail-closed)."""
        bridge_id = _make_active_bridge(manager, permissions_docs)
        assert not manager.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="unknown-agent",
            path="docs/readme.md",
            access_type="read",
            # agent_team_id not provided — fail-closed denies access
        )

    def test_outsider_team_still_rejected(self, manager, permissions_docs):
        """Agent from a team NOT source or target is still rejected (RT2-16)."""
        bridge_id = _make_active_bridge(manager, permissions_docs)
        assert not manager.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="outsider-agent",
            path="docs/readme.md",
            access_type="read",
            agent_team_id="unrelated-team",
        )

    def test_bidirectional_requires_two_bridges(self, manager, permissions_docs):
        """For bidirectional access, two separate bridges are needed."""
        # Bridge 1: source -> target
        bridge_id_1 = _make_active_bridge(manager, permissions_docs)

        # Bridge 2: target -> source (reverse direction)
        reverse_perms = BridgePermission(read_paths=["source-docs/*"])
        bridge_rev = manager.create_standing_bridge(
            source_team="target-team",
            target_team="source-team",
            purpose="Reverse direction bridge",
            permissions=reverse_perms,
            created_by="admin",
        )
        bridge_rev.approve_source("target-lead")
        bridge_rev.approve_target("source-lead")
        bridge_id_2 = bridge_rev.bridge_id

        # Source agent can use bridge 1 (source->target)
        assert manager.access_through_bridge(
            bridge_id=bridge_id_1,
            agent_id="source-agent",
            path="docs/readme.md",
            access_type="read",
            agent_team_id="source-team",
        )

        # Source agent cannot use bridge 1 in reverse
        # (target-team agent on bridge 1 is denied)
        assert not manager.access_through_bridge(
            bridge_id=bridge_id_1,
            agent_id="target-agent",
            path="docs/readme.md",
            access_type="read",
            agent_team_id="target-team",
        )

        # Target agent can use bridge 2 (reverse direction, target is source here)
        assert manager.access_through_bridge(
            bridge_id=bridge_id_2,
            agent_id="target-agent",
            path="source-docs/report.md",
            access_type="read",
            agent_team_id="target-team",
        )


# ===========================================================================
# RT7-12: resume_bridge must check valid_until before reactivation
# ===========================================================================


class TestResumeBridgeExpiryCheck:
    """RT7-12: resume_bridge should not reactivate expired bridges."""

    def test_resume_expired_bridge_raises(self, manager, permissions_docs):
        """Resuming a suspended bridge past valid_until raises ValueError."""
        bridge = manager.create_scoped_bridge(
            source_team="source-team",
            target_team="target-team",
            purpose="Scoped bridge for resume test",
            permissions=permissions_docs,
            created_by="admin",
            valid_days=7,
        )
        bridge.approve_source("source-lead")
        bridge.approve_target("target-lead")

        manager.suspend_bridge(bridge.bridge_id, reason="Maintenance")
        assert bridge.status == BridgeStatus.SUSPENDED

        # Force past expiry
        bridge.valid_until = datetime.now(UTC) - timedelta(hours=1)

        with pytest.raises(ValueError, match="expired"):
            manager.resume_bridge(bridge.bridge_id)

    def test_resume_expired_bridge_transitions_to_expired(self, manager, permissions_docs):
        """After failed resume due to expiry, bridge should be in EXPIRED state."""
        bridge = manager.create_scoped_bridge(
            source_team="source-team",
            target_team="target-team",
            purpose="Scoped bridge for resume test",
            permissions=permissions_docs,
            created_by="admin",
            valid_days=7,
        )
        bridge.approve_source("source-lead")
        bridge.approve_target("target-lead")

        manager.suspend_bridge(bridge.bridge_id, reason="Maintenance")
        bridge.valid_until = datetime.now(UTC) - timedelta(hours=1)

        with pytest.raises(ValueError, match="expired"):
            manager.resume_bridge(bridge.bridge_id)

        assert bridge.status == BridgeStatus.EXPIRED

    def test_resume_within_valid_until_succeeds(self, manager, permissions_docs):
        """Resuming a suspended bridge still within valid_until succeeds."""
        bridge = manager.create_scoped_bridge(
            source_team="source-team",
            target_team="target-team",
            purpose="Scoped bridge for resume test",
            permissions=permissions_docs,
            created_by="admin",
            valid_days=7,
        )
        bridge.approve_source("source-lead")
        bridge.approve_target("target-lead")

        manager.suspend_bridge(bridge.bridge_id, reason="Short pause")
        assert bridge.status == BridgeStatus.SUSPENDED

        # valid_until is still in the future
        result = manager.resume_bridge(bridge.bridge_id)
        assert result.status == BridgeStatus.ACTIVE

    def test_resume_standing_bridge_no_valid_until(self, manager, permissions_docs):
        """Standing bridge with no valid_until resumes normally."""
        bridge = manager.create_standing_bridge(
            source_team="source-team",
            target_team="target-team",
            purpose="Standing bridge for resume test",
            permissions=permissions_docs,
            created_by="admin",
        )
        bridge.approve_source("source-lead")
        bridge.approve_target("target-lead")

        manager.suspend_bridge(bridge.bridge_id, reason="Planned maintenance")
        assert bridge.status == BridgeStatus.SUSPENDED
        assert bridge.valid_until is None

        result = manager.resume_bridge(bridge.bridge_id)
        assert result.status == BridgeStatus.ACTIVE

    def test_resume_expired_error_message_includes_valid_until(self, manager, permissions_docs):
        """Error message from expired resume includes the valid_until timestamp."""
        bridge = manager.create_scoped_bridge(
            source_team="source-team",
            target_team="target-team",
            purpose="Scoped bridge for error message test",
            permissions=permissions_docs,
            created_by="admin",
            valid_days=7,
        )
        bridge.approve_source("source-lead")
        bridge.approve_target("target-lead")

        manager.suspend_bridge(bridge.bridge_id, reason="Pause")
        past_time = datetime.now(UTC) - timedelta(hours=2)
        bridge.valid_until = past_time

        with pytest.raises(ValueError, match="valid_until") as exc_info:
            manager.resume_bridge(bridge.bridge_id)

        # The error message should contain the valid_until timestamp info
        assert "expired" in str(exc_info.value).lower()
