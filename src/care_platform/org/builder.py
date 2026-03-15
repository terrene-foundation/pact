# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Organization definition and builder — enables defining any team structure.

OrgDefinition is the data model for a complete organization.
OrgBuilder provides a fluent builder API for constructing org definitions.
OrgTemplate provides predefined templates for common org structures.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from care_platform.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    PlatformConfig,
    TeamConfig,
    WorkspaceConfig,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class OrgDefinition(BaseModel):
    """Complete organization definition.

    Contains all agents, teams, envelopes, and workspaces for an organization.
    Provides validation to ensure internal consistency (no dangling references,
    no duplicate IDs).
    """

    org_id: str = Field(description="Unique organization identifier")
    name: str = Field(description="Human-readable organization name")
    authority_id: str = Field(default="", description="Genesis authority identifier")
    teams: list[TeamConfig] = Field(default_factory=list, description="All team definitions")
    agents: list[AgentConfig] = Field(default_factory=list, description="All agent definitions")
    envelopes: list[ConstraintEnvelopeConfig] = Field(
        default_factory=list, description="All constraint envelope definitions"
    )
    workspaces: list[WorkspaceConfig] = Field(
        default_factory=list, description="All workspace definitions"
    )

    def get_team_agents(self, team_id: str) -> list[AgentConfig]:
        """Get all agents in a team.

        Args:
            team_id: The team to look up.

        Returns:
            List of AgentConfig for agents assigned to the team.

        Raises:
            ValueError: If the team_id is not found in this organization.
        """
        team = None
        for t in self.teams:
            if t.id == team_id:
                team = t
                break
        if team is None:
            raise ValueError(
                f"Team '{team_id}' not found in organization '{self.org_id}'. "
                f"Available teams: {[t.id for t in self.teams]}"
            )

        agent_index = {a.id: a for a in self.agents}
        return [agent_index[aid] for aid in team.agents if aid in agent_index]

    def validate_org(self) -> tuple[bool, list[str]]:
        """Validate org definition for internal consistency.

        Checks:
        - No duplicate IDs across agents, teams, envelopes, workspaces
        - All agent envelope references resolve to defined envelopes
        - All team workspace references resolve to defined workspaces

        Returns:
            (True, []) if valid, (False, [list of error messages]) otherwise.
        """
        errors: list[str] = []

        # Check duplicate agent IDs
        agent_ids = [a.id for a in self.agents]
        seen_agents: set[str] = set()
        for aid in agent_ids:
            if aid in seen_agents:
                errors.append(f"Duplicate agent ID: '{aid}'")
            seen_agents.add(aid)

        # Check duplicate team IDs
        team_ids = [t.id for t in self.teams]
        seen_teams: set[str] = set()
        for tid in team_ids:
            if tid in seen_teams:
                errors.append(f"Duplicate team ID: '{tid}'")
            seen_teams.add(tid)

        # Check duplicate envelope IDs
        envelope_ids = [e.id for e in self.envelopes]
        seen_envelopes: set[str] = set()
        for eid in envelope_ids:
            if eid in seen_envelopes:
                errors.append(f"Duplicate envelope ID: '{eid}'")
            seen_envelopes.add(eid)

        # Check duplicate workspace IDs
        workspace_ids = [w.id for w in self.workspaces]
        seen_workspaces: set[str] = set()
        for wid in workspace_ids:
            if wid in seen_workspaces:
                errors.append(f"Duplicate workspace ID: '{wid}'")
            seen_workspaces.add(wid)

        # Check all agent envelope references resolve
        envelope_id_set = set(envelope_ids)
        for agent in self.agents:
            if agent.constraint_envelope not in envelope_id_set:
                errors.append(
                    f"Agent '{agent.id}' references envelope '{agent.constraint_envelope}' "
                    f"which does not exist. Available envelopes: {sorted(envelope_id_set)}"
                )

        # Check all team workspace references resolve
        workspace_id_set = set(workspace_ids)
        for team in self.teams:
            if team.workspace not in workspace_id_set:
                errors.append(
                    f"Team '{team.id}' references workspace '{team.workspace}' "
                    f"which does not exist. Available workspaces: {sorted(workspace_id_set)}"
                )

        return (len(errors) == 0, errors)


