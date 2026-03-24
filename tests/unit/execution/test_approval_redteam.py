# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Red team tests for approval queue enforcement gaps.

Covers RT-10 findings:
- Lazy expiry: expire_old() called automatically at start of submit/pending/approve/reject
- Queue overflow protection: max_queue_depth with QueueOverflowError
- oldest_pending_age_seconds() method
"""

from datetime import UTC, datetime, timedelta

import pytest

from pact_platform.use.execution.approval import (
    ApprovalQueue,
    QueueOverflowError,
)

# ===========================================================================
# RT-10a: Lazy expiry — _check_expiry() called at entry points
# ===========================================================================


class TestLazyExpiry:
    """RT-10: expire_old() must be called automatically at the start of
    submit(), pending, approve(), and reject()."""

    def test_submit_triggers_lazy_expiry(self):
        """Old pending actions should be expired when submit() is called."""
        queue = ApprovalQueue()
        old = queue.submit(agent_id="a", action="old_action", reason="r")
        old.submitted_at = datetime.now(UTC) - timedelta(hours=50)

        # This submit should trigger lazy expiry, clearing the old action
        queue.submit(agent_id="b", action="new_action", reason="r")

        # Only the new action should be pending
        assert queue.queue_depth == 1
        assert queue.pending[0].action == "new_action"

    def test_pending_triggers_lazy_expiry(self):
        """Accessing pending property should trigger lazy expiry."""
        queue = ApprovalQueue()
        old = queue.submit(agent_id="a", action="old_action", reason="r")
        old.submitted_at = datetime.now(UTC) - timedelta(hours=50)

        # Accessing pending should trigger expiry
        pending = queue.pending
        assert len(pending) == 0

    def test_approve_triggers_lazy_expiry(self):
        """approve() should trigger lazy expiry first."""
        queue = ApprovalQueue()
        old = queue.submit(agent_id="a", action="old_action", reason="r")
        old.submitted_at = datetime.now(UTC) - timedelta(hours=50)

        current = queue.submit(agent_id="b", action="current_action", reason="r")

        # Approve the current action -- old should have been expired first
        queue.approve(current.action_id, approver_id="human-1")

        # Old action should be expired (not pending)
        assert queue.queue_depth == 0

    def test_reject_triggers_lazy_expiry(self):
        """reject() should trigger lazy expiry first."""
        queue = ApprovalQueue()
        old = queue.submit(agent_id="a", action="old_action", reason="r")
        old.submitted_at = datetime.now(UTC) - timedelta(hours=50)

        current = queue.submit(agent_id="b", action="current_action", reason="r")

        # Reject the current action -- old should have been expired first
        queue.reject(current.action_id, approver_id="human-1", reason="no")

        # Both resolved
        assert queue.queue_depth == 0

    def test_recent_items_not_expired_by_lazy_check(self):
        """Lazy expiry should not remove recent items."""
        queue = ApprovalQueue()
        queue.submit(agent_id="a", action="fresh_action", reason="r")

        # Trigger lazy expiry by submitting another
        queue.submit(agent_id="b", action="fresh_action_2", reason="r")

        # Both should still be pending
        assert queue.queue_depth == 2


# ===========================================================================
# RT-10b: Queue overflow protection
# ===========================================================================


class TestQueueOverflowProtection:
    """RT-10: ApprovalQueue should enforce max_queue_depth."""

    def test_default_max_queue_depth_is_100(self):
        """Default max_queue_depth should be 100."""
        queue = ApprovalQueue()
        assert queue.max_queue_depth == 100

    def test_custom_max_queue_depth(self):
        """max_queue_depth should be configurable."""
        queue = ApprovalQueue(max_queue_depth=5)
        assert queue.max_queue_depth == 5

    def test_overflow_raises_queue_overflow_error(self):
        """Submitting beyond max_queue_depth should raise QueueOverflowError."""
        queue = ApprovalQueue(max_queue_depth=3)
        queue.submit(agent_id="a", action="x1", reason="r")
        queue.submit(agent_id="b", action="x2", reason="r")
        queue.submit(agent_id="c", action="x3", reason="r")

        with pytest.raises(QueueOverflowError):
            queue.submit(agent_id="d", action="x4", reason="r")

    def test_queue_overflow_error_is_runtime_error(self):
        """QueueOverflowError must be a subclass of RuntimeError."""
        assert issubclass(QueueOverflowError, RuntimeError)

    def test_overflow_after_lazy_expiry_clears_room(self):
        """If lazy expiry frees slots, submit should succeed."""
        queue = ApprovalQueue(max_queue_depth=3)
        old1 = queue.submit(agent_id="a", action="x1", reason="r")
        old1.submitted_at = datetime.now(UTC) - timedelta(hours=50)
        old2 = queue.submit(agent_id="b", action="x2", reason="r")
        old2.submitted_at = datetime.now(UTC) - timedelta(hours=50)
        queue.submit(agent_id="c", action="x3", reason="r")

        # Queue is at 3, but 2 are expired. Lazy expiry should clear them first.
        # So this submit should succeed.
        pa = queue.submit(agent_id="d", action="x4", reason="r")
        assert pa.action == "x4"
        assert queue.queue_depth == 2  # x3 + x4

    def test_overflow_message_includes_depth(self):
        """QueueOverflowError message should be informative."""
        queue = ApprovalQueue(max_queue_depth=2)
        queue.submit(agent_id="a", action="x1", reason="r")
        queue.submit(agent_id="b", action="x2", reason="r")

        with pytest.raises(QueueOverflowError, match="2"):
            queue.submit(agent_id="c", action="x3", reason="r")


# ===========================================================================
# RT-10c: oldest_pending_age_seconds() method
# ===========================================================================


class TestOldestPendingAge:
    """RT-10: oldest_pending_age_seconds() should report the age of the oldest pending item."""

    def test_empty_queue_returns_zero(self):
        """Empty queue should return 0.0."""
        queue = ApprovalQueue()
        assert queue.oldest_pending_age_seconds() == 0.0

    def test_returns_age_of_oldest_item(self):
        """Should return age in seconds of the oldest pending item."""
        queue = ApprovalQueue()
        old = queue.submit(agent_id="a", action="x", reason="r")
        old.submitted_at = datetime.now(UTC) - timedelta(seconds=120)
        queue.submit(agent_id="b", action="y", reason="r")

        age = queue.oldest_pending_age_seconds()
        # Should be approximately 120 seconds (allow some tolerance)
        assert age >= 119.0
        assert age < 125.0

    def test_age_after_oldest_is_approved(self):
        """After the oldest is approved, age should reflect the next oldest."""
        queue = ApprovalQueue()
        old = queue.submit(agent_id="a", action="x", reason="r")
        old.submitted_at = datetime.now(UTC) - timedelta(seconds=200)

        newer = queue.submit(agent_id="b", action="y", reason="r")
        newer.submitted_at = datetime.now(UTC) - timedelta(seconds=50)

        queue.approve(old.action_id, approver_id="human-1")

        age = queue.oldest_pending_age_seconds()
        assert age >= 49.0
        assert age < 55.0
