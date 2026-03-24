# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Bridge Lifecycle State Machine (M14 Task 1402)."""

import pytest

from pact_platform.build.workspace.bridge import BridgeStatus
from pact_platform.build.workspace.bridge_lifecycle import (
    BridgeStateMachine,
    InvalidBridgeTransitionError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sm():
    """Create a fresh BridgeStateMachine starting in PENDING."""
    return BridgeStateMachine()


# ---------------------------------------------------------------------------
# Test: Initial State
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_default_initial_state_is_pending(self, sm):
        assert sm.state == BridgeStatus.PENDING

    def test_custom_initial_state(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.ACTIVE)
        assert sm.state == BridgeStatus.ACTIVE


# ---------------------------------------------------------------------------
# Test: Valid Transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    def test_pending_to_negotiating(self, sm):
        sm.transition_to(BridgeStatus.NEGOTIATING)
        assert sm.state == BridgeStatus.NEGOTIATING

    def test_pending_to_active(self, sm):
        sm.transition_to(BridgeStatus.ACTIVE)
        assert sm.state == BridgeStatus.ACTIVE

    def test_pending_to_closed(self, sm):
        sm.transition_to(BridgeStatus.CLOSED)
        assert sm.state == BridgeStatus.CLOSED

    def test_pending_to_revoked(self, sm):
        sm.transition_to(BridgeStatus.REVOKED)
        assert sm.state == BridgeStatus.REVOKED

    def test_negotiating_to_active(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.NEGOTIATING)
        sm.transition_to(BridgeStatus.ACTIVE)
        assert sm.state == BridgeStatus.ACTIVE

    def test_negotiating_to_closed(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.NEGOTIATING)
        sm.transition_to(BridgeStatus.CLOSED)
        assert sm.state == BridgeStatus.CLOSED

    def test_negotiating_to_revoked(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.NEGOTIATING)
        sm.transition_to(BridgeStatus.REVOKED)
        assert sm.state == BridgeStatus.REVOKED

    def test_active_to_suspended(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.ACTIVE)
        sm.transition_to(BridgeStatus.SUSPENDED)
        assert sm.state == BridgeStatus.SUSPENDED

    def test_active_to_expired(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.ACTIVE)
        sm.transition_to(BridgeStatus.EXPIRED)
        assert sm.state == BridgeStatus.EXPIRED

    def test_active_to_closed(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.ACTIVE)
        sm.transition_to(BridgeStatus.CLOSED)
        assert sm.state == BridgeStatus.CLOSED

    def test_active_to_revoked(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.ACTIVE)
        sm.transition_to(BridgeStatus.REVOKED)
        assert sm.state == BridgeStatus.REVOKED

    def test_suspended_to_active(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.SUSPENDED)
        sm.transition_to(BridgeStatus.ACTIVE)
        assert sm.state == BridgeStatus.ACTIVE

    def test_suspended_to_expired(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.SUSPENDED)
        sm.transition_to(BridgeStatus.EXPIRED)
        assert sm.state == BridgeStatus.EXPIRED

    def test_suspended_to_closed(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.SUSPENDED)
        sm.transition_to(BridgeStatus.CLOSED)
        assert sm.state == BridgeStatus.CLOSED

    def test_suspended_to_revoked(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.SUSPENDED)
        sm.transition_to(BridgeStatus.REVOKED)
        assert sm.state == BridgeStatus.REVOKED


# ---------------------------------------------------------------------------
# Test: Invalid Transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    def test_pending_to_suspended_rejected(self, sm):
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.SUSPENDED)

    def test_pending_to_expired_rejected(self, sm):
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.EXPIRED)

    def test_negotiating_to_suspended_rejected(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.NEGOTIATING)
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.SUSPENDED)

    def test_negotiating_to_expired_rejected(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.NEGOTIATING)
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.EXPIRED)

    def test_expired_is_terminal(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.EXPIRED)
        for target in BridgeStatus:
            if target != BridgeStatus.EXPIRED:
                with pytest.raises(InvalidBridgeTransitionError):
                    sm.transition_to(target)

    def test_closed_is_terminal(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.CLOSED)
        for target in BridgeStatus:
            if target != BridgeStatus.CLOSED:
                with pytest.raises(InvalidBridgeTransitionError):
                    sm.transition_to(target)

    def test_revoked_is_terminal(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.REVOKED)
        for target in BridgeStatus:
            if target != BridgeStatus.REVOKED:
                with pytest.raises(InvalidBridgeTransitionError):
                    sm.transition_to(target)

    def test_self_transition_rejected(self, sm):
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.PENDING)

    def test_active_to_pending_rejected(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.ACTIVE)
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.PENDING)

    def test_active_to_negotiating_rejected(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.ACTIVE)
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.NEGOTIATING)

    def test_suspended_to_pending_rejected(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.SUSPENDED)
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.PENDING)

    def test_suspended_to_negotiating_rejected(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.SUSPENDED)
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.NEGOTIATING)


