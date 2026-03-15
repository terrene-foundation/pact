# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Task lifecycle state machine — tracks task state from submission to completion.

Lifecycle states:
    SUBMITTED -> VERIFYING -> HELD/EXECUTING -> COMPLETED/FAILED/REJECTED

Each transition emits a WebSocket event via the event bus (when available)
and records a timestamped transition record. At lifecycle end, the full
record (all stages, decisions, timestamps) is available for audit.

Valid transitions:
    SUBMITTED  -> VERIFYING
    VERIFYING  -> HELD, EXECUTING, REJECTED
    HELD       -> EXECUTING, REJECTED, FAILED
    EXECUTING  -> COMPLETED, FAILED
    COMPLETED  -> (terminal)
    FAILED     -> (terminal)
    REJECTED   -> (terminal)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskLifecycleState(str, Enum):
    """Lifecycle states for a task."""

    SUBMITTED = "submitted"
    VERIFYING = "verifying"
    HELD = "held"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


# Terminal states — no further transitions allowed.
_TERMINAL_STATES: frozenset[TaskLifecycleState] = frozenset(
    {
        TaskLifecycleState.COMPLETED,
        TaskLifecycleState.FAILED,
        TaskLifecycleState.REJECTED,
    }
)

# Valid transitions: from_state -> set of valid to_states
_VALID_TRANSITIONS: dict[TaskLifecycleState, frozenset[TaskLifecycleState]] = {
    TaskLifecycleState.SUBMITTED: frozenset({TaskLifecycleState.VERIFYING}),
    TaskLifecycleState.VERIFYING: frozenset(
        {
            TaskLifecycleState.HELD,
            TaskLifecycleState.EXECUTING,
            TaskLifecycleState.REJECTED,
        }
    ),
    TaskLifecycleState.HELD: frozenset(
        {
            TaskLifecycleState.EXECUTING,
            TaskLifecycleState.REJECTED,
            TaskLifecycleState.FAILED,
        }
    ),
    TaskLifecycleState.EXECUTING: frozenset(
        {
            TaskLifecycleState.COMPLETED,
            TaskLifecycleState.FAILED,
        }
    ),
    # Terminal states have no valid transitions
    TaskLifecycleState.COMPLETED: frozenset(),
    TaskLifecycleState.FAILED: frozenset(),
    TaskLifecycleState.REJECTED: frozenset(),
}


class LifecycleTransition(BaseModel):
    """Record of a single state transition."""

    from_state: TaskLifecycleState
    to_state: TaskLifecycleState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskLifecycle:
    """State machine tracking a task through its lifecycle.

    Each TaskLifecycle instance tracks one task from SUBMITTED through
    to a terminal state (COMPLETED, FAILED, or REJECTED). Every
    transition is recorded with a timestamp for audit purposes.

    Usage:
        lifecycle = TaskLifecycle(task_id="task-1", agent_id="agent-1", action="summarize")
        lifecycle.transition_to(TaskLifecycleState.VERIFYING)
        lifecycle.transition_to(TaskLifecycleState.EXECUTING)
        lifecycle.transition_to(TaskLifecycleState.COMPLETED)
        record = lifecycle.to_audit_record()
    """

    def __init__(
        self,
        task_id: str,
        agent_id: str,
        action: str,
    ) -> None:
        """Initialize lifecycle in SUBMITTED state.

        Args:
            task_id: Unique identifier for the task.
            agent_id: The agent assigned to the task.
            action: The action description.
        """
        self._task_id = task_id
        self._agent_id = agent_id
        self._action = action
        self._current_state = TaskLifecycleState.SUBMITTED
        self._transitions: list[LifecycleTransition] = []
        self._created_at = datetime.now(UTC)

    @property
    def current_state(self) -> TaskLifecycleState:
        """Current lifecycle state."""
        return self._current_state

    @property
    def transitions(self) -> list[LifecycleTransition]:
        """All recorded transitions."""
        return list(self._transitions)

    @property
    def is_terminal(self) -> bool:
        """Whether the lifecycle has reached a terminal state."""
        return self._current_state in _TERMINAL_STATES

    def transition_to(
        self,
        new_state: TaskLifecycleState,
        *,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> LifecycleTransition:
        """Transition to a new state.

        Args:
            new_state: The target state.
            reason: Optional reason for the transition.
            metadata: Optional metadata for the transition.

        Returns:
            The recorded LifecycleTransition.

        Raises:
            ValueError: If the transition is invalid (not in the valid
                transitions map for the current state).
        """
        valid_targets = _VALID_TRANSITIONS.get(self._current_state, frozenset())

        if new_state not in valid_targets:
            raise ValueError(
                f"Invalid transition from {self._current_state.value} to "
                f"{new_state.value} for task '{self._task_id}'. "
                f"Valid targets from {self._current_state.value}: "
                f"{[s.value for s in valid_targets]}"
            )

        transition = LifecycleTransition(
            from_state=self._current_state,
            to_state=new_state,
            reason=reason,
            metadata=metadata or {},
        )

        self._transitions.append(transition)
        old_state = self._current_state
        self._current_state = new_state

        logger.info(
            "Task '%s' lifecycle: %s -> %s (reason: %s)",
            self._task_id,
            old_state.value,
            new_state.value,
            reason or "none",
        )

        return transition

    def to_audit_record(self) -> dict[str, Any]:
        """Convert the full lifecycle to an audit-friendly dict.

        Returns:
            Dictionary containing the complete lifecycle record with
            all transitions, timestamps, and the final state.
        """
        return {
            "task_id": self._task_id,
            "agent_id": self._agent_id,
            "action": self._action,
            "created_at": self._created_at.isoformat(),
            "final_state": self._current_state.value,
            "is_terminal": self.is_terminal,
            "transitions": [
                {
                    "from_state": t.from_state.value,
                    "to_state": t.to_state.value,
                    "timestamp": t.timestamp.isoformat(),
                    "reason": t.reason,
                    "metadata": t.metadata,
                }
                for t in self._transitions
            ],
        }
