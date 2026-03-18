# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for DM team API endpoints — Task 5052.

Validates:
- POST /api/v1/dm/tasks — submit a DM task (auto-routes, returns task_id)
- GET /api/v1/dm/tasks/{task_id} — get task result and lifecycle
- GET /api/v1/dm/status — all 5 agents' postures and stats
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from care_platform.use.api.endpoints import PlatformAPI
from care_platform.use.api.server import create_app
from care_platform.build.config.env import EnvConfig
from care_platform.use.execution.registry import AgentRegistry
from care_platform.trust.store.cost_tracking import CostTracker
from care_platform.build.verticals.dm_runner import DMTeamRunner


def _make_dev_env() -> EnvConfig:
    """Create a dev-mode env config with auth disabled."""
    return EnvConfig(
        care_api_token="",
        care_dev_mode=True,
        care_api_host="127.0.0.1",
        care_api_port=8000,
    )


def _make_test_app() -> TestClient:
    """Create a test FastAPI app with DM runner endpoints wired."""
    runner = DMTeamRunner()

    # Build a PlatformAPI with the runner's registry and approval queue
    registry = AgentRegistry()
    for agent_id in runner.registered_agents:
        record = runner.get_agent_record(agent_id)
        if record is not None:
            try:
                registry.register(
                    agent_id=record.agent_id,
                    name=record.name,
                    role=record.role,
                    team_id=record.team_id,
                    capabilities=record.capabilities,
                    posture=record.current_posture,
                )
            except ValueError:
                pass  # Already registered

    api = PlatformAPI(
        registry=registry,
        approval_queue=runner.approval_queue,
        cost_tracker=CostTracker(),
    )

    app = create_app(platform_api=api, env_config=_make_dev_env(), dm_runner=runner)
    return TestClient(app)


class TestDMTaskSubmissionEndpoint:
    """POST /api/v1/dm/tasks — submit a DM task."""

    def test_submit_task_returns_200(self):
        """Submitting a valid task returns 200 with task_id."""
        client = _make_test_app()
        response = client.post(
            "/api/v1/dm/tasks",
            json={"description": "Draft a post about EATP SDK"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "task_id" in data["data"]

    def test_submit_task_with_target_agent(self):
        """Submitting a task with explicit target_agent routes correctly."""
        client = _make_test_app()
        response = client.post(
            "/api/v1/dm/tasks",
            json={
                "description": "Draft a blog post",
                "target_agent": "dm-content-creator",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["data"]["routed_to"] == "dm-content-creator"

    def test_submit_task_auto_routes(self):
        """Task without target_agent is auto-routed by keywords."""
        client = _make_test_app()
        response = client.post(
            "/api/v1/dm/tasks",
            json={"description": "Analyze keywords for our website"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["routed_to"] == "dm-seo-specialist"

    def test_submit_task_returns_error_for_missing_description(self):
        """Missing description returns error."""
        client = _make_test_app()
        response = client.post("/api/v1/dm/tasks", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"

    def test_submit_task_returns_error_for_invalid_agent(self):
        """Invalid target_agent returns error."""
        client = _make_test_app()
        response = client.post(
            "/api/v1/dm/tasks",
            json={
                "description": "Draft something",
                "target_agent": "nonexistent-agent",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"


class TestDMTaskStatusEndpoint:
    """GET /api/v1/dm/tasks/{task_id} — get task result."""

    def test_get_task_result_after_submission(self):
        """After submitting, can retrieve the task result by task_id."""
        client = _make_test_app()
        # Submit a task first
        submit_resp = client.post(
            "/api/v1/dm/tasks",
            json={
                "description": "Draft a post about governance",
                "target_agent": "dm-content-creator",
            },
        )
        task_id = submit_resp.json()["data"]["task_id"]

        # Retrieve it
        get_resp = client.get(f"/api/v1/dm/tasks/{task_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["status"] == "ok"
        assert data["data"]["task_id"] == task_id

    def test_get_unknown_task_returns_error(self):
        """Requesting an unknown task_id returns an error."""
        client = _make_test_app()
        get_resp = client.get("/api/v1/dm/tasks/nonexistent-task-id")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["status"] == "error"


class TestDMStatusEndpoint:
    """GET /api/v1/dm/status — all 5 agents' postures and stats."""

    def test_dm_status_returns_all_five_agents(self):
        """Status endpoint returns information for all 5 DM agents."""
        client = _make_test_app()
        response = client.get("/api/v1/dm/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        agents = data["data"]["agents"]
        assert len(agents) == 5

    def test_dm_status_includes_posture(self):
        """Each agent in status response includes their trust posture."""
        client = _make_test_app()
        response = client.get("/api/v1/dm/status")
        data = response.json()
        for agent in data["data"]["agents"]:
            assert "posture" in agent, f"Agent {agent.get('agent_id')} missing posture"

    def test_dm_status_includes_task_count(self):
        """Each agent includes a task count (starts at 0)."""
        client = _make_test_app()
        response = client.get("/api/v1/dm/status")
        data = response.json()
        for agent in data["data"]["agents"]:
            assert "tasks_submitted" in agent
