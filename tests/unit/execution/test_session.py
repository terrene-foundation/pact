# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for session management (Task 405).

Covers: start, checkpoint, end, briefing generation,
session state transitions, and context preservation.
"""

from datetime import UTC, datetime

import pytest

from pact_platform.use.execution.session import (
    PactSession,
    SessionCheckpoint,
    SessionManager,
    SessionState,
)


class TestSessionState:
    """Tests for session state enum values."""

    def test_all_states_exist(self):
        assert SessionState.ACTIVE == "active"
        assert SessionState.ENDED == "ended"
        assert SessionState.SUSPENDED == "suspended"


class TestSessionCheckpoint:
    """Tests for the SessionCheckpoint model."""

    def test_defaults(self):
        cp = SessionCheckpoint(session_id="sess-abc")
        assert cp.checkpoint_id.startswith("ck-")
        assert cp.session_id == "sess-abc"
        assert cp.active_teams == []
        assert cp.pending_approvals == 0
        assert cp.agent_statuses == {}
        assert cp.notes == ""

    def test_custom_fields(self):
        cp = SessionCheckpoint(
            session_id="sess-abc",
            active_teams=["team-ops", "team-dev"],
            pending_approvals=3,
            agent_statuses={"agent-1": "active", "agent-2": "suspended"},
            notes="Mid-sprint checkpoint",
        )
        assert cp.active_teams == ["team-ops", "team-dev"]
        assert cp.pending_approvals == 3
        assert cp.agent_statuses["agent-2"] == "suspended"
        assert cp.notes == "Mid-sprint checkpoint"


class TestPactSession:
    """Tests for the PactSession model."""

    def test_defaults(self):
        session = PactSession()
        assert session.session_id.startswith("sess-")
        assert session.state == SessionState.ACTIVE
        assert session.ended_at is None
        assert session.checkpoints == []
        assert session.notes == ""

    def test_started_at_is_set(self):
        before = datetime.now(UTC)
        session = PactSession()
        after = datetime.now(UTC)
        assert before <= session.started_at <= after


class TestSessionManagerStart:
    """Tests for starting sessions."""

    def test_start_session_creates_active_session(self):
        mgr = SessionManager()
        session = mgr.start_session()
        assert isinstance(session, PactSession)
        assert session.state == SessionState.ACTIVE
        assert mgr.current_session is session

    def test_start_session_ends_previous(self):
        mgr = SessionManager()
        s1 = mgr.start_session()
        s2 = mgr.start_session()
        assert s1.state == SessionState.ENDED
        assert s1.ended_at is not None
        assert mgr.current_session is s2

    def test_start_session_tracks_history(self):
        mgr = SessionManager()
        mgr.start_session()
        mgr.start_session()
        mgr.start_session()
        assert len(mgr._sessions) == 3


class TestSessionManagerCheckpoint:
    """Tests for creating checkpoints."""

    def test_checkpoint_creates_snapshot(self):
        mgr = SessionManager()
        mgr.start_session()
        cp = mgr.checkpoint(
            active_teams=["team-ops"],
            pending_approvals=2,
            agent_statuses={"agent-1": "active"},
            notes="Check-in",
        )
        assert isinstance(cp, SessionCheckpoint)
        assert cp.active_teams == ["team-ops"]
        assert cp.pending_approvals == 2
        assert cp.notes == "Check-in"

    def test_checkpoint_added_to_session(self):
        mgr = SessionManager()
        session = mgr.start_session()
        mgr.checkpoint(active_teams=["team-ops"])
        assert len(session.checkpoints) == 1

    def test_checkpoint_without_active_session_raises(self):
        mgr = SessionManager()
        with pytest.raises(ValueError, match="[Nn]o active session"):
            mgr.checkpoint()

    def test_multiple_checkpoints(self):
        mgr = SessionManager()
        session = mgr.start_session()
        mgr.checkpoint(notes="first")
        mgr.checkpoint(notes="second")
        assert len(session.checkpoints) == 2
        assert session.checkpoints[0].notes == "first"
        assert session.checkpoints[1].notes == "second"


class TestSessionManagerEnd:
    """Tests for ending sessions."""

    def test_end_session(self):
        mgr = SessionManager()
        mgr.start_session()
        ended = mgr.end_session(notes="Done for the day")
        assert ended.state == SessionState.ENDED
        assert ended.ended_at is not None
        assert ended.notes == "Done for the day"
        assert mgr.current_session is None

    def test_end_session_without_active_raises(self):
        mgr = SessionManager()
        with pytest.raises(ValueError, match="[Nn]o active session"):
            mgr.end_session()

    def test_end_session_creates_final_checkpoint(self):
        mgr = SessionManager()
        mgr.start_session()
        ended = mgr.end_session(notes="wrap-up")
        # End session should create a final checkpoint
        assert len(ended.checkpoints) >= 1


class TestSessionManagerLastCheckpoint:
    """Tests for retrieving the most recent checkpoint."""

    def test_get_last_checkpoint_none_when_empty(self):
        mgr = SessionManager()
        assert mgr.get_last_checkpoint() is None

    def test_get_last_checkpoint_from_current(self):
        mgr = SessionManager()
        mgr.start_session()
        mgr.checkpoint(notes="cp1")
        mgr.checkpoint(notes="cp2")
        last = mgr.get_last_checkpoint()
        assert last is not None
        assert last.notes == "cp2"

    def test_get_last_checkpoint_from_ended_session(self):
        mgr = SessionManager()
        mgr.start_session()
        mgr.checkpoint(notes="from-ended")
        mgr.end_session(notes="done")
        last = mgr.get_last_checkpoint()
        assert last is not None


class TestSessionManagerBriefing:
    """Tests for generating session briefings."""

    def test_briefing_with_no_sessions(self):
        mgr = SessionManager()
        briefing = mgr.generate_briefing()
        assert isinstance(briefing, str)
        assert len(briefing) > 0  # Should produce meaningful output even when empty

    def test_briefing_with_checkpoint(self):
        mgr = SessionManager()
        mgr.start_session()
        mgr.checkpoint(
            active_teams=["team-ops", "team-dev"],
            pending_approvals=3,
            agent_statuses={"agent-1": "active", "agent-2": "suspended"},
            notes="Sprint in progress",
        )
        briefing = mgr.generate_briefing()
        assert "team-ops" in briefing
        assert "team-dev" in briefing
        assert "3" in briefing  # pending approvals count
        assert "Sprint in progress" in briefing

    def test_briefing_after_end(self):
        mgr = SessionManager()
        mgr.start_session()
        mgr.checkpoint(
            active_teams=["team-ops"],
            notes="Last state before shutdown",
        )
        mgr.end_session(notes="Session closed")
        briefing = mgr.generate_briefing()
        assert isinstance(briefing, str)
        assert len(briefing) > 0
