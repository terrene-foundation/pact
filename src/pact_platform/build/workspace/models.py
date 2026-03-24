# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Workspace-as-knowledge-base model — manages agent team institutional memory.

Each workspace is a knowledge base for an agent team, with lifecycle phases
matching the CO methodology and a top-level state machine governing the
workspace's overall lifecycle (provisioning, active, archived, decommissioned).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from pact_platform.build.config.schema import WorkspaceConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidWorkspaceTransitionError(Exception):
    """Raised when an invalid workspace state transition is attempted."""


# ---------------------------------------------------------------------------
# Workspace State (top-level lifecycle)
# ---------------------------------------------------------------------------


class WorkspaceState(str, Enum):
    """Top-level lifecycle state for a workspace.

    PROVISIONING -> ACTIVE -> ARCHIVED -> ACTIVE (reactivation)
                          |-> DECOMMISSIONED
                 ARCHIVED -> DECOMMISSIONED
    """

    PROVISIONING = "provisioning"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DECOMMISSIONED = "decommissioned"


# Valid workspace state transitions.
_WORKSPACE_STATE_TRANSITIONS: dict[WorkspaceState, list[WorkspaceState]] = {
    WorkspaceState.PROVISIONING: [WorkspaceState.ACTIVE],
    WorkspaceState.ACTIVE: [WorkspaceState.ARCHIVED, WorkspaceState.DECOMMISSIONED],
    WorkspaceState.ARCHIVED: [WorkspaceState.ACTIVE, WorkspaceState.DECOMMISSIONED],
    WorkspaceState.DECOMMISSIONED: [],  # terminal
}


class StateTransitionRecord(BaseModel):
    """Record of a workspace state transition."""

    from_state: WorkspaceState
    to_state: WorkspaceState
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Workspace Phase (CO methodology cycle)
# ---------------------------------------------------------------------------


class WorkspacePhase(str, Enum):
    """Workspace lifecycle phases (aligned with CO methodology)."""

    ANALYZE = "analyze"
    PLAN = "plan"
    IMPLEMENT = "implement"
    VALIDATE = "validate"
    CODIFY = "codify"


# Valid phase transitions
PHASE_TRANSITIONS: dict[WorkspacePhase, list[WorkspacePhase]] = {
    WorkspacePhase.ANALYZE: [WorkspacePhase.PLAN],
    WorkspacePhase.PLAN: [WorkspacePhase.IMPLEMENT, WorkspacePhase.ANALYZE],
    WorkspacePhase.IMPLEMENT: [WorkspacePhase.VALIDATE, WorkspacePhase.PLAN],
    WorkspacePhase.VALIDATE: [WorkspacePhase.CODIFY, WorkspacePhase.IMPLEMENT],
    WorkspacePhase.CODIFY: [WorkspacePhase.ANALYZE],
}


class PhaseTransition(BaseModel):
    """Record of a workspace phase transition."""

    from_phase: WorkspacePhase
    to_phase: WorkspacePhase
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Workspace Model
# ---------------------------------------------------------------------------


