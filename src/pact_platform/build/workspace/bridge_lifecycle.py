# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Bridge Lifecycle State Machine — explicit transition table for Cross-Functional Bridges.

Consolidates the scattered transition logic from bridge.py into a single
authoritative state machine. The bridge lifecycle follows the CARE formal spec:

    PENDING -> NEGOTIATING -> ACTIVE -> SUSPENDED -> ACTIVE (resume)
           |         |    |         |-> EXPIRED
           |         |    |         |-> CLOSED
           |         |    |         |-> REVOKED
           |         |    |-> CLOSED
           |         |    |-> REVOKED
           |         |-> PENDING (terms_rejected, RT13-01)
           |-> ACTIVE
           |-> CLOSED
           |-> REVOKED

    SUSPENDED -> EXPIRED
             |-> CLOSED
             |-> REVOKED

Terminal states: EXPIRED, CLOSED, REVOKED (no transitions out).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from pact_platform.build.workspace.bridge import BridgeStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidBridgeTransitionError(Exception):
    """Raised when an invalid bridge state transition is attempted."""


# ---------------------------------------------------------------------------
# Transition Table
# ---------------------------------------------------------------------------

# Maps each BridgeStatus to its valid target states.
_BRIDGE_TRANSITIONS: dict[BridgeStatus, list[BridgeStatus]] = {
    BridgeStatus.PENDING: [
        BridgeStatus.NEGOTIATING,
        BridgeStatus.ACTIVE,
        BridgeStatus.CLOSED,
        BridgeStatus.REVOKED,
    ],
    BridgeStatus.NEGOTIATING: [
        BridgeStatus.PENDING,  # RT13-01: CARE spec allows terms_rejected() -> PROPOSED (PENDING)
        BridgeStatus.ACTIVE,
        BridgeStatus.CLOSED,
        BridgeStatus.REVOKED,
    ],
    BridgeStatus.ACTIVE: [
        BridgeStatus.SUSPENDED,
        BridgeStatus.EXPIRED,
        BridgeStatus.CLOSED,
        BridgeStatus.REVOKED,
    ],
    BridgeStatus.SUSPENDED: [
        BridgeStatus.ACTIVE,
        BridgeStatus.EXPIRED,
        BridgeStatus.CLOSED,
        BridgeStatus.REVOKED,
    ],
    BridgeStatus.EXPIRED: [],  # terminal
    BridgeStatus.CLOSED: [],  # terminal
    BridgeStatus.REVOKED: [],  # terminal
}


# ---------------------------------------------------------------------------
# Transition Record
# ---------------------------------------------------------------------------


class BridgeTransitionRecord(BaseModel):
    """Record of a single bridge state transition."""

    from_state: BridgeStatus
    to_state: BridgeStatus
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------


class BridgeStateMachine:
    """Manages the lifecycle state machine for a Cross-Functional Bridge.

    Provides a single authoritative transition table that consolidates the
    scattered transition logic found in BridgeManager methods (negotiate_bridge,
    suspend_bridge, resume_bridge, close, revoke, expire_bridges, etc.).

    Args:
        initial_state: The starting state. Defaults to PENDING.
    """

    def __init__(
        self,
        initial_state: BridgeStatus = BridgeStatus.PENDING,
    ) -> None:
        self._state = initial_state
        self._history: list[BridgeTransitionRecord] = []

    @property
    def state(self) -> BridgeStatus:
        """Current state of the bridge."""
        return self._state

    @property
    def history(self) -> list[BridgeTransitionRecord]:
        """Ordered list of all state transitions."""
        return list(self._history)

    @property
    def allowed_transitions(self) -> list[BridgeStatus]:
        """List of states reachable from the current state."""
        return list(_BRIDGE_TRANSITIONS.get(self._state, []))

    def can_transition_to(self, target: BridgeStatus) -> bool:
        """Check whether transitioning to the target state is valid.

        Args:
            target: The desired target state.

        Returns:
            True if the transition is allowed, False otherwise.
        """
        return target in _BRIDGE_TRANSITIONS.get(self._state, [])

    def transition_to(
        self,
        target: BridgeStatus,
        *,
        reason: str = "",
    ) -> BridgeTransitionRecord:
        """Transition to a new state.

        Args:
            target: The desired target state.
            reason: Optional human-readable reason for the transition.

        Returns:
            A BridgeTransitionRecord describing the transition.

        Raises:
            InvalidBridgeTransitionError: If the transition is not valid from
                the current state. The error message includes the current state,
                the attempted target, and the list of allowed transitions.
        """
        allowed = _BRIDGE_TRANSITIONS.get(self._state, [])
        if target not in allowed:
            allowed_names = [s.value for s in allowed] if allowed else ["(none -- terminal state)"]
            raise InvalidBridgeTransitionError(
                f"Cannot transition bridge from {self._state.value} to {target.value}. "
                f"Allowed transitions from {self._state.value}: {', '.join(allowed_names)}"
            )

        record = BridgeTransitionRecord(
            from_state=self._state,
            to_state=target,
            reason=reason,
        )
        previous = self._state
        self._state = target
        self._history.append(record)

        logger.info(
            "Bridge state: %s -> %s (reason: %s)",
            previous.value,
            target.value,
            reason or "(none)",
        )

        return record
