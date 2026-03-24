# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""RT-04: Approver authorization and self-approval prevention tests.

Tests that:
1. authorized_approvers restricts who can approve/reject actions
2. Self-approval is prevented (approver_id != agent_id)
3. batch_approve also enforces both checks
4. Backward compatibility: empty authorized_approvers = no restriction
"""

import pytest

from pact_platform.use.execution.approval import ApprovalQueue


class TestApproverAuthorization:
    """Test that only authorized approvers can approve or reject actions."""

    def test_empty_authorized_approvers_allows_anyone_to_approve(self):
        """Backward compatibility: empty set means no restriction."""
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        result = queue.approve(pa.action_id, approver_id="anyone", reason="ok")
        assert result.status == "approved"

    def test_empty_authorized_approvers_allows_anyone_to_reject(self):
        """Backward compatibility: empty set means no restriction for reject."""
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        result = queue.reject(pa.action_id, approver_id="anyone", reason="no")
        assert result.status == "rejected"

    def test_authorized_approver_can_approve(self):
        """An approver in the authorized set should succeed."""
        queue = ApprovalQueue(authorized_approvers={"human-1", "human-2"})
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        result = queue.approve(pa.action_id, approver_id="human-1", reason="ok")
        assert result.status == "approved"
        assert result.decided_by == "human-1"

    def test_authorized_approver_can_reject(self):
        """An approver in the authorized set should be able to reject."""
        queue = ApprovalQueue(authorized_approvers={"human-1", "human-2"})
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        result = queue.reject(pa.action_id, approver_id="human-2", reason="risky")
        assert result.status == "rejected"
        assert result.decided_by == "human-2"

    def test_unauthorized_approver_cannot_approve(self):
        """An approver NOT in the authorized set should raise PermissionError."""
        queue = ApprovalQueue(authorized_approvers={"human-1", "human-2"})
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        with pytest.raises(PermissionError):
            queue.approve(pa.action_id, approver_id="unauthorized-person")

    def test_unauthorized_approver_cannot_reject(self):
        """An approver NOT in the authorized set should raise PermissionError."""
        queue = ApprovalQueue(authorized_approvers={"human-1", "human-2"})
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        with pytest.raises(PermissionError):
            queue.reject(pa.action_id, approver_id="unauthorized-person")

    def test_unauthorized_approver_leaves_action_pending(self):
        """A failed authorization attempt should not change the action status."""
        queue = ApprovalQueue(authorized_approvers={"human-1"})
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        with pytest.raises(PermissionError):
            queue.approve(pa.action_id, approver_id="intruder")
        # Action should still be pending
        assert queue.queue_depth == 1
        assert pa.status == "pending"


class TestSelfApprovalPrevention:
    """Test that agents cannot approve their own actions."""

    def test_self_approval_raises_permission_error(self):
        """An agent approving its own action should raise PermissionError."""
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        with pytest.raises(PermissionError, match="Self-approval is not permitted"):
            queue.approve(pa.action_id, approver_id="agent-1")

    def test_self_approval_prevented_even_with_authorized_set(self):
        """Self-approval should be prevented even if agent is in authorized set."""
        queue = ApprovalQueue(authorized_approvers={"agent-1", "human-1"})
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        with pytest.raises(PermissionError, match="Self-approval is not permitted"):
            queue.approve(pa.action_id, approver_id="agent-1")

    def test_different_approver_same_team_succeeds(self):
        """A different agent on the same team should be able to approve."""
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held", team_id="team-ops")
        result = queue.approve(pa.action_id, approver_id="agent-2", reason="reviewed")
        assert result.status == "approved"

    def test_self_rejection_is_allowed(self):
        """An agent rejecting its own action is acceptable (conservative direction)."""
        queue = ApprovalQueue()
        pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
        # Self-rejection is the safe direction -- no restriction needed
        result = queue.reject(pa.action_id, approver_id="agent-1", reason="changed mind")
        assert result.status == "rejected"


class TestBatchApproveAuthorization:
    """Test that batch_approve enforces authorization and self-approval checks."""

    def test_batch_approve_unauthorized_raises(self):
        """batch_approve with unauthorized approver should raise PermissionError."""
        queue = ApprovalQueue(authorized_approvers={"human-1"})
        pa1 = queue.submit(agent_id="agent-1", action="x", reason="r")
        pa2 = queue.submit(agent_id="agent-2", action="y", reason="r")
        with pytest.raises(PermissionError):
            queue.batch_approve([pa1.action_id, pa2.action_id], approver_id="unauthorized")

    def test_batch_approve_self_approval_raises(self):
        """batch_approve should reject if approver is the agent on any action."""
        queue = ApprovalQueue()
        pa1 = queue.submit(agent_id="agent-1", action="x", reason="r")
        pa2 = queue.submit(agent_id="agent-2", action="y", reason="r")
        with pytest.raises(PermissionError, match="Self-approval is not permitted"):
            queue.batch_approve([pa1.action_id, pa2.action_id], approver_id="agent-1")

    def test_batch_approve_self_approval_does_not_partially_approve(self):
        """If self-approval check fails, no actions should be approved."""
        queue = ApprovalQueue()
        pa1 = queue.submit(agent_id="agent-2", action="x", reason="r")
        pa2 = queue.submit(agent_id="agent-1", action="y", reason="r")
        with pytest.raises(PermissionError):
            queue.batch_approve([pa1.action_id, pa2.action_id], approver_id="agent-1")
        # Both should still be pending
        assert queue.queue_depth == 2

    def test_batch_approve_authorized_succeeds(self):
        """batch_approve with authorized approver for all actions should succeed."""
        queue = ApprovalQueue(authorized_approvers={"human-1"})
        pa1 = queue.submit(agent_id="agent-1", action="x", reason="r")
        pa2 = queue.submit(agent_id="agent-2", action="y", reason="r")
        results = queue.batch_approve([pa1.action_id, pa2.action_id], approver_id="human-1")
        assert len(results) == 2
        assert all(r.status == "approved" for r in results)
