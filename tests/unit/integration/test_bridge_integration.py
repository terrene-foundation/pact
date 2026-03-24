# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Integration tests for cross-functional bridges (Milestone 5, Todos 504/506).

Tests the full bridge lifecycle across all three types:
- Standing bridges (permanent, dual-approval)
- Scoped bridges (time-bounded, path-restricted)
- Ad-hoc bridges (one-time request/response)

Plus: revocation cascade, concurrent bridges, audit completeness.
"""

from __future__ import annotations

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


def _standing_permissions() -> BridgePermission:
    """Read access to standards workspace."""
    return BridgePermission(
        read_paths=["standards/*", "policies/*"],
        message_types=["reference_request", "standard_query"],
    )


def _scoped_permissions() -> BridgePermission:
    """Scoped read access to specific documents."""
    return BridgePermission(
        read_paths=["reviews/governance-doc-123.md"],
        message_types=["review_request"],
    )


def _activate_bridge(bridge: Bridge) -> Bridge:
    """Approve both sides to activate a bridge."""
    bridge.approve_source("source-lead")
    bridge.approve_target("target-lead")
    return bridge


# ===========================================================================
# 1. Standing Bridge Data Flow
# ===========================================================================


class TestStandingBridgeDataFlow:
    """Standing bridge: create, approve, access, audit, revoke."""

    def test_create_standing_bridge_pending(self):
        """Creating a standing bridge starts in PENDING status."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="DM needs to read standards",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )

        assert bridge.bridge_type == BridgeType.STANDING
        assert bridge.status == BridgeStatus.PENDING
        assert not bridge.is_active

    def test_standing_bridge_dual_approval_activates(self):
        """Both source and target approval transitions bridge to ACTIVE."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Read standards",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )

        # Only source approved -> still pending
        bridge.approve_source("dm-lead")
        assert bridge.status == BridgeStatus.PENDING
        assert bridge.approved_by_source
        assert not bridge.approved_by_target

        # Target approves -> now active
        bridge.approve_target("standards-lead")
        assert bridge.status == BridgeStatus.ACTIVE
        assert bridge.is_active

    def test_standing_bridge_read_access_works(self):
        """Active standing bridge allows read access to permitted paths."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Read standards",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )
        _activate_bridge(bridge)

        # Access through the bridge (source team agent)
        allowed = mgr.access_through_bridge(
            bridge.bridge_id,
            "dm-agent-1",
            "standards/naming.md",
            agent_team_id="team-dm",
        )
        assert allowed

        # Verify access was logged
        assert len(bridge.access_log) == 1
        assert bridge.access_log[0]["agent_id"] == "dm-agent-1"
        assert bridge.access_log[0]["path"] == "standards/naming.md"

    def test_standing_bridge_access_produces_audit_entries(self):
        """5 bridge accesses produce 5 audit log entries."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Read standards",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )
        _activate_bridge(bridge)

        # 5 accesses (source team agents)
        for i in range(5):
            mgr.access_through_bridge(
                bridge.bridge_id,
                f"dm-agent-{i}",
                f"standards/doc-{i}.md",
                agent_team_id="team-dm",
            )

        assert len(bridge.access_log) == 5
        # Verify each entry has the correct agent
        for i in range(5):
            assert bridge.access_log[i]["agent_id"] == f"dm-agent-{i}"

    def test_standing_bridge_revoke_blocks_access(self):
        """Revoking a standing bridge blocks subsequent access."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Read standards",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )
        _activate_bridge(bridge)

        # Access works before revocation (source team agent)
        assert mgr.access_through_bridge(
            bridge.bridge_id,
            "agent-1",
            "standards/a.md",
            agent_team_id="team-dm",
        )

        # Revoke
        bridge.revoke(reason="Team trust revoked")
        assert bridge.status == BridgeStatus.REVOKED

        # Access denied after revocation
        assert not mgr.access_through_bridge(
            bridge.bridge_id,
            "agent-1",
            "standards/b.md",
            agent_team_id="team-dm",
        )

    def test_standing_bridge_unauthorized_path_denied(self):
        """Access to path not in permissions is denied."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Read standards only",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )
        _activate_bridge(bridge)

        # Try to access a path not in permissions (source team agent)
        denied = mgr.access_through_bridge(
            bridge.bridge_id,
            "agent-1",
            "secrets/credentials.json",
            agent_team_id="team-dm",
        )
        assert not denied


# ===========================================================================
# 2. Scoped Bridge Lifecycle
# ===========================================================================


class TestScopedBridgeLifecycle:
    """Scoped bridge: create, use within bounds, expiry."""

    def test_scoped_bridge_within_bounds(self):
        """Scoped bridge allows access within time and path bounds."""
        mgr = BridgeManager()

        bridge = mgr.create_scoped_bridge(
            source_team="team-dm",
            target_team="team-governance",
            purpose="Review governance doc 123",
            permissions=_scoped_permissions(),
            created_by="dm-lead",
            valid_days=1,
        )
        _activate_bridge(bridge)

        # Access within scope (source team agent)
        allowed = mgr.access_through_bridge(
            bridge.bridge_id,
            "dm-agent",
            "reviews/governance-doc-123.md",
            agent_team_id="team-dm",
        )
        assert allowed

    def test_scoped_bridge_outside_scope_denied(self):
        """Scoped bridge denies access outside permitted paths."""
        mgr = BridgeManager()

        bridge = mgr.create_scoped_bridge(
            source_team="team-dm",
            target_team="team-governance",
            purpose="Review specific doc",
            permissions=_scoped_permissions(),
            created_by="dm-lead",
            valid_days=7,
        )
        _activate_bridge(bridge)

        # Different document -> denied (source team agent, but wrong path)
        denied = mgr.access_through_bridge(
            bridge.bridge_id,
            "dm-agent",
            "reviews/other-doc.md",
            agent_team_id="team-dm",
        )
        assert not denied

    def test_scoped_bridge_expiry_denies_access(self):
        """Expired scoped bridge denies access."""
        mgr = BridgeManager()

        bridge = mgr.create_scoped_bridge(
            source_team="team-dm",
            target_team="team-governance",
            purpose="Review doc",
            permissions=_scoped_permissions(),
            created_by="dm-lead",
            valid_days=1,
        )
        _activate_bridge(bridge)

        # Fast-forward: set valid_until to the past
        bridge.valid_until = datetime.now(UTC) - timedelta(hours=1)

        # Bridge is no longer active
        assert not bridge.is_active

        # Access denied (expired, regardless of team)
        denied = mgr.access_through_bridge(
            bridge.bridge_id,
            "dm-agent",
            "reviews/governance-doc-123.md",
            agent_team_id="team-dm",
        )
        assert not denied

    def test_expire_bridges_transitions_status(self):
        """expire_bridges() transitions expired bridges to EXPIRED status."""
        mgr = BridgeManager()

        bridge = mgr.create_scoped_bridge(
            source_team="team-dm",
            target_team="team-governance",
            purpose="Time-limited review",
            permissions=_scoped_permissions(),
            created_by="dm-lead",
            valid_days=1,
        )
        _activate_bridge(bridge)

        # Fast-forward time
        bridge.valid_until = datetime.now(UTC) - timedelta(hours=1)

        expired = mgr.expire_bridges()
        assert len(expired) == 1
        assert expired[0].status == BridgeStatus.EXPIRED

    def test_scoped_bridge_with_time_limit(self):
        """Scoped bridge with valid_days=7 sets correct expiry."""
        mgr = BridgeManager()

        bridge = mgr.create_scoped_bridge(
            source_team="team-dm",
            target_team="team-governance",
            purpose="Week-long review",
            permissions=_scoped_permissions(),
            created_by="dm-lead",
            valid_days=7,
        )

        # valid_until should be approximately 7 days from now
        expected = datetime.now(UTC) + timedelta(days=7)
        delta = abs((bridge.valid_until - expected).total_seconds())
        assert delta < 5  # within 5 seconds


# ===========================================================================
# 3. Ad-Hoc Bridge Lifecycle
# ===========================================================================


class TestAdHocBridgeLifecycle:
    """Ad-hoc bridge: request, approve, respond, auto-close."""

    def test_adhoc_request_response_lifecycle(self):
        """Full ad-hoc lifecycle: create -> approve -> respond -> closed."""
        mgr = BridgeManager()

        # DM posts governance content for review
        bridge = mgr.create_adhoc_bridge(
            source_team="team-dm",
            target_team="team-governance",
            purpose="Review governance blog post",
            request_payload={"content": "Draft blog post about AI governance..."},
            created_by="dm-content-writer",
        )

        assert bridge.bridge_type == BridgeType.AD_HOC
        assert bridge.status == BridgeStatus.PENDING
        assert bridge.request_payload["content"] == "Draft blog post about AI governance..."

        # Both sides approve
        _activate_bridge(bridge)
        assert bridge.status == BridgeStatus.ACTIVE

        # Governance team responds
        updated = mgr.respond_to_adhoc(
            bridge.bridge_id,
            response={"approved": True, "comments": "Looks good, minor edits suggested"},
            responder_id="governance-reviewer",
        )

        assert updated.status == BridgeStatus.CLOSED
        assert updated.response_payload["approved"] is True
        assert updated.responded_at is not None

    def test_adhoc_one_time_use(self):
        """Ad-hoc bridges are one-time-use by default."""
        mgr = BridgeManager()

        bridge = mgr.create_adhoc_bridge(
            source_team="team-dm",
            target_team="team-governance",
            purpose="Quick review",
            request_payload={"question": "Is this compliant?"},
            created_by="dm-agent",
        )

        assert bridge.one_time_use

    def test_respond_to_nonexistent_raises(self):
        """Responding to a nonexistent bridge raises ValueError."""
        mgr = BridgeManager()
        with pytest.raises(ValueError, match="not found"):
            mgr.respond_to_adhoc("nonexistent-id", {"data": "response"}, "responder-1")

    def test_respond_to_non_adhoc_raises(self):
        """Responding to a non-ad-hoc bridge raises ValueError."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Not ad-hoc",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )

        with pytest.raises(ValueError, match="not ad-hoc"):
            mgr.respond_to_adhoc(bridge.bridge_id, {"data": "response"}, "responder-1")


