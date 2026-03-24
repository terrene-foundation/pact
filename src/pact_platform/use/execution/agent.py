# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Agent and team definition models — runtime representations of agents and teams.

These models extend the config-level AgentConfig/TeamConfig with runtime state
(posture, attestation, action history).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from pact_platform.build.config.schema import AgentConfig, TeamConfig
from kailash.trust import CapabilityAttestation
from pact_platform.trust._compat import TrustPosture


class AgentDefinition(BaseModel):
    """Runtime agent definition combining config with trust state."""

    config: AgentConfig
    posture: TrustPosture
    attestation: CapabilityAttestation | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    active: bool = True

    @property
    def id(self) -> str:
        return self.config.id

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_operational(self) -> bool:
        """Agent is operational if active, has valid attestation, and not revoked."""
        if not self.active:
            return False
        return not (self.attestation is not None and not self.attestation.is_valid)

    def revoke(self, reason: str) -> None:
        """Revoke this agent — deactivates and revokes attestation."""
        self.active = False
        if self.attestation is not None:
            self.attestation.revoke(reason)

    @classmethod
    def from_config(cls, config: AgentConfig) -> AgentDefinition:
        """Create an AgentDefinition from an AgentConfig."""
        return cls(
            config=config,
            posture=TrustPosture(
                agent_id=config.id,
                current_level=config.initial_posture,
            ),
        )


class TeamDefinition(BaseModel):
    """Runtime team definition with member agents."""

    config: TeamConfig
    agents: dict[str, AgentDefinition] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    active: bool = True

    @property
    def id(self) -> str:
        return self.config.id

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def team_lead(self) -> AgentDefinition | None:
        if self.config.team_lead is None:
            return None
        return self.agents.get(self.config.team_lead)

    @property
    def operational_agents(self) -> list[AgentDefinition]:
        return [a for a in self.agents.values() if a.is_operational]

    def add_agent(self, agent: AgentDefinition) -> None:
        self.agents[agent.id] = agent

    def revoke_agent(self, agent_id: str, reason: str) -> None:
        """Surgical revocation — revoke one agent without affecting others."""
        agent = self.agents.get(agent_id)
        if agent is None:
            raise ValueError(f"Agent '{agent_id}' not found in team '{self.id}'")
        agent.revoke(reason)

    def revoke_all(self, reason: str) -> None:
        """Team-wide cascade revocation — revoke all agents."""
        self.active = False
        for agent in self.agents.values():
            agent.revoke(reason)
