# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Trust Chain Lifecycle State Machine — manages state transitions for EATP trust chains.

The trust chain lifecycle follows a strict state machine:

    DRAFT -> PENDING -> ACTIVE -> SUSPENDED -> ACTIVE (resume)
                    |         |-> REVOKED
                    |         |-> EXPIRED
                    |-> REVOKED
    SUSPENDED -> REVOKED

Terminal states: REVOKED, EXPIRED (no transitions out).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


# ---------------------------------------------------------------------------
# State Enum
# ---------------------------------------------------------------------------


class TrustChainState(str, Enum):
    """Lifecycle states for a trust chain."""

    DRAFT = "DRAFT"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


# ---------------------------------------------------------------------------
# Transition Table
# ---------------------------------------------------------------------------

# Maps each state to its valid target states.
_TRUST_CHAIN_TRANSITIONS: dict[TrustChainState, list[TrustChainState]] = {
    TrustChainState.DRAFT: [TrustChainState.PENDING],
    TrustChainState.PENDING: [TrustChainState.ACTIVE, TrustChainState.REVOKED],
    TrustChainState.ACTIVE: [
        TrustChainState.SUSPENDED,
        TrustChainState.REVOKED,
        TrustChainState.EXPIRED,
    ],
    TrustChainState.SUSPENDED: [TrustChainState.ACTIVE, TrustChainState.REVOKED],
    TrustChainState.REVOKED: [],  # terminal
    TrustChainState.EXPIRED: [],  # terminal
}


# ---------------------------------------------------------------------------
# Transition Record
# ---------------------------------------------------------------------------


class TrustChainTransitionRecord(BaseModel):
    """Record of a single state transition in the trust chain lifecycle."""

    from_state: TrustChainState
    to_state: TrustChainState
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------


class TrustChainStateMachine:
    """Manages the lifecycle state machine for a trust chain.

    Enforces valid transitions according to the CARE formal specification.
    Records all transitions with timestamps and optional reasons.

    Args:
        initial_state: The starting state. Defaults to DRAFT.
    """

    def __init__(
        self,
        initial_state: TrustChainState = TrustChainState.DRAFT,
    ) -> None:
        self._state = initial_state
        self._history: list[TrustChainTransitionRecord] = []

    @property
    def state(self) -> TrustChainState:
        """Current state of the trust chain."""
        return self._state

    @property
    def history(self) -> list[TrustChainTransitionRecord]:
        """Ordered list of all state transitions."""
        return list(self._history)

    @property
    def allowed_transitions(self) -> list[TrustChainState]:
        """List of states reachable from the current state."""
        return list(_TRUST_CHAIN_TRANSITIONS.get(self._state, []))

    def can_transition_to(self, target: TrustChainState) -> bool:
        """Check whether transitioning to the target state is valid.

        Args:
            target: The desired target state.

        Returns:
            True if the transition is allowed, False otherwise.
        """
        return target in _TRUST_CHAIN_TRANSITIONS.get(self._state, [])

    def transition_to(
        self,
        target: TrustChainState,
        *,
        reason: str = "",
    ) -> TrustChainTransitionRecord:
        """Transition to a new state.

        Args:
            target: The desired target state.
            reason: Optional human-readable reason for the transition.

        Returns:
            A TrustChainTransitionRecord describing the transition.

        Raises:
            InvalidTransitionError: If the transition is not valid from the
                current state. The error message includes the current state,
                the attempted target, and the list of allowed transitions.
        """
        allowed = _TRUST_CHAIN_TRANSITIONS.get(self._state, [])
        if target not in allowed:
            allowed_names = [s.value for s in allowed] if allowed else ["(none — terminal state)"]
            raise InvalidTransitionError(
                f"Cannot transition from {self._state.value} to {target.value}. "
                f"Allowed transitions from {self._state.value}: {', '.join(allowed_names)}"
            )

        record = TrustChainTransitionRecord(
            from_state=self._state,
            to_state=target,
            reason=reason,
        )
        previous = self._state
        self._state = target
        self._history.append(record)

        logger.info(
            "Trust chain state: %s -> %s (reason: %s)",
            previous.value,
            target.value,
            reason or "(none)",
        )

        return record
