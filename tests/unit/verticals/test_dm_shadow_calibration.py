# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for DM shadow calibration — Tasks 5053, 5054, 5055.

Validates:
- Shadow simulation runner generates baseline metrics (5053)
- ShadowEnforcerLive integration with DMTeamRunner (5054)
- Posture upgrade recommendation API (5055)
"""

from __future__ import annotations

import pytest

from care_platform.trust.shadow_enforcer_live import ShadowEnforcerLive
from care_platform.build.verticals.dm_runner import DMTeamRunner

# ---------------------------------------------------------------------------
# Task 5053: Shadow simulation runner
# ---------------------------------------------------------------------------


class TestShadowSimulationRunner:
    """scripts/shadow_calibrate.py feeds synthetic actions through ShadowEnforcer."""

    def test_runner_generates_baseline_metrics(self):
        """DMTeamRunner can run shadow calibration and produce per-agent metrics."""
        runner = DMTeamRunner()
        metrics = runner.run_shadow_calibration()
        # Must produce metrics for all 5 agents
        assert len(metrics) == 5
        for agent_id, m in metrics.items():
            assert m["total_evaluations"] > 0, f"Agent {agent_id} has no shadow evaluations"

    def test_calibration_produces_pass_rates(self):
        """Shadow calibration metrics include pass_rate for each agent."""
        runner = DMTeamRunner()
        metrics = runner.run_shadow_calibration()
        for agent_id, m in metrics.items():
            assert "pass_rate" in m, f"Agent {agent_id} missing pass_rate"
            assert 0.0 <= m["pass_rate"] <= 1.0

    def test_calibration_detects_blocked_actions(self):
        """Shadow calibration identifies blocked actions correctly."""
        runner = DMTeamRunner()
        metrics = runner.run_shadow_calibration()
        # At least one agent should have blocked actions in the calibration set
        has_blocked = any(m.get("blocked_count", 0) > 0 for m in metrics.values())
        assert has_blocked, "Calibration should detect at least some blocked actions"

    def test_calibration_covers_all_verification_levels(self):
        """Shadow calibration covers AUTO_APPROVED, FLAGGED, HELD, and BLOCKED."""
        runner = DMTeamRunner()
        metrics = runner.run_shadow_calibration()
        # Aggregate across all agents
        total_auto = sum(m.get("auto_approved_count", 0) for m in metrics.values())
        total_flagged = sum(m.get("flagged_count", 0) for m in metrics.values())
        total_held = sum(m.get("held_count", 0) for m in metrics.values())
        total_blocked = sum(m.get("blocked_count", 0) for m in metrics.values())
        assert total_auto > 0, "Expected some AUTO_APPROVED actions"
        assert total_flagged > 0, "Expected some FLAGGED actions"
        assert total_held > 0, "Expected some HELD actions"
        assert total_blocked > 0, "Expected some BLOCKED actions"


# ---------------------------------------------------------------------------
# Task 5054: Shadow live mode integration
# ---------------------------------------------------------------------------


class TestShadowLiveModeIntegration:
    """ShadowEnforcerLive wired into DMTeamRunner for every execution."""

    def test_runner_has_shadow_enforcer_live(self):
        """DMTeamRunner creates a ShadowEnforcerLive instance."""
        runner = DMTeamRunner()
        assert runner.shadow_enforcer_live is not None
        assert isinstance(runner.shadow_enforcer_live, ShadowEnforcerLive)
        assert runner.shadow_enforcer_live.is_enabled is True

    def test_live_shadow_records_after_task_execution(self):
        """After executing a task, ShadowEnforcerLive has recorded the comparison."""
        runner = DMTeamRunner()
        runner.submit_task(
            description="Draft a post about open governance",
            target_agent="dm-content-creator",
        )
        metrics = runner.shadow_enforcer_live.get_metrics("dm-content-creator")
        assert metrics.total_evaluations >= 1

    def test_live_shadow_records_agreement(self):
        """For a standard auto-approved task, real and shadow should agree."""
        runner = DMTeamRunner()
        runner.submit_task(
            description="Draft a post about Foundation updates",
            target_agent="dm-content-creator",
        )
        metrics = runner.shadow_enforcer_live.get_metrics("dm-content-creator")
        assert metrics.agreement_count >= 1

    def test_live_shadow_per_agent_isolation(self):
        """Each agent's live shadow metrics are tracked independently."""
        runner = DMTeamRunner()
        runner.submit_task(
            description="Draft a blog article",
            target_agent="dm-content-creator",
        )
        runner.submit_task(
            description="Read engagement metrics",
            target_agent="dm-analytics",
        )
        content_metrics = runner.shadow_enforcer_live.get_metrics("dm-content-creator")
        analytics_metrics = runner.shadow_enforcer_live.get_metrics("dm-analytics")
        assert content_metrics.total_evaluations >= 1
        assert analytics_metrics.total_evaluations >= 1


# ---------------------------------------------------------------------------
# Task 5055: Posture upgrade recommendation API
# ---------------------------------------------------------------------------


class TestPostureUpgradeRecommendation:
    """GET /api/v1/shadow/{agent_id}/upgrade-recommendation endpoint."""

    def test_runner_generates_upgrade_recommendation(self):
        """DMTeamRunner can generate an upgrade recommendation for an agent."""
        runner = DMTeamRunner()
        # Run calibration first to populate shadow data
        runner.run_shadow_calibration()
        recommendation = runner.get_upgrade_recommendation("dm-content-creator")
        assert recommendation is not None
        assert "agent_id" in recommendation
        assert recommendation["agent_id"] == "dm-content-creator"
        assert "eligible" in recommendation
        assert "recommendation" in recommendation

    def test_recommendation_includes_metrics_summary(self):
        """Upgrade recommendation includes key metrics."""
        runner = DMTeamRunner()
        runner.run_shadow_calibration()
        rec = runner.get_upgrade_recommendation("dm-analytics")
        assert "pass_rate" in rec
        assert "total_evaluations" in rec
        assert "blocked_count" in rec

    def test_recommendation_for_unknown_agent_raises(self):
        """Requesting recommendation for unknown agent raises KeyError."""
        runner = DMTeamRunner()
        with pytest.raises(KeyError, match="unknown-agent"):
            runner.get_upgrade_recommendation("unknown-agent")

    def test_recommendation_reflects_blocked_actions(self):
        """Agents with blocked actions in calibration are not upgrade-eligible."""
        runner = DMTeamRunner()
        runner.run_shadow_calibration()
        # Team lead has blocked actions (modify_constraints) in calibration
        rec = runner.get_upgrade_recommendation("dm-team-lead")
        assert rec["eligible"] is False
        assert len(rec.get("blockers", [])) > 0
