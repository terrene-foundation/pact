# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for PACT configuration schema."""

import pytest
from pydantic import ValidationError

from pact_platform.build.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    PactConfig,
    TeamConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
    WorkspaceConfig,
)

# --- FinancialConstraintConfig ---


class TestFinancialConstraint:
    def test_defaults(self):
        fc = FinancialConstraintConfig()
        assert fc.max_spend_usd == 0.0
        assert fc.api_cost_budget_usd is None

    def test_zero_spend(self):
        fc = FinancialConstraintConfig(max_spend_usd=0.0)
        assert fc.max_spend_usd == 0.0

    def test_negative_spend_rejected(self):
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            FinancialConstraintConfig(max_spend_usd=-1.0)


# --- TemporalConstraintConfig ---


class TestTemporalConstraint:
    def test_valid_time(self):
        tc = TemporalConstraintConfig(active_hours_start="09:00", active_hours_end="18:00")
        assert tc.active_hours_start == "09:00"
        assert tc.active_hours_end == "18:00"

    def test_invalid_time_format(self):
        with pytest.raises(ValidationError, match="HH:MM"):
            TemporalConstraintConfig(active_hours_start="9am")

    def test_invalid_hour(self):
        with pytest.raises(ValidationError, match="Invalid time"):
            TemporalConstraintConfig(active_hours_start="25:00")

    def test_none_times_allowed(self):
        tc = TemporalConstraintConfig()
        assert tc.active_hours_start is None
        assert tc.active_hours_end is None

    def test_midnight(self):
        tc = TemporalConstraintConfig(active_hours_start="00:00", active_hours_end="23:59")
        assert tc.active_hours_start == "00:00"


# --- ConstraintEnvelopeConfig ---


class TestConstraintEnvelope:
    def test_minimal_envelope(self):
        env = ConstraintEnvelopeConfig(id="test-envelope")
        assert env.id == "test-envelope"
        assert env.financial.max_spend_usd == 0.0
        assert env.communication.internal_only is True

    def test_full_envelope(self):
        env = ConstraintEnvelopeConfig(
            id="full-envelope",
            description="A fully configured envelope",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
                blocked_actions=["delete"],
                max_actions_per_day=50,
            ),
        )
        assert env.financial.max_spend_usd == 100.0
        assert "read" in env.operational.allowed_actions
        assert env.operational.max_actions_per_day == 50


# --- VerificationGradientConfig ---


class TestVerificationGradient:
    def test_default_level(self):
        vg = VerificationGradientConfig()
        assert vg.default_level == VerificationLevel.HELD

    def test_with_rules(self):
        vg = VerificationGradientConfig(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read operations are safe",
                ),
                GradientRuleConfig(
                    pattern="publish_*",
                    level=VerificationLevel.BLOCKED,
                    reason="No publishing allowed",
                ),
            ],
            default_level=VerificationLevel.FLAGGED,
        )
        assert len(vg.rules) == 2
        assert vg.rules[0].level == VerificationLevel.AUTO_APPROVED


# --- AgentConfig ---


class TestAgentConfig:
    def test_minimal_agent(self):
        agent = AgentConfig(
            id="test-agent",
            name="Test Agent",
            role="Testing",
            constraint_envelope="test-envelope",
        )
        assert agent.id == "test-agent"
        assert agent.initial_posture == TrustPostureLevel.SUPERVISED
        assert agent.llm_backend is None

    def test_full_agent(self):
        agent = AgentConfig(
            id="dm-content",
            name="Content Creator",
            role="Drafts content",
            constraint_envelope="dm-content-envelope",
            initial_posture=TrustPostureLevel.SHARED_PLANNING,
            capabilities=["draft", "format"],
            llm_backend="openai",
            metadata={"team": "dm"},
        )
        assert agent.initial_posture == TrustPostureLevel.SHARED_PLANNING
        assert agent.llm_backend == "openai"


# --- WorkspaceConfig ---


