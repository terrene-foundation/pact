# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Session management — tracks platform sessions with context preservation.

A PactSession represents a period of active work. Sessions contain
checkpoints (point-in-time snapshots) that capture which teams are active,
how many approvals are pending, and what agents are doing. When a session
ends, context is preserved for the next session's briefing.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Lifecycle state of a platform session."""

    ACTIVE = "active"
    ENDED = "ended"
    SUSPENDED = "suspended"


class SessionCheckpoint(BaseModel):
    """Point-in-time snapshot of platform state."""

    checkpoint_id: str = Field(default_factory=lambda: f"ck-{uuid4().hex[:8]}")
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    active_teams: list[str] = Field(default_factory=list)
    pending_approvals: int = 0
    agent_statuses: dict[str, str] = Field(default_factory=dict)  # agent_id -> status
    notes: str = ""


class PactSession(BaseModel):
    """A platform session tracking active work."""

    session_id: str = Field(default_factory=lambda: f"sess-{uuid4().hex[:8]}")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    state: SessionState = SessionState.ACTIVE
    checkpoints: list[SessionCheckpoint] = Field(default_factory=list)
    notes: str = ""


class SessionManager:
    """Manages platform sessions with context preservation.

    Handles session lifecycle (start, checkpoint, end) and generates
    briefings from the most recent checkpoint to support continuity
    across sessions.
    """

    def __init__(self) -> None:
        self._sessions: list[PactSession] = []
        self._current: PactSession | None = None

    def start_session(self) -> PactSession:
        """Start a new session, ending any currently active session.

        Returns:
            The newly created active PactSession.
        """
        # End previous session if one is active
        if self._current is not None and self._current.state == SessionState.ACTIVE:
            self._current.state = SessionState.ENDED
            self._current.ended_at = datetime.now(UTC)
            logger.info(
                "Auto-ended previous session: session_id=%s",
                self._current.session_id,
            )

        session = PactSession()
        self._sessions.append(session)
        self._current = session
        logger.info("Session started: session_id=%s", session.session_id)
        return session

    def checkpoint(
        self,
        active_teams: list[str] | None = None,
        pending_approvals: int = 0,
        agent_statuses: dict[str, str] | None = None,
        notes: str = "",
    ) -> SessionCheckpoint:
        """Create a checkpoint of current state.

        Args:
            active_teams: List of active team IDs.
            pending_approvals: Number of pending approval items.
            agent_statuses: Map of agent_id to status string.
            notes: Free-form notes about current state.

        Returns:
            The newly created SessionCheckpoint.

        Raises:
            ValueError: If no active session exists.
        """
        if self._current is None or self._current.state != SessionState.ACTIVE:
            raise ValueError("No active session. Call start_session() first.")

        cp = SessionCheckpoint(
            session_id=self._current.session_id,
            active_teams=active_teams if active_teams is not None else [],
            pending_approvals=pending_approvals,
            agent_statuses=agent_statuses if agent_statuses is not None else {},
            notes=notes,
        )
        self._current.checkpoints.append(cp)
        logger.info(
            "Checkpoint created: checkpoint_id=%s session_id=%s",
            cp.checkpoint_id,
            self._current.session_id,
        )
        return cp

    def end_session(self, notes: str = "") -> PactSession:
        """End current session with a final checkpoint.

        Args:
            notes: Notes to attach to the ended session.

        Returns:
            The ended PactSession.

        Raises:
            ValueError: If no active session exists.
        """
        if self._current is None or self._current.state != SessionState.ACTIVE:
            raise ValueError("No active session to end.")

        # Create a final checkpoint to capture end state
        self.checkpoint(notes=f"Session ended: {notes}" if notes else "Session ended")

        self._current.state = SessionState.ENDED
        self._current.ended_at = datetime.now(UTC)
        self._current.notes = notes
        ended = self._current
        self._current = None
        logger.info("Session ended: session_id=%s", ended.session_id)
        return ended

    @property
    def current_session(self) -> PactSession | None:
        """Get the active session, or None if no session is active."""
        return self._current

    def get_last_checkpoint(self) -> SessionCheckpoint | None:
        """Get most recent checkpoint across all sessions.

        Returns:
            The most recent SessionCheckpoint, or None if no checkpoints exist.
        """
        all_checkpoints: list[SessionCheckpoint] = []
        for session in self._sessions:
            all_checkpoints.extend(session.checkpoints)

        if not all_checkpoints:
            return None

        return max(all_checkpoints, key=lambda cp: cp.created_at)

    def generate_briefing(self) -> str:
        """Generate session briefing from last checkpoint.

        Produces a human-readable summary of the platform's last known state,
        suitable for starting a new session with context.

        Returns:
            A formatted briefing string.
        """
        last_cp = self.get_last_checkpoint()

        if last_cp is None:
            return "No previous session data. This is a fresh start."

        lines: list[str] = []
        lines.append("Session Briefing")
        lines.append("=" * 40)
        lines.append(f"Last checkpoint: {last_cp.created_at.isoformat()}")

        if last_cp.active_teams:
            lines.append(f"Active teams: {', '.join(last_cp.active_teams)}")
        else:
            lines.append("Active teams: none")

        lines.append(f"Pending approvals: {last_cp.pending_approvals}")

        if last_cp.agent_statuses:
            lines.append("Agent statuses:")
            for agent_id, status in last_cp.agent_statuses.items():
                lines.append(f"  {agent_id}: {status}")

        if last_cp.notes:
            lines.append(f"Notes: {last_cp.notes}")

        return "\n".join(lines)


# Backward-compatible alias (renamed in TODO-0004)
PlatformSession = PactSession
