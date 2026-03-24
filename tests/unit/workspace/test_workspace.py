# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for workspace model."""

import pytest

from pact_platform.build.config.schema import WorkspaceConfig
from pact_platform.build.workspace.models import (
    Workspace,
    WorkspacePhase,
    WorkspaceRegistry,
)


def _active_workspace(ws_id: str = "ws-1") -> Workspace:
    """Create a workspace and activate it for phase transition tests."""
    ws = Workspace(config=WorkspaceConfig(id=ws_id, path=f"workspaces/{ws_id}/"))
    ws.activate(reason="test setup")
    return ws


class TestWorkspaceLifecycle:
    def test_starts_in_analyze(self):
        ws = Workspace(config=WorkspaceConfig(id="ws-1", path="workspaces/test/"))
        assert ws.current_phase == WorkspacePhase.ANALYZE

    def test_valid_transition(self):
        ws = _active_workspace()
        ws.transition_to(WorkspacePhase.PLAN, "Analysis complete")
        assert ws.current_phase == WorkspacePhase.PLAN

    def test_invalid_transition_rejected(self):
        ws = _active_workspace()
        with pytest.raises(ValueError, match="Cannot transition"):
            ws.transition_to(WorkspacePhase.CODIFY)

    def test_full_lifecycle(self):
        ws = _active_workspace()
        ws.transition_to(WorkspacePhase.PLAN)
        ws.transition_to(WorkspacePhase.IMPLEMENT)
        ws.transition_to(WorkspacePhase.VALIDATE)
        ws.transition_to(WorkspacePhase.CODIFY)
        ws.transition_to(WorkspacePhase.ANALYZE)  # cycle back
        assert ws.current_phase == WorkspacePhase.ANALYZE
        assert len(ws.phase_history) == 5

    def test_can_go_back_to_plan(self):
        ws = _active_workspace()
        ws.transition_to(WorkspacePhase.PLAN)
        ws.transition_to(WorkspacePhase.IMPLEMENT)
        ws.transition_to(WorkspacePhase.PLAN)  # go back
        assert ws.current_phase == WorkspacePhase.PLAN


class TestWorkspaceRegistry:
    def test_register_and_get(self):
        reg = WorkspaceRegistry()
        ws = Workspace(config=WorkspaceConfig(id="ws-1", path="workspaces/test/"))
        reg.register(ws)
        assert reg.get("ws-1") is not None
        assert reg.get("nonexistent") is None

    def test_get_by_team(self):
        reg = WorkspaceRegistry()
        ws = Workspace(
            config=WorkspaceConfig(id="ws-1", path="workspaces/test/"),
            team_id="dm-team",
        )
        reg.register(ws)
        found = reg.get_by_team("dm-team")
        assert found is not None
        assert found.id == "ws-1"

    def test_list_active(self):
        reg = WorkspaceRegistry()
        reg.register(Workspace(config=WorkspaceConfig(id="ws-1", path="workspaces/a/")))
        reg.register(Workspace(config=WorkspaceConfig(id="ws-2", path="workspaces/b/")))
        assert len(reg.list_active()) == 2
