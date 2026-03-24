# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Workspace Lifecycle State Machine (M14 Task 1403)."""

import pytest

from pact_platform.build.config.schema import WorkspaceConfig
from pact_platform.build.workspace.models import (
    InvalidWorkspaceTransitionError,
    Workspace,
    WorkspacePhase,
    WorkspaceState,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ws_config():
    return WorkspaceConfig(id="ws-test", path="workspaces/test/")


@pytest.fixture()
def workspace(ws_config):
    return Workspace(config=ws_config)


# ---------------------------------------------------------------------------
# Test: Workspace State Enum
# ---------------------------------------------------------------------------


class TestWorkspaceStateEnum:
    def test_provisioning_state_exists(self):
        assert WorkspaceState.PROVISIONING.value == "provisioning"

    def test_active_state_exists(self):
        assert WorkspaceState.ACTIVE.value == "active"

    def test_archived_state_exists(self):
        assert WorkspaceState.ARCHIVED.value == "archived"

    def test_decommissioned_state_exists(self):
        assert WorkspaceState.DECOMMISSIONED.value == "decommissioned"


# ---------------------------------------------------------------------------
# Test: Initial State
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_default_state_is_provisioning(self, workspace):
        assert workspace.workspace_state == WorkspaceState.PROVISIONING

    def test_custom_initial_state(self, ws_config):
        ws = Workspace(config=ws_config, workspace_state=WorkspaceState.ACTIVE)
        assert ws.workspace_state == WorkspaceState.ACTIVE


# ---------------------------------------------------------------------------
# Test: Valid State Transitions
# ---------------------------------------------------------------------------


class TestValidStateTransitions:
    def test_provisioning_to_active(self, workspace):
        workspace.activate()
        assert workspace.workspace_state == WorkspaceState.ACTIVE

    def test_active_to_archived(self, workspace):
        workspace.activate()
        workspace.archive()
        assert workspace.workspace_state == WorkspaceState.ARCHIVED

    def test_archived_to_active_reactivation(self, workspace):
        workspace.activate()
        workspace.archive()
        workspace.reactivate()
        assert workspace.workspace_state == WorkspaceState.ACTIVE

    def test_active_to_decommissioned(self, workspace):
        workspace.activate()
        workspace.decommission()
        assert workspace.workspace_state == WorkspaceState.DECOMMISSIONED

    def test_archived_to_decommissioned(self, workspace):
        workspace.activate()
        workspace.archive()
        workspace.decommission()
        assert workspace.workspace_state == WorkspaceState.DECOMMISSIONED


# ---------------------------------------------------------------------------
# Test: Invalid State Transitions
# ---------------------------------------------------------------------------


class TestInvalidStateTransitions:
    def test_provisioning_to_archived_rejected(self, workspace):
        with pytest.raises(InvalidWorkspaceTransitionError):
            workspace.archive()

    def test_provisioning_to_decommissioned_rejected(self, workspace):
        with pytest.raises(InvalidWorkspaceTransitionError):
            workspace.decommission()

    def test_decommissioned_is_terminal(self, workspace):
        workspace.activate()
        workspace.decommission()
        with pytest.raises(InvalidWorkspaceTransitionError):
            workspace.activate()

    def test_decommissioned_to_archived_rejected(self, workspace):
        workspace.activate()
        workspace.decommission()
        with pytest.raises(InvalidWorkspaceTransitionError):
            workspace.archive()

    def test_decommissioned_to_reactivate_rejected(self, workspace):
        workspace.activate()
        workspace.decommission()
        with pytest.raises(InvalidWorkspaceTransitionError):
            workspace.reactivate()

    def test_archived_to_archived_rejected(self, workspace):
        workspace.activate()
        workspace.archive()
        with pytest.raises(InvalidWorkspaceTransitionError):
            workspace.archive()

    def test_provisioning_to_reactivate_rejected(self, workspace):
        with pytest.raises(InvalidWorkspaceTransitionError):
            workspace.reactivate()


# ---------------------------------------------------------------------------
# Test: Phase Cycling Only When Active
# ---------------------------------------------------------------------------


class TestPhaseCyclingOnlyWhenActive:
    def test_phase_transition_allowed_when_active(self, workspace):
        workspace.activate()
        workspace.transition_to(WorkspacePhase.PLAN)
        assert workspace.current_phase == WorkspacePhase.PLAN

    def test_phase_transition_blocked_when_provisioning(self, workspace):
        with pytest.raises(InvalidWorkspaceTransitionError, match="ACTIVE"):
            workspace.transition_to(WorkspacePhase.PLAN)

    def test_phase_transition_blocked_when_archived(self, workspace):
        workspace.activate()
        workspace.archive()
        with pytest.raises(InvalidWorkspaceTransitionError, match="ACTIVE"):
            workspace.transition_to(WorkspacePhase.PLAN)

    def test_phase_transition_blocked_when_decommissioned(self, workspace):
        workspace.activate()
        workspace.decommission()
        with pytest.raises(InvalidWorkspaceTransitionError, match="ACTIVE"):
            workspace.transition_to(WorkspacePhase.PLAN)

    def test_phase_transition_allowed_after_reactivation(self, workspace):
        workspace.activate()
        workspace.transition_to(WorkspacePhase.PLAN)
        workspace.archive()
        workspace.reactivate()
        # Phase should be preserved, and transitions should work
        workspace.transition_to(WorkspacePhase.IMPLEMENT)
        assert workspace.current_phase == WorkspacePhase.IMPLEMENT


# ---------------------------------------------------------------------------
# Test: State Transition History
# ---------------------------------------------------------------------------


class TestStateTransitionHistory:
    def test_state_history_starts_empty(self, workspace):
        assert workspace.state_history == []

    def test_state_history_records_activation(self, workspace):
        workspace.activate()
        assert len(workspace.state_history) == 1
        record = workspace.state_history[0]
        assert record.from_state == WorkspaceState.PROVISIONING
        assert record.to_state == WorkspaceState.ACTIVE

    def test_state_history_accumulates(self, workspace):
        workspace.activate()
        workspace.archive()
        workspace.reactivate()
        assert len(workspace.state_history) == 3

    def test_state_history_has_timestamps(self, workspace):
        workspace.activate()
        assert workspace.state_history[0].timestamp is not None


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_multiple_archive_reactivate_cycles(self, workspace):
        workspace.activate()
        workspace.archive()
        workspace.reactivate()
        workspace.archive()
        workspace.reactivate()
        assert workspace.workspace_state == WorkspaceState.ACTIVE
        assert len(workspace.state_history) == 5

    def test_phase_preserved_across_archive_reactivate(self, workspace):
        workspace.activate()
        workspace.transition_to(WorkspacePhase.PLAN)
        workspace.transition_to(WorkspacePhase.IMPLEMENT)
        workspace.archive()
        workspace.reactivate()
        assert workspace.current_phase == WorkspacePhase.IMPLEMENT

    def test_error_message_is_informative(self, workspace):
        with pytest.raises(InvalidWorkspaceTransitionError) as exc_info:
            workspace.archive()
        error_msg = str(exc_info.value)
        assert "PROVISIONING" in error_msg or "provisioning" in error_msg
