# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the agent registry (Task 407).

Covers: register, deregister, get, find by capability, team lookup,
status updates, active agents, touch, and stale detection.
"""

from datetime import UTC, datetime, timedelta

import pytest

from pact_platform.use.execution.registry import AgentRecord, AgentRegistry, AgentStatus


class TestAgentStatus:
    """Tests for agent status enum values."""

    def test_all_statuses_exist(self):
        assert AgentStatus.ACTIVE == "active"
        assert AgentStatus.SUSPENDED == "suspended"
        assert AgentStatus.REVOKED == "revoked"
        assert AgentStatus.INACTIVE == "inactive"


class TestAgentRecord:
    """Tests for the AgentRecord model."""

    def test_defaults(self):
        rec = AgentRecord(agent_id="agent-1", name="Analyst", role="data-analysis")
        assert rec.agent_id == "agent-1"
        assert rec.name == "Analyst"
        assert rec.role == "data-analysis"
        assert rec.team_id == ""
        assert rec.capabilities == []
        assert rec.current_posture == "supervised"
        assert rec.status == AgentStatus.ACTIVE
        assert rec.last_active_at is None
        assert rec.envelope_id is None

    def test_custom_fields(self):
        rec = AgentRecord(
            agent_id="agent-1",
            name="Deployer",
            role="deployment",
            team_id="team-ops",
            capabilities=["deploy", "rollback"],
            current_posture="delegated",
            envelope_id="env-ops",
        )
        assert rec.team_id == "team-ops"
        assert rec.capabilities == ["deploy", "rollback"]
        assert rec.current_posture == "delegated"
        assert rec.envelope_id == "env-ops"

    def test_registered_at_is_set(self):
        before = datetime.now(UTC)
        rec = AgentRecord(agent_id="a", name="A", role="r")
        after = datetime.now(UTC)
        assert before <= rec.registered_at <= after


class TestAgentRegistryRegister:
    """Tests for registering agents."""

    def test_register_returns_record(self):
        registry = AgentRegistry()
        rec = registry.register(agent_id="agent-1", name="Analyst", role="analysis")
        assert isinstance(rec, AgentRecord)
        assert rec.agent_id == "agent-1"
        assert rec.name == "Analyst"
        assert rec.role == "analysis"

    def test_register_with_optional_fields(self):
        registry = AgentRegistry()
        rec = registry.register(
            agent_id="agent-1",
            name="Deployer",
            role="deployment",
            team_id="team-ops",
            capabilities=["deploy", "monitor"],
            posture="delegated",
        )
        assert rec.team_id == "team-ops"
        assert rec.capabilities == ["deploy", "monitor"]
        assert rec.current_posture == "delegated"

    def test_register_duplicate_raises(self):
        registry = AgentRegistry()
        registry.register(agent_id="agent-1", name="A", role="r")
        with pytest.raises(ValueError, match="already registered"):
            registry.register(agent_id="agent-1", name="B", role="r")


class TestAgentRegistryDeregister:
    """Tests for deregistering agents."""

    def test_deregister_removes_agent(self):
        registry = AgentRegistry()
        registry.register(agent_id="agent-1", name="A", role="r")
        registry.deregister("agent-1")
        assert registry.get("agent-1") is None

    def test_deregister_nonexistent_raises(self):
        registry = AgentRegistry()
        with pytest.raises(ValueError, match="not found"):
            registry.deregister("nonexistent")


class TestAgentRegistryGet:
    """Tests for looking up agents."""

    def test_get_existing(self):
        registry = AgentRegistry()
        registry.register(agent_id="agent-1", name="A", role="r")
        rec = registry.get("agent-1")
        assert rec is not None
        assert rec.agent_id == "agent-1"

    def test_get_nonexistent_returns_none(self):
        registry = AgentRegistry()
        assert registry.get("nonexistent") is None


class TestAgentRegistryTeam:
    """Tests for team-based agent lookup."""

    def test_get_team(self):
        registry = AgentRegistry()
        registry.register(agent_id="a1", name="A", role="r", team_id="team-ops")
        registry.register(agent_id="a2", name="B", role="r", team_id="team-ops")
        registry.register(agent_id="a3", name="C", role="r", team_id="team-dev")
        team = registry.get_team("team-ops")
        assert len(team) == 2
        assert all(r.team_id == "team-ops" for r in team)

    def test_get_team_empty(self):
        registry = AgentRegistry()
        assert registry.get_team("nonexistent") == []


class TestAgentRegistryCapability:
    """Tests for capability-based agent lookup."""

    def test_find_by_capability(self):
        registry = AgentRegistry()
        registry.register(agent_id="a1", name="A", role="r", capabilities=["deploy", "monitor"])
        registry.register(agent_id="a2", name="B", role="r", capabilities=["deploy"])
        registry.register(agent_id="a3", name="C", role="r", capabilities=["analyze"])
        deployers = registry.find_by_capability("deploy")
        assert len(deployers) == 2

    def test_find_by_capability_no_match(self):
        registry = AgentRegistry()
        registry.register(agent_id="a1", name="A", role="r", capabilities=["deploy"])
        assert registry.find_by_capability("nonexistent") == []


class TestAgentRegistryStatus:
    """Tests for status updates."""

    def test_update_status(self):
        registry = AgentRegistry()
        registry.register(agent_id="agent-1", name="A", role="r")
        registry.update_status("agent-1", AgentStatus.SUSPENDED)
        rec = registry.get("agent-1")
        assert rec is not None
        assert rec.status == AgentStatus.SUSPENDED

    def test_update_status_nonexistent_raises(self):
        registry = AgentRegistry()
        with pytest.raises(ValueError, match="not found"):
            registry.update_status("nonexistent", AgentStatus.REVOKED)


class TestAgentRegistryActiveAgents:
    """Tests for listing active agents."""

    def test_active_agents(self):
        registry = AgentRegistry()
        registry.register(agent_id="a1", name="A", role="r")
        registry.register(agent_id="a2", name="B", role="r")
        registry.register(agent_id="a3", name="C", role="r")
        registry.update_status("a2", AgentStatus.SUSPENDED)
        active = registry.active_agents()
        assert len(active) == 2
        assert all(r.status == AgentStatus.ACTIVE for r in active)

    def test_active_agents_empty(self):
        registry = AgentRegistry()
        assert registry.active_agents() == []


class TestAgentRegistryTouch:
    """Tests for updating last-active timestamp."""

    def test_touch_updates_timestamp(self):
        registry = AgentRegistry()
        registry.register(agent_id="agent-1", name="A", role="r")
        before = datetime.now(UTC)
        registry.touch("agent-1")
        after = datetime.now(UTC)
        rec = registry.get("agent-1")
        assert rec is not None
        assert rec.last_active_at is not None
        assert before <= rec.last_active_at <= after

    def test_touch_nonexistent_raises(self):
        registry = AgentRegistry()
        with pytest.raises(ValueError, match="not found"):
            registry.touch("nonexistent")


class TestAgentRegistryStale:
    """Tests for detecting stale (inactive) agents."""

    def test_stale_agents_detects_inactive(self):
        registry = AgentRegistry()
        rec = registry.register(agent_id="agent-1", name="A", role="r")
        # Manually set last_active_at to 48 hours ago
        rec.last_active_at = datetime.now(UTC) - timedelta(hours=48)
        stale = registry.stale_agents(threshold_hours=24)
        assert len(stale) == 1
        assert stale[0].agent_id == "agent-1"

    def test_stale_agents_excludes_recent(self):
        registry = AgentRegistry()
        registry.register(agent_id="agent-1", name="A", role="r")
        registry.touch("agent-1")
        stale = registry.stale_agents(threshold_hours=24)
        assert len(stale) == 0

    def test_stale_agents_includes_never_active(self):
        """Agents that were never active (last_active_at is None) should be
        considered stale if they were registered before the threshold."""
        registry = AgentRegistry()
        rec = registry.register(agent_id="agent-1", name="A", role="r")
        # Backdate registration to simulate an old agent
        rec.registered_at = datetime.now(UTC) - timedelta(hours=48)
        stale = registry.stale_agents(threshold_hours=24)
        assert len(stale) == 1

    def test_stale_agents_excludes_non_active_status(self):
        """Only ACTIVE agents should be checked for staleness."""
        registry = AgentRegistry()
        rec = registry.register(agent_id="agent-1", name="A", role="r")
        rec.last_active_at = datetime.now(UTC) - timedelta(hours=48)
        registry.update_status("agent-1", AgentStatus.REVOKED)
        stale = registry.stale_agents(threshold_hours=24)
        assert len(stale) == 0
