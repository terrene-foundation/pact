# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Cross-Functional Bridges — standing, scoped, and ad-hoc."""

from datetime import UTC, datetime, timedelta

import pytest

from pact_platform.build.workspace.bridge import (
    Bridge,
    BridgeManager,
    BridgePermission,
    BridgeStatus,
    BridgeType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def permissions_read_content():
    """Permissions granting read access to content paths."""
    return BridgePermission(
        read_paths=["workspaces/dm-team/content/*", "workspaces/dm-team/analytics/*"],
        message_types=["status_update", "review_request"],
        requires_attribution=True,
    )


@pytest.fixture()
def permissions_write_drafts():
    """Permissions granting write access to drafts."""
    return BridgePermission(
        read_paths=["workspaces/standards-team/specs/*"],
        write_paths=["workspaces/standards-team/drafts/*"],
        message_types=["edit_request"],
    )


@pytest.fixture()
def manager():
    """Fresh BridgeManager instance."""
    return BridgeManager()


# ---------------------------------------------------------------------------
# Test: Standing Bridge Creation
# ---------------------------------------------------------------------------


class TestStandingBridgeCreation:
    def test_create_standing_bridge_pending_until_both_approve(
        self, manager, permissions_read_content
    ):
        """A new standing bridge must be pending until both teams approve."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Ongoing standards alignment for DM content",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        assert bridge.bridge_type == BridgeType.STANDING
        assert bridge.status == BridgeStatus.PENDING
        assert bridge.approved_by_source is None
        assert bridge.approved_by_target is None
        assert bridge.is_active is False
        assert bridge.valid_until is None  # standing bridges have no expiry
        assert bridge.one_time_use is False

    def test_standing_bridge_stored_in_manager(self, manager, permissions_read_content):
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        retrieved = manager.get_bridge(bridge.bridge_id)
        assert retrieved is not None
        assert retrieved.bridge_id == bridge.bridge_id


# ---------------------------------------------------------------------------
# Test: Bridge Approval
# ---------------------------------------------------------------------------


class TestBridgeApproval:
    def test_approve_both_sides_becomes_active(self, manager, permissions_read_content):
        """Bridge becomes active only when both source and target approve."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        assert bridge.status == BridgeStatus.PENDING
        assert bridge.approved_by_source == "lead-001"
        assert bridge.is_active is False

        bridge.approve_target("standards-lead-001")
        assert bridge.status == BridgeStatus.ACTIVE
        assert bridge.approved_by_target == "standards-lead-001"
        assert bridge.is_active is True

    def test_approve_target_first_then_source(self, manager, permissions_read_content):
        """Approval order does not matter — both sides must approve."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_target("standards-lead-001")
        assert bridge.status == BridgeStatus.PENDING

        bridge.approve_source("lead-001")
        assert bridge.status == BridgeStatus.ACTIVE
        assert bridge.is_active is True


# ---------------------------------------------------------------------------
# Test: Access Control Through Bridges
# ---------------------------------------------------------------------------


class TestBridgeAccessControl:
    def test_access_allowed_path_through_active_bridge(self, manager, permissions_read_content):
        """An active bridge allows access to permitted paths."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        assert bridge.check_access("workspaces/dm-team/content/post-1.md", "read") is True
        assert bridge.check_access("workspaces/dm-team/analytics/report.csv", "read") is True

    def test_access_denied_path_not_in_permissions(self, manager, permissions_read_content):
        """Paths not listed in permissions are denied."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        assert bridge.check_access("workspaces/dm-team/secrets/key.pem", "read") is False
        assert bridge.check_access("workspaces/other-team/content/file.md", "read") is False

    def test_write_access_denied_when_only_read_permitted(self, manager, permissions_read_content):
        """Write access is denied when permissions only grant read."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        assert bridge.check_access("workspaces/dm-team/content/post-1.md", "write") is False

    def test_access_denied_on_inactive_bridge(self, manager, permissions_read_content):
        """Inactive (pending) bridges deny all access."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        # Not approved yet
        assert bridge.check_access("workspaces/dm-team/content/post-1.md", "read") is False

    def test_access_through_bridge_records_and_returns(self, manager, permissions_read_content):
        """access_through_bridge returns True/False and records access."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        allowed = manager.access_through_bridge(
            bridge.bridge_id,
            "agent-007",
            "workspaces/dm-team/content/post-1.md",
            "read",
            agent_team_id="dm-team",
        )
        assert allowed is True

        denied = manager.access_through_bridge(
            bridge.bridge_id,
            "agent-007",
            "workspaces/dm-team/secrets/key.pem",
            "read",
            agent_team_id="dm-team",
        )
        assert denied is False


