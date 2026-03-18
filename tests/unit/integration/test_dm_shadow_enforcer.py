# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Task 606: DM Team ShadowEnforcer calibration test.

Generates a simulated dataset of 50 DM team actions covering all 5 agent roles,
runs per-agent ShadowEnforcers (each with its own constraint envelope), and verifies:
- Distribution: majority auto-approved, some flagged, some held, few blocked
- No "should-be-blocked" action is ever classified as auto-approved
- ShadowReport contains metrics for every agent evaluated

Each agent is evaluated against its own constraint envelope, matching production
behavior. The verification gradient is shared across the team.

Verification gradient rules (from dm_team.py):
  read_*          -> AUTO_APPROVED
  draft_*         -> AUTO_APPROVED
  analyze_*       -> AUTO_APPROVED
  approve_*       -> HELD
  publish_*       -> HELD
  external_*      -> HELD
  delete_*        -> BLOCKED
  modify_constraints -> BLOCKED
  default         -> FLAGGED
"""

from datetime import UTC, datetime

import pytest

from care_platform.build.config.schema import VerificationLevel
from care_platform.trust.constraint.envelope import ConstraintEnvelope
from care_platform.trust.constraint.gradient import GradientEngine
from care_platform.trust.shadow_enforcer import (
    ShadowEnforcer,
    ShadowReport,
    ShadowResult,
)
from care_platform.build.verticals.dm_team import (
    DM_ANALYTICS_ENVELOPE,
    DM_COMMUNITY_ENVELOPE,
    DM_CONTENT_ENVELOPE,
    DM_LEAD_ENVELOPE,
    DM_SEO_ENVELOPE,
    DM_VERIFICATION_GRADIENT,
)

# ---------------------------------------------------------------------------
# Agent envelope mapping — each agent gets its own ShadowEnforcer
# ---------------------------------------------------------------------------

_AGENT_ENVELOPE_MAP = {
    "dm-team-lead": DM_LEAD_ENVELOPE,
    "dm-content-creator": DM_CONTENT_ENVELOPE,
    "dm-analytics": DM_ANALYTICS_ENVELOPE,
    "dm-community-manager": DM_COMMUNITY_ENVELOPE,
    "dm-seo-specialist": DM_SEO_ENVELOPE,
}

# Actions that MUST be blocked by the gradient (destructive / self-modifying).
# These are in every agent's blocked_actions list too.
_BLOCKED_ACTIONS = [
    "delete_old_posts",
    "delete_analytics_data",
    "modify_constraints",
]

# Actions that MUST be held (external-facing / approval-required).
# These match the publish_*, approve_*, external_* gradient rules.
_HELD_ACTIONS = [
    "publish_linkedin_post",
    "publish_blog_article",
    "approve_publication",
    "external_email",
    "external_outreach",
]


def _build_simulated_actions() -> list[dict]:
    """Build 50 simulated DM team actions covering all agent roles.

    Each action is assigned to the agent whose constraint envelope lists the
    action as allowed (or it is deliberately a blocked/held action for
    testing those gradient levels).

    Distribution target: ~60% auto-approved, ~16% flagged, ~14% held, ~10% blocked.

    DM agent allowed actions (from dm_team.py):
    - Lead:    review_content, approve_publication, coordinate_team,
               schedule_content, analyze_metrics, draft_strategy
    - Creator: draft_post, edit_content, research_topic, suggest_hashtags
    - Analytics: read_metrics, generate_report, track_engagement, analyze_trends
    - Community: draft_response, moderate_content, track_community, flag_issues
    - SEO:     analyze_keywords, suggest_structure, audit_seo, research_topics
    """
    actions: list[dict] = []

    # --- AUTO_APPROVED actions (30 actions = 60%) ---
    # These use actions that are in each agent's allowed_actions AND match
    # auto-approved gradient patterns (read_*, draft_*, analyze_*).

    # Team Lead: draft_strategy matches draft_*, analyze_metrics matches analyze_*
    actions.append({"agent_id": "dm-team-lead", "action": "draft_strategy"})
    actions.append({"agent_id": "dm-team-lead", "action": "draft_strategy"})
    actions.append({"agent_id": "dm-team-lead", "action": "analyze_metrics"})
    actions.append({"agent_id": "dm-team-lead", "action": "analyze_metrics"})
    actions.append({"agent_id": "dm-team-lead", "action": "analyze_metrics"})

    # Content Creator: draft_post matches draft_*
    actions.append({"agent_id": "dm-content-creator", "action": "draft_post"})
    actions.append({"agent_id": "dm-content-creator", "action": "draft_post"})
    actions.append({"agent_id": "dm-content-creator", "action": "draft_post"})
    actions.append({"agent_id": "dm-content-creator", "action": "draft_post"})
    actions.append({"agent_id": "dm-content-creator", "action": "draft_post"})
    actions.append({"agent_id": "dm-content-creator", "action": "draft_post"})

    # Analytics Agent: read_metrics matches read_*, analyze_trends matches analyze_*
    actions.append({"agent_id": "dm-analytics", "action": "read_metrics"})
    actions.append({"agent_id": "dm-analytics", "action": "read_metrics"})
    actions.append({"agent_id": "dm-analytics", "action": "read_metrics"})
    actions.append({"agent_id": "dm-analytics", "action": "analyze_trends"})
    actions.append({"agent_id": "dm-analytics", "action": "analyze_trends"})
    actions.append({"agent_id": "dm-analytics", "action": "read_metrics"})
    actions.append({"agent_id": "dm-analytics", "action": "analyze_trends"})

    # Community Manager: draft_response matches draft_*
    actions.append({"agent_id": "dm-community-manager", "action": "draft_response"})
    actions.append({"agent_id": "dm-community-manager", "action": "draft_response"})
    actions.append({"agent_id": "dm-community-manager", "action": "draft_response"})
    actions.append({"agent_id": "dm-community-manager", "action": "draft_response"})

    # SEO Specialist: analyze_keywords matches analyze_*
    actions.append({"agent_id": "dm-seo-specialist", "action": "analyze_keywords"})
    actions.append({"agent_id": "dm-seo-specialist", "action": "analyze_keywords"})
    actions.append({"agent_id": "dm-seo-specialist", "action": "analyze_keywords"})
    actions.append({"agent_id": "dm-seo-specialist", "action": "analyze_keywords"})
    actions.append({"agent_id": "dm-seo-specialist", "action": "analyze_keywords"})
    actions.append({"agent_id": "dm-seo-specialist", "action": "analyze_keywords"})
    actions.append({"agent_id": "dm-analytics", "action": "read_metrics"})
    actions.append({"agent_id": "dm-content-creator", "action": "draft_post"})

    # --- FLAGGED actions (8 actions = 16%) ---
    # These are in each agent's allowed_actions but match no gradient pattern,
    # so they fall to the default level (FLAGGED).
    actions.append({"agent_id": "dm-team-lead", "action": "schedule_content"})
    actions.append({"agent_id": "dm-team-lead", "action": "coordinate_team"})
    actions.append({"agent_id": "dm-community-manager", "action": "moderate_content"})
    actions.append({"agent_id": "dm-community-manager", "action": "flag_issues"})
    actions.append({"agent_id": "dm-content-creator", "action": "suggest_hashtags"})
    actions.append({"agent_id": "dm-community-manager", "action": "track_community"})
    actions.append({"agent_id": "dm-seo-specialist", "action": "suggest_structure"})
    actions.append({"agent_id": "dm-team-lead", "action": "review_content"})

    # --- HELD actions (7 actions = 14%) ---
    # These match publish_*, approve_*, external_* gradient patterns -> HELD.
    # Note: approve_publication is in the lead's allowed_actions, so the
    # envelope allows it, but the gradient classifies it as HELD.
    # publish_* and external_* are NOT in any agent's allowed_actions, so
    # the envelope will DENY them, and the gradient will see BLOCKED.
    # For HELD testing, we use approve_publication (lead) which is allowed
    # by the envelope but HELD by the gradient.
    actions.append({"agent_id": "dm-team-lead", "action": "approve_publication"})
    actions.append({"agent_id": "dm-team-lead", "action": "approve_publication"})
    actions.append({"agent_id": "dm-team-lead", "action": "approve_publication"})
    actions.append({"agent_id": "dm-team-lead", "action": "approve_publication"})
    actions.append({"agent_id": "dm-team-lead", "action": "approve_publication"})
    actions.append({"agent_id": "dm-team-lead", "action": "approve_publication"})
    actions.append({"agent_id": "dm-team-lead", "action": "approve_publication"})

    # --- BLOCKED actions (5 actions = 10%) ---
    # delete_* and modify_constraints match blocked gradient patterns.
    # These are also in blocked_actions lists, so the envelope denies them too.
    actions.append({"agent_id": "dm-content-creator", "action": "delete_old_posts"})
    actions.append({"agent_id": "dm-analytics", "action": "delete_analytics_data"})
    actions.append({"agent_id": "dm-team-lead", "action": "modify_constraints"})
    actions.append({"agent_id": "dm-seo-specialist", "action": "delete_old_posts"})
    actions.append({"agent_id": "dm-community-manager", "action": "delete_old_posts"})

    assert len(actions) == 50, f"Expected 50 actions, got {len(actions)}"
    return actions


def _build_enforcers() -> dict[str, ShadowEnforcer]:
    """Build one ShadowEnforcer per agent, each with its own envelope.

    This matches production behavior where each agent's actions are evaluated
    against that agent's specific constraint envelope.
    """
    gradient = GradientEngine(config=DM_VERIFICATION_GRADIENT)
    enforcers: dict[str, ShadowEnforcer] = {}
    for agent_id, envelope_config in _AGENT_ENVELOPE_MAP.items():
        envelope = ConstraintEnvelope(config=envelope_config)
        enforcers[agent_id] = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=envelope,
        )
    return enforcers


def _evaluate_all(
    enforcers: dict[str, ShadowEnforcer],
    actions: list[dict],
) -> list[ShadowResult]:
    """Evaluate all actions through the correct per-agent enforcer.

    Uses a fixed time (12:00 UTC) within all DM team active hour windows
    (lead: 06:00-22:00, content: 08:00-20:00, etc.) to avoid time-of-day
    sensitivity in CI/test environments.
    """
    # Fixed midday UTC time — within all DM team active hour windows
    fixed_time = datetime(2026, 3, 14, 12, 0, 0, tzinfo=UTC)
    results: list[ShadowResult] = []
    for act in actions:
        agent_id = act["agent_id"]
        enforcer = enforcers[agent_id]
        result = enforcer.evaluate(act["action"], agent_id, current_time=fixed_time)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDmShadowEnforcerCalibration:
    """Run ShadowEnforcer over 50 simulated DM team actions and verify calibration."""

    def test_dataset_covers_all_agent_roles(self):
        """The simulated dataset must include actions from all 5 DM agent roles."""
        actions = _build_simulated_actions()
        agent_ids = {a["agent_id"] for a in actions}
        expected_agents = {
            "dm-team-lead",
            "dm-content-creator",
            "dm-analytics",
            "dm-community-manager",
            "dm-seo-specialist",
        }
        assert agent_ids == expected_agents, (
            f"Missing agent roles in dataset: {expected_agents - agent_ids}"
        )

    def test_dataset_has_50_actions(self):
        """Simulated dataset has exactly 50 actions."""
        actions = _build_simulated_actions()
        assert len(actions) == 50

    def test_shadow_enforcer_processes_all_actions(self):
        """ShadowEnforcer successfully processes every action without errors."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        results = _evaluate_all(enforcers, actions)
        assert len(results) == 50

    def test_distribution_majority_auto_approved(self):
        """Majority of actions (>50%) are classified as AUTO_APPROVED."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        results = _evaluate_all(enforcers, actions)
        auto_approved = sum(1 for r in results if r.would_be_auto_approved)
        assert auto_approved >= 25, (
            f"Expected majority auto-approved (>= 25/50), got {auto_approved}"
        )

    def test_distribution_some_flagged(self):
        """Some actions are FLAGGED (default level for unmatched patterns)."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        results = _evaluate_all(enforcers, actions)
        flagged = sum(1 for r in results if r.would_be_flagged)
        assert flagged >= 1, f"Expected some flagged actions, got {flagged}"

    def test_distribution_some_held(self):
        """Some actions are HELD (approve_* pattern for team lead)."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        results = _evaluate_all(enforcers, actions)
        held = sum(1 for r in results if r.would_be_held)
        assert held >= 1, f"Expected some held actions, got {held}"

    def test_distribution_few_blocked(self):
        """A few actions are BLOCKED (delete/modify_constraints)."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        results = _evaluate_all(enforcers, actions)
        blocked = sum(1 for r in results if r.would_be_blocked)
        assert blocked >= 1, f"Expected some blocked actions, got {blocked}"

    def test_no_blocked_action_auto_approved(self):
        """CRITICAL: No action from _BLOCKED_ACTIONS must ever be AUTO_APPROVED.

        This is the primary safety invariant for the DM team.
        Every blocked action is tested against every agent's envelope.
        """
        enforcers = _build_enforcers()
        for action in _BLOCKED_ACTIONS:
            for agent_id, enforcer in enforcers.items():
                result = enforcer.evaluate(action, agent_id)
                assert not result.would_be_auto_approved, (
                    f"CRITICAL: Blocked action '{action}' by agent '{agent_id}' "
                    f"was classified as AUTO_APPROVED. "
                    f"Actual level: {result.verification_level.value}. "
                    f"This is a safety violation -- blocked actions must never be auto-approved."
                )

    def test_no_held_action_auto_approved(self):
        """Actions that MUST be held (publish/approve/external) are never AUTO_APPROVED.

        Tested against every agent -- even if the envelope blocks the action
        (making it BLOCKED rather than HELD), it must never be AUTO_APPROVED.
        """
        enforcers = _build_enforcers()
        for action in _HELD_ACTIONS:
            for agent_id, enforcer in enforcers.items():
                result = enforcer.evaluate(action, agent_id)
                assert not result.would_be_auto_approved, (
                    f"HELD action '{action}' by agent '{agent_id}' "
                    f"was classified as AUTO_APPROVED. "
                    f"Actual level: {result.verification_level.value}. "
                    f"External/approval actions require human review."
                )

    def test_auto_approved_actions_correctly_classified(self):
        """Actions matching read_*/draft_*/analyze_* that are in the agent's
        allowed_actions are AUTO_APPROVED when evaluated against their own envelope.
        """
        enforcers = _build_enforcers()
        # Test per-agent: each action must be in that agent's allowed_actions
        test_cases = [
            ("dm-team-lead", "draft_strategy"),
            ("dm-team-lead", "analyze_metrics"),
            ("dm-content-creator", "draft_post"),
            ("dm-analytics", "read_metrics"),
            ("dm-analytics", "analyze_trends"),
            ("dm-community-manager", "draft_response"),
            ("dm-seo-specialist", "analyze_keywords"),
        ]
        # Fixed midday UTC time — within all DM team active hour windows
        fixed_time = datetime(2026, 3, 14, 12, 0, 0, tzinfo=UTC)
        for agent_id, action in test_cases:
            enforcer = enforcers[agent_id]
            result = enforcer.evaluate(action, agent_id, current_time=fixed_time)
            assert result.would_be_auto_approved, (
                f"Safe action '{action}' by '{agent_id}' should be AUTO_APPROVED "
                f"but got {result.verification_level.value}"
            )

    def test_approve_publication_held_for_lead(self):
        """approve_publication is in lead's allowed_actions and matches approve_* -> HELD."""
        enforcers = _build_enforcers()
        fixed_time = datetime(2026, 3, 14, 12, 0, 0, tzinfo=UTC)
        result = enforcers["dm-team-lead"].evaluate(
            "approve_publication", "dm-team-lead", current_time=fixed_time
        )
        assert result.verification_level == VerificationLevel.HELD, (
            f"approve_publication should be HELD for team lead, "
            f"got {result.verification_level.value}"
        )

    def test_shadow_report_generated_for_each_agent(self):
        """ShadowReport can be generated for every agent after processing."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        _evaluate_all(enforcers, actions)

        for agent_id, enforcer in enforcers.items():
            report = enforcer.generate_report(agent_id)
            assert isinstance(report, ShadowReport), (
                f"Expected ShadowReport for {agent_id}, got {type(report)}"
            )
            assert report.agent_id == agent_id
            assert report.total_evaluations > 0, f"Agent {agent_id} has 0 evaluations in report"

    def test_shadow_report_contains_required_metrics(self):
        """ShadowReport contains pass_rate, block_rate, hold_rate, flag_rate."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        _evaluate_all(enforcers, actions)

        # Team lead has a mix of auto-approved, flagged, held, and blocked
        report = enforcers["dm-team-lead"].generate_report("dm-team-lead")
        assert report.pass_rate >= 0.0
        assert report.block_rate >= 0.0
        assert report.hold_rate >= 0.0
        assert report.flag_rate >= 0.0
        # Rates must sum to 1.0
        total_rate = report.pass_rate + report.block_rate + report.hold_rate + report.flag_rate
        assert total_rate == pytest.approx(1.0, abs=0.01), (
            f"Rates sum to {total_rate}, expected 1.0. "
            f"pass={report.pass_rate}, block={report.block_rate}, "
            f"hold={report.hold_rate}, flag={report.flag_rate}"
        )

    def test_shadow_report_has_recommendation(self):
        """ShadowReport includes a non-empty recommendation string."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        _evaluate_all(enforcers, actions)

        report = enforcers["dm-team-lead"].generate_report("dm-team-lead")
        assert len(report.recommendation) > 0, "ShadowReport recommendation is empty"

    def test_shadow_report_upgrade_blockers_present_with_blocked_actions(self):
        """Agents with blocked actions should have upgrade blockers documented."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        _evaluate_all(enforcers, actions)

        # dm-team-lead has at least 1 blocked action (modify_constraints)
        report = enforcers["dm-team-lead"].generate_report("dm-team-lead")
        assert report.upgrade_eligible is False, (
            "Agent with blocked actions should not be upgrade eligible"
        )
        assert len(report.upgrade_blockers) > 0, (
            "Agent with blocked actions should have upgrade blockers"
        )

    def test_per_agent_metrics_independent(self):
        """Each agent's metrics are tracked independently across enforcers."""
        enforcers = _build_enforcers()
        actions = _build_simulated_actions()
        _evaluate_all(enforcers, actions)

        total = 0
        for agent_id, enforcer in enforcers.items():
            metrics = enforcer.get_metrics(agent_id)
            total += metrics.total_evaluations

        assert total == 50, (
            f"Sum of per-agent evaluations ({total}) does not equal total actions (50)"
        )

    def test_blocked_actions_classified_as_blocked_for_all_agents(self):
        """Delete and modify_constraints are classified as BLOCKED for every agent."""
        enforcers = _build_enforcers()
        for action in ["delete_old_posts", "delete_analytics_data", "modify_constraints"]:
            for agent_id, enforcer in enforcers.items():
                result = enforcer.evaluate(action, agent_id)
                assert result.verification_level == VerificationLevel.BLOCKED, (
                    f"Action '{action}' for agent '{agent_id}' should be BLOCKED, "
                    f"got {result.verification_level.value}"
                )

    def test_publish_actions_never_auto_approved(self):
        """publish_* actions are never auto-approved for any agent.

        For most agents, publish_externally is in their blocked_actions,
        so the envelope denies it (-> BLOCKED). This is correct and
        conservative: blocked is stricter than held.
        """
        enforcers = _build_enforcers()
        for action in ["publish_externally", "publish_linkedin_post"]:
            for agent_id, enforcer in enforcers.items():
                result = enforcer.evaluate(action, agent_id)
                assert result.verification_level != VerificationLevel.AUTO_APPROVED, (
                    f"Action '{action}' for '{agent_id}' must not be AUTO_APPROVED, "
                    f"got {result.verification_level.value}"
                )