class OrgBuilder:
    """Builder for creating organization definitions with fluent API.

    Usage:
        org = (
            OrgBuilder("my-org", "My Organization")
            .add_workspace(WorkspaceConfig(...))
            .add_envelope(ConstraintEnvelopeConfig(...))
            .add_agent(AgentConfig(...))
            .add_team(TeamConfig(...))
            .build()
        )
    """

    def __init__(self, org_id: str, name: str) -> None:
        self._org = OrgDefinition(org_id=org_id, name=name)

    def add_team(self, team: TeamConfig) -> OrgBuilder:
        """Add a team to the organization."""
        self._org.teams.append(team)
        return self

    def add_agent(self, agent: AgentConfig) -> OrgBuilder:
        """Add an agent to the organization."""
        self._org.agents.append(agent)
        return self

    def add_envelope(self, envelope: ConstraintEnvelopeConfig) -> OrgBuilder:
        """Add a constraint envelope to the organization."""
        self._org.envelopes.append(envelope)
        return self

    def add_workspace(self, workspace: WorkspaceConfig) -> OrgBuilder:
        """Add a workspace to the organization."""
        self._org.workspaces.append(workspace)
        return self

    def build(self) -> OrgDefinition:
        """Build and validate the organization definition.

        Raises:
            ValueError: If validation fails with details of all errors.

        Returns:
            A validated OrgDefinition.
        """
        valid, errors = self._org.validate_org()
        if not valid:
            raise ValueError(
                f"Organization '{self._org.org_id}' failed validation:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        return self._org

    @staticmethod
    def save(org: OrgDefinition, store: Any) -> None:
        """Persist an OrgDefinition to a TrustStore.

        Serializes the OrgDefinition using Pydantic's model_dump() and stores
        it via the store's store_org_definition() method.

        Args:
            org: The OrgDefinition to persist.
            store: A TrustStore implementation with store_org_definition().

        Raises:
            AttributeError: If store does not have store_org_definition method.
        """
        data = org.model_dump(mode="json")
        store.store_org_definition(org.org_id, data)
        logger.info("Saved OrgDefinition '%s' to store", org.org_id)

    @staticmethod
    def load(org_id: str, store: Any) -> OrgDefinition | None:
        """Load an OrgDefinition from a TrustStore.

        Retrieves the serialized data and reconstructs an OrgDefinition.

        Args:
            org_id: The organization ID to load.
            store: A TrustStore implementation with get_org_definition().

        Returns:
            The reconstructed OrgDefinition, or None if not found.
        """
        data = store.get_org_definition(org_id)
        if data is None:
            logger.info("OrgDefinition '%s' not found in store", org_id)
            return None

        # Reconstruct nested Pydantic models from the dict
        org = OrgDefinition(**data)
        logger.info("Loaded OrgDefinition '%s' from store", org_id)
        return org

    @classmethod
    def from_config(cls, config: PlatformConfig) -> OrgDefinition:
        """Create an OrgDefinition from a PlatformConfig.

        This enables round-tripping between PlatformConfig (the YAML-level config)
        and OrgDefinition (the runtime representation).

        Args:
            config: A fully-populated PlatformConfig.

        Returns:
            An OrgDefinition with all data from the PlatformConfig.
        """
        return OrgDefinition(
            org_id=config.name.lower().replace(" ", "-"),
            name=config.name,
            authority_id=config.genesis.authority,
            teams=list(config.teams),
            agents=list(config.agents),
            envelopes=list(config.constraint_envelopes),
            workspaces=list(config.workspaces),
        )


class OrgTemplate:
    """Predefined organization templates for common structures."""

    @staticmethod
    def foundation_template() -> OrgDefinition:
        """Terrene Foundation template with standard teams.

        Includes the DM team as the first vertical, with all agents, envelopes,
        and workspaces pre-configured.
        """
        from care_platform.verticals.dm_team import get_dm_team_config

        dm = get_dm_team_config()

        # Foundation-level workspace for the DM team
        dm_workspace = WorkspaceConfig(
            id="ws-dm",
            path="workspaces/dm/",
            description="Digital Media team workspace",
        )

        return OrgDefinition(
            org_id="terrene-foundation",
            name="Terrene Foundation",
            authority_id="terrene.foundation",
            teams=dm["teams"],
            agents=dm["agents"],
            envelopes=dm["envelopes"],
            workspaces=[dm_workspace],
        )

    @staticmethod
    def minimal_template(org_name: str) -> OrgDefinition:
        """Minimal organization with one team, one agent, one workspace, one envelope.

        Useful as a starting point for new organizations or for testing.

        Args:
            org_name: Name of the organization.

        Returns:
            A valid OrgDefinition with the minimal set of resources.
        """
        org_id = org_name.lower().replace(" ", "-")
        envelope_id = f"{org_id}-default-envelope"
        agent_id = f"{org_id}-default-agent"
        team_id = f"{org_id}-default-team"
        workspace_id = f"{org_id}-default-ws"

        return OrgDefinition(
            org_id=org_id,
            name=org_name,
            agents=[
                AgentConfig(
                    id=agent_id,
                    name=f"{org_name} Default Agent",
                    role="General-purpose agent",
                    constraint_envelope=envelope_id,
                ),
            ],
            envelopes=[
                ConstraintEnvelopeConfig(
                    id=envelope_id,
                    description=f"Default constraint envelope for {org_name}",
                ),
            ],
            teams=[
                TeamConfig(
                    id=team_id,
                    name=f"{org_name} Default Team",
                    workspace=workspace_id,
                    agents=[agent_id],
                ),
            ],
            workspaces=[
                WorkspaceConfig(
                    id=workspace_id,
                    path=f"workspaces/{org_id}/",
                    description=f"Default workspace for {org_name}",
                ),
            ],
        )