# ---------------------------------------------------------------------------
# Test: Scoped Bridges
# ---------------------------------------------------------------------------


class TestScopedBridges:
    def test_create_scoped_bridge_with_time_limit(self, manager, permissions_read_content):
        """Scoped bridges have a valid_until timestamp set."""
        bridge = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="7-day read access for standards review",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=7,
        )
        assert bridge.bridge_type == BridgeType.SCOPED
        assert bridge.valid_until is not None
        # valid_until should be approximately 7 days from now
        expected_expiry = datetime.now(UTC) + timedelta(days=7)
        delta = abs((bridge.valid_until - expected_expiry).total_seconds())
        assert delta < 5  # within 5 seconds of expected

    def test_scoped_bridge_expires_after_time_limit(self, manager, permissions_read_content):
        """A scoped bridge with an expired valid_until is not active."""
        bridge = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Short-lived access",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=7,
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")
        assert bridge.is_active is True

        # Simulate time passing beyond expiry
        bridge.valid_until = datetime.now(UTC) - timedelta(hours=1)
        assert bridge.is_active is False

    def test_expired_bridge_denies_access(self, manager, permissions_read_content):
        """An expired bridge denies all access even for permitted paths."""
        bridge = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Expired bridge test",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=7,
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        # Expire it
        bridge.valid_until = datetime.now(UTC) - timedelta(hours=1)
        assert bridge.check_access("workspaces/dm-team/content/post-1.md", "read") is False

    def test_one_time_use_bridge_closes_after_first_access(self, manager, permissions_read_content):
        """A one-time-use bridge becomes inactive after the first access."""
        bridge = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Single-use document fetch",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=1,
            one_time=True,
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")
        assert bridge.is_active is True

        # First access succeeds
        bridge.record_access("agent-007", "workspaces/dm-team/content/post-1.md", "read")
        assert bridge.used is True
        assert bridge.is_active is False

    def test_expire_bridges_returns_expired_list(self, manager, permissions_read_content):
        """expire_bridges() transitions expired scoped bridges and returns them."""
        bridge = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="About to expire",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=7,
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        # Force expiry
        bridge.valid_until = datetime.now(UTC) - timedelta(hours=1)

        expired = manager.expire_bridges()
        assert len(expired) == 1
        assert expired[0].bridge_id == bridge.bridge_id
        assert expired[0].status == BridgeStatus.EXPIRED


# ---------------------------------------------------------------------------
# Test: Ad-Hoc Bridges
# ---------------------------------------------------------------------------


