# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Terrene Foundation full organization validation (Task 706).

Builds the complete Foundation org using OrgTemplate.foundation_template(),
validates it, and verifies all constraints, delegation chains, and team
structure match expectations.
"""

import pytest

from care_platform.build.config.schema import ConstraintEnvelopeConfig
from care_platform.trust.constraint.envelope import ConstraintEnvelope
from care_platform.build.org.builder import OrgTemplate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def foundation_org():
    """Complete Terrene Foundation organization from the template."""
    return OrgTemplate.foundation_template()


# ---------------------------------------------------------------------------
# Test: Foundation template validates
# ---------------------------------------------------------------------------


class TestFoundationOrgValidation:
    def test_foundation_template_passes_validation(self, foundation_org):
        """The Foundation org passes validate_org() with no errors."""
        valid, errors = foundation_org.validate_org()
        assert valid is True, f"Foundation org validation failed: {errors}"

    def test_foundation_org_has_name(self, foundation_org):
        assert foundation_org.name == "Terrene Foundation"

    def test_foundation_org_has_authority(self, foundation_org):
        assert foundation_org.authority_id == "terrene.foundation"

    def test_foundation_org_has_org_id(self, foundation_org):
        assert foundation_org.org_id == "terrene-foundation"


# ---------------------------------------------------------------------------
# Test: Team structure
# ---------------------------------------------------------------------------


class TestFoundationTeamStructure:
    def test_has_dm_team(self, foundation_org):
        """Foundation org has the DM team."""
        team_ids = {t.id for t in foundation_org.teams}
        assert "dm-team" in team_ids

    def test_dm_team_has_expected_agents(self, foundation_org):
        """DM team has the expected 5 agents."""
        dm_agents = foundation_org.get_team_agents("dm-team")
        assert len(dm_agents) == 5
        agent_ids = {a.id for a in dm_agents}
        assert "dm-team-lead" in agent_ids
        assert "dm-content-creator" in agent_ids
        assert "dm-analytics" in agent_ids
        assert "dm-community-manager" in agent_ids
        assert "dm-seo-specialist" in agent_ids


# ---------------------------------------------------------------------------
# Test: All DM agents have envelopes
# ---------------------------------------------------------------------------


class TestDMAgentsHaveEnvelopes:
    def test_all_dm_agents_have_constraint_envelopes(self, foundation_org):
        """Every DM team agent references an envelope that exists."""
        dm_agents = foundation_org.get_team_agents("dm-team")
        envelope_ids = {e.id for e in foundation_org.envelopes}
        for agent in dm_agents:
            assert agent.constraint_envelope in envelope_ids, (
                f"Agent '{agent.id}' references envelope '{agent.constraint_envelope}' "
                f"which is not in the org envelopes: {envelope_ids}"
            )

    def test_dm_agents_all_start_supervised(self, foundation_org):
        """All DM agents start at SUPERVISED trust posture."""
        dm_agents = foundation_org.get_team_agents("dm-team")
        for agent in dm_agents:
            assert agent.initial_posture == "supervised", (
                f"Agent '{agent.id}' starts at '{agent.initial_posture}', expected 'supervised'"
            )


# ---------------------------------------------------------------------------
# Test: Monotonic tightening across all delegation chains
# ---------------------------------------------------------------------------


class TestMonotonicTightening:
    def test_dm_sub_agents_tighter_than_lead(self, foundation_org):
        """Every DM sub-agent envelope is a monotonic tightening of the lead envelope."""
        envelope_map: dict[str, ConstraintEnvelopeConfig] = {
            e.id: e for e in foundation_org.envelopes
        }

        # Find lead envelope
        lead_config = envelope_map.get("dm-lead-envelope")
        assert lead_config is not None, "dm-lead-envelope not found in org envelopes"
        lead_envelope = ConstraintEnvelope(config=lead_config)

        # All sub-agent envelope IDs
        sub_envelope_ids = [
            "dm-content-envelope",
            "dm-analytics-envelope",
            "dm-community-envelope",
            "dm-seo-envelope",
        ]

        for env_id in sub_envelope_ids:
            sub_config = envelope_map.get(env_id)
            assert sub_config is not None, f"Envelope '{env_id}' not found"
            sub_envelope = ConstraintEnvelope(config=sub_config)
            assert sub_envelope.is_tighter_than(lead_envelope), (
                f"Envelope '{env_id}' is NOT a monotonic tightening of 'dm-lead-envelope'"
            )

    def test_all_dm_envelopes_zero_spend(self, foundation_org):
        """All DM envelopes have $0 financial spend."""
        dm_agents = foundation_org.get_team_agents("dm-team")
        envelope_map = {e.id: e for e in foundation_org.envelopes}
        for agent in dm_agents:
            env = envelope_map.get(agent.constraint_envelope)
            assert env is not None
            assert env.financial.max_spend_usd == 0.0, (
                f"Agent '{agent.id}' envelope '{env.id}' allows "
                f"${env.financial.max_spend_usd} spend, expected $0"
            )

    def test_all_dm_envelopes_internal_only(self, foundation_org):
        """All DM envelopes enforce internal-only communication."""
        dm_agents = foundation_org.get_team_agents("dm-team")
        envelope_map = {e.id: e for e in foundation_org.envelopes}
        for agent in dm_agents:
            env = envelope_map.get(agent.constraint_envelope)
            assert env is not None
            assert env.communication.internal_only is True, (
                f"Agent '{agent.id}' envelope '{env.id}' allows external communication"
            )


# ---------------------------------------------------------------------------
# Test: Team structure expectations
# ---------------------------------------------------------------------------


class TestTeamStructureExpectations:
    def test_dm_team_has_team_lead(self, foundation_org):
        """DM team has a designated team lead."""
        dm_team = None
        for t in foundation_org.teams:
            if t.id == "dm-team":
                dm_team = t
                break
        assert dm_team is not None
        assert dm_team.team_lead == "dm-team-lead"

    def test_dm_team_has_workspace(self, foundation_org):
        """DM team references a valid workspace."""
        dm_team = None
        for t in foundation_org.teams:
            if t.id == "dm-team":
                dm_team = t
                break
        assert dm_team is not None
        workspace_ids = {w.id for w in foundation_org.workspaces}
        assert dm_team.workspace in workspace_ids

    def test_dm_team_workspace_path(self, foundation_org):
        """DM team workspace has a valid path."""
        workspace_map = {w.id: w for w in foundation_org.workspaces}
        dm_team = None
        for t in foundation_org.teams:
            if t.id == "dm-team":
                dm_team = t
                break
        assert dm_team is not None
        ws = workspace_map.get(dm_team.workspace)
        assert ws is not None
        assert ws.path  # non-empty path
