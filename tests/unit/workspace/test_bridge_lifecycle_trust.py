# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Bridge Lifecycle Trust Integration (M34 Tasks 3401-3404).

Covers:
- Approval flow triggers trust_callback on ACTIVE transition
- Suspension callback invoked
- Closure callback invoked
- modify_bridge suspends old, creates new with replacement link
- Modified bridge requires re-approval
- Old bridge preserved with replaced_by link
- get_bridges_needing_review returns overdue bridges
- mark_bridge_reviewed schedules next review
- get_adhoc_bridge_frequency suggests standing bridge when threshold exceeded
- Review policy defaults based on bridge type
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from pact_platform.build.workspace.bridge import (
    Bridge,
    BridgeManager,
    BridgePermission,
    BridgeReviewPolicy,
    BridgeStatus,
    BridgeType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def permissions():
    """Standard read permissions for tests."""
    return BridgePermission(
        read_paths=["workspaces/team-b/docs/*"],
        message_types=["status_update"],
    )


@pytest.fixture()
def trust_callback():
    """Mock trust callback for tracking invocations."""
    return MagicMock(name="trust_callback")


@pytest.fixture()
def closure_callback():
    """Mock closure callback for tracking invocations."""
    return MagicMock(name="closure_callback")


@pytest.fixture()
def suspension_callback():
    """Mock suspension callback for tracking invocations."""
    return MagicMock(name="suspension_callback")


@pytest.fixture()
def manager(trust_callback, closure_callback, suspension_callback):
    """BridgeManager with all callbacks wired."""
    return BridgeManager(
        trust_callback=trust_callback,
        closure_callback=closure_callback,
        suspension_callback=suspension_callback,
    )


@pytest.fixture()
def active_bridge(manager, permissions):
    """Create and fully approve a standing bridge, returning it in ACTIVE status."""
    bridge = manager.create_standing_bridge(
        source_team="team-a",
        target_team="team-b",
        purpose="Knowledge sharing",
        permissions=permissions,
        created_by="agent-setup",
    )
    manager.approve_bridge_source(bridge.bridge_id, "approver-a")
    manager.approve_bridge_target(bridge.bridge_id, "approver-b")
    assert bridge.status == BridgeStatus.ACTIVE
    return bridge


# ---------------------------------------------------------------------------
# Test: Approval Flow Triggers trust_callback (Task 3401)
# ---------------------------------------------------------------------------


class TestApprovalFlowTrustCallback:
    def test_both_sides_approve_triggers_trust_callback(self, manager, permissions, trust_callback):
        bridge = manager.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Data sharing",
            permissions=permissions,
            created_by="creator",
        )
        manager.approve_bridge_source(bridge.bridge_id, "source-lead")
        # After only source approval, callback should NOT have been called.
        trust_callback.assert_not_called()

        manager.approve_bridge_target(bridge.bridge_id, "target-lead")
        # Now both sides approved — callback must fire.
        trust_callback.assert_called_once_with(bridge)
        assert bridge.status == BridgeStatus.ACTIVE

    def test_single_side_approval_no_trust_callback(self, manager, permissions, trust_callback):
        bridge = manager.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Single side test",
            permissions=permissions,
            created_by="creator",
        )
        manager.approve_bridge_source(bridge.bridge_id, "source-lead")
        trust_callback.assert_not_called()
        assert bridge.status != BridgeStatus.ACTIVE

    def test_target_approves_first_then_source_triggers_callback(
        self, manager, permissions, trust_callback
    ):
        bridge = manager.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Reverse approval order",
            permissions=permissions,
            created_by="creator",
        )
        manager.approve_bridge_target(bridge.bridge_id, "target-lead")
        trust_callback.assert_not_called()

        manager.approve_bridge_source(bridge.bridge_id, "source-lead")
        trust_callback.assert_called_once_with(bridge)
        assert bridge.status == BridgeStatus.ACTIVE

    def test_no_trust_callback_when_none(self, permissions):
        """Manager without callbacks still works — no error on activation."""
        mgr = BridgeManager()  # no callbacks
        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="No callback",
            permissions=permissions,
            created_by="creator",
        )
        mgr.approve_bridge_source(bridge.bridge_id, "a")
        mgr.approve_bridge_target(bridge.bridge_id, "b")
        assert bridge.status == BridgeStatus.ACTIVE


