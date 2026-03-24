# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the human approval queue (Task 403).

Covers: submit, approve, reject, batch approve, urgency sorting,
capacity metrics, and expiration of stale pending actions.
"""

from datetime import UTC, datetime, timedelta

import pytest

from pact_platform.use.execution.approval import ApprovalQueue, PendingAction, UrgencyLevel


class TestPendingAction:
    """Tests for the PendingAction model."""

    def test_defaults(self):
        pa = PendingAction(agent_id="agent-1", action="deploy", reason="high-risk")
        assert pa.action_id.startswith("pa-")
        assert pa.agent_id == "agent-1"
        assert pa.action == "deploy"
        assert pa.reason == "high-risk"
        assert pa.status == "pending"
        assert pa.urgency == UrgencyLevel.STANDARD
        assert pa.team_id == ""
        assert pa.resource == ""
        assert pa.constraint_details == {}
        assert pa.decided_by is None
        assert pa.decided_at is None
        assert pa.decision_reason == ""

    def test_submitted_at_is_set(self):
        before = datetime.now(UTC)
        pa = PendingAction(agent_id="a", action="x", reason="r")
        after = datetime.now(UTC)
        assert before <= pa.submitted_at <= after

    def test_custom_fields(self):
        pa = PendingAction(
            agent_id="agent-1",
            action="delete_data",
            reason="destructive",
            team_id="team-ops",
            resource="/data/records",
            urgency=UrgencyLevel.IMMEDIATE,
            constraint_details={"dimension": "data_access"},
        )
        assert pa.team_id == "team-ops"
        assert pa.resource == "/data/records"
        assert pa.urgency == UrgencyLevel.IMMEDIATE
        assert pa.constraint_details["dimension"] == "data_access"


class TestUrgencyLevel:
    """Tests for urgency level enum values."""

    def test_all_levels_exist(self):
        assert UrgencyLevel.IMMEDIATE == "immediate"
        assert UrgencyLevel.STANDARD == "standard"
        assert UrgencyLevel.BATCH == "batch"


class TestApprovalQueueSubmit:
    """Tests for submitting actions to the approval queue."""

    def test_submit_returns_pending_action(self):
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="constraint-held")
        assert isinstance(pa, PendingAction)
        assert pa.status == "pending"
        assert pa.agent_id == "agent-1"
        assert pa.action == "deploy"
        assert pa.reason == "constraint-held"

    def test_submit_increments_queue_depth(self):
        queue = ApprovalQueue()
        assert queue.queue_depth == 0
        queue.submit(agent_id="a", action="x", reason="r")
        assert queue.queue_depth == 1
        queue.submit(agent_id="b", action="y", reason="r")
        assert queue.queue_depth == 2

    def test_submit_with_all_optional_fields(self):
        queue = ApprovalQueue()
        pa = queue.submit(
            agent_id="agent-1",
            action="send_email",
            reason="external-comm",
            team_id="team-ops",
            resource="email://external",
            urgency=UrgencyLevel.IMMEDIATE,
            constraint_details={"dimension": "communication"},
        )
        assert pa.team_id == "team-ops"
        assert pa.resource == "email://external"
        assert pa.urgency == UrgencyLevel.IMMEDIATE
        assert pa.constraint_details["dimension"] == "communication"

    def test_submit_appears_in_pending(self):
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="a", action="x", reason="r")
        assert pa in queue.pending


class TestApprovalQueueApprove:
    """Tests for approving pending actions."""

    def test_approve_changes_status(self):
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="a", action="x", reason="r")
        result = queue.approve(pa.action_id, approver_id="human-1", reason="looks good")
        assert result.status == "approved"
        assert result.decided_by == "human-1"
        assert result.decided_at is not None
        assert result.decision_reason == "looks good"

    def test_approve_removes_from_pending(self):
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="a", action="x", reason="r")
        queue.approve(pa.action_id, approver_id="human-1")
        assert queue.queue_depth == 0

    def test_approve_nonexistent_raises(self):
        queue = ApprovalQueue()
        with pytest.raises(ValueError, match="not found"):
            queue.approve("pa-nonexistent", approver_id="human-1")

    def test_approve_already_resolved_raises(self):
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="a", action="x", reason="r")
        queue.approve(pa.action_id, approver_id="human-1")
        with pytest.raises(ValueError, match="not pending"):
            queue.approve(pa.action_id, approver_id="human-2")


class TestApprovalQueueReject:
    """Tests for rejecting pending actions."""

    def test_reject_changes_status(self):
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="a", action="x", reason="r")
        result = queue.reject(pa.action_id, approver_id="human-1", reason="too risky")
        assert result.status == "rejected"
        assert result.decided_by == "human-1"
        assert result.decision_reason == "too risky"

    def test_reject_removes_from_pending(self):
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="a", action="x", reason="r")
        queue.reject(pa.action_id, approver_id="human-1")
        assert queue.queue_depth == 0

    def test_reject_nonexistent_raises(self):
        queue = ApprovalQueue()
        with pytest.raises(ValueError, match="not found"):
            queue.reject("pa-nonexistent", approver_id="human-1")


class TestApprovalQueueBatchApprove:
    """Tests for batch-approving multiple actions."""

    def test_batch_approve_all(self):
        queue = ApprovalQueue()
        pa1 = queue.submit(agent_id="a", action="x", reason="r", urgency=UrgencyLevel.BATCH)
        pa2 = queue.submit(agent_id="b", action="y", reason="r", urgency=UrgencyLevel.BATCH)
        results = queue.batch_approve([pa1.action_id, pa2.action_id], approver_id="human-1")
        assert len(results) == 2
        assert all(r.status == "approved" for r in results)
        assert queue.queue_depth == 0

    def test_batch_approve_partial(self):
        """Batch approve should approve valid IDs and raise for invalid."""
        queue = ApprovalQueue()
        pa1 = queue.submit(agent_id="a", action="x", reason="r")
        with pytest.raises(ValueError, match="not found"):
            queue.batch_approve([pa1.action_id, "pa-nonexistent"], approver_id="human-1")

    def test_batch_approve_empty_list(self):
        queue = ApprovalQueue()
        results = queue.batch_approve([], approver_id="human-1")
        assert results == []


class TestApprovalQueuePendingSorting:
    """Tests for pending property ordering: urgency (immediate first), then time."""

    def test_pending_sorted_by_urgency(self):
        queue = ApprovalQueue()
        queue.submit(agent_id="a", action="batch-task", reason="r", urgency=UrgencyLevel.BATCH)
        queue.submit(
            agent_id="b", action="immediate-task", reason="r", urgency=UrgencyLevel.IMMEDIATE
        )
        queue.submit(
            agent_id="c", action="standard-task", reason="r", urgency=UrgencyLevel.STANDARD
        )
        pending = queue.pending
        assert pending[0].urgency == UrgencyLevel.IMMEDIATE
        assert pending[1].urgency == UrgencyLevel.STANDARD
        assert pending[2].urgency == UrgencyLevel.BATCH


class TestApprovalQueueCapacityMetrics:
    """Tests for capacity metrics tracking."""

    def test_capacity_metrics_empty_queue(self):
        queue = ApprovalQueue()
        metrics = queue.get_capacity_metrics()
        assert "pending_count" in metrics
        assert "resolved_count" in metrics
        assert metrics["pending_count"] == 0
        assert metrics["resolved_count"] == 0

    def test_capacity_metrics_with_resolved(self):
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="a", action="x", reason="r")
        queue.approve(pa.action_id, approver_id="human-1")
        metrics = queue.get_capacity_metrics()
        assert metrics["pending_count"] == 0
        assert metrics["resolved_count"] == 1

    def test_capacity_metrics_with_pending(self):
        queue = ApprovalQueue()
        queue.submit(agent_id="a", action="x", reason="r")
        queue.submit(agent_id="b", action="y", reason="r")
        metrics = queue.get_capacity_metrics()
        assert metrics["pending_count"] == 2


class TestApprovalQueueExpiry:
    """Tests for expiring old pending actions."""

    def test_expire_old_removes_stale(self):
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="a", action="x", reason="r")
        # Manually backdate the submission to simulate age
        pa.submitted_at = datetime.now(UTC) - timedelta(hours=50)
        expired = queue.expire_old(max_age_hours=48)
        assert len(expired) == 1
        assert expired[0].status == "expired"
        assert queue.queue_depth == 0

    def test_expire_old_keeps_recent(self):
        queue = ApprovalQueue()
        queue.submit(agent_id="a", action="x", reason="r")
        expired = queue.expire_old(max_age_hours=48)
        assert len(expired) == 0
        assert queue.queue_depth == 1

    def test_expire_old_mixed(self):
        queue = ApprovalQueue()
        old = queue.submit(agent_id="a", action="old", reason="r")
        old.submitted_at = datetime.now(UTC) - timedelta(hours=72)
        queue.submit(agent_id="b", action="new", reason="r")
        # Note: lazy expiry (RT-10) fires during the second submit(),
        # so 'old' is already expired before this explicit call.
        expired = queue.expire_old(max_age_hours=48)
        # The old action was already expired by lazy expiry in submit()
        assert len(expired) == 0
        assert queue.queue_depth == 1
