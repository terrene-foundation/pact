# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Trust Chain Lifecycle State Machine (M14 Task 1401)."""

import pytest

from care_platform.trust.lifecycle import (
    InvalidTransitionError,
    TrustChainState,
    TrustChainStateMachine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sm():
    """Create a fresh TrustChainStateMachine starting in DRAFT."""
    return TrustChainStateMachine()


# ---------------------------------------------------------------------------
# Test: Initial State
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_default_initial_state_is_draft(self, sm):
        assert sm.state == TrustChainState.DRAFT

    def test_custom_initial_state(self):
        sm = TrustChainStateMachine(initial_state=TrustChainState.ACTIVE)
        assert sm.state == TrustChainState.ACTIVE

    def test_all_states_are_valid_initial(self):
        """Every enum member can be used as an initial state."""
        for state in TrustChainState:
            sm = TrustChainStateMachine(initial_state=state)
            assert sm.state == state


# ---------------------------------------------------------------------------
# Test: Valid Transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    def test_draft_to_pending(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        assert sm.state == TrustChainState.PENDING

    def test_pending_to_active(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        assert sm.state == TrustChainState.ACTIVE

    def test_pending_to_revoked(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.REVOKED)
        assert sm.state == TrustChainState.REVOKED

    def test_active_to_suspended(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        sm.transition_to(TrustChainState.SUSPENDED)
        assert sm.state == TrustChainState.SUSPENDED

    def test_active_to_revoked(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        sm.transition_to(TrustChainState.REVOKED)
        assert sm.state == TrustChainState.REVOKED

    def test_active_to_expired(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        sm.transition_to(TrustChainState.EXPIRED)
        assert sm.state == TrustChainState.EXPIRED

    def test_suspended_to_active(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        sm.transition_to(TrustChainState.SUSPENDED)
        sm.transition_to(TrustChainState.ACTIVE)
        assert sm.state == TrustChainState.ACTIVE

    def test_suspended_to_revoked(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        sm.transition_to(TrustChainState.SUSPENDED)
        sm.transition_to(TrustChainState.REVOKED)
        assert sm.state == TrustChainState.REVOKED


# ---------------------------------------------------------------------------
# Test: Invalid Transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    def test_draft_to_active_rejected(self, sm):
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.ACTIVE)

    def test_draft_to_suspended_rejected(self, sm):
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.SUSPENDED)

    def test_draft_to_revoked_rejected(self, sm):
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.REVOKED)

    def test_draft_to_expired_rejected(self, sm):
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.EXPIRED)

    def test_pending_to_suspended_rejected(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.SUSPENDED)

    def test_pending_to_expired_rejected(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.EXPIRED)

    def test_active_to_pending_rejected(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.PENDING)

    def test_active_to_draft_rejected(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.DRAFT)

    def test_suspended_to_pending_rejected(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        sm.transition_to(TrustChainState.SUSPENDED)
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.PENDING)

    def test_suspended_to_expired_rejected(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        sm.transition_to(TrustChainState.SUSPENDED)
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.EXPIRED)

    def test_revoked_is_terminal(self, sm):
        """REVOKED is a terminal state; no transitions out."""
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.REVOKED)
        for target in TrustChainState:
            if target != TrustChainState.REVOKED:
                with pytest.raises(InvalidTransitionError):
                    sm.transition_to(target)

    def test_expired_is_terminal(self, sm):
        """EXPIRED is a terminal state; no transitions out."""
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        sm.transition_to(TrustChainState.EXPIRED)
        for target in TrustChainState:
            if target != TrustChainState.EXPIRED:
                with pytest.raises(InvalidTransitionError):
                    sm.transition_to(target)

    def test_self_transition_rejected(self, sm):
        """Transitioning to the same state is always invalid."""
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.DRAFT)


# ---------------------------------------------------------------------------
# Test: Transition History
# ---------------------------------------------------------------------------


class TestTransitionHistory:
    def test_history_starts_empty(self, sm):
        assert sm.history == []

    def test_history_records_transition(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        assert len(sm.history) == 1
        record = sm.history[0]
        assert record.from_state == TrustChainState.DRAFT
        assert record.to_state == TrustChainState.PENDING

    def test_history_accumulates(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        sm.transition_to(TrustChainState.ACTIVE)
        sm.transition_to(TrustChainState.SUSPENDED)
        sm.transition_to(TrustChainState.ACTIVE)
        assert len(sm.history) == 4

    def test_history_preserves_reason(self, sm):
        sm.transition_to(TrustChainState.PENDING, reason="submitted for review")
        assert sm.history[0].reason == "submitted for review"

    def test_history_has_timestamps(self, sm):
        sm.transition_to(TrustChainState.PENDING)
        assert sm.history[0].timestamp is not None

    def test_failed_transition_does_not_add_to_history(self, sm):
        with pytest.raises(InvalidTransitionError):
            sm.transition_to(TrustChainState.ACTIVE)
        assert len(sm.history) == 0


# ---------------------------------------------------------------------------
# Test: Error Messages
# ---------------------------------------------------------------------------


class TestErrorMessages:
    def test_error_includes_current_state(self, sm):
        with pytest.raises(InvalidTransitionError, match="DRAFT"):
            sm.transition_to(TrustChainState.ACTIVE)

    def test_error_includes_target_state(self, sm):
        with pytest.raises(InvalidTransitionError, match="ACTIVE"):
            sm.transition_to(TrustChainState.ACTIVE)

    def test_error_includes_allowed_transitions(self, sm):
        """The error message should indicate what transitions are valid."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            sm.transition_to(TrustChainState.ACTIVE)
        error_msg = str(exc_info.value)
        assert "PENDING" in error_msg


# ---------------------------------------------------------------------------
# Test: can_transition_to
# ---------------------------------------------------------------------------


class TestCanTransitionTo:
    def test_can_transition_draft_to_pending(self, sm):
        assert sm.can_transition_to(TrustChainState.PENDING) is True

    def test_cannot_transition_draft_to_active(self, sm):
        assert sm.can_transition_to(TrustChainState.ACTIVE) is False

    def test_can_transition_active_to_suspended(self):
        sm = TrustChainStateMachine(initial_state=TrustChainState.ACTIVE)
        assert sm.can_transition_to(TrustChainState.SUSPENDED) is True

    def test_cannot_self_transition(self, sm):
        assert sm.can_transition_to(TrustChainState.DRAFT) is False


# ---------------------------------------------------------------------------
# Test: allowed_transitions
# ---------------------------------------------------------------------------


class TestAllowedTransitions:
    def test_draft_allowed_transitions(self, sm):
        allowed = sm.allowed_transitions
        assert TrustChainState.PENDING in allowed
        assert len(allowed) == 1

    def test_active_allowed_transitions(self):
        sm = TrustChainStateMachine(initial_state=TrustChainState.ACTIVE)
        allowed = sm.allowed_transitions
        assert TrustChainState.SUSPENDED in allowed
        assert TrustChainState.REVOKED in allowed
        assert TrustChainState.EXPIRED in allowed
        assert len(allowed) == 3

    def test_terminal_state_has_no_transitions(self):
        sm = TrustChainStateMachine(initial_state=TrustChainState.REVOKED)
        assert sm.allowed_transitions == []

    def test_expired_has_no_transitions(self):
        sm = TrustChainStateMachine(initial_state=TrustChainState.EXPIRED)
        assert sm.allowed_transitions == []