# ---------------------------------------------------------------------------
# Test: Suspension Callback (Task 3401)
# ---------------------------------------------------------------------------


class TestSuspensionCallback:
    def test_suspend_bridge_invokes_suspension_callback(
        self, manager, active_bridge, suspension_callback
    ):
        # Reset the mock (trust_callback was already called during activation).
        suspension_callback.reset_mock()

        manager.suspend_bridge(active_bridge.bridge_id, reason="Audit review")
        suspension_callback.assert_called_once_with(active_bridge)
        assert active_bridge.status == BridgeStatus.SUSPENDED

    def test_suspension_callback_not_invoked_when_none(self, permissions):
        mgr = BridgeManager()
        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="No callback",
            permissions=permissions,
            created_by="creator",
        )
        bridge.approve_source("a")
        bridge.approve_target("b")
        # Should not raise even without callback.
        mgr.suspend_bridge(bridge.bridge_id, reason="Test")
        assert bridge.status == BridgeStatus.SUSPENDED


# ---------------------------------------------------------------------------
# Test: Closure Callback (Task 3401)
# ---------------------------------------------------------------------------


class TestClosureCallback:
    def test_close_bridge_invokes_closure_callback(self, manager, active_bridge, closure_callback):
        manager.close_bridge(active_bridge.bridge_id, reason="Project complete")
        closure_callback.assert_called_once_with(active_bridge)
        assert active_bridge.status == BridgeStatus.CLOSED

    def test_close_bridge_rejects_terminal_state(self, manager, active_bridge):
        manager.close_bridge(active_bridge.bridge_id, reason="First close")
        with pytest.raises(ValueError, match="terminal state"):
            manager.close_bridge(active_bridge.bridge_id, reason="Second close")

    def test_close_bridge_rejects_unknown_id(self, manager):
        with pytest.raises(ValueError, match="not found"):
            manager.close_bridge("nonexistent-id", reason="Should fail")


# ---------------------------------------------------------------------------
# Test: Bridge Modification via Replacement (Task 3402)
# ---------------------------------------------------------------------------