class TestAdHocBridges:
    def test_create_adhoc_bridge_with_request(self, manager):
        """Ad-hoc bridges carry a request payload."""
        bridge = manager.create_adhoc_bridge(
            source_team="dm-team",
            target_team="governance-team",
            purpose="Governance review of draft publication",
            request_payload={
                "document": "workspaces/dm-team/content/draft-post.md",
                "review_type": "governance_compliance",
            },
            created_by="agent-writer-001",
        )
        assert bridge.bridge_type == BridgeType.AD_HOC
        assert bridge.status == BridgeStatus.PENDING
        assert bridge.one_time_use is True
        assert bridge.request_payload["review_type"] == "governance_compliance"
        assert bridge.response_payload is None

    def test_respond_to_adhoc_auto_closes(self, manager):
        """Responding to an ad-hoc bridge auto-closes it."""
        bridge = manager.create_adhoc_bridge(
            source_team="dm-team",
            target_team="governance-team",
            purpose="Governance review",
            request_payload={"document": "draft.md"},
            created_by="agent-writer-001",
        )
        bridge.approve_source("agent-writer-001")
        bridge.approve_target("governance-lead-001")

        responded = manager.respond_to_adhoc(
            bridge.bridge_id,
            response={"approved": True, "notes": "Compliant with CARE principles"},
            responder_id="governance-lead-001",
        )
        assert responded.status == BridgeStatus.CLOSED
        assert responded.response_payload is not None
        assert responded.response_payload["approved"] is True
        assert responded.responded_at is not None
        assert responded.is_active is False

    def test_respond_to_adhoc_fails_for_non_adhoc(self, manager, permissions_read_content):
        """Cannot respond to a non-ad-hoc bridge."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standing bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        with pytest.raises(ValueError, match="ad-hoc"):
            manager.respond_to_adhoc(
                bridge.bridge_id,
                response={"result": "test"},
                responder_id="responder-001",
            )

    def test_respond_to_adhoc_fails_for_unknown_bridge(self, manager):
        """Cannot respond to a bridge that does not exist."""
        with pytest.raises(ValueError, match="not found"):
            manager.respond_to_adhoc(
                "br-nonexistent",
                response={"result": "test"},
                responder_id="responder-001",
            )


# ---------------------------------------------------------------------------
# Test: Bridge Revocation
# ---------------------------------------------------------------------------


class TestBridgeRevocation:
    def test_revoke_team_bridges_all_revoked(
        self, manager, permissions_read_content, permissions_write_drafts
    ):
        """Revoking a team revokes all bridges involving that team."""
        bridge_a = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Bridge A",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge_a.approve_source("lead-001")
        bridge_a.approve_target("standards-lead-001")

        bridge_b = manager.create_standing_bridge(
            source_team="governance-team",
            target_team="dm-team",
            purpose="Bridge B",
            permissions=permissions_write_drafts,
            created_by="gov-lead-001",
        )
        bridge_b.approve_source("gov-lead-001")
        bridge_b.approve_target("dm-lead-001")

        # Unrelated bridge
        bridge_c = manager.create_standing_bridge(
            source_team="governance-team",
            target_team="standards-team",
            purpose="Bridge C (unrelated to dm-team)",
            permissions=permissions_read_content,
            created_by="gov-lead-001",
        )
        bridge_c.approve_source("gov-lead-001")
        bridge_c.approve_target("standards-lead-001")

        revoked = manager.revoke_team_bridges("dm-team", reason="Trust violation")
        assert len(revoked) == 2
        assert all(b.status == BridgeStatus.REVOKED for b in revoked)
        # Unrelated bridge should remain active
        assert bridge_c.status == BridgeStatus.ACTIVE

    def test_revoke_single_bridge(self, manager, permissions_read_content):
        """Revoking a single bridge sets its status to REVOKED."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="To be revoked",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")
        assert bridge.is_active is True

        bridge.revoke(reason="Trust compromised")
        assert bridge.status == BridgeStatus.REVOKED
        assert bridge.is_active is False

    def test_close_bridge(self, manager, permissions_read_content):
        """Closing a bridge sets its status to CLOSED."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Temporary collaboration",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        bridge.close(reason="Project completed")
        assert bridge.status == BridgeStatus.CLOSED
        assert bridge.is_active is False


# ---------------------------------------------------------------------------
# Test: Audit Log
# ---------------------------------------------------------------------------


class TestBridgeAuditLog:
    def test_access_log_records_all_interactions(self, manager, permissions_read_content):
        """Every access through a bridge is recorded in the audit log."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Audited access",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        bridge.record_access("agent-007", "workspaces/dm-team/content/post-1.md", "read")
        bridge.record_access("agent-008", "workspaces/dm-team/analytics/report.csv", "read")

        assert len(bridge.access_log) == 2
        assert bridge.access_log[0]["agent_id"] == "agent-007"
        assert bridge.access_log[0]["path"] == "workspaces/dm-team/content/post-1.md"
        assert bridge.access_log[0]["access_type"] == "read"
        assert "timestamp" in bridge.access_log[0]
        assert bridge.access_log[1]["agent_id"] == "agent-008"


# ---------------------------------------------------------------------------
# Test: Get Bridges For Team
# ---------------------------------------------------------------------------


class TestGetBridgesForTeam:
    def test_returns_correct_set(self, manager, permissions_read_content, permissions_write_drafts):
        """get_bridges_for_team returns bridges where team is source OR target."""
        # dm-team as source
        bridge_a = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Bridge A",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge_a.approve_source("lead-001")
        bridge_a.approve_target("standards-lead-001")

        # dm-team as target
        bridge_b = manager.create_standing_bridge(
            source_team="governance-team",
            target_team="dm-team",
            purpose="Bridge B",
            permissions=permissions_write_drafts,
            created_by="gov-lead-001",
        )
        bridge_b.approve_source("gov-lead-001")
        bridge_b.approve_target("dm-lead-001")

        # Unrelated bridge
        manager.create_standing_bridge(
            source_team="governance-team",
            target_team="standards-team",
            purpose="Bridge C (unrelated)",
            permissions=permissions_read_content,
            created_by="gov-lead-001",
        )

        dm_bridges = manager.get_bridges_for_team("dm-team")
        assert len(dm_bridges) == 2
        bridge_ids = {b.bridge_id for b in dm_bridges}
        assert bridge_a.bridge_id in bridge_ids
        assert bridge_b.bridge_id in bridge_ids

    def test_returns_empty_for_unknown_team(self, manager):
        """No bridges for a team that has no bridges."""
        result = manager.get_bridges_for_team("nonexistent-team")
        assert result == []


