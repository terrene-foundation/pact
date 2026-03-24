# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for PACT API layer (Task 408).

Tests endpoint definitions and PactAPI handler logic using plain
dataclasses/Pydantic — not FastAPI or Nexus (which are not installed).
"""

import pytest

from pact_platform.trust.store.cost_tracking import CostTracker
from pact_platform.use.api.endpoints import (
    ApiResponse,
    EndpointDefinition,
    PactAPI,
)
from pact_platform.use.execution.approval import ApprovalQueue, UrgencyLevel
from pact_platform.use.execution.registry import AgentRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry():
    """Registry with two agents in one team."""
    reg = AgentRegistry()
    reg.register(
        agent_id="agent-1",
        name="Agent One",
        role="Testing",
        team_id="team-alpha",
        capabilities=["read", "write"],
        posture="supervised",
    )
    reg.register(
        agent_id="agent-2",
        name="Agent Two",
        role="Analytics",
        team_id="team-alpha",
        capabilities=["read"],
        posture="supervised",
    )
    reg.register(
        agent_id="agent-3",
        name="Agent Three",
        role="Lead",
        team_id="team-beta",
        capabilities=["approve"],
        posture="delegated",
    )
    return reg


@pytest.fixture()
def approval_queue():
    """Approval queue with one pending action."""
    q = ApprovalQueue()
    q.submit(
        agent_id="agent-1",
        action="publish_post",
        reason="External publication requires approval",
        team_id="team-alpha",
        urgency=UrgencyLevel.STANDARD,
    )
    return q


@pytest.fixture()
def cost_tracker():
    """Empty cost tracker."""
    return CostTracker()


@pytest.fixture()
def api(registry, approval_queue, cost_tracker):
    """PactAPI wired with real components."""
    return PactAPI(
        registry=registry,
        approval_queue=approval_queue,
        cost_tracker=cost_tracker,
    )


# ---------------------------------------------------------------------------
# Test: Endpoint Definitions
# ---------------------------------------------------------------------------


class TestEndpointDefinitions:
    """Endpoint schema definitions exist and have correct structure."""

    def test_endpoint_definition_model(self):
        """EndpointDefinition holds method, path, and description."""
        ep = EndpointDefinition(
            method="GET",
            path="/api/v1/teams",
            description="List all active teams",
        )
        assert ep.method == "GET"
        assert ep.path == "/api/v1/teams"
        assert ep.description == "List all active teams"

    def test_api_response_success(self):
        """ApiResponse wraps data with status info."""
        resp = ApiResponse(status="ok", data={"teams": []})
        assert resp.status == "ok"
        assert resp.data == {"teams": []}
        assert resp.error is None

    def test_api_response_error(self):
        """ApiResponse can carry error information."""
        resp = ApiResponse(status="error", data=None, error="Not found")
        assert resp.status == "error"
        assert resp.error == "Not found"

    def test_platform_api_lists_endpoints(self, api):
        """PactAPI.endpoints returns all defined endpoint schemas."""
        endpoints = api.endpoints
        assert isinstance(endpoints, list)
        assert len(endpoints) >= 7  # at least the 7 endpoints from todo

        paths = [ep.path for ep in endpoints]
        assert "/api/v1/teams" in paths
        assert "/api/v1/agents/{agent_id}/status" in paths
        assert "/api/v1/agents/{agent_id}/approve/{action_id}" in paths
        assert "/api/v1/agents/{agent_id}/reject/{action_id}" in paths
        assert "/api/v1/held-actions" in paths
        assert "/api/v1/cost/report" in paths


# ---------------------------------------------------------------------------
# Test: List Teams
# ---------------------------------------------------------------------------


class TestListTeams:
    def test_list_teams_returns_unique_team_ids(self, api):
        """list_teams() returns unique team IDs from the registry."""
        resp = api.list_teams()
        assert resp.status == "ok"
        teams = resp.data["teams"]
        assert isinstance(teams, list)
        assert "team-alpha" in teams
        assert "team-beta" in teams
        assert len(teams) == 2

    def test_list_teams_empty_registry(self, approval_queue, cost_tracker):
        """list_teams() returns empty list when no agents registered."""
        empty_reg = AgentRegistry()
        api = PactAPI(
            registry=empty_reg,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
        )
        resp = api.list_teams()
        assert resp.status == "ok"
        assert resp.data["teams"] == []


# ---------------------------------------------------------------------------
# Test: List Team Agents
# ---------------------------------------------------------------------------


class TestListTeamAgents:
    def test_list_agents_for_team(self, api):
        """list_agents(team_id) returns agents in that team."""
        resp = api.list_agents("team-alpha")
        assert resp.status == "ok"
        agents = resp.data["agents"]
        assert len(agents) == 2
        ids = [a["agent_id"] for a in agents]
        assert "agent-1" in ids
        assert "agent-2" in ids

    def test_list_agents_unknown_team_returns_empty(self, api):
        """list_agents() for unknown team returns empty list, not error."""
        resp = api.list_agents("team-nonexistent")
        assert resp.status == "ok"
        assert resp.data["agents"] == []


# ---------------------------------------------------------------------------
# Test: Agent Status
# ---------------------------------------------------------------------------


class TestAgentStatus:
    def test_agent_status_found(self, api):
        """agent_status() returns agent details."""
        resp = api.agent_status("agent-1")
        assert resp.status == "ok"
        data = resp.data
        assert data["agent_id"] == "agent-1"
        assert data["name"] == "Agent One"
        assert data["role"] == "Testing"
        assert data["team_id"] == "team-alpha"
        assert data["posture"] == "supervised"
        assert "status" in data

    def test_agent_status_not_found(self, api):
        """agent_status() for unknown agent returns error."""
        resp = api.agent_status("nonexistent-agent")
        assert resp.status == "error"
        assert resp.error is not None
        assert "not found" in resp.error.lower()


# ---------------------------------------------------------------------------
# Test: Approve / Reject Action
# ---------------------------------------------------------------------------


class TestApproveRejectAction:
    def test_approve_action(self, api, approval_queue):
        """approve_action() approves a pending action."""
        action_id = approval_queue.pending[0].action_id
        resp = api.approve_action(
            agent_id="agent-1",
            action_id=action_id,
            approver_id="human-001",
            reason="Looks good",
        )
        assert resp.status == "ok"
        assert resp.data["action_id"] == action_id
        assert resp.data["decision"] == "approved"

    def test_approve_nonexistent_action_returns_error(self, api):
        """approve_action() for unknown action returns error."""
        resp = api.approve_action(
            agent_id="agent-1",
            action_id="pa-nonexistent",
            approver_id="human-001",
        )
        assert resp.status == "error"
        assert resp.error is not None

    def test_reject_action(self, api, approval_queue):
        """reject_action() rejects a pending action."""
        action_id = approval_queue.pending[0].action_id
        resp = api.reject_action(
            agent_id="agent-1",
            action_id=action_id,
            approver_id="human-001",
            reason="Not appropriate",
        )
        assert resp.status == "ok"
        assert resp.data["action_id"] == action_id
        assert resp.data["decision"] == "rejected"

    def test_reject_nonexistent_action_returns_error(self, api):
        """reject_action() for unknown action returns error."""
        resp = api.reject_action(
            agent_id="agent-1",
            action_id="pa-nonexistent",
            approver_id="human-001",
        )
        assert resp.status == "error"
        assert resp.error is not None


# ---------------------------------------------------------------------------
# Test: Held Actions
# ---------------------------------------------------------------------------


class TestHeldActions:
    def test_held_actions_returns_pending(self, api, approval_queue):
        """held_actions() returns all pending items from the approval queue."""
        resp = api.held_actions()
        assert resp.status == "ok"
        actions = resp.data["actions"]
        assert len(actions) == 1
        assert actions[0]["agent_id"] == "agent-1"
        assert actions[0]["action"] == "publish_post"

    def test_held_actions_empty_queue(self, registry, cost_tracker):
        """held_actions() returns empty when queue is empty."""
        empty_q = ApprovalQueue()
        api = PactAPI(
            registry=registry,
            approval_queue=empty_q,
            cost_tracker=cost_tracker,
        )
        resp = api.held_actions()
        assert resp.status == "ok"
        assert resp.data["actions"] == []


# ---------------------------------------------------------------------------
# Test: Cost Report
# ---------------------------------------------------------------------------


class TestCostReport:
    def test_cost_report_returns_report(self, api):
        """cost_report() returns a cost report."""
        resp = api.cost_report()
        assert resp.status == "ok"
        data = resp.data
        assert "total_cost" in data
        assert "period_days" in data
        assert "total_calls" in data

    def test_cost_report_with_team_filter(self, api):
        """cost_report() accepts optional team_id filter."""
        resp = api.cost_report(team_id="team-alpha")
        assert resp.status == "ok"
        assert "total_cost" in resp.data


# ---------------------------------------------------------------------------
# Test: PactAPI requires all components
# ---------------------------------------------------------------------------


class TestPactAPIConstruction:
    def test_requires_registry(self, approval_queue, cost_tracker):
        """PactAPI raises if registry is None."""
        with pytest.raises((TypeError, ValueError)):
            PactAPI(
                registry=None,
                approval_queue=approval_queue,
                cost_tracker=cost_tracker,
            )

    def test_requires_approval_queue(self, registry, cost_tracker):
        """PactAPI raises if approval_queue is None."""
        with pytest.raises((TypeError, ValueError)):
            PactAPI(
                registry=registry,
                approval_queue=None,
                cost_tracker=cost_tracker,
            )

    def test_requires_cost_tracker(self, registry, approval_queue):
        """PactAPI raises if cost_tracker is None."""
        with pytest.raises((TypeError, ValueError)):
            PactAPI(
                registry=registry,
                approval_queue=approval_queue,
                cost_tracker=None,
            )
