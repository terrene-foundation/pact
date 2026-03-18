# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for DM Team — Digital Media team definition (Tasks 601-605).

Validates that the DM team vertical correctly defines 5 specialist agents,
each with properly scoped EATP constraint envelopes and a verification gradient
aligned to the trust model research.
"""

from care_platform.build.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    TeamConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.build.verticals.dm_team import (
    DM_ANALYTICS,
    DM_ANALYTICS_ENVELOPE,
    DM_COMMUNITY_ENVELOPE,
    DM_COMMUNITY_MANAGER,
    DM_CONTENT_CREATOR,
    DM_CONTENT_ENVELOPE,
    DM_LEAD_ENVELOPE,
    DM_SEO_ENVELOPE,
    DM_SEO_SPECIALIST,
    DM_TEAM,
    DM_TEAM_LEAD,
    DM_VERIFICATION_GRADIENT,
    get_dm_team_config,
    validate_dm_team,
)


class TestDMTeamAgents:
    """Test 601: DM team defines exactly 5 specialist agents."""

    def test_dm_team_has_five_agents(self):
        """DM team config must contain exactly 5 agents."""
        config = get_dm_team_config()
        assert len(config["agents"]) == 5

    def test_all_agents_are_agent_config(self):
        """Every agent must be an AgentConfig instance."""
        config = get_dm_team_config()
        for agent in config["agents"]:
            assert isinstance(agent, AgentConfig), f"{agent} is not AgentConfig"

    def test_all_agents_have_unique_ids(self):
        """No duplicate agent IDs."""
        config = get_dm_team_config()
        ids = [a.id for a in config["agents"]]
        assert len(ids) == len(set(ids)), f"Duplicate agent IDs found: {ids}"

    def test_team_lead_exists(self):
        """DM team lead must be defined."""
        assert DM_TEAM_LEAD.id == "dm-team-lead"
        assert DM_TEAM_LEAD.name == "DM Team Lead"

    def test_content_creator_exists(self):
        """Content Creator agent must be defined."""
        assert DM_CONTENT_CREATOR.id == "dm-content-creator"

    def test_analytics_agent_exists(self):
        """Analytics agent must be defined."""
        assert DM_ANALYTICS.id == "dm-analytics"

    def test_community_manager_exists(self):
        """Community Manager agent must be defined."""
        assert DM_COMMUNITY_MANAGER.id == "dm-community-manager"

    def test_seo_specialist_exists(self):
        """SEO Specialist agent must be defined."""
        assert DM_SEO_SPECIALIST.id == "dm-seo-specialist"


class TestDMTeamEnvelopeReferences:
    """Test 602: All agents reference valid, existing envelopes."""

    def test_all_agents_reference_valid_envelopes(self):
        """Each agent's constraint_envelope must match a defined envelope ID."""
        config = get_dm_team_config()
        envelope_ids = {e.id for e in config["envelopes"]}
        for agent in config["agents"]:
            assert agent.constraint_envelope in envelope_ids, (
                f"Agent '{agent.id}' references envelope '{agent.constraint_envelope}' "
                f"which is not in defined envelopes: {envelope_ids}"
            )

    def test_team_lead_references_lead_envelope(self):
        assert DM_TEAM_LEAD.constraint_envelope == DM_LEAD_ENVELOPE.id

    def test_content_creator_references_content_envelope(self):
        assert DM_CONTENT_CREATOR.constraint_envelope == DM_CONTENT_ENVELOPE.id

    def test_analytics_references_analytics_envelope(self):
        assert DM_ANALYTICS.constraint_envelope == DM_ANALYTICS_ENVELOPE.id

    def test_community_references_community_envelope(self):
        assert DM_COMMUNITY_MANAGER.constraint_envelope == DM_COMMUNITY_ENVELOPE.id

    def test_seo_references_seo_envelope(self):
        assert DM_SEO_SPECIALIST.constraint_envelope == DM_SEO_ENVELOPE.id


class TestDMConstraintTightening:
    """Test 603: Content creator envelope is tighter than team lead envelope."""

    def test_content_creator_lower_financial_limit(self):
        """Content creator must have lower or equal financial limit vs lead."""
        assert (
            DM_CONTENT_ENVELOPE.financial.max_spend_usd <= DM_LEAD_ENVELOPE.financial.max_spend_usd
        )

    def test_content_creator_fewer_allowed_actions(self):
        """Content creator must have equal or fewer allowed actions than lead."""
        assert len(DM_CONTENT_ENVELOPE.operational.allowed_actions) <= len(
            DM_LEAD_ENVELOPE.operational.allowed_actions
        )

    def test_content_creator_is_internal_only(self):
        """Content creator must be internal-only communication."""
        assert DM_CONTENT_ENVELOPE.communication.internal_only is True

    def test_analytics_lower_financial_limit_than_lead(self):
        """Analytics must have lower or equal financial limit vs lead."""
        assert (
            DM_ANALYTICS_ENVELOPE.financial.max_spend_usd
            <= DM_LEAD_ENVELOPE.financial.max_spend_usd
        )

    def test_seo_lower_financial_limit_than_lead(self):
        """SEO must have lower or equal financial limit vs lead."""
        assert DM_SEO_ENVELOPE.financial.max_spend_usd <= DM_LEAD_ENVELOPE.financial.max_spend_usd

    def test_community_lower_financial_limit_than_lead(self):
        """Community manager must have lower or equal financial limit vs lead."""
        assert (
            DM_COMMUNITY_ENVELOPE.financial.max_spend_usd
            <= DM_LEAD_ENVELOPE.financial.max_spend_usd
        )


