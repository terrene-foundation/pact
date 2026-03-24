# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Constraint Envelope Template Library (Task 704).

Tests TemplateRegistry: list(), get(), apply() with predefined
templates for media, governance, standards, and partnerships teams.
"""

import pytest

from pact_platform.build.templates.registry import (
    TeamTemplate,
    TemplateRegistry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry():
    """TemplateRegistry with all built-in templates loaded."""
    return TemplateRegistry()


# ---------------------------------------------------------------------------
# Test: TemplateRegistry list
# ---------------------------------------------------------------------------


class TestRegistryList:
    def test_list_returns_all_builtin_templates(self, registry):
        """list() returns at least the four Foundation team templates."""
        templates = registry.list()
        assert isinstance(templates, list)
        assert len(templates) >= 4

    def test_list_contains_expected_template_names(self, registry):
        """All four Foundation team type templates are present."""
        names = registry.list()
        assert "media" in names
        assert "governance" in names
        assert "standards" in names
        assert "partnerships" in names


# ---------------------------------------------------------------------------
# Test: TemplateRegistry get
# ---------------------------------------------------------------------------


class TestRegistryGet:
    def test_get_media_template(self, registry):
        """get('media') returns a valid TeamTemplate."""
        tpl = registry.get("media")
        assert isinstance(tpl, TeamTemplate)
        assert tpl.name == "media"
        assert len(tpl.agents) > 0
        assert len(tpl.envelopes) > 0
        assert tpl.team is not None

    def test_get_governance_template(self, registry):
        """get('governance') returns a valid TeamTemplate."""
        tpl = registry.get("governance")
        assert isinstance(tpl, TeamTemplate)
        assert tpl.name == "governance"
        assert len(tpl.agents) > 0

    def test_get_standards_template(self, registry):
        """get('standards') returns a valid TeamTemplate."""
        tpl = registry.get("standards")
        assert isinstance(tpl, TeamTemplate)
        assert tpl.name == "standards"
        assert len(tpl.agents) > 0

    def test_get_partnerships_template(self, registry):
        """get('partnerships') returns a valid TeamTemplate."""
        tpl = registry.get("partnerships")
        assert isinstance(tpl, TeamTemplate)
        assert tpl.name == "partnerships"
        assert len(tpl.agents) > 0

    def test_get_unknown_template_raises(self, registry):
        """get() for a non-existent template raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            registry.get("nonexistent-template")


# ---------------------------------------------------------------------------
# Test: TeamTemplate structure
# ---------------------------------------------------------------------------


class TestTeamTemplateStructure:
    def test_media_template_has_agent_configs(self, registry):
        """Media template agents are AgentConfig instances."""
        from pact_platform.build.config.schema import AgentConfig

        tpl = registry.get("media")
        for agent in tpl.agents:
            assert isinstance(agent, AgentConfig)

    def test_media_template_has_envelope_configs(self, registry):
        """Media template envelopes are ConstraintEnvelopeConfig instances."""
        from pact_platform.build.config.schema import ConstraintEnvelopeConfig

        tpl = registry.get("media")
        for env in tpl.envelopes:
            assert isinstance(env, ConstraintEnvelopeConfig)

    def test_media_template_has_team_config(self, registry):
        """Media template has a TeamConfig."""
        from pact_platform.build.config.schema import TeamConfig

        tpl = registry.get("media")
        assert isinstance(tpl.team, TeamConfig)

    def test_all_agents_reference_existing_envelopes(self, registry):
        """Every agent in every template references an envelope that exists in the template."""
        for name in registry.list():
            tpl = registry.get(name)
            envelope_ids = {e.id for e in tpl.envelopes}
            for agent in tpl.agents:
                assert agent.constraint_envelope in envelope_ids, (
                    f"Template '{name}': agent '{agent.id}' references "
                    f"envelope '{agent.constraint_envelope}' not in {envelope_ids}"
                )

    def test_all_agents_listed_in_team(self, registry):
        """Every agent in a template is listed in the team's agents list."""
        for name in registry.list():
            tpl = registry.get(name)
            team_agent_ids = set(tpl.team.agents)
            for agent in tpl.agents:
                assert agent.id in team_agent_ids, (
                    f"Template '{name}': agent '{agent.id}' not in team agent list"
                )


# ---------------------------------------------------------------------------
# Test: Apply with overrides
# ---------------------------------------------------------------------------


class TestApplyTemplate:
    def test_apply_returns_team_template(self, registry):
        """apply() returns a TeamTemplate."""
        result = registry.apply("media", overrides={})
        assert isinstance(result, TeamTemplate)

    def test_apply_with_team_name_override(self, registry):
        """apply() with team name override changes the team name."""
        result = registry.apply("media", overrides={"team_name": "Custom Media Team"})
        assert result.team.name == "Custom Media Team"

    def test_apply_with_team_id_override(self, registry):
        """apply() with team_id override changes the team id."""
        result = registry.apply("media", overrides={"team_id": "custom-media"})
        assert result.team.id == "custom-media"

    def test_apply_with_workspace_override(self, registry):
        """apply() with workspace override changes the workspace reference."""
        result = registry.apply("media", overrides={"workspace": "ws-custom-media"})
        assert result.team.workspace == "ws-custom-media"

    def test_apply_preserves_envelope_constraints_when_no_overrides(self, registry):
        """apply() without envelope overrides preserves original constraints."""
        original = registry.get("media")
        applied = registry.apply("media", overrides={})
        assert len(applied.envelopes) == len(original.envelopes)

    def test_apply_unknown_template_raises(self, registry):
        """apply() for unknown template raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            registry.apply("nonexistent-template", overrides={})


# ---------------------------------------------------------------------------
# Test: Envelope constraints per template
# ---------------------------------------------------------------------------


class TestTemplateConstraints:
    def test_media_template_internal_only(self, registry):
        """All media template envelopes enforce internal-only communication."""
        tpl = registry.get("media")
        for env in tpl.envelopes:
            assert env.communication.internal_only is True, (
                f"Media envelope '{env.id}' should be internal_only"
            )

    def test_partnerships_grant_writer_stricter_financial(self, registry):
        """Partnerships template grant-writer has $0 financial (strict controls)."""
        tpl = registry.get("partnerships")
        for env in tpl.envelopes:
            assert env.financial.max_spend_usd == 0.0, (
                f"Partnerships envelope '{env.id}' should have $0 spend"
            )