class TestBridgeModification:
    def test_modify_bridge_suspends_old_creates_new(self, manager, active_bridge, permissions):
        new_perms = BridgePermission(
            read_paths=["workspaces/team-b/reports/*"],
            message_types=["report_update"],
        )
        new_bridge = manager.modify_bridge(
            active_bridge.bridge_id,
            new_permissions=new_perms,
            modifier_id="modifier-agent",
        )

        # Old bridge should be SUSPENDED.
        assert active_bridge.status == BridgeStatus.SUSPENDED
        # New bridge should be PENDING (requires re-approval).
        assert new_bridge.status == BridgeStatus.PENDING
        # Replacement links should be set.
        assert new_bridge.replacement_for == active_bridge.bridge_id
        assert active_bridge.replaced_by == new_bridge.bridge_id

    def test_modified_bridge_requires_re_approval(self, manager, active_bridge, trust_callback):
        new_perms = BridgePermission(read_paths=["workspaces/team-b/new-data/*"])
        trust_callback.reset_mock()

        new_bridge = manager.modify_bridge(
            active_bridge.bridge_id,
            new_permissions=new_perms,
            modifier_id="modifier",
        )

        # New bridge is NOT active — needs fresh approval.
        assert new_bridge.status == BridgeStatus.PENDING
        assert not new_bridge.approved_by_source
        assert not new_bridge.approved_by_target

        # Approve new bridge.
        manager.approve_bridge_source(new_bridge.bridge_id, "source-lead")
        manager.approve_bridge_target(new_bridge.bridge_id, "target-lead")
        assert new_bridge.status == BridgeStatus.ACTIVE
        # Trust callback should fire for the new bridge.
        trust_callback.assert_called_with(new_bridge)

    def test_old_bridge_preserved_after_modification(self, manager, active_bridge):
        new_perms = BridgePermission(read_paths=["workspaces/team-b/archive/*"])
        new_bridge = manager.modify_bridge(
            active_bridge.bridge_id,
            new_permissions=new_perms,
        )

        # Old bridge remains in the manager.
        old = manager.get_bridge(active_bridge.bridge_id)
        assert old is not None
        assert old.status == BridgeStatus.SUSPENDED
        assert old.replaced_by == new_bridge.bridge_id

    def test_modify_preserves_same_type_and_teams(self, manager, active_bridge):
        new_perms = BridgePermission(read_paths=["workspaces/team-b/shared/*"])
        new_bridge = manager.modify_bridge(
            active_bridge.bridge_id,
            new_permissions=new_perms,
        )
        assert new_bridge.bridge_type == active_bridge.bridge_type
        assert new_bridge.source_team_id == active_bridge.source_team_id
        assert new_bridge.target_team_id == active_bridge.target_team_id

    def test_modify_with_new_purpose(self, manager, active_bridge):
        new_perms = BridgePermission(read_paths=["workspaces/team-b/v2/*"])
        new_bridge = manager.modify_bridge(
            active_bridge.bridge_id,
            new_permissions=new_perms,
            new_purpose="Updated knowledge sharing v2",
        )
        assert new_bridge.purpose == "Updated knowledge sharing v2"

    def test_modify_non_active_bridge_raises(self, manager, permissions):
        bridge = manager.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Not yet approved",
            permissions=permissions,
            created_by="creator",
        )
        new_perms = BridgePermission(read_paths=["workspaces/team-b/new/*"])
        with pytest.raises(ValueError, match="not ACTIVE"):
            manager.modify_bridge(bridge.bridge_id, new_permissions=new_perms)

    def test_modify_scoped_bridge(self, manager, permissions, trust_callback):
        bridge = manager.create_scoped_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Scoped review",
            permissions=permissions,
            created_by="creator",
            valid_days=14,
        )
        manager.approve_bridge_source(bridge.bridge_id, "a")
        manager.approve_bridge_target(bridge.bridge_id, "b")
        assert bridge.status == BridgeStatus.ACTIVE

        new_perms = BridgePermission(read_paths=["workspaces/team-b/extended/*"])
        new_bridge = manager.modify_bridge(
            bridge.bridge_id,
            new_permissions=new_perms,
            modifier_id="modifier",
        )
        assert new_bridge.bridge_type == BridgeType.SCOPED
        assert new_bridge.replacement_for == bridge.bridge_id
        assert bridge.replaced_by == new_bridge.bridge_id


# ---------------------------------------------------------------------------
# Test: Bridge Review Cadence (Task 3403)
# ---------------------------------------------------------------------------


class TestBridgeReviewCadence:
    def test_standing_bridge_next_review_date_from_creation(self, permissions):
        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id="team-a",
            target_team_id="team-b",
            purpose="Quarterly review",
            permissions=permissions,
        )
        review_date = bridge.next_review_date
        assert review_date is not None
        # Should be ~90 days after creation.
        expected = bridge.created_at + timedelta(days=90)
        assert abs((review_date - expected).total_seconds()) < 1

    def test_adhoc_bridge_has_no_review_date(self, permissions):
        bridge = Bridge(
            bridge_type=BridgeType.AD_HOC,
            source_team_id="team-a",
            target_team_id="team-b",
            purpose="One-time request",
            permissions=permissions,
        )
        assert bridge.next_review_date is None

    def test_mark_reviewed_resets_next_review(self, permissions):
        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id="team-a",
            target_team_id="team-b",
            purpose="Review tracking",
            permissions=permissions,
        )
        entry = bridge.mark_reviewed("reviewer-1", notes="All good")

        assert entry["reviewer_id"] == "reviewer-1"
        assert entry["notes"] == "All good"
        assert "timestamp" in entry

        # next_review_date should now be ~90 days after the review timestamp.
        review_ts = datetime.fromisoformat(entry["timestamp"])
        expected = review_ts + timedelta(days=90)
        actual = bridge.next_review_date
        assert actual is not None
        assert abs((actual - expected).total_seconds()) < 1

    def test_mark_reviewed_twice_uses_latest(self, permissions):
        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id="team-a",
            target_team_id="team-b",
            purpose="Multiple reviews",
            permissions=permissions,
        )
        bridge.mark_reviewed("reviewer-1", notes="First review")
        entry2 = bridge.mark_reviewed("reviewer-2", notes="Second review")

        assert len(bridge.reviews) == 2
        # next_review_date should be relative to the second review.
        review_ts = datetime.fromisoformat(entry2["timestamp"])
        expected = review_ts + timedelta(days=90)
        actual = bridge.next_review_date
        assert actual is not None
        assert abs((actual - expected).total_seconds()) < 1