# ===========================================================================
# 4. Bridge Request and Approval Workflow
# ===========================================================================


class TestBridgeRequestApproval:
    """Bridge request -> PENDING -> approve/reject."""

    def test_bridge_starts_pending(self):
        """New bridge starts in PENDING state."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Collaboration",
            permissions=BridgePermission(read_paths=["docs/*"]),
            created_by="lead-a",
        )

        assert bridge.status == BridgeStatus.PENDING
        assert not bridge.approved_by_source
        assert not bridge.approved_by_target

    def test_source_approval_only_stays_pending(self):
        """Single-side approval does not activate the bridge."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Collaboration",
            permissions=BridgePermission(read_paths=["docs/*"]),
            created_by="lead-a",
        )

        bridge.approve_source("lead-a")
        assert bridge.status == BridgeStatus.PENDING

    def test_both_approvals_activate(self):
        """Both approvals transition to ACTIVE."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Collaboration",
            permissions=BridgePermission(read_paths=["docs/*"]),
            created_by="lead-a",
        )

        bridge.approve_target("lead-b")
        assert bridge.status == BridgeStatus.PENDING  # source not yet

        bridge.approve_source("lead-a")
        assert bridge.status == BridgeStatus.ACTIVE

    def test_close_bridge(self):
        """Closing a bridge sets status to CLOSED."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Temp collaboration",
            permissions=BridgePermission(read_paths=["docs/*"]),
            created_by="lead-a",
        )
        _activate_bridge(bridge)

        bridge.close(reason="Project complete")
        assert bridge.status == BridgeStatus.CLOSED
        assert not bridge.is_active


