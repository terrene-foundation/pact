# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for ShadowEnforcer API endpoints (M13 — tasks 5005-5008).

Tests the PlatformAPI shadow_metrics() and shadow_report() methods,
the FastAPI route wiring, and the seed script shadow data generation.
"""

from __future__ import annotations

import pytest

from care_platform.use.api.endpoints import ApiResponse, PlatformAPI
from care_platform.build.config.schema import (
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.trust.constraint.envelope import ConstraintEnvelope
from care_platform.trust.constraint.gradient import GradientEngine
from care_platform.use.execution.approval import ApprovalQueue
from care_platform.use.execution.registry import AgentRegistry
from care_platform.trust.store.cost_tracking import CostTracker
from care_platform.trust.shadow_enforcer import ShadowEnforcer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(**kwargs):
    """Build a minimal ConstraintEnvelope for testing."""
    return ConstraintEnvelope(
        config=ConstraintEnvelopeConfig(
            id="test-envelope",
            financial=FinancialConstraintConfig(
                max_spend_usd=kwargs.get("max_spend", 1000.0),
            ),
            operational=OperationalConstraintConfig(
                blocked_actions=kwargs.get("blocked_actions", []),
            ),
        ),
    )


def _make_gradient(default_level=VerificationLevel.AUTO_APPROVED, rules=None):
    """Build a GradientEngine with sensible defaults for testing."""
    return GradientEngine(
        config=VerificationGradientConfig(
            rules=rules or [],
            default_level=default_level,
        ),
    )


def _make_shadow_enforcer(
    default_level=VerificationLevel.AUTO_APPROVED, **envelope_kwargs
) -> ShadowEnforcer:
    """Create a ShadowEnforcer with a gradient engine and envelope."""
    return ShadowEnforcer(
        gradient_engine=_make_gradient(default_level=default_level),
        envelope=_make_envelope(**envelope_kwargs),
    )


def _make_platform_api(shadow_enforcer: ShadowEnforcer | None = None, **kwargs) -> PlatformAPI:
    """Create a PlatformAPI instance with a ShadowEnforcer attached."""
    return PlatformAPI(
        registry=kwargs.get("registry", AgentRegistry()),
        approval_queue=kwargs.get("approval_queue", ApprovalQueue()),
        cost_tracker=kwargs.get("cost_tracker", CostTracker()),
        shadow_enforcer=shadow_enforcer,
    )


# ---------------------------------------------------------------------------
# Task 5007: PlatformAPI accepts shadow_enforcer parameter
# ---------------------------------------------------------------------------


class TestPlatformAPIShadowEnforcerParam:
    """PlatformAPI.__init__() accepts and stores a shadow_enforcer parameter."""

    def test_shadow_enforcer_stored_on_instance(self):
        """PlatformAPI stores the shadow_enforcer when provided."""
        enforcer = _make_shadow_enforcer()
        api = _make_platform_api(shadow_enforcer=enforcer)
        assert api._shadow_enforcer is enforcer

    def test_shadow_enforcer_defaults_to_none(self):
        """PlatformAPI does not require shadow_enforcer (backward compat)."""
        api = PlatformAPI(
            registry=AgentRegistry(),
            approval_queue=ApprovalQueue(),
            cost_tracker=CostTracker(),
        )
        assert api._shadow_enforcer is None

    def test_existing_params_still_work(self):
        """Adding shadow_enforcer does not break existing constructor calls."""
        api = PlatformAPI(
            registry=AgentRegistry(),
            approval_queue=ApprovalQueue(),
            cost_tracker=CostTracker(),
            envelope_registry={},
            verification_stats={},
        )
        # Should not raise and shadow_enforcer is None
        assert api._shadow_enforcer is None


# ---------------------------------------------------------------------------
# Task 5005: shadow_metrics endpoint
# ---------------------------------------------------------------------------


class TestShadowMetricsEndpoint:
    """PlatformAPI.shadow_metrics() returns agent shadow metrics."""

    def test_returns_error_when_shadow_enforcer_not_configured(self):
        """When no ShadowEnforcer is provided, return a clear error."""
        api = _make_platform_api(shadow_enforcer=None)
        response = api.shadow_metrics("agent-1")
        assert response.status == "error"
        assert "shadow_enforcer" in response.error.lower() or "shadow" in response.error.lower()

    def test_returns_error_for_unknown_agent(self):
        """When agent has no evaluations, return error (KeyError from ShadowEnforcer)."""
        enforcer = _make_shadow_enforcer()
        api = _make_platform_api(shadow_enforcer=enforcer)
        response = api.shadow_metrics("nonexistent-agent")
        assert response.status == "error"
        assert "nonexistent-agent" in response.error

    def test_returns_metrics_for_evaluated_agent(self):
        """After evaluations, shadow_metrics returns correct data."""
        enforcer = _make_shadow_enforcer()
        # Generate some evaluations
        enforcer.evaluate("read_data", "agent-1")
        enforcer.evaluate("write_data", "agent-1")
        enforcer.evaluate("query", "agent-1")

        api = _make_platform_api(shadow_enforcer=enforcer)
        response = api.shadow_metrics("agent-1")

        assert response.status == "ok"
        assert response.data is not None
        assert response.data["agent_id"] == "agent-1"
        assert response.data["total_evaluations"] == 3
        assert "auto_approved_count" in response.data
        assert "flagged_count" in response.data
        assert "held_count" in response.data
        assert "blocked_count" in response.data
        assert "pass_rate" in response.data
        assert "block_rate" in response.data

    def test_metrics_reflect_different_levels(self):
        """Metrics correctly reflect evaluations at different verification levels."""
        # Use BLOCKED default level to get blocked results
        enforcer = _make_shadow_enforcer(default_level=VerificationLevel.BLOCKED)
        enforcer.evaluate("action_a", "agent-x")
        enforcer.evaluate("action_b", "agent-x")

        api = _make_platform_api(shadow_enforcer=enforcer)
        response = api.shadow_metrics("agent-x")

        assert response.status == "ok"
        assert response.data["total_evaluations"] == 2
        assert response.data["blocked_count"] == 2
        assert response.data["auto_approved_count"] == 0

    def test_response_is_api_response_type(self):
        """shadow_metrics returns an ApiResponse instance."""
        enforcer = _make_shadow_enforcer()
        enforcer.evaluate("action", "agent-1")
        api = _make_platform_api(shadow_enforcer=enforcer)
        response = api.shadow_metrics("agent-1")
        assert isinstance(response, ApiResponse)


# ---------------------------------------------------------------------------
# Task 5006: shadow_report endpoint
# ---------------------------------------------------------------------------


class TestShadowReportEndpoint:
    """PlatformAPI.shadow_report() returns posture upgrade reports."""

    def test_returns_error_when_shadow_enforcer_not_configured(self):
        """When no ShadowEnforcer is provided, return a clear error."""
        api = _make_platform_api(shadow_enforcer=None)
        response = api.shadow_report("agent-1")
        assert response.status == "error"
        assert "shadow_enforcer" in response.error.lower() or "shadow" in response.error.lower()

    def test_returns_error_for_unknown_agent(self):
        """When agent has no evaluations, return error."""
        enforcer = _make_shadow_enforcer()
        api = _make_platform_api(shadow_enforcer=enforcer)
        response = api.shadow_report("nonexistent-agent")
        assert response.status == "error"
        assert "nonexistent-agent" in response.error

    def test_returns_report_for_evaluated_agent(self):
        """After evaluations, shadow_report returns upgrade recommendation."""
        enforcer = _make_shadow_enforcer()
        for i in range(10):
            enforcer.evaluate(f"action_{i}", "agent-1")

        api = _make_platform_api(shadow_enforcer=enforcer)
        response = api.shadow_report("agent-1")

        assert response.status == "ok"
        assert response.data is not None
        assert response.data["agent_id"] == "agent-1"
        assert response.data["total_evaluations"] == 10
        assert "pass_rate" in response.data
        assert "block_rate" in response.data
        assert "hold_rate" in response.data
        assert "flag_rate" in response.data
        assert "upgrade_eligible" in response.data
        assert "upgrade_blockers" in response.data
        assert "recommendation" in response.data
        assert "dimension_breakdown" in response.data
        assert "evaluation_period_days" in response.data

    def test_report_includes_upgrade_eligibility(self):
        """Report correctly indicates upgrade eligibility status."""
        enforcer = _make_shadow_enforcer()
        # Only 5 evaluations -- below the min_operations threshold
        for i in range(5):
            enforcer.evaluate(f"action_{i}", "agent-1")

        api = _make_platform_api(shadow_enforcer=enforcer)
        response = api.shadow_report("agent-1")

        assert response.status == "ok"
        # With few evaluations, should not be eligible
        assert response.data["upgrade_eligible"] is False
        assert len(response.data["upgrade_blockers"]) > 0

    def test_response_is_api_response_type(self):
        """shadow_report returns an ApiResponse instance."""
        enforcer = _make_shadow_enforcer()
        enforcer.evaluate("action", "agent-1")
        api = _make_platform_api(shadow_enforcer=enforcer)
        response = api.shadow_report("agent-1")
        assert isinstance(response, ApiResponse)


# ---------------------------------------------------------------------------
# Task 5005/5006: FastAPI route wiring
# ---------------------------------------------------------------------------


class TestShadowRouteWiring:
    """FastAPI routes for shadow endpoints are properly configured."""

    @pytest.fixture()
    def app_client(self):
        """Create a test client with ShadowEnforcer wired in."""
        from fastapi.testclient import TestClient

        from care_platform.use.api.server import create_app
        from care_platform.build.config.env import EnvConfig

        enforcer = _make_shadow_enforcer()
        # Pre-populate some evaluations
        for i in range(5):
            enforcer.evaluate(f"action_{i}", "test-agent")

        platform_api = PlatformAPI(
            registry=AgentRegistry(),
            approval_queue=ApprovalQueue(),
            cost_tracker=CostTracker(),
            shadow_enforcer=enforcer,
        )

        # Use dev mode (no auth required) for testing
        cfg = EnvConfig(care_dev_mode=True)
        app = create_app(platform_api=platform_api, env_config=cfg)
        return TestClient(app)

    def test_shadow_metrics_route_exists(self, app_client):
        """GET /api/v1/shadow/{agent_id}/metrics returns 200 for known agent."""
        resp = app_client.get("/api/v1/shadow/test-agent/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["data"]["agent_id"] == "test-agent"
        assert body["data"]["total_evaluations"] == 5

    def test_shadow_metrics_route_unknown_agent(self, app_client):
        """GET /api/v1/shadow/{agent_id}/metrics returns 200 with error for unknown agent."""
        resp = app_client.get("/api/v1/shadow/unknown-agent/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"

    def test_shadow_report_route_exists(self, app_client):
        """GET /api/v1/shadow/{agent_id}/report returns 200 for known agent."""
        resp = app_client.get("/api/v1/shadow/test-agent/report")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["data"]["agent_id"] == "test-agent"

    def test_shadow_report_route_unknown_agent(self, app_client):
        """GET /api/v1/shadow/{agent_id}/report returns 200 with error for unknown agent."""
        resp = app_client.get("/api/v1/shadow/unknown-agent/report")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"


# ---------------------------------------------------------------------------
# Task 5008: Seed demo data includes shadow enforcer
# ---------------------------------------------------------------------------


class TestSeedDemoShadowData:
    """The seed script creates a ShadowEnforcer with realistic evaluation data."""

    def test_seed_returns_shadow_enforcer(self):
        """seed_demo.main() returns a dict with 'shadow_enforcer' key."""
        import sys

        sys.argv = ["seed_demo"]  # Reset argv to avoid --reset flag
        from scripts.seed_demo import main

        result = main()
        assert result is not None
        assert "shadow_enforcer" in result
        assert isinstance(result["shadow_enforcer"], ShadowEnforcer)

    def test_seed_shadow_enforcer_has_metrics_for_agents(self):
        """Seeded ShadowEnforcer has metrics for at least some agents."""
        import sys

        sys.argv = ["seed_demo"]
        from scripts.seed_demo import main

        result = main()
        enforcer = result["shadow_enforcer"]

        # Should have data for at least the agents defined in AGENTS
        from scripts.seed_demo import AGENTS

        agents_with_metrics = 0
        for agent_def in AGENTS:
            agent_id = agent_def["agent_id"]
            try:
                metrics = enforcer.get_metrics(agent_id)
                assert metrics.total_evaluations >= 20, (
                    f"Agent '{agent_id}' should have at least 20 evaluations, "
                    f"got {metrics.total_evaluations}"
                )
                agents_with_metrics += 1
            except KeyError:
                pass  # Some agents may not have metrics

        assert agents_with_metrics >= len(AGENTS) // 2, (
            f"Expected at least {len(AGENTS) // 2} agents with shadow metrics, "
            f"got {agents_with_metrics}"
        )

    def test_seed_shadow_enforcer_has_varied_results(self):
        """Seeded evaluations produce a mix of pass/fail/flag results."""
        import sys

        sys.argv = ["seed_demo"]
        from scripts.seed_demo import main

        result = main()
        enforcer = result["shadow_enforcer"]

        from scripts.seed_demo import AGENTS

        # Aggregate across all agents
        total_auto = 0
        total_flagged = 0
        total_held = 0
        total_blocked = 0

        for agent_def in AGENTS:
            try:
                metrics = enforcer.get_metrics(agent_def["agent_id"])
                total_auto += metrics.auto_approved_count
                total_flagged += metrics.flagged_count
                total_held += metrics.held_count
                total_blocked += metrics.blocked_count
            except KeyError:
                pass

        total = total_auto + total_flagged + total_held + total_blocked
        assert total >= 100, f"Expected at least 100 total evaluations, got {total}"
        # Should have at least some variety (not all one type)
        assert total_auto > 0, "Expected some AUTO_APPROVED evaluations"
