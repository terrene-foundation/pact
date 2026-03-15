# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Organization Builder (Tasks 701-703).

Validates that OrgDefinition, OrgBuilder, and OrgTemplate correctly create,
validate, and manage organization definitions with proper constraint enforcement.
"""

import pytest

from care_platform.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    GenesisConfig,
    PlatformConfig,
    TeamConfig,
    WorkspaceConfig,
)
from care_platform.org.builder import OrgBuilder, OrgDefinition, OrgTemplate


class TestOrgDefinition:
    """OrgDefinition model correctness."""

    def test_minimal_org_definition(self):
        """An org with just an id and name is valid."""
        org = OrgDefinition(org_id="test-org", name="Test Organization")
        assert org.org_id == "test-org"
        assert org.name == "Test Organization"
        assert org.teams == []
        assert org.agents == []
        assert org.envelopes == []
        assert org.workspaces == []

    def test_org_definition_with_authority(self):
        org = OrgDefinition(
            org_id="terrene",
            name="Terrene Foundation",
            authority_id="terrene.foundation",
        )
        assert org.authority_id == "terrene.foundation"


class TestOrgBuilder:
    """Test 701: OrgBuilder creates valid organization definitions."""

    def test_builder_creates_valid_org(self):
        """Building a fully-wired org should produce a valid OrgDefinition."""
        org = (
            OrgBuilder("test-org", "Test Organization")
            .add_workspace(WorkspaceConfig(id="ws-1", path="workspaces/test/"))
            .add_envelope(ConstraintEnvelopeConfig(id="env-1"))
            .add_agent(
                AgentConfig(
                    id="agent-1",
                    name="Agent One",
                    role="Testing",
                    constraint_envelope="env-1",
                )
            )
            .add_team(
                TeamConfig(
                    id="team-1",
                    name="Team One",
                    workspace="ws-1",
                    agents=["agent-1"],
                )
            )
            .build()
        )
        assert isinstance(org, OrgDefinition)
        assert org.org_id == "test-org"
        assert len(org.agents) == 1
        assert len(org.teams) == 1
        assert len(org.envelopes) == 1
        assert len(org.workspaces) == 1

    def test_builder_returns_self_for_chaining(self):
        """Each add_* method must return the builder for fluent chaining."""
        builder = OrgBuilder("chain-test", "Chain Test")
        result = builder.add_workspace(WorkspaceConfig(id="ws", path="workspaces/ws/"))
        assert result is builder
        result = builder.add_envelope(ConstraintEnvelopeConfig(id="env"))
        assert result is builder
        result = builder.add_agent(
            AgentConfig(id="a", name="A", role="R", constraint_envelope="env")
        )
        assert result is builder
        result = builder.add_team(TeamConfig(id="t", name="T", workspace="ws"))
        assert result is builder


class TestOrgValidationMissingEnvelope:
    """Test 702: Validation catches missing envelope references."""

    def test_validation_catches_missing_envelope_reference(self):
        """An agent referencing a non-existent envelope must fail validation."""
        org = OrgDefinition(
            org_id="bad-org",
            name="Bad Org",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="nonexistent-envelope",
                )
            ],
            envelopes=[],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any(
            "nonexistent-envelope" in e for e in errors
        ), f"Expected error about 'nonexistent-envelope', got: {errors}"

    def test_validation_catches_missing_workspace_reference(self):
        """A team referencing a non-existent workspace must fail validation."""
        org = OrgDefinition(
            org_id="bad-org",
            name="Bad Org",
            teams=[TeamConfig(id="team-1", name="Team", workspace="nonexistent-ws")],
            workspaces=[],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any(
            "nonexistent-ws" in e for e in errors
        ), f"Expected error about 'nonexistent-ws', got: {errors}"


class TestOrgValidationDuplicateIDs:
    """Test 703: Validation catches duplicate IDs."""

    def test_validation_catches_duplicate_agent_ids(self):
        org = OrgDefinition(
            org_id="dup-org",
            name="Dup Org",
            agents=[
                AgentConfig(id="dup", name="A", role="R", constraint_envelope="e"),
                AgentConfig(id="dup", name="B", role="R", constraint_envelope="e"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("dup" in e.lower() for e in errors)

    def test_validation_catches_duplicate_team_ids(self):
        org = OrgDefinition(
            org_id="dup-org",
            name="Dup Org",
            teams=[
                TeamConfig(id="dup", name="A", workspace="ws"),
                TeamConfig(id="dup", name="B", workspace="ws"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("dup" in e.lower() for e in errors)

    def test_validation_catches_duplicate_envelope_ids(self):
        org = OrgDefinition(
            org_id="dup-org",
            name="Dup Org",
            envelopes=[
                ConstraintEnvelopeConfig(id="dup"),
                ConstraintEnvelopeConfig(id="dup"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("dup" in e.lower() for e in errors)

    def test_validation_catches_duplicate_workspace_ids(self):
        org = OrgDefinition(
            org_id="dup-org",
            name="Dup Org",
            workspaces=[
                WorkspaceConfig(id="dup", path="workspaces/a/"),
                WorkspaceConfig(id="dup", path="workspaces/b/"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("dup" in e.lower() for e in errors)


class TestOrgFromConfigRoundTrip:
    """Test 704: from_config round-trips correctly."""

    def test_from_config_round_trips(self):
        """Creating an OrgDefinition from PlatformConfig should preserve all data."""
        platform = PlatformConfig(
            name="Round Trip Org",
            genesis=GenesisConfig(
                authority="test.org",
                authority_name="Test Organization",
            ),
            constraint_envelopes=[
                ConstraintEnvelopeConfig(id="env-1"),
            ],
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent One",
                    role="Testing",
                    constraint_envelope="env-1",
                ),
            ],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team One",
                    workspace="ws-1",
                    agents=["agent-1"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/test/"),
            ],
        )
        org = OrgBuilder.from_config(platform)
        assert isinstance(org, OrgDefinition)
        assert org.name == "Round Trip Org"
        assert org.authority_id == "test.org"
        assert len(org.agents) == 1
        assert len(org.teams) == 1
        assert len(org.envelopes) == 1
        assert len(org.workspaces) == 1
        assert org.agents[0].id == "agent-1"
        assert org.teams[0].id == "team-1"
        assert org.envelopes[0].id == "env-1"
        assert org.workspaces[0].id == "ws-1"


class TestOrgTemplateMinimal:
    """Test 705: Minimal template is a valid org."""

    def test_minimal_template_is_valid(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert isinstance(org, OrgDefinition)
        valid, errors = org.validate_org()
        assert valid is True, f"Minimal template invalid: {errors}"

    def test_minimal_template_has_name(self):
        org = OrgTemplate.minimal_template("My Org")
        assert org.name == "My Org"

    def test_minimal_template_has_at_least_one_agent(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert len(org.agents) >= 1

    def test_minimal_template_has_at_least_one_team(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert len(org.teams) >= 1

    def test_minimal_template_has_at_least_one_workspace(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert len(org.workspaces) >= 1

    def test_minimal_template_has_at_least_one_envelope(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert len(org.envelopes) >= 1


class TestOrgTemplateFoundation:
    """Test 706: Foundation template has expected structure."""

    def test_foundation_template_is_valid(self):
        org = OrgTemplate.foundation_template()
        valid, errors = org.validate_org()
        assert valid is True, f"Foundation template invalid: {errors}"

    def test_foundation_template_has_dm_team(self):
        """Foundation template must include the DM team."""
        org = OrgTemplate.foundation_template()
        team_ids = {t.id for t in org.teams}
        assert "dm-team" in team_ids, f"Expected 'dm-team' in {team_ids}"

    def test_foundation_template_name(self):
        org = OrgTemplate.foundation_template()
        assert org.name == "Terrene Foundation"

    def test_foundation_template_authority(self):
        org = OrgTemplate.foundation_template()
        assert org.authority_id == "terrene.foundation"


class TestOrgGetTeamAgents:
    """Test 707: get_team_agents returns the correct subset of agents."""

    def test_get_team_agents_returns_correct_subset(self):
        org = OrgDefinition(
            org_id="test-org",
            name="Test Org",
            agents=[
                AgentConfig(id="a-1", name="A1", role="R", constraint_envelope="e"),
                AgentConfig(id="a-2", name="A2", role="R", constraint_envelope="e"),
                AgentConfig(id="a-3", name="A3", role="R", constraint_envelope="e"),
            ],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team One",
                    workspace="ws",
                    agents=["a-1", "a-2"],
                ),
                TeamConfig(
                    id="team-2",
                    name="Team Two",
                    workspace="ws",
                    agents=["a-3"],
                ),
            ],
        )
        team1_agents = org.get_team_agents("team-1")
        assert len(team1_agents) == 2
        agent_ids = {a.id for a in team1_agents}
        assert agent_ids == {"a-1", "a-2"}

    def test_get_team_agents_unknown_team_raises(self):
        org = OrgDefinition(org_id="test-org", name="Test Org")
        with pytest.raises(ValueError, match="not found"):
            org.get_team_agents("nonexistent-team")

    def test_get_team_agents_empty_team(self):
        org = OrgDefinition(
            org_id="test-org",
            name="Test Org",
            teams=[
                TeamConfig(id="empty-team", name="Empty", workspace="ws", agents=[]),
            ],
        )
        agents = org.get_team_agents("empty-team")
        assert agents == []


class TestOrgBuildValidation:
    """build() must validate and raise on invalid configurations."""

    def test_build_raises_on_missing_envelope(self):
        """OrgBuilder.build() must raise ValueError when an agent references a missing envelope."""
        with pytest.raises(ValueError, match="nonexistent-envelope"):
            (
                OrgBuilder("bad-org", "Bad Org")
                .add_agent(
                    AgentConfig(
                        id="agent-1",
                        name="Agent",
                        role="Role",
                        constraint_envelope="nonexistent-envelope",
                    )
                )
                .build()
            )

    def test_build_raises_on_missing_workspace(self):
        """OrgBuilder.build() must raise ValueError when a team references a missing workspace."""
        with pytest.raises(ValueError, match="nonexistent-ws"):
            (
                OrgBuilder("bad-org", "Bad Org")
                .add_team(TeamConfig(id="team-1", name="Team", workspace="nonexistent-ws"))
                .build()
            )