class TestBridgesNeedingReview:
    def test_overdue_bridge_returned(self, manager, permissions, trust_callback):
        bridge = manager.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Will be overdue",
            permissions=permissions,
            created_by="creator",
        )
        manager.approve_bridge_source(bridge.bridge_id, "a")
        manager.approve_bridge_target(bridge.bridge_id, "b")

        # Backdate created_at to make it overdue.
        bridge.created_at = datetime.now(UTC) - timedelta(days=100)

        needing_review = manager.get_bridges_needing_review()
        assert bridge in needing_review

    def test_not_overdue_bridge_excluded(self, manager, permissions, trust_callback):
        bridge = manager.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Recently created",
            permissions=permissions,
            created_by="creator",
        )
        manager.approve_bridge_source(bridge.bridge_id, "a")
        manager.approve_bridge_target(bridge.bridge_id, "b")
        # created_at is "now" — not due for review yet.

        needing_review = manager.get_bridges_needing_review()
        assert bridge not in needing_review

    def test_adhoc_bridges_excluded_from_review(self, manager, trust_callback):
        bridge = manager.create_adhoc_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Quick question",
            request_payload={"question": "status?"},
            created_by="creator",
        )
        manager.approve_bridge_source(bridge.bridge_id, "a")
        manager.approve_bridge_target(bridge.bridge_id, "b")
        bridge.created_at = datetime.now(UTC) - timedelta(days=200)

        needing_review = manager.get_bridges_needing_review()
        assert bridge not in needing_review

    def test_non_active_bridges_excluded(self, manager, permissions):
        bridge = manager.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Pending bridge",
            permissions=permissions,
            created_by="creator",
        )
        bridge.created_at = datetime.now(UTC) - timedelta(days=200)
        # Bridge is still PENDING — should not appear in review list.
        needing_review = manager.get_bridges_needing_review()
        assert bridge not in needing_review


class TestMarkBridgeReviewed:
    def test_mark_bridge_reviewed_via_manager(self, manager, active_bridge):
        result = manager.mark_bridge_reviewed(
            active_bridge.bridge_id,
            reviewer_id="reviewer-1",
            notes="Quarterly check passed",
        )
        assert result.reviews[-1]["reviewer_id"] == "reviewer-1"
        assert result.review_policy is not None
        assert result.review_policy.last_reviewed_at is not None

    def test_mark_nonexistent_bridge_raises(self, manager):
        with pytest.raises(ValueError, match="not found"):
            manager.mark_bridge_reviewed("nonexistent", "reviewer")


# ---------------------------------------------------------------------------
# Test: Ad-Hoc Bridge Frequency (Task 3403)
# ---------------------------------------------------------------------------