# ---------------------------------------------------------------------------
# Test: Bridge Model Enums
# ---------------------------------------------------------------------------


class TestBridgeEnums:
    def test_bridge_type_values(self):
        assert BridgeType.STANDING == "standing"
        assert BridgeType.SCOPED == "scoped"
        assert BridgeType.AD_HOC == "ad_hoc"

    def test_bridge_status_values(self):
        assert BridgeStatus.PENDING == "pending"
        assert BridgeStatus.ACTIVE == "active"
        assert BridgeStatus.EXPIRED == "expired"
        assert BridgeStatus.CLOSED == "closed"
        assert BridgeStatus.REVOKED == "revoked"

    def test_bridge_status_negotiating(self):
        """RT5-13: NEGOTIATING state exists per CARE spec."""
        assert BridgeStatus.NEGOTIATING == "negotiating"

    def test_bridge_status_suspended(self):
        """RT5-13: SUSPENDED state exists per CARE spec."""
        assert BridgeStatus.SUSPENDED == "suspended"


# ---------------------------------------------------------------------------
# Test: RT5-13 — NEGOTIATING State
# ---------------------------------------------------------------------------


class TestBridgeNegotiating:
    """RT5-13: Bridge NEGOTIATING state machine transitions."""

    def test_negotiate_bridge_transitions_from_pending(self, manager, permissions_read_content):
        """negotiate_bridge() transitions PENDING -> NEGOTIATING."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        assert bridge.status == BridgeStatus.PENDING

        result = manager.negotiate_bridge(bridge.bridge_id)
        assert result.status == BridgeStatus.NEGOTIATING

    def test_negotiate_bridge_invalid_state_raises(self, manager, permissions_read_content):
        """negotiate_bridge() raises ValueError if bridge is not PENDING."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")
        assert bridge.status == BridgeStatus.ACTIVE

        with pytest.raises(ValueError, match="PENDING"):
            manager.negotiate_bridge(bridge.bridge_id)

    def test_negotiate_bridge_unknown_bridge_raises(self, manager):
        """negotiate_bridge() raises ValueError for non-existent bridge."""
        with pytest.raises(ValueError, match="not found"):
            manager.negotiate_bridge("br-nonexistent")

    def test_activate_from_negotiating(self, manager, permissions_read_content):
        """activate_bridge() accepts bridges in NEGOTIATING state."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        manager.negotiate_bridge(bridge.bridge_id)
        assert bridge.status == BridgeStatus.NEGOTIATING

        # Approve both sides — should transition to ACTIVE
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")
        assert bridge.status == BridgeStatus.ACTIVE
        assert bridge.is_active is True


# ---------------------------------------------------------------------------
# Test: RT5-13 — SUSPENDED State
# ---------------------------------------------------------------------------


class TestBridgeSuspended:
    """RT5-13: Bridge SUSPENDED state machine transitions."""

    def test_suspend_active_bridge(self, manager, permissions_read_content):
        """suspend_bridge() transitions ACTIVE -> SUSPENDED."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")
        assert bridge.status == BridgeStatus.ACTIVE

        result = manager.suspend_bridge(bridge.bridge_id, reason="Maintenance window")
        assert result.status == BridgeStatus.SUSPENDED
        assert result.is_active is False

    def test_suspend_non_active_raises(self, manager, permissions_read_content):
        """suspend_bridge() raises ValueError if bridge is not ACTIVE."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        assert bridge.status == BridgeStatus.PENDING

        with pytest.raises(ValueError, match="ACTIVE"):
            manager.suspend_bridge(bridge.bridge_id, reason="Attempt on pending")

    def test_suspend_unknown_bridge_raises(self, manager):
        """suspend_bridge() raises ValueError for non-existent bridge."""
        with pytest.raises(ValueError, match="not found"):
            manager.suspend_bridge("br-nonexistent", reason="Does not exist")

    def test_suspended_bridge_denies_access(self, manager, permissions_read_content):
        """A suspended bridge denies all access."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        manager.suspend_bridge(bridge.bridge_id, reason="Security review")

        assert bridge.check_access("workspaces/dm-team/content/post-1.md", "read") is False


# ---------------------------------------------------------------------------
# Test: RT5-13 — Resume from SUSPENDED
# ---------------------------------------------------------------------------


