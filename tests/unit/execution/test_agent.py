# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for agent and team definition models."""

import pytest

from care_platform.build.config.schema import AgentConfig, TeamConfig, TrustPostureLevel
from care_platform.use.execution.agent import AgentDefinition, TeamDefinition
from care_platform.trust.attestation import CapabilityAttestation


class TestAgentDefinition:
    def test_from_config(self):
        config = AgentConfig(
            id="agent-1",
            name="Test Agent",
            role="Testing",
            constraint_envelope="env-1",
        )
        agent = AgentDefinition.from_config(config)
        assert agent.id == "agent-1"
        assert agent.posture.current_level == TrustPostureLevel.SUPERVISED
        assert agent.is_operational

    def test_revoke(self):
        config = AgentConfig(
            id="agent-1",
            name="Test",
            role="Test",
            constraint_envelope="env-1",
        )
        agent = AgentDefinition.from_config(config)
        agent.revoke("Security issue")
        assert not agent.is_operational
        assert not agent.active

    def test_revoke_with_attestation(self):
        config = AgentConfig(
            id="agent-1",
            name="Test",
            role="Test",
            constraint_envelope="env-1",
        )
        agent = AgentDefinition.from_config(config)
        agent.attestation = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="root",
        )
        agent.revoke("Revoked")
        assert agent.attestation.revoked


class TestTeamDefinition:
    def test_add_and_list_agents(self):
        team = TeamDefinition(config=TeamConfig(id="team-1", name="Test", workspace="ws-1"))
        agent = AgentDefinition.from_config(
            AgentConfig(id="a-1", name="A", role="R", constraint_envelope="e")
        )
        team.add_agent(agent)
        assert len(team.operational_agents) == 1

    def test_surgical_revocation(self):
        team = TeamDefinition(config=TeamConfig(id="team-1", name="Test", workspace="ws-1"))
        a1 = AgentDefinition.from_config(
            AgentConfig(id="a-1", name="A", role="R", constraint_envelope="e")
        )
        a2 = AgentDefinition.from_config(
            AgentConfig(id="a-2", name="B", role="R", constraint_envelope="e")
        )
        team.add_agent(a1)
        team.add_agent(a2)
        team.revoke_agent("a-1", "Incident")
        assert len(team.operational_agents) == 1
        assert team.operational_agents[0].id == "a-2"

    def test_cascade_revocation(self):
        team = TeamDefinition(config=TeamConfig(id="team-1", name="Test", workspace="ws-1"))
        for i in range(3):
            team.add_agent(
                AgentDefinition.from_config(
                    AgentConfig(id=f"a-{i}", name=f"A{i}", role="R", constraint_envelope="e")
                )
            )
        team.revoke_all("Emergency")
        assert not team.active
        assert len(team.operational_agents) == 0

    def test_revoke_unknown_agent_raises(self):
        team = TeamDefinition(config=TeamConfig(id="team-1", name="Test", workspace="ws-1"))
        with pytest.raises(ValueError, match="not found"):
            team.revoke_agent("nonexistent", "Reason")