class TestAdhocBridgeFrequency:
    def test_frequency_below_threshold(self, manager):
        for i in range(3):
            manager.create_adhoc_bridge(
                source_team="team-a",
                target_team="team-b",
                purpose=f"Request {i}",
                request_payload={"q": str(i)},
                created_by="creator",
            )

        result = manager.get_adhoc_bridge_frequency("team-a", "team-b")
        assert result["count"] == 3
        assert result["suggest_standing"] is False

    def test_frequency_above_threshold_suggests_standing(self, manager):
        for i in range(7):
            manager.create_adhoc_bridge(
                source_team="team-a",
                target_team="team-b",
                purpose=f"Request {i}",
                request_payload={"q": str(i)},
                created_by="creator",
            )

        result = manager.get_adhoc_bridge_frequency("team-a", "team-b")
        assert result["count"] == 7
        assert result["suggest_standing"] is True

    def test_frequency_exact_threshold_no_suggestion(self, manager):
        for i in range(5):
            manager.create_adhoc_bridge(
                source_team="team-a",
                target_team="team-b",
                purpose=f"Request {i}",
                request_payload={"q": str(i)},
                created_by="creator",
            )

        result = manager.get_adhoc_bridge_frequency("team-a", "team-b")
        assert result["count"] == 5
        # Threshold is 5, suggest_standing requires count > threshold.
        assert result["suggest_standing"] is False

    def test_frequency_custom_threshold(self, manager):
        for i in range(3):
            manager.create_adhoc_bridge(
                source_team="team-a",
                target_team="team-b",
                purpose=f"Request {i}",
                request_payload={"q": str(i)},
                created_by="creator",
            )

        result = manager.get_adhoc_bridge_frequency("team-a", "team-b", threshold=2)
        assert result["count"] == 3
        assert result["suggest_standing"] is True

    def test_frequency_matches_reverse_direction(self, manager):
        """Ad-hoc bridges from B->A should also count when querying A->B."""
        manager.create_adhoc_bridge(
            source_team="team-b",
            target_team="team-a",
            purpose="Reverse direction",
            request_payload={"q": "reverse"},
            created_by="creator",
        )

        result = manager.get_adhoc_bridge_frequency("team-a", "team-b")
        assert result["count"] == 1

    def test_frequency_excludes_other_teams(self, manager):
        manager.create_adhoc_bridge(
            source_team="team-a",
            target_team="team-c",
            purpose="Different team pair",
            request_payload={"q": "other"},
            created_by="creator",
        )

        result = manager.get_adhoc_bridge_frequency("team-a", "team-b")
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# Test: Review Policy Defaults (Task 3403)
# ---------------------------------------------------------------------------


class TestReviewPolicyDefaults:
    def test_standing_bridge_default_interval(self):
        policy = BridgeReviewPolicy(review_interval_days=90)
        assert policy.review_interval_days == 90

    def test_review_policy_tracks_notes(self):
        policy = BridgeReviewPolicy(review_interval_days=90)
        policy.review_notes.append("Looks good")
        assert len(policy.review_notes) == 1

    def test_scoped_bridge_uses_valid_until_as_milestone_proxy(self):
        bridge = Bridge(
            bridge_type=BridgeType.SCOPED,
            source_team_id="team-a",
            target_team_id="team-b",
            purpose="Milestone-based review",
            permissions=BridgePermission(read_paths=["workspaces/team-b/*"]),
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        # Scoped bridge should still return a review date (not None).
        assert bridge.next_review_date is not None


# ---------------------------------------------------------------------------
# Test: Backwards Compatibility
# ---------------------------------------------------------------------------


class TestBackwardsCompatibility:
    def test_manager_without_callbacks_works(self):
        """BridgeManager() with no arguments should work exactly as before."""
        mgr = BridgeManager()
        perms = BridgePermission(read_paths=["workspaces/team-b/*"])
        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="No callbacks",
            permissions=perms,
            created_by="creator",
        )
        bridge.approve_source("a")
        bridge.approve_target("b")
        assert bridge.status == BridgeStatus.ACTIVE

    def test_bridge_model_new_fields_default_none(self):
        """New fields should default to None/empty and not break existing bridges."""
        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id="team-a",
            target_team_id="team-b",
            purpose="Legacy bridge",
            permissions=BridgePermission(),
        )
        assert bridge.replaced_by is None
        assert bridge.replacement_for is None
        assert bridge.review_policy is None
        assert bridge.reviews == []