class TestWorkspaceConfig:
    def test_minimal_workspace(self):
        ws = WorkspaceConfig(id="test-ws", path="workspaces/test/")
        assert ws.id == "test-ws"
        assert len(ws.knowledge_base_paths) > 0

    def test_empty_path_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            WorkspaceConfig(id="bad", path="")

    def test_whitespace_path_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            WorkspaceConfig(id="bad", path="   ")


# --- TeamConfig ---


class TestTeamConfig:
    def test_minimal_team(self):
        team = TeamConfig(id="test-team", name="Test Team", workspace="test-ws")
        assert team.default_llm_backend == "anthropic"
        assert team.team_lead is None

    def test_full_team(self):
        team = TeamConfig(
            id="dm",
            name="Digital Marketing",
            workspace="media",
            team_lead="dm-lead",
            agents=["dm-lead", "dm-content", "dm-analytics"],
        )
        assert len(team.agents) == 3


# --- PactConfig ---


class TestPactConfig:
    @pytest.fixture()
    def minimal_config(self):
        return PactConfig(
            name="Test Org",
            genesis=GenesisConfig(
                authority="test.org",
                authority_name="Test Organization",
            ),
        )

    @pytest.fixture()
    def full_config(self):
        return PactConfig(
            name="Terrene Foundation",
            genesis=GenesisConfig(
                authority="terrene.foundation",
                authority_name="Terrene Foundation",
            ),
            constraint_envelopes=[
                ConstraintEnvelopeConfig(id="env-1"),
                ConstraintEnvelopeConfig(id="env-2"),
            ],
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent One",
                    role="Testing",
                    constraint_envelope="env-1",
                ),
                AgentConfig(
                    id="agent-2",
                    name="Agent Two",
                    role="Testing",
                    constraint_envelope="env-2",
                ),
            ],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team One",
                    workspace="ws-1",
                    agents=["agent-1", "agent-2"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/test/"),
            ],
        )

    def test_minimal_config(self, minimal_config):
        assert minimal_config.name == "Test Org"
        assert minimal_config.default_posture == TrustPostureLevel.SUPERVISED

    def test_lookup_envelope(self, full_config):
        env = full_config.get_envelope("env-1")
        assert env is not None
        assert env.id == "env-1"

    def test_lookup_missing_envelope(self, full_config):
        assert full_config.get_envelope("nonexistent") is None

    def test_lookup_agent(self, full_config):
        agent = full_config.get_agent("agent-1")
        assert agent is not None
        assert agent.name == "Agent One"

    def test_lookup_team(self, full_config):
        team = full_config.get_team("team-1")
        assert team is not None
        assert len(team.agents) == 2

    def test_lookup_workspace(self, full_config):
        ws = full_config.get_workspace("ws-1")
        assert ws is not None
        assert ws.path == "workspaces/test/"

    def test_duplicate_envelope_ids_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate constraint envelope IDs"):
            PactConfig(
                name="Test",
                genesis=GenesisConfig(authority="test", authority_name="Test"),
                constraint_envelopes=[
                    ConstraintEnvelopeConfig(id="dup"),
                    ConstraintEnvelopeConfig(id="dup"),
                ],
            )

    def test_duplicate_agent_ids_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate agent IDs"):
            PactConfig(
                name="Test",
                genesis=GenesisConfig(authority="test", authority_name="Test"),
                agents=[
                    AgentConfig(id="dup", name="A", role="R", constraint_envelope="e"),
                    AgentConfig(id="dup", name="B", role="R", constraint_envelope="e"),
                ],
            )

    def test_duplicate_team_ids_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate team IDs"):
            PactConfig(
                name="Test",
                genesis=GenesisConfig(authority="test", authority_name="Test"),
                teams=[
                    TeamConfig(id="dup", name="A", workspace="ws"),
                    TeamConfig(id="dup", name="B", workspace="ws"),
                ],
            )