class Workspace(BaseModel):
    """Runtime workspace with lifecycle management.

    The workspace has two layers of lifecycle:
    1. **Workspace state** (top-level): PROVISIONING -> ACTIVE -> ARCHIVED / DECOMMISSIONED
    2. **Phase cycle** (CO methodology): ANALYZE -> PLAN -> IMPLEMENT -> VALIDATE -> CODIFY

    Phase cycling is only allowed when workspace_state is ACTIVE.
    """

    config: WorkspaceConfig
    team_id: str | None = None
    workspace_state: WorkspaceState = WorkspaceState.PROVISIONING
    current_phase: WorkspacePhase = WorkspacePhase.ANALYZE
    phase_history: list[PhaseTransition] = Field(default_factory=list)
    state_history: list[StateTransitionRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def id(self) -> str:
        return self.config.id

    @property
    def path(self) -> str:
        return self.config.path

    # -------------------------------------------------------------------
    # Workspace State Transitions
    # -------------------------------------------------------------------

    def _transition_state(self, target: WorkspaceState, reason: str = "") -> StateTransitionRecord:
        """Internal: transition the workspace state.

        Raises:
            InvalidWorkspaceTransitionError: If the transition is not valid.
        """
        allowed = _WORKSPACE_STATE_TRANSITIONS.get(self.workspace_state, [])
        if target not in allowed:
            allowed_names = [s.value for s in allowed] if allowed else ["(none -- terminal state)"]
            raise InvalidWorkspaceTransitionError(
                f"Cannot transition workspace from {self.workspace_state.value} "
                f"to {target.value}. "
                f"Allowed transitions from {self.workspace_state.value}: "
                f"{', '.join(allowed_names)}"
            )

        record = StateTransitionRecord(
            from_state=self.workspace_state,
            to_state=target,
            reason=reason,
        )
        previous = self.workspace_state
        self.workspace_state = target
        self.last_activity = record.timestamp
        self.state_history.append(record)

        logger.info(
            "Workspace '%s' state: %s -> %s (reason: %s)",
            self.id,
            previous.value,
            target.value,
            reason or "(none)",
        )

        return record

    def activate(self, reason: str = "") -> StateTransitionRecord:
        """Transition from PROVISIONING or ARCHIVED to ACTIVE.

        Args:
            reason: Optional human-readable reason.

        Returns:
            StateTransitionRecord for the transition.

        Raises:
            InvalidWorkspaceTransitionError: If not in a state that can activate.
        """
        return self._transition_state(WorkspaceState.ACTIVE, reason)

    def archive(self, reason: str = "") -> StateTransitionRecord:
        """Transition from ACTIVE to ARCHIVED.

        Args:
            reason: Optional human-readable reason.

        Returns:
            StateTransitionRecord for the transition.

        Raises:
            InvalidWorkspaceTransitionError: If not ACTIVE.
        """
        return self._transition_state(WorkspaceState.ARCHIVED, reason)

    def reactivate(self, reason: str = "") -> StateTransitionRecord:
        """Transition from ARCHIVED back to ACTIVE.

        Args:
            reason: Optional human-readable reason.

        Returns:
            StateTransitionRecord for the transition.

        Raises:
            InvalidWorkspaceTransitionError: If not ARCHIVED.
        """
        if self.workspace_state != WorkspaceState.ARCHIVED:
            raise InvalidWorkspaceTransitionError(
                f"Cannot reactivate workspace from {self.workspace_state.value} state. "
                f"Workspace must be ARCHIVED to reactivate."
            )
        return self._transition_state(WorkspaceState.ACTIVE, reason)

    def decommission(self, reason: str = "") -> StateTransitionRecord:
        """Transition from ACTIVE or ARCHIVED to DECOMMISSIONED (terminal).

        Args:
            reason: Optional human-readable reason.

        Returns:
            StateTransitionRecord for the transition.

        Raises:
            InvalidWorkspaceTransitionError: If not ACTIVE or ARCHIVED.
        """
        return self._transition_state(WorkspaceState.DECOMMISSIONED, reason)

    # -------------------------------------------------------------------
    # Phase Transitions (CO Methodology Cycle)
    # -------------------------------------------------------------------

    def can_transition_to(self, target: WorkspacePhase) -> bool:
        """Check if transitioning to the target phase is allowed.

        Phase cycling is only allowed when workspace_state is ACTIVE.
        """
        if self.workspace_state != WorkspaceState.ACTIVE:
            return False
        allowed = PHASE_TRANSITIONS.get(self.current_phase, [])
        return target in allowed

    def transition_to(self, target: WorkspacePhase, reason: str = "") -> PhaseTransition:
        """Transition to a new phase.

        Phase cycling is only allowed when the workspace state is ACTIVE.

        Raises:
            InvalidWorkspaceTransitionError: If workspace is not ACTIVE.
            ValueError: If the phase transition is not valid.
        """
        if self.workspace_state != WorkspaceState.ACTIVE:
            raise InvalidWorkspaceTransitionError(
                f"Cannot cycle phases while workspace is in {self.workspace_state.value} state. "
                f"Workspace must be ACTIVE for phase transitions."
            )

        allowed = PHASE_TRANSITIONS.get(self.current_phase, [])
        if target not in allowed:
            allowed_names = [p.value for p in allowed]
            raise ValueError(
                f"Cannot transition from {self.current_phase.value} to {target.value}. "
                f"Allowed transitions: {allowed_names}"
            )

        transition = PhaseTransition(
            from_phase=self.current_phase,
            to_phase=target,
            reason=reason,
        )
        self.current_phase = target
        self.last_activity = transition.timestamp
        self.phase_history.append(transition)
        return transition

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Workspace Registry
# ---------------------------------------------------------------------------


class WorkspaceRegistry(BaseModel):
    """Registry of all active workspaces."""

    workspaces: dict[str, Workspace] = Field(default_factory=dict)

    def register(self, workspace: Workspace) -> None:
        self.workspaces[workspace.id] = workspace

    def get(self, workspace_id: str) -> Workspace | None:
        return self.workspaces.get(workspace_id)

    def list_active(self) -> list[Workspace]:
        return list(self.workspaces.values())

    def get_by_team(self, team_id: str) -> Workspace | None:
        for ws in self.workspaces.values():
            if ws.team_id == team_id:
                return ws
        return None