class TestBridgeResume:
    """RT5-13: Bridge resume from SUSPENDED state."""

    def test_resume_suspended_bridge(self, manager, permissions_read_content):
        """resume_bridge() transitions SUSPENDED -> ACTIVE."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        manager.suspend_bridge(bridge.bridge_id, reason="Temporary pause")
        assert bridge.status == BridgeStatus.SUSPENDED

        result = manager.resume_bridge(bridge.bridge_id)
        assert result.status == BridgeStatus.ACTIVE
        assert result.is_active is True

    def test_resume_non_suspended_raises(self, manager, permissions_read_content):
        """resume_bridge() raises ValueError if bridge is not SUSPENDED."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        with pytest.raises(ValueError, match="SUSPENDED"):
            manager.resume_bridge(bridge.bridge_id)

    def test_resume_unknown_bridge_raises(self, manager):
        """resume_bridge() raises ValueError for non-existent bridge."""
        with pytest.raises(ValueError, match="not found"):
            manager.resume_bridge("br-nonexistent")

    def test_resume_restores_access(self, manager, permissions_read_content):
        """After resuming a suspended bridge, access is restored."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Standards alignment",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        manager.suspend_bridge(bridge.bridge_id, reason="Pause")
        assert bridge.check_access("workspaces/dm-team/content/post-1.md", "read") is False

        manager.resume_bridge(bridge.bridge_id)
        assert bridge.check_access("workspaces/dm-team/content/post-1.md", "read") is True


# ---------------------------------------------------------------------------
# Test: RT5-13 — Immutability After Activation
# ---------------------------------------------------------------------------


class TestBridgeImmutabilityAfterActivation:
    """RT5-13: Once ACTIVE, bridge config (permissions/terms) cannot be modified."""

    def test_update_permissions_raises_when_active(self, manager, permissions_read_content):
        """Cannot update bridge permissions after activation."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Immutable after activation",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")
        assert bridge.status == BridgeStatus.ACTIVE

        new_perms = BridgePermission(
            read_paths=["workspaces/dm-team/secrets/*"],
            message_types=["escalation"],
        )
        with pytest.raises(ValueError, match="immutable"):
            manager.update_bridge_permissions(bridge.bridge_id, new_perms)

    def test_update_permissions_allowed_when_pending(self, manager, permissions_read_content):
        """Permissions can be updated while bridge is still PENDING."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Mutable while pending",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        assert bridge.status == BridgeStatus.PENDING

        new_perms = BridgePermission(
            read_paths=["workspaces/dm-team/public/*"],
            message_types=["info"],
        )
        result = manager.update_bridge_permissions(bridge.bridge_id, new_perms)
        assert result.permissions.read_paths == ["workspaces/dm-team/public/*"]

    def test_update_permissions_allowed_when_negotiating(self, manager, permissions_read_content):
        """Permissions can be updated while bridge is NEGOTIATING."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Terms under discussion",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        manager.negotiate_bridge(bridge.bridge_id)
        assert bridge.status == BridgeStatus.NEGOTIATING

        new_perms = BridgePermission(
            read_paths=["workspaces/dm-team/negotiated/*"],
            message_types=["proposal"],
        )
        result = manager.update_bridge_permissions(bridge.bridge_id, new_perms)
        assert result.permissions.read_paths == ["workspaces/dm-team/negotiated/*"]

    def test_update_permissions_unknown_bridge_raises(self, manager):
        """update_bridge_permissions() raises ValueError for non-existent bridge."""
        new_perms = BridgePermission(read_paths=["*"])
        with pytest.raises(ValueError, match="not found"):
            manager.update_bridge_permissions("br-nonexistent", new_perms)


# ---------------------------------------------------------------------------
# Test: RT6-05 — Terminal State Guards on close() and revoke()
# ---------------------------------------------------------------------------


