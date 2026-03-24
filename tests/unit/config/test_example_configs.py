# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for example configuration files (Task 112).

Validates that all example YAML configs pass schema validation and contain
the expected Foundation team structure.
"""

from pathlib import Path

import pytest

from pact_platform.build.config.loader import load_config

EXAMPLES_DIR = Path(__file__).parents[3] / "examples"


class TestCareConfigYaml:
    """Tests for the full Foundation configuration (care-config.yaml)."""

    @pytest.fixture()
    def config(self):
        config_path = EXAMPLES_DIR / "care-config.yaml"
        assert config_path.exists(), f"Example config not found at {config_path}"
        return load_config(config_path)

    def test_loads_without_error(self, config):
        assert config is not None

    def test_foundation_name(self, config):
        assert config.name == "Terrene Foundation"

    def test_genesis_authority(self, config):
        assert config.genesis.authority == "terrene.foundation"
        assert config.genesis.authority_name == "Terrene Foundation"

    def test_default_posture_is_supervised(self, config):
        assert config.default_posture.value == "supervised"

    # --- DM Team agents from the analysis doc ---

    def test_has_dm_team_lead(self, config):
        agent = config.get_agent("dm-team-lead")
        assert agent is not None, "DM Team Lead agent must exist"
        assert agent.constraint_envelope is not None

    def test_has_dm_content_creator(self, config):
        agent = config.get_agent("dm-content-creator")
        assert agent is not None, "Content Creator agent must exist"

    def test_has_dm_analytics(self, config):
        agent = config.get_agent("dm-analytics")
        assert agent is not None, "Analytics agent must exist"

    def test_has_dm_scheduling(self, config):
        agent = config.get_agent("dm-scheduling")
        assert agent is not None, "Scheduling agent must exist"

    def test_has_dm_podcast_extractor(self, config):
        agent = config.get_agent("dm-podcast-extractor")
        assert agent is not None, "Podcast Clip Extractor agent must exist"

    def test_has_dm_outreach(self, config):
        agent = config.get_agent("dm-outreach")
        assert agent is not None, "Outreach agent must exist"

    # --- Constraint envelopes from the analysis doc ---

    def test_dm_team_lead_envelope_financial(self, config):
        env = config.get_envelope("dm-team-lead-envelope")
        assert env is not None
        assert env.financial.max_spend_usd == 0.0

    def test_dm_team_lead_envelope_operational(self, config):
        env = config.get_envelope("dm-team-lead-envelope")
        assert env is not None
        assert "coordinate_team" in env.operational.allowed_actions
        assert "publish_external" in env.operational.blocked_actions

    def test_dm_team_lead_envelope_temporal(self, config):
        env = config.get_envelope("dm-team-lead-envelope")
        assert env is not None
        assert env.temporal.active_hours_start == "09:00"
        assert env.temporal.active_hours_end == "18:00"
        assert env.temporal.timezone == "Asia/Singapore"

    def test_dm_team_lead_envelope_data_access(self, config):
        env = config.get_envelope("dm-team-lead-envelope")
        assert env is not None
        assert "pii" in env.data_access.blocked_data_types
        assert "financial_records" in env.data_access.blocked_data_types

    def test_dm_team_lead_envelope_communication(self, config):
        env = config.get_envelope("dm-team-lead-envelope")
        assert env is not None
        assert env.communication.internal_only is True
        assert env.communication.external_requires_approval is True

    def test_dm_content_creator_envelope_rate_limit(self, config):
        env = config.get_envelope("dm-content-creator-envelope")
        assert env is not None
        assert env.operational.max_actions_per_day == 20

    def test_dm_content_creator_envelope_blocked_publish(self, config):
        env = config.get_envelope("dm-content-creator-envelope")
        assert env is not None
        assert "publish_external" in env.operational.blocked_actions

    def test_dm_analytics_envelope_batch_hours(self, config):
        env = config.get_envelope("dm-analytics-envelope")
        assert env is not None
        assert env.temporal.active_hours_start == "22:00"
        assert env.temporal.active_hours_end == "06:00"

    def test_dm_scheduling_envelope_exists(self, config):
        env = config.get_envelope("dm-scheduling-envelope")
        assert env is not None
        assert env.financial.max_spend_usd == 0.0

    def test_dm_podcast_extractor_envelope_exists(self, config):
        env = config.get_envelope("dm-podcast-extractor-envelope")
        assert env is not None

    def test_dm_outreach_envelope_exists(self, config):
        env = config.get_envelope("dm-outreach-envelope")
        assert env is not None

    # --- Team structure ---

    def test_has_dm_team(self, config):
        team = config.get_team("dm-team")
        assert team is not None
        assert team.name == "Digital Marketing"
        assert team.team_lead == "dm-team-lead"

    def test_dm_team_has_all_agents(self, config):
        team = config.get_team("dm-team")
        assert team is not None
        expected_agents = [
            "dm-team-lead",
            "dm-content-creator",
            "dm-analytics",
            "dm-scheduling",
            "dm-podcast-extractor",
            "dm-outreach",
        ]
        for agent_id in expected_agents:
            assert agent_id in team.agents, f"{agent_id} not in DM team agents list"

    # --- Workspaces ---

    def test_has_media_workspace(self, config):
        ws = config.get_workspace("media")
        assert ws is not None
        assert "media" in ws.path.lower() or "workspaces" in ws.path.lower()

    # --- No duplicate IDs ---

    def test_unique_envelope_ids(self, config):
        ids = [e.id for e in config.constraint_envelopes]
        assert len(ids) == len(set(ids)), f"Duplicate envelope IDs: {ids}"

    def test_unique_agent_ids(self, config):
        ids = [a.id for a in config.agents]
        assert len(ids) == len(set(ids)), f"Duplicate agent IDs: {ids}"

    # --- All agents reference valid envelopes ---

    def test_all_agents_reference_valid_envelopes(self, config):
        envelope_ids = {e.id for e in config.constraint_envelopes}
        for agent in config.agents:
            assert agent.constraint_envelope in envelope_ids, (
                f"Agent '{agent.id}' references envelope '{agent.constraint_envelope}' "
                f"which does not exist"
            )


class TestMinimalConfigYaml:
    """Tests for the minimal configuration (minimal-config.yaml)."""

    @pytest.fixture()
    def config(self):
        config_path = EXAMPLES_DIR / "minimal-config.yaml"
        assert config_path.exists(), f"Minimal config not found at {config_path}"
        return load_config(config_path)

    def test_loads_without_error(self, config):
        assert config is not None

    def test_has_name(self, config):
        assert config.name is not None
        assert len(config.name) > 0

    def test_has_genesis(self, config):
        assert config.genesis is not None
        assert config.genesis.authority is not None
        assert config.genesis.authority_name is not None

    def test_minimal_means_few_items(self, config):
        """Minimal config should have at most 1 agent, 1 team, 1 envelope, 1 workspace."""
        assert len(config.agents) <= 1
        assert len(config.teams) <= 1
        assert len(config.constraint_envelopes) <= 1
        assert len(config.workspaces) <= 1


class TestQuickstartScript:
    """Tests for the quickstart.py example script."""

    def test_quickstart_exists(self):
        quickstart = EXAMPLES_DIR / "quickstart.py"
        assert quickstart.exists(), "quickstart.py must exist in examples/"

    def test_quickstart_is_valid_python(self):
        """Verify quickstart.py compiles without syntax errors."""
        import py_compile

        quickstart = EXAMPLES_DIR / "quickstart.py"
        if quickstart.exists():
            py_compile.compile(str(quickstart), doraise=True)

    def test_quickstart_imports_core_types(self):
        """Verify quickstart.py references the core API types."""
        quickstart = EXAMPLES_DIR / "quickstart.py"
        if quickstart.exists():
            source = quickstart.read_text()
            assert "ConstraintEnvelope" in source
            assert "EvaluationResult" in source or "evaluate_action" in source
            assert "TrustScore" in source or "calculate_trust_score" in source