# ---------------------------------------------------------------------------
# Test: Transition History
# ---------------------------------------------------------------------------


class TestTransitionHistory:
    def test_history_starts_empty(self, sm):
        assert sm.history == []

    def test_history_records_transition(self, sm):
        sm.transition_to(BridgeStatus.NEGOTIATING)
        assert len(sm.history) == 1
        record = sm.history[0]
        assert record.from_state == BridgeStatus.PENDING
        assert record.to_state == BridgeStatus.NEGOTIATING

    def test_history_accumulates(self, sm):
        sm.transition_to(BridgeStatus.ACTIVE)
        sm.transition_to(BridgeStatus.SUSPENDED)
        sm.transition_to(BridgeStatus.ACTIVE)
        assert len(sm.history) == 3

    def test_history_preserves_reason(self, sm):
        sm.transition_to(BridgeStatus.ACTIVE, reason="both sides approved")
        assert sm.history[0].reason == "both sides approved"

    def test_failed_transition_does_not_add_to_history(self, sm):
        with pytest.raises(InvalidBridgeTransitionError):
            sm.transition_to(BridgeStatus.SUSPENDED)
        assert len(sm.history) == 0


# ---------------------------------------------------------------------------
# Test: Error Messages
# ---------------------------------------------------------------------------


class TestErrorMessages:
    def test_error_includes_current_state(self, sm):
        with pytest.raises(InvalidBridgeTransitionError, match="pending"):
            sm.transition_to(BridgeStatus.SUSPENDED)

    def test_error_includes_target_state(self, sm):
        with pytest.raises(InvalidBridgeTransitionError, match="suspended"):
            sm.transition_to(BridgeStatus.SUSPENDED)


# ---------------------------------------------------------------------------
# Test: can_transition_to / allowed_transitions
# ---------------------------------------------------------------------------


class TestCanTransitionTo:
    def test_pending_can_transition_to_negotiating(self, sm):
        assert sm.can_transition_to(BridgeStatus.NEGOTIATING) is True

    def test_pending_cannot_transition_to_suspended(self, sm):
        assert sm.can_transition_to(BridgeStatus.SUSPENDED) is False

    def test_allowed_transitions_from_pending(self, sm):
        allowed = sm.allowed_transitions
        assert BridgeStatus.NEGOTIATING in allowed
        assert BridgeStatus.ACTIVE in allowed
        assert BridgeStatus.CLOSED in allowed
        assert BridgeStatus.REVOKED in allowed

    def test_terminal_state_has_no_transitions(self):
        sm = BridgeStateMachine(initial_state=BridgeStatus.REVOKED)
        assert sm.allowed_transitions == []


# ---------------------------------------------------------------------------
# Test: Full Lifecycle Scenarios
# ---------------------------------------------------------------------------


class TestFullLifecycleScenarios:
    def test_happy_path_pending_negotiating_active_closed(self):
        sm = BridgeStateMachine()
        sm.transition_to(BridgeStatus.NEGOTIATING)
        sm.transition_to(BridgeStatus.ACTIVE)
        sm.transition_to(BridgeStatus.CLOSED)
        assert sm.state == BridgeStatus.CLOSED
        assert len(sm.history) == 3

    def test_suspension_and_resume(self):
        sm = BridgeStateMachine()
        sm.transition_to(BridgeStatus.ACTIVE)
        sm.transition_to(BridgeStatus.SUSPENDED)
        sm.transition_to(BridgeStatus.ACTIVE)
        sm.transition_to(BridgeStatus.CLOSED)
        assert sm.state == BridgeStatus.CLOSED
        assert len(sm.history) == 4

    def test_revocation_from_active(self):
        sm = BridgeStateMachine()
        sm.transition_to(BridgeStatus.ACTIVE)
        sm.transition_to(BridgeStatus.REVOKED)
        assert sm.state == BridgeStatus.REVOKED
