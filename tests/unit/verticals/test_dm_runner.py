# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for DMTeamRunner — Task 5049, 5050, 5051.

Validates:
- DMTeamRunner wires DM team config, agents, envelopes, gradient, StubBackend
- Agent-specific system prompts for all 5 DM agents
- Capability-based task routing
- Task submission returns result with audit trail
- Dry-run mode (StubBackend) by default
"""

from __future__ import annotations

import pytest

from care_platform.build.config.schema import VerificationLevel
from care_platform.build.verticals.dm_prompts import DM_AGENT_PROMPTS, get_system_prompt
from care_platform.build.verticals.dm_runner import DMTeamRunner

# ---------------------------------------------------------------------------
# Task 5049: DMTeamRunner orchestrator
# ---------------------------------------------------------------------------


class TestDMTeamRunnerConstruction:
    """DMTeamRunner initializes from DM team config with all components wired."""

    def test_creates_from_dm_team_config(self):
        """DMTeamRunner can be created with default (dry-run) configuration."""
        runner = DMTeamRunner()
        assert runner is not None

    def test_default_uses_stub_backend(self):
        """DMTeamRunner starts in dry-run mode with StubBackend by default."""
        runner = DMTeamRunner()
        assert runner.is_dry_run is True

    def test_all_five_agents_registered(self):
        """DMTeamRunner registers all 5 DM agents in its internal registry."""
        runner = DMTeamRunner()
        agents = runner.registered_agents
        assert len(agents) == 5
        agent_ids = {a for a in agents}
        assert agent_ids == {
            "dm-team-lead",
            "dm-content-creator",
            "dm-analytics",
            "dm-community-manager",
            "dm-seo-specialist",
        }

    def test_gradient_engine_configured(self):
        """DMTeamRunner configures a GradientEngine from DM verification gradient."""
        runner = DMTeamRunner()
        # The gradient engine should exist and classify actions correctly
        assert runner.gradient_engine is not None

    def test_approval_queue_configured(self):
        """DMTeamRunner has an approval queue for HELD actions."""
        runner = DMTeamRunner()
        assert runner.approval_queue is not None

    def test_envelopes_loaded(self):
        """DMTeamRunner loads constraint envelopes for all 5 agents."""
        runner = DMTeamRunner()
        envelopes = runner.envelopes
        assert len(envelopes) == 5


class TestDMTeamRunnerSubmitTask:
    """DMTeamRunner.submit_task processes tasks through the governance pipeline."""

    def test_submit_auto_approved_task(self):
        """Submitting a draft_post task to content creator succeeds (AUTO_APPROVED)."""
        runner = DMTeamRunner()
        result = runner.submit_task(
            description="Draft a LinkedIn post about the EATP SDK release",
            target_agent="dm-content-creator",
        )
        assert result is not None
        assert result.error is None, f"Expected no error, got: {result.error}"
        assert result.output != ""
        assert result.metadata.get("verification_level") == VerificationLevel.AUTO_APPROVED.value

    def test_submit_held_task(self):
        """Submitting an approve_publication task is HELD for human review."""
        runner = DMTeamRunner()
        result = runner.submit_task(
            description="approve_publication for LinkedIn post",
            target_agent="dm-team-lead",
        )
        assert result is not None
        assert (
            result.metadata.get("held") is True
            or result.metadata.get("verification_level") == VerificationLevel.HELD.value
        )

    def test_submit_blocked_task(self):
        """Submitting a delete_old_posts task is BLOCKED."""
        runner = DMTeamRunner()
        result = runner.submit_task(
            description="delete_old_posts from archive",
            target_agent="dm-content-creator",
        )
        assert result is not None
        assert result.error is not None
        assert (
            "BLOCKED" in result.error
            or result.metadata.get("verification_level") == VerificationLevel.BLOCKED.value
        )

    def test_submit_task_has_audit_trail(self):
        """Task results include lifecycle audit metadata."""
        runner = DMTeamRunner()
        result = runner.submit_task(
            description="Draft a blog post about CARE philosophy",
            target_agent="dm-content-creator",
        )
        assert "lifecycle" in result.metadata

    def test_submit_task_records_llm_provider(self):
        """Auto-approved tasks include LLM provider information in metadata."""
        runner = DMTeamRunner()
        result = runner.submit_task(
            description="Draft a tweet about open governance",
            target_agent="dm-content-creator",
        )
        if result.error is None:
            assert "llm_provider" in result.metadata

    def test_submit_task_with_no_target_routes_to_lead(self):
        """When no target_agent and task is ambiguous, routes to team lead."""
        runner = DMTeamRunner()
        result = runner.submit_task(
            description="Review the content strategy for Q2",
        )
        assert result is not None
        assert result.metadata.get("routed_to") is not None


class TestDMTeamRunnerTaskStats:
    """DMTeamRunner tracks task statistics per agent."""

    def test_stats_empty_on_creation(self):
        """Stats start at zero for all agents."""
        runner = DMTeamRunner()
        stats = runner.get_agent_stats()
        for agent_id in runner.registered_agents:
            assert stats[agent_id]["tasks_submitted"] == 0

    def test_stats_increment_after_task(self):
        """Stats increment after a task is submitted."""
        runner = DMTeamRunner()
        runner.submit_task(
            description="Draft a post about the Foundation",
            target_agent="dm-content-creator",
        )
        stats = runner.get_agent_stats()
        assert stats["dm-content-creator"]["tasks_submitted"] >= 1


# ---------------------------------------------------------------------------
# Task 5050: Agent-specific system prompts
# ---------------------------------------------------------------------------


class TestDMAgentPrompts:
    """System prompts exist for all 5 DM agents and reflect their roles."""

    def test_prompts_defined_for_all_five_agents(self):
        """DM_AGENT_PROMPTS must have entries for all 5 agent IDs."""
        expected = {
            "dm-team-lead",
            "dm-content-creator",
            "dm-analytics",
            "dm-community-manager",
            "dm-seo-specialist",
        }
        assert set(DM_AGENT_PROMPTS.keys()) == expected

    def test_team_lead_prompt_mentions_coordination(self):
        """Team lead prompt includes coordination responsibility."""
        prompt = get_system_prompt("dm-team-lead")
        assert "coordinat" in prompt.lower() or "team lead" in prompt.lower()

    def test_content_creator_prompt_mentions_content(self):
        """Content creator prompt references content creation."""
        prompt = get_system_prompt("dm-content-creator")
        assert "content" in prompt.lower() or "draft" in prompt.lower()

    def test_analytics_prompt_mentions_metrics(self):
        """Analytics prompt mentions metrics or analytics."""
        prompt = get_system_prompt("dm-analytics")
        assert "metric" in prompt.lower() or "analyt" in prompt.lower()

    def test_community_manager_prompt_mentions_community(self):
        """Community manager prompt references community engagement."""
        prompt = get_system_prompt("dm-community-manager")
        assert "communit" in prompt.lower()

    def test_seo_specialist_prompt_mentions_seo(self):
        """SEO specialist prompt mentions SEO or search optimization."""
        prompt = get_system_prompt("dm-seo-specialist")
        assert "seo" in prompt.lower() or "search" in prompt.lower()

    def test_all_prompts_mention_eatp_governance(self):
        """All agent prompts reference EATP trust governance."""
        for agent_id in DM_AGENT_PROMPTS:
            prompt = get_system_prompt(agent_id)
            assert (
                "eatp" in prompt.lower()
                or "constraint" in prompt.lower()
                or "trust" in prompt.lower()
            ), f"Prompt for {agent_id} does not mention EATP governance"

    def test_all_prompts_are_nonempty(self):
        """All system prompts must be non-empty strings."""
        for agent_id in DM_AGENT_PROMPTS:
            prompt = get_system_prompt(agent_id)
            assert isinstance(prompt, str)
            assert len(prompt) > 50, f"Prompt for {agent_id} is too short ({len(prompt)} chars)"

    def test_get_system_prompt_raises_for_unknown_agent(self):
        """get_system_prompt raises KeyError for unknown agent IDs."""
        with pytest.raises(KeyError, match="unknown-agent"):
            get_system_prompt("unknown-agent")


# ---------------------------------------------------------------------------
# Task 5051: Capability-based task routing
# ---------------------------------------------------------------------------


class TestCapabilityBasedRouting:
    """DMTeamRunner routes tasks to agents by matching keywords to capabilities."""

    def test_draft_post_routes_to_content_creator(self):
        """'Draft a post' routes to content creator."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Draft a LinkedIn post about open source")
        assert agent_id == "dm-content-creator"

    def test_check_seo_routes_to_seo_specialist(self):
        """'Check SEO' routes to SEO specialist."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Check SEO for the blog article")
        assert agent_id == "dm-seo-specialist"

    def test_analyze_keywords_routes_to_seo(self):
        """'Analyze keywords' routes to SEO specialist."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Analyze keywords for our content strategy")
        assert agent_id == "dm-seo-specialist"

    def test_read_metrics_routes_to_analytics(self):
        """'Read metrics' routes to analytics agent."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Read engagement metrics for last week")
        assert agent_id == "dm-analytics"

    def test_generate_report_routes_to_analytics(self):
        """'Generate report' routes to analytics agent."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Generate a performance report for Q1")
        assert agent_id == "dm-analytics"

    def test_community_response_routes_to_community_manager(self):
        """'Draft a community response' routes to community manager."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Draft a response to the community question")
        assert agent_id == "dm-community-manager"

    def test_moderate_routes_to_community_manager(self):
        """'Moderate' task routes to community manager."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Moderate the forum discussion")
        assert agent_id == "dm-community-manager"

    def test_ambiguous_task_routes_to_team_lead(self):
        """Ambiguous tasks with no clear keyword match go to team lead."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Help me with something")
        assert agent_id == "dm-team-lead"

    def test_schedule_routes_to_team_lead(self):
        """'Schedule content' routes to team lead."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Schedule the content calendar for next week")
        assert agent_id == "dm-team-lead"

    def test_approve_routes_to_team_lead(self):
        """'Approve publication' routes to team lead."""
        runner = DMTeamRunner()
        agent_id = runner.route_task("Approve the publication of the blog post")
        assert agent_id == "dm-team-lead"

    def test_submit_task_auto_routes_when_no_target(self):
        """submit_task uses routing when target_agent is not specified."""
        runner = DMTeamRunner()
        result = runner.submit_task(
            description="Draft a post about Foundation governance",
        )
        assert result.metadata.get("routed_to") == "dm-content-creator"