class TestTerminalStateGuards:
    """RT6-05: close() and revoke() must not transition from terminal states."""

    def _make_active_bridge(self, manager, permissions_read_content):
        """Helper to create an active bridge."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Terminal state guard test",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")
        assert bridge.status == BridgeStatus.ACTIVE
        return bridge

    def test_close_from_expired_is_noop(self, manager, permissions_read_content):
        """close() on an EXPIRED bridge must be a no-op (stay EXPIRED)."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        bridge.status = BridgeStatus.EXPIRED

        bridge.close(reason="Attempting to close expired bridge")
        assert bridge.status == BridgeStatus.EXPIRED

    def test_close_from_revoked_is_noop(self, manager, permissions_read_content):
        """close() on a REVOKED bridge must be a no-op (stay REVOKED)."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        bridge.revoke(reason="Trust violation")
        assert bridge.status == BridgeStatus.REVOKED

        bridge.close(reason="Attempting to close revoked bridge")
        assert bridge.status == BridgeStatus.REVOKED

    def test_close_from_closed_is_noop(self, manager, permissions_read_content):
        """close() on an already-CLOSED bridge must be a no-op."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        bridge.close(reason="First close")
        assert bridge.status == BridgeStatus.CLOSED

        bridge.close(reason="Double close attempt")
        assert bridge.status == BridgeStatus.CLOSED

    def test_revoke_from_expired_is_noop(self, manager, permissions_read_content):
        """revoke() on an EXPIRED bridge must be a no-op (stay EXPIRED)."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        bridge.status = BridgeStatus.EXPIRED

        bridge.revoke(reason="Attempting to revoke expired bridge")
        assert bridge.status == BridgeStatus.EXPIRED

    def test_revoke_from_closed_is_noop(self, manager, permissions_read_content):
        """revoke() on a CLOSED bridge must be a no-op (stay CLOSED)."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        bridge.close(reason="Manually closed")
        assert bridge.status == BridgeStatus.CLOSED

        bridge.revoke(reason="Attempting to revoke closed bridge")
        assert bridge.status == BridgeStatus.CLOSED

    def test_revoke_from_revoked_is_noop(self, manager, permissions_read_content):
        """revoke() on an already-REVOKED bridge must be a no-op."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        bridge.revoke(reason="First revoke")
        assert bridge.status == BridgeStatus.REVOKED

        bridge.revoke(reason="Double revoke attempt")
        assert bridge.status == BridgeStatus.REVOKED

    def test_close_from_active_succeeds(self, manager, permissions_read_content):
        """close() from ACTIVE state works normally."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        bridge.close(reason="Normal close")
        assert bridge.status == BridgeStatus.CLOSED

    def test_close_from_pending_succeeds(self, manager, permissions_read_content):
        """close() from PENDING state works normally."""
        bridge = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Close pending bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        assert bridge.status == BridgeStatus.PENDING
        bridge.close(reason="Cancelled before approval")
        assert bridge.status == BridgeStatus.CLOSED

    def test_close_from_suspended_succeeds(self, manager, permissions_read_content):
        """close() from SUSPENDED state works normally."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        manager.suspend_bridge(bridge.bridge_id, reason="Pause")
        assert bridge.status == BridgeStatus.SUSPENDED

        bridge.close(reason="Closing suspended bridge")
        assert bridge.status == BridgeStatus.CLOSED

    def test_revoke_from_active_succeeds(self, manager, permissions_read_content):
        """revoke() from ACTIVE state works normally."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        bridge.revoke(reason="Trust violation")
        assert bridge.status == BridgeStatus.REVOKED

    def test_revoke_from_suspended_succeeds(self, manager, permissions_read_content):
        """revoke() from SUSPENDED state works normally."""
        bridge = self._make_active_bridge(manager, permissions_read_content)
        manager.suspend_bridge(bridge.bridge_id, reason="Pause")
        assert bridge.status == BridgeStatus.SUSPENDED

        bridge.revoke(reason="Trust revoked while suspended")
        assert bridge.status == BridgeStatus.REVOKED


# ---------------------------------------------------------------------------
# Test: RT6-05 — SUSPENDED bridge expiry
# ---------------------------------------------------------------------------


