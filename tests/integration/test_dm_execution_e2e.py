# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Task 5059: End-to-end DM execution test.

Integration test: submit task -> route -> verify gradient -> execute -> check audit.
Tests all 3 gradient levels: AUTO_APPROVED, HELD, BLOCKED.

This test exercises the full DMTeamRunner pipeline without mocking:
- Real GradientEngine evaluation
- Real constraint envelope checking
- Real approval queue for HELD actions
- StubBackend for LLM (dry-run mode)
- Real ShadowEnforcerLive recording
"""

from __future__ import annotations

import pytest

from care_platform.build.config.schema import VerificationLevel
from care_platform.build.verticals.dm_runner import DMTeamRunner


class TestDMExecutionE2E:
    """Full lifecycle tests for the DM team execution pipeline."""

    @pytest.fixture
    def runner(self) -> DMTeamRunner:
        """Create a fresh DMTeamRunner for each test."""
        return DMTeamRunner()

    # ----- AUTO_APPROVED path -----

    def test_auto_approved_draft_post(self, runner: DMTeamRunner):
        """draft_post -> content creator -> AUTO_APPROVED -> StubBackend response."""
        result = runner.submit_task(
            description="draft_post about EATP SDK release on LinkedIn",
            target_agent="dm-content-creator",
        )
        assert result.error is None, f"Expected success, got error: {result.error}"
        assert result.output != "", "Expected non-empty output from StubBackend"
        assert result.metadata["verification_level"] == VerificationLevel.AUTO_APPROVED.value
        assert "lifecycle" in result.metadata
        lifecycle = result.metadata["lifecycle"]
        assert lifecycle["final_state"] == "completed"

    def test_auto_approved_read_metrics(self, runner: DMTeamRunner):
        """read_metrics -> analytics -> AUTO_APPROVED -> StubBackend response."""
        result = runner.submit_task(
            description="read_metrics for last week's engagement",
            target_agent="dm-analytics",
        )
        assert result.error is None
        assert result.metadata["verification_level"] == VerificationLevel.AUTO_APPROVED.value

    def test_auto_approved_analyze_keywords(self, runner: DMTeamRunner):
        """analyze_keywords -> SEO specialist -> AUTO_APPROVED."""
        result = runner.submit_task(
            description="analyze_keywords for content strategy",
            target_agent="dm-seo-specialist",
        )
        assert result.error is None
        assert result.metadata["verification_level"] == VerificationLevel.AUTO_APPROVED.value

    def test_auto_approved_draft_response(self, runner: DMTeamRunner):
        """draft_response -> community manager -> AUTO_APPROVED."""
        result = runner.submit_task(
            description="draft_response to community question about CARE",
            target_agent="dm-community-manager",
        )
        assert result.error is None
        assert result.metadata["verification_level"] == VerificationLevel.AUTO_APPROVED.value

    def test_auto_approved_draft_strategy(self, runner: DMTeamRunner):
        """draft_strategy -> team lead -> AUTO_APPROVED."""
        result = runner.submit_task(
            description="draft_strategy for Q2 content plan",
            target_agent="dm-team-lead",
        )
        assert result.error is None
        assert result.metadata["verification_level"] == VerificationLevel.AUTO_APPROVED.value

    # ----- HELD path -----

    def test_held_approve_publication(self, runner: DMTeamRunner):
        """approve_publication -> team lead -> HELD (needs human approval)."""
        result = runner.submit_task(
            description="approve_publication for the LinkedIn blog post",
            target_agent="dm-team-lead",
        )
        assert result.metadata.get("verification_level") == VerificationLevel.HELD.value
        assert result.metadata.get("held") is True
        # Task should be in approval queue
        assert runner.approval_queue.queue_depth >= 1

    def test_held_task_lifecycle_shows_held_state(self, runner: DMTeamRunner):
        """HELD tasks have lifecycle with held final state."""
        result = runner.submit_task(
            description="approve_publication for blog",
            target_agent="dm-team-lead",
        )
        lifecycle = result.metadata.get("lifecycle", {})
        assert lifecycle.get("final_state") == "held"

    # ----- BLOCKED path -----

    def test_blocked_delete_action(self, runner: DMTeamRunner):
        """delete_old_posts -> any agent -> BLOCKED."""
        result = runner.submit_task(
            description="delete_old_posts from the archive",
            target_agent="dm-content-creator",
        )
        assert result.error is not None
        assert result.metadata.get("verification_level") == VerificationLevel.BLOCKED.value

    def test_blocked_modify_constraints(self, runner: DMTeamRunner):
        """modify_constraints -> BLOCKED for all agents."""
        result = runner.submit_task(
            description="modify_constraints to allow external posting",
            target_agent="dm-team-lead",
        )
        assert result.error is not None
        assert result.metadata.get("verification_level") == VerificationLevel.BLOCKED.value

    def test_blocked_lifecycle_shows_rejected(self, runner: DMTeamRunner):
        """BLOCKED tasks have lifecycle with rejected final state."""
        result = runner.submit_task(
            description="delete_old_posts from drafts",
            target_agent="dm-content-creator",
        )
        lifecycle = result.metadata.get("lifecycle", {})
        assert lifecycle.get("final_state") == "rejected"

    # ----- Routing integration -----

    def test_auto_route_draft_to_content_creator(self, runner: DMTeamRunner):
        """Auto-routing: 'Draft a post' goes to content creator."""
        result = runner.submit_task(
            description="Draft a post about open governance",
        )
        assert result.metadata.get("routed_to") == "dm-content-creator"

    def test_auto_route_seo_to_specialist(self, runner: DMTeamRunner):
        """Auto-routing: 'Check SEO' goes to SEO specialist."""
        result = runner.submit_task(
            description="Check SEO for the latest blog article",
        )
        assert result.metadata.get("routed_to") == "dm-seo-specialist"

    # ----- Audit trail integration -----

    def test_successful_task_has_complete_audit(self, runner: DMTeamRunner):
        """Successful task audit trail contains all transitions."""
        result = runner.submit_task(
            description="draft_post about Foundation updates",
            target_agent="dm-content-creator",
        )
        lifecycle = result.metadata["lifecycle"]
        transitions = lifecycle["transitions"]
        # Expect: SUBMITTED -> VERIFYING -> EXECUTING -> COMPLETED
        states = [t["to_state"] for t in transitions]
        assert "verifying" in states
        assert "executing" in states
        assert "completed" in states

    # ----- Shadow enforcer integration -----

    def test_shadow_enforcer_records_after_execution(self, runner: DMTeamRunner):
        """ShadowEnforcerLive records comparison after each execution."""
        runner.submit_task(
            description="draft_post about Foundation principles",
            target_agent="dm-content-creator",
        )
        metrics = runner.shadow_enforcer_live.get_metrics("dm-content-creator")
        assert metrics.total_evaluations >= 1
        assert metrics.agreement_count >= 1

    # ----- Multiple tasks -----

    def test_multiple_tasks_tracked_independently(self, runner: DMTeamRunner):
        """Multiple tasks are tracked in stats independently."""
        runner.submit_task(
            description="draft_post about CARE",
            target_agent="dm-content-creator",
        )
        runner.submit_task(
            description="read_metrics for March",
            target_agent="dm-analytics",
        )
        runner.submit_task(
            description="draft_response to community feedback",
            target_agent="dm-community-manager",
        )
        stats = runner.get_agent_stats()
        assert stats["dm-content-creator"]["tasks_submitted"] == 1
        assert stats["dm-analytics"]["tasks_submitted"] == 1
        assert stats["dm-community-manager"]["tasks_submitted"] == 1
        assert stats["dm-seo-specialist"]["tasks_submitted"] == 0
        assert stats["dm-team-lead"]["tasks_submitted"] == 0

    # ----- Error handling -----

    def test_submit_task_with_invalid_agent_returns_error(self, runner: DMTeamRunner):
        """Submitting to a non-existent agent returns an error result."""
        result = runner.submit_task(
            description="Do something",
            target_agent="nonexistent-agent",
        )
        assert result.error is not None
        assert "not found" in result.error.lower() or "not registered" in result.error.lower()

    def test_submit_task_with_empty_description_returns_error(self, runner: DMTeamRunner):
        """Empty task description returns an error."""
        result = runner.submit_task(description="")
        assert result.error is not None