# ===========================================================================
# 5. Revocation Cascade Through Bridges
# ===========================================================================


class TestRevocationCascadeThroughBridges:
    """Agent revoked -> bridges invalidated; team lead revoked -> all team bridges."""

    def test_revoke_team_bridges(self):
        """Revoking a team invalidates all that team's bridges."""
        mgr = BridgeManager()

        # Create two bridges involving team-dm
        bridge1 = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Read standards",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )
        _activate_bridge(bridge1)

        bridge2 = mgr.create_scoped_bridge(
            source_team="team-dm",
            target_team="team-governance",
            purpose="Review doc",
            permissions=_scoped_permissions(),
            created_by="dm-lead",
            valid_days=7,
        )
        _activate_bridge(bridge2)

        # Create a bridge not involving team-dm
        bridge3 = mgr.create_standing_bridge(
            source_team="team-ops",
            target_team="team-standards",
            purpose="Ops access",
            permissions=BridgePermission(read_paths=["ops/*"]),
            created_by="ops-lead",
        )
        _activate_bridge(bridge3)

        # Revoke all team-dm bridges
        revoked = mgr.revoke_team_bridges("team-dm", "Team trust compromised")

        assert len(revoked) == 2
        assert bridge1.status == BridgeStatus.REVOKED
        assert bridge2.status == BridgeStatus.REVOKED
        assert bridge3.status == BridgeStatus.ACTIVE  # unaffected

    def test_revoked_bridge_denies_access(self):
        """Access through revoked bridge is denied."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Read standards",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )
        _activate_bridge(bridge)

        # Works before revocation (source team agent)
        assert mgr.access_through_bridge(
            bridge.bridge_id,
            "agent-1",
            "standards/doc.md",
            agent_team_id="team-dm",
        )

        # Revoke
        mgr.revoke_team_bridges("team-dm", "Incident")

        # Denied after revocation
        assert not mgr.access_through_bridge(
            bridge.bridge_id,
            "agent-1",
            "standards/doc.md",
            agent_team_id="team-dm",
        )


# ===========================================================================
# 6. Concurrent Bridges No Cross-Contamination
# ===========================================================================


class TestConcurrentBridges:
    """Multiple active bridges independently verified, no cross-contamination."""

    def test_three_concurrent_bridges_independent(self):
        """3 active bridges between different team pairs work independently."""
        mgr = BridgeManager()

        bridge_dm_std = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="DM reads standards",
            permissions=BridgePermission(read_paths=["standards/*"]),
            created_by="dm-lead",
        )
        _activate_bridge(bridge_dm_std)

        bridge_ops_gov = mgr.create_standing_bridge(
            source_team="team-ops",
            target_team="team-governance",
            purpose="Ops reads governance",
            permissions=BridgePermission(read_paths=["governance/*"]),
            created_by="ops-lead",
        )
        _activate_bridge(bridge_ops_gov)

        bridge_eng_docs = mgr.create_standing_bridge(
            source_team="team-eng",
            target_team="team-docs",
            purpose="Eng reads docs",
            permissions=BridgePermission(read_paths=["docs/*"]),
            created_by="eng-lead",
        )
        _activate_bridge(bridge_eng_docs)

        # Access through each bridge (source team agents)
        assert mgr.access_through_bridge(
            bridge_dm_std.bridge_id,
            "dm-agent",
            "standards/naming.md",
            agent_team_id="team-dm",
        )
        assert mgr.access_through_bridge(
            bridge_ops_gov.bridge_id,
            "ops-agent",
            "governance/policy.md",
            agent_team_id="team-ops",
        )
        assert mgr.access_through_bridge(
            bridge_eng_docs.bridge_id,
            "eng-agent",
            "docs/api.md",
            agent_team_id="team-eng",
        )

        # Each bridge has exactly 1 log entry (no cross-contamination)
        assert len(bridge_dm_std.access_log) == 1
        assert len(bridge_ops_gov.access_log) == 1
        assert len(bridge_eng_docs.access_log) == 1

        # Verify log entries are isolated to their respective bridges
        assert bridge_dm_std.access_log[0]["agent_id"] == "dm-agent"
        assert bridge_ops_gov.access_log[0]["agent_id"] == "ops-agent"
        assert bridge_eng_docs.access_log[0]["agent_id"] == "eng-agent"

    def test_revoke_one_bridge_does_not_affect_others(self):
        """Revoking one bridge does not affect unrelated bridges."""
        mgr = BridgeManager()

        bridge1 = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="A-B bridge",
            permissions=BridgePermission(read_paths=["docs/*"]),
            created_by="lead-a",
        )
        _activate_bridge(bridge1)

        bridge2 = mgr.create_standing_bridge(
            source_team="team-c",
            target_team="team-d",
            purpose="C-D bridge",
            permissions=BridgePermission(read_paths=["reports/*"]),
            created_by="lead-c",
        )
        _activate_bridge(bridge2)

        # Revoke bridge1
        bridge1.revoke("Test revocation")

        # bridge2 is unaffected
        assert bridge2.is_active
        assert bridge2.status == BridgeStatus.ACTIVE
        assert mgr.access_through_bridge(
            bridge2.bridge_id,
            "agent-d",
            "reports/monthly.md",
            agent_team_id="team-c",
        )

    def test_messages_isolated_per_bridge(self):
        """Access logs on one bridge do not appear on another."""
        mgr = BridgeManager()

        bridge_a = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-shared",
            purpose="Team A access",
            permissions=BridgePermission(read_paths=["shared/*"]),
            created_by="lead-a",
        )
        _activate_bridge(bridge_a)

        bridge_b = mgr.create_standing_bridge(
            source_team="team-b",
            target_team="team-shared",
            purpose="Team B access",
            permissions=BridgePermission(read_paths=["shared/*"]),
            created_by="lead-b",
        )
        _activate_bridge(bridge_b)

        # Multiple accesses through bridge A (source team agents)
        for i in range(3):
            mgr.access_through_bridge(
                bridge_a.bridge_id,
                f"agent-a-{i}",
                f"shared/doc-{i}.md",
                agent_team_id="team-a",
            )

        # One access through bridge B (source team agent)
        mgr.access_through_bridge(
            bridge_b.bridge_id,
            "agent-b-0",
            "shared/other.md",
            agent_team_id="team-b",
        )

        # Verify isolation
        assert len(bridge_a.access_log) == 3
        assert len(bridge_b.access_log) == 1
        assert all(log["agent_id"].startswith("agent-a") for log in bridge_a.access_log)
        assert bridge_b.access_log[0]["agent_id"] == "agent-b-0"


# ===========================================================================
# 7. Bridge Audit Completeness
# ===========================================================================


class TestBridgeAuditCompleteness:
    """Every bridge interaction produces audit log entries."""

    def test_every_access_logged(self):
        """Every access through a bridge creates an audit log entry."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Read standards",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )
        _activate_bridge(bridge)

        # 10 accesses (source team agents)
        for i in range(10):
            mgr.access_through_bridge(
                bridge.bridge_id,
                f"dm-agent-{i % 3}",
                f"standards/doc-{i}.md",
                agent_team_id="team-dm",
            )

        # All 10 logged
        assert len(bridge.access_log) == 10

        # Each entry has required fields
        for entry in bridge.access_log:
            assert "agent_id" in entry
            assert "path" in entry
            assert "access_type" in entry
            assert "timestamp" in entry

    def test_denied_access_not_logged(self):
        """Denied access (wrong path) does not create a log entry."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Read standards only",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )
        _activate_bridge(bridge)

        # Attempt access to unauthorized path (source team agent, wrong path)
        allowed = mgr.access_through_bridge(
            bridge.bridge_id,
            "agent-1",
            "secrets/keys.txt",
            agent_team_id="team-dm",
        )
        assert not allowed

        # No log entry created for denied access
        assert len(bridge.access_log) == 0

    def test_one_time_bridge_audit_trail(self):
        """One-time-use bridge creates audit entries and becomes inactive after use."""
        mgr = BridgeManager()

        bridge = mgr.create_scoped_bridge(
            source_team="team-dm",
            target_team="team-governance",
            purpose="One-time doc review",
            permissions=BridgePermission(read_paths=["reviews/*"]),
            created_by="dm-lead",
            valid_days=1,
            one_time=True,
        )
        _activate_bridge(bridge)

        # First access works (source team agent)
        allowed = mgr.access_through_bridge(
            bridge.bridge_id,
            "dm-agent",
            "reviews/doc.md",
            agent_team_id="team-dm",
        )
        assert allowed
        assert bridge.used
        assert len(bridge.access_log) == 1

        # Second access denied (one-time-use consumed)
        denied = mgr.access_through_bridge(
            bridge.bridge_id,
            "dm-agent",
            "reviews/doc.md",
            agent_team_id="team-dm",
        )
        assert not denied
        assert len(bridge.access_log) == 1  # no new entry

    def test_get_bridges_for_team(self):
        """get_bridges_for_team returns all bridges involving a team."""
        mgr = BridgeManager()

        mgr.create_standing_bridge(
            source_team="team-dm",
            target_team="team-standards",
            purpose="Bridge 1",
            permissions=_standing_permissions(),
            created_by="dm-lead",
        )
        mgr.create_scoped_bridge(
            source_team="team-ops",
            target_team="team-dm",
            purpose="Bridge 2",
            permissions=_scoped_permissions(),
            created_by="ops-lead",
            valid_days=7,
        )
        mgr.create_standing_bridge(
            source_team="team-ops",
            target_team="team-standards",
            purpose="Bridge 3",
            permissions=_standing_permissions(),
            created_by="ops-lead",
        )

        dm_bridges = mgr.get_bridges_for_team("team-dm")
        assert len(dm_bridges) == 2  # bridge 1 (source) and bridge 2 (target)

    def test_get_bridge_by_id(self):
        """Get bridge by ID returns the correct bridge."""
        mgr = BridgeManager()

        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Test",
            permissions=BridgePermission(read_paths=["*"]),
            created_by="lead-a",
        )

        retrieved = mgr.get_bridge(bridge.bridge_id)
        assert retrieved is not None
        assert retrieved.bridge_id == bridge.bridge_id

    def test_get_nonexistent_bridge_returns_none(self):
        """Getting a nonexistent bridge returns None."""
        mgr = BridgeManager()
        assert mgr.get_bridge("nonexistent") is None

    def test_access_nonexistent_bridge_returns_false(self):
        """Accessing through a nonexistent bridge ID returns False."""
        mgr = BridgeManager()
        result = mgr.access_through_bridge("nonexistent", "agent-1", "some/path")
        assert not result