class TestSuspendedBridgeExpiry:
    """RT6-05: expire_bridges() must also expire SUSPENDED bridges past valid_until."""

    def test_expire_bridges_includes_suspended(self, manager, permissions_read_content):
        """A SUSPENDED bridge past valid_until should be expired by expire_bridges()."""
        bridge = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Scoped bridge that gets suspended then expires",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=7,
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")

        # Suspend it
        manager.suspend_bridge(bridge.bridge_id, reason="Temporary pause")
        assert bridge.status == BridgeStatus.SUSPENDED

        # Force past expiry
        bridge.valid_until = datetime.now(UTC) - timedelta(hours=1)

        expired = manager.expire_bridges()
        assert len(expired) == 1
        assert expired[0].bridge_id == bridge.bridge_id
        assert expired[0].status == BridgeStatus.EXPIRED

    def test_expire_bridges_mixed_active_and_suspended(self, manager, permissions_read_content):
        """Both ACTIVE and SUSPENDED bridges past valid_until are expired."""
        active_bridge = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Active scoped bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=7,
        )
        active_bridge.approve_source("lead-001")
        active_bridge.approve_target("standards-lead-001")

        suspended_bridge = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="governance-team",
            purpose="Suspended scoped bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=7,
        )
        suspended_bridge.approve_source("lead-001")
        suspended_bridge.approve_target("gov-lead-001")
        manager.suspend_bridge(suspended_bridge.bridge_id, reason="Paused")

        # Force both past expiry
        active_bridge.valid_until = datetime.now(UTC) - timedelta(hours=1)
        suspended_bridge.valid_until = datetime.now(UTC) - timedelta(hours=2)

        expired = manager.expire_bridges()
        assert len(expired) == 2
        expired_ids = {b.bridge_id for b in expired}
        assert active_bridge.bridge_id in expired_ids
        assert suspended_bridge.bridge_id in expired_ids
        assert all(b.status == BridgeStatus.EXPIRED for b in expired)

    def test_suspended_bridge_not_expired_if_within_valid_until(
        self, manager, permissions_read_content
    ):
        """A SUSPENDED bridge still within valid_until should NOT be expired."""
        bridge = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Suspended but not yet expired",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=7,
        )
        bridge.approve_source("lead-001")
        bridge.approve_target("standards-lead-001")
        manager.suspend_bridge(bridge.bridge_id, reason="Temporary pause")

        # valid_until is still in the future — should NOT expire
        expired = manager.expire_bridges()
        assert len(expired) == 0
        assert bridge.status == BridgeStatus.SUSPENDED


# ---------------------------------------------------------------------------
# Test: RT6-11 — revoke_team_bridges skips terminal-state bridges
# ---------------------------------------------------------------------------


class TestRevokeTeamBridgesTerminalFilter:
    """RT6-11: revoke_team_bridges must skip bridges already in terminal states."""

    def test_revoke_team_bridges_skips_already_expired(self, manager, permissions_read_content):
        """Bridges already EXPIRED should not appear in revoked list."""
        bridge_active = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Active bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge_active.approve_source("lead-001")
        bridge_active.approve_target("standards-lead-001")

        bridge_expired = manager.create_scoped_bridge(
            source_team="dm-team",
            target_team="governance-team",
            purpose="Already expired bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
            valid_days=7,
        )
        bridge_expired.approve_source("lead-001")
        bridge_expired.approve_target("gov-lead-001")
        bridge_expired.valid_until = datetime.now(UTC) - timedelta(hours=1)
        manager.expire_bridges()
        assert bridge_expired.status == BridgeStatus.EXPIRED

        revoked = manager.revoke_team_bridges("dm-team", reason="Trust violation")
        assert len(revoked) == 1
        assert revoked[0].bridge_id == bridge_active.bridge_id
        assert revoked[0].status == BridgeStatus.REVOKED
        # The expired bridge must stay EXPIRED, not become REVOKED
        assert bridge_expired.status == BridgeStatus.EXPIRED

    def test_revoke_team_bridges_skips_already_closed(self, manager, permissions_read_content):
        """Bridges already CLOSED should not appear in revoked list."""
        bridge_active = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Active bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge_active.approve_source("lead-001")
        bridge_active.approve_target("standards-lead-001")

        bridge_closed = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="governance-team",
            purpose="Already closed bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge_closed.approve_source("lead-001")
        bridge_closed.approve_target("gov-lead-001")
        bridge_closed.close(reason="Completed")
        assert bridge_closed.status == BridgeStatus.CLOSED

        revoked = manager.revoke_team_bridges("dm-team", reason="Trust violation")
        assert len(revoked) == 1
        assert revoked[0].bridge_id == bridge_active.bridge_id
        # The closed bridge must stay CLOSED
        assert bridge_closed.status == BridgeStatus.CLOSED

    def test_revoke_team_bridges_skips_already_revoked(self, manager, permissions_read_content):
        """Bridges already REVOKED should not appear in revoked list again."""
        bridge_active = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Active bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge_active.approve_source("lead-001")
        bridge_active.approve_target("standards-lead-001")

        bridge_already_revoked = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="governance-team",
            purpose="Previously revoked bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge_already_revoked.approve_source("lead-001")
        bridge_already_revoked.approve_target("gov-lead-001")
        bridge_already_revoked.revoke(reason="Earlier incident")
        assert bridge_already_revoked.status == BridgeStatus.REVOKED

        revoked = manager.revoke_team_bridges("dm-team", reason="New trust violation")
        assert len(revoked) == 1
        assert revoked[0].bridge_id == bridge_active.bridge_id

    def test_revoke_team_bridges_includes_pending_and_suspended(
        self, manager, permissions_read_content
    ):
        """PENDING and SUSPENDED bridges should be revoked (they are non-terminal)."""
        bridge_pending = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="standards-team",
            purpose="Pending bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        assert bridge_pending.status == BridgeStatus.PENDING

        bridge_suspended = manager.create_standing_bridge(
            source_team="dm-team",
            target_team="governance-team",
            purpose="Suspended bridge",
            permissions=permissions_read_content,
            created_by="lead-001",
        )
        bridge_suspended.approve_source("lead-001")
        bridge_suspended.approve_target("gov-lead-001")
        manager.suspend_bridge(bridge_suspended.bridge_id, reason="Paused")
        assert bridge_suspended.status == BridgeStatus.SUSPENDED

        revoked = manager.revoke_team_bridges("dm-team", reason="Trust violation")
        assert len(revoked) == 2
        assert all(b.status == BridgeStatus.REVOKED for b in revoked)