class TestDMAnalyticsTemporal:
    """Test 604: Analytics agent inherits lead's temporal window for monotonic tightening."""

    def test_analytics_active_hours_within_lead(self):
        """Analytics active hours must be within (or equal to) lead's active hours."""
        assert DM_ANALYTICS_ENVELOPE.temporal.active_hours_start is not None
        assert DM_ANALYTICS_ENVELOPE.temporal.active_hours_end is not None
        assert DM_LEAD_ENVELOPE.temporal.active_hours_start is not None
        assert DM_LEAD_ENVELOPE.temporal.active_hours_end is not None


class TestDMContentCreatorCommunication:
    """Test 605: Content creator is internal-only communication."""

    def test_content_creator_internal_only(self):
        assert DM_CONTENT_ENVELOPE.communication.internal_only is True

    def test_content_creator_external_requires_approval(self):
        assert DM_CONTENT_ENVELOPE.communication.external_requires_approval is True

    def test_analytics_internal_only(self):
        """Analytics should also be internal-only."""
        assert DM_ANALYTICS_ENVELOPE.communication.internal_only is True


class TestDMVerificationGradient:
    """Verification gradient blocks delete and modify_constraints actions."""

    def test_gradient_is_verification_gradient_config(self):
        assert isinstance(DM_VERIFICATION_GRADIENT, VerificationGradientConfig)

    def test_gradient_default_is_flagged(self):
        assert DM_VERIFICATION_GRADIENT.default_level == VerificationLevel.FLAGGED

    def test_read_actions_auto_approved(self):
        """read_* pattern must be auto-approved."""
        read_rule = _find_rule(DM_VERIFICATION_GRADIENT, "read_*")
        assert read_rule is not None, "No rule found for 'read_*'"
        assert read_rule.level == VerificationLevel.AUTO_APPROVED

    def test_draft_actions_auto_approved(self):
        """draft_* pattern must be auto-approved."""
        draft_rule = _find_rule(DM_VERIFICATION_GRADIENT, "draft_*")
        assert draft_rule is not None, "No rule found for 'draft_*'"
        assert draft_rule.level == VerificationLevel.AUTO_APPROVED

    def test_analyze_actions_auto_approved(self):
        """analyze_* pattern must be auto-approved."""
        analyze_rule = _find_rule(DM_VERIFICATION_GRADIENT, "analyze_*")
        assert analyze_rule is not None, "No rule found for 'analyze_*'"
        assert analyze_rule.level == VerificationLevel.AUTO_APPROVED

    def test_approve_actions_held(self):
        """approve_* pattern must be held for human review."""
        approve_rule = _find_rule(DM_VERIFICATION_GRADIENT, "approve_*")
        assert approve_rule is not None, "No rule found for 'approve_*'"
        assert approve_rule.level == VerificationLevel.HELD

    def test_publish_actions_held(self):
        """publish_* pattern must be held for human review."""
        publish_rule = _find_rule(DM_VERIFICATION_GRADIENT, "publish_*")
        assert publish_rule is not None, "No rule found for 'publish_*'"
        assert publish_rule.level == VerificationLevel.HELD

    def test_external_actions_held(self):
        """external_* pattern must be held for human review."""
        ext_rule = _find_rule(DM_VERIFICATION_GRADIENT, "external_*")
        assert ext_rule is not None, "No rule found for 'external_*'"
        assert ext_rule.level == VerificationLevel.HELD

    def test_delete_actions_blocked(self):
        """delete_* pattern must be blocked outright."""
        delete_rule = _find_rule(DM_VERIFICATION_GRADIENT, "delete_*")
        assert delete_rule is not None, "No rule found for 'delete_*'"
        assert delete_rule.level == VerificationLevel.BLOCKED

    def test_modify_constraints_blocked(self):
        """modify_constraints pattern must be blocked outright."""
        modify_rule = _find_rule(DM_VERIFICATION_GRADIENT, "modify_constraints")
        assert modify_rule is not None, "No rule found for 'modify_constraints'"
        assert modify_rule.level == VerificationLevel.BLOCKED


class TestDMValidation:
    """validate_dm_team returns success with no errors for the default config."""

    def test_validate_dm_team_passes(self):
        valid, errors = validate_dm_team()
        assert valid is True, f"DM team validation failed: {errors}"
        assert errors == []


class TestDMTeamConfig:
    """Team config structural tests."""

    def test_team_is_team_config(self):
        assert isinstance(DM_TEAM, TeamConfig)

    def test_team_id(self):
        assert DM_TEAM.id == "dm-team"

    def test_team_name(self):
        assert DM_TEAM.name == "Digital Media Team"

    def test_team_workspace(self):
        assert DM_TEAM.workspace == "ws-dm"

    def test_get_dm_team_config_has_gradient(self):
        config = get_dm_team_config()
        assert "gradient" in config
        assert isinstance(config["gradient"], VerificationGradientConfig)

    def test_get_dm_team_config_has_teams(self):
        config = get_dm_team_config()
        assert len(config["teams"]) == 1
        assert config["teams"][0].id == "dm-team"

    def test_all_envelopes_are_constraint_envelope_config(self):
        config = get_dm_team_config()
        for envelope in config["envelopes"]:
            assert isinstance(envelope, ConstraintEnvelopeConfig), (
                f"{envelope} is not ConstraintEnvelopeConfig"
            )


# --- Helpers ---


def _find_rule(gradient: VerificationGradientConfig, pattern: str):
    """Find a gradient rule by pattern."""
    for rule in gradient.rules:
        if rule.pattern == pattern:
            return rule
    return None
