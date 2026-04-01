# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for HELD timeout in ApprovalQueue (implemented, formerly TODO-09).

Covers: timeout not triggered immediately, auto-deny after timeout,
resolved actions unaffected, and timeout reason message.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from pact_platform.use.execution.approval import ApprovalQueue, UrgencyLevel


class TestCheckTimeoutsBasic:
    """Tests that check_timeouts() behaves correctly under normal conditions."""

    def test_not_timed_out_immediately(self):
        """A newly submitted action should not be timed out."""
        queue = ApprovalQueue(timeout_seconds=86400)
        queue.submit(agent_id="agent-1", action="deploy", reason="held")
        timed_out = queue.check_timeouts()
        assert timed_out == []
        assert queue.queue_depth == 1

    def test_default_timeout_is_24h(self):
        """Default timeout_seconds should be 86400 (24 hours)."""
        queue = ApprovalQueue()
        assert queue._timeout_seconds == 86400


class TestCheckTimeoutsWithFreezegun:
    """Tests using freezegun to advance time past the timeout threshold."""

    def test_auto_deny_after_timeout(self):
        """An action pending longer than timeout_seconds is auto-denied."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        with freeze_time(base_time):
            queue = ApprovalQueue(timeout_seconds=3600)  # 1 hour timeout
            pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")
            action_id = pa.action_id

        # 30 minutes: not timed out
        with freeze_time(base_time + timedelta(minutes=30)):
            timed_out = queue.check_timeouts()
            assert timed_out == []
            assert queue.queue_depth == 1

        # 61 minutes: timed out
        with freeze_time(base_time + timedelta(minutes=61)):
            timed_out = queue.check_timeouts()
            assert timed_out == [action_id]
            assert queue.queue_depth == 0

    def test_timeout_sets_correct_status(self):
        """Timed-out actions have status 'timeout_denied'."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        with freeze_time(base_time):
            queue = ApprovalQueue(timeout_seconds=3600)
            pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")

        with freeze_time(base_time + timedelta(hours=2)):
            queue.check_timeouts()

        # The action should be in resolved with correct status
        resolved = list(queue._resolved)
        assert len(resolved) == 1
        assert resolved[0].action_id == pa.action_id
        assert resolved[0].status == "timeout_denied"

    def test_timeout_reason_message(self):
        """Timed-out actions carry the EATP-guidance reason message."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        with freeze_time(base_time):
            queue = ApprovalQueue(timeout_seconds=3600)
            queue.submit(agent_id="agent-1", action="deploy", reason="held")

        with freeze_time(base_time + timedelta(hours=2)):
            queue.check_timeouts()

        resolved = list(queue._resolved)
        assert len(resolved) == 1
        assert "Auto-denied: exceeded approval timeout" in resolved[0].decision_reason
        assert "per EATP guidance" in resolved[0].decision_reason

    def test_timeout_sets_decided_at(self):
        """Timed-out actions have decided_at set to the timeout check time."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        check_time = base_time + timedelta(hours=2)

        with freeze_time(base_time):
            queue = ApprovalQueue(timeout_seconds=3600)
            queue.submit(agent_id="agent-1", action="deploy", reason="held")

        with freeze_time(check_time):
            queue.check_timeouts()

        resolved = list(queue._resolved)
        assert resolved[0].decided_at is not None
        assert resolved[0].decided_at == check_time


class TestCheckTimeoutsResolvedActions:
    """Tests that already-resolved actions are not affected by timeout checks."""

    def test_approved_action_not_affected(self):
        """An action that was approved before timeout is unaffected."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        with freeze_time(base_time):
            queue = ApprovalQueue(timeout_seconds=3600)
            pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")

        # Approve it within the timeout window
        with freeze_time(base_time + timedelta(minutes=30)):
            queue.approve(pa.action_id, approver_id="human-1", reason="looks good")

        # Check timeouts after the timeout period
        with freeze_time(base_time + timedelta(hours=2)):
            timed_out = queue.check_timeouts()
            assert timed_out == []

        # The resolved action should still be 'approved'
        approved_actions = [r for r in queue._resolved if r.action_id == pa.action_id]
        assert len(approved_actions) == 1
        assert approved_actions[0].status == "approved"

    def test_rejected_action_not_affected(self):
        """An action that was rejected before timeout is unaffected."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        with freeze_time(base_time):
            queue = ApprovalQueue(timeout_seconds=3600)
            pa = queue.submit(agent_id="agent-1", action="deploy", reason="held")

        with freeze_time(base_time + timedelta(minutes=30)):
            queue.reject(pa.action_id, approver_id="human-1", reason="denied")

        with freeze_time(base_time + timedelta(hours=2)):
            timed_out = queue.check_timeouts()
            assert timed_out == []

        rejected = [r for r in queue._resolved if r.action_id == pa.action_id]
        assert len(rejected) == 1
        assert rejected[0].status == "rejected"


class TestCheckTimeoutsMultipleActions:
    """Tests for timeout behavior with multiple pending actions."""

    def test_only_old_actions_timed_out(self):
        """Only actions past the timeout are denied; newer ones survive."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        with freeze_time(base_time):
            queue = ApprovalQueue(timeout_seconds=3600)
            old = queue.submit(agent_id="agent-1", action="old-deploy", reason="held")

        with freeze_time(base_time + timedelta(minutes=50)):
            new = queue.submit(agent_id="agent-2", action="new-deploy", reason="held")

        # At 65 minutes: old is 65 min (expired), new is 15 min (not expired)
        with freeze_time(base_time + timedelta(minutes=65)):
            timed_out = queue.check_timeouts()
            assert timed_out == [old.action_id]
            assert queue.queue_depth == 1

            # The remaining action should be the new one
            pending = queue.pending
            assert len(pending) == 1
            assert pending[0].action_id == new.action_id

    def test_multiple_actions_timed_out_at_once(self):
        """Multiple old actions can be timed out in a single check."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        with freeze_time(base_time):
            queue = ApprovalQueue(timeout_seconds=3600)
            pa1 = queue.submit(agent_id="agent-1", action="deploy-1", reason="held")
            pa2 = queue.submit(agent_id="agent-2", action="deploy-2", reason="held")

        with freeze_time(base_time + timedelta(hours=2)):
            timed_out = queue.check_timeouts()
            assert set(timed_out) == {pa1.action_id, pa2.action_id}
            assert queue.queue_depth == 0

    def test_check_timeouts_idempotent(self):
        """Calling check_timeouts() twice does not re-timeout already denied actions."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        with freeze_time(base_time):
            queue = ApprovalQueue(timeout_seconds=3600)
            queue.submit(agent_id="agent-1", action="deploy", reason="held")

        with freeze_time(base_time + timedelta(hours=2)):
            first_check = queue.check_timeouts()
            assert len(first_check) == 1

            second_check = queue.check_timeouts()
            assert second_check == []