# ---------------------------------------------------------------------------
# RT13 — Additional security hardening tests
# ---------------------------------------------------------------------------


class TestRT13SecurityHardening:
    """RT13 red team findings: self-bridge, count limit, access log cap."""

    def test_self_bridge_rejected(self):
        """RT13-001: Cannot create a bridge from a team to itself."""
        manager = BridgeManager()
        with pytest.raises(ValueError, match="to itself"):
            manager.create_standing_bridge(
                source_team="team-alpha",
                target_team="team-alpha",
                purpose="Self-bridge",
                permissions=BridgePermission(read_paths=["*"]),
                created_by="agent-1",
            )

    def test_self_bridge_rejected_scoped(self):
        """RT13-001: Scoped self-bridge also rejected."""
        manager = BridgeManager()
        with pytest.raises(ValueError, match="to itself"):
            manager.create_scoped_bridge(
                source_team="same-team",
                target_team="same-team",
                purpose="Self-bridge",
                permissions=BridgePermission(),
                created_by="agent-1",
            )

    def test_self_bridge_rejected_adhoc(self):
        """RT13-001: Ad-hoc self-bridge also rejected."""
        manager = BridgeManager()
        with pytest.raises(ValueError, match="to itself"):
            manager.create_adhoc_bridge(
                source_team="same-team",
                target_team="same-team",
                purpose="Self-bridge",
                request_payload={"question": "why?"},
                created_by="agent-1",
            )

    def test_bridge_count_limit(self):
        """RT13-002: Cannot exceed MAX_BRIDGES_PER_TEAM non-terminal bridges."""
        from pact_platform.build.workspace.bridge import _MAX_BRIDGES_PER_TEAM

        manager = BridgeManager()
        # Create bridges up to the limit (with unique target teams)
        for i in range(_MAX_BRIDGES_PER_TEAM):
            manager.create_standing_bridge(
                source_team="team-alpha",
                target_team=f"team-target-{i}",
                purpose=f"Bridge {i}",
                permissions=BridgePermission(),
                created_by="agent-1",
            )
        # Next one should fail
        with pytest.raises(ValueError, match="maximum"):
            manager.create_standing_bridge(
                source_team="team-alpha",
                target_team="team-overflow",
                purpose="One too many",
                permissions=BridgePermission(),
                created_by="agent-1",
            )

    def test_long_identifier_rejected(self):
        """RT13-H7: Pathologically long identifiers are rejected."""
        manager = BridgeManager()
        with pytest.raises(ValueError, match="maximum length"):
            manager.create_standing_bridge(
                source_team="x" * 300,
                target_team="team-beta",
                purpose="Long ID",
                permissions=BridgePermission(),
                created_by="agent-1",
            )

    def test_access_log_cap(self):
        """RT13-008: Access log does not grow beyond _MAX_ACCESS_LOG_ENTRIES."""
        from pact_platform.build.workspace.bridge import _MAX_ACCESS_LOG_ENTRIES

        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id="team-a",
            target_team_id="team-b",
            purpose="Cap test",
            status=BridgeStatus.ACTIVE,
        )
        bridge.frozen_permissions = BridgePermission(read_paths=["*"])

        # Record more accesses than the cap
        for i in range(_MAX_ACCESS_LOG_ENTRIES + 100):
            bridge.record_access(f"agent-{i}", f"path-{i}", "read")

        assert len(bridge.access_log) == _MAX_ACCESS_LOG_ENTRIES
        # Most recent entry should be the last one recorded
        assert bridge.access_log[-1]["agent_id"] == f"agent-{_MAX_ACCESS_LOG_ENTRIES + 99}"
