# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Organization Generator — auto-generates valid organizations from high-level definitions.

The OrgGenerator takes an OrgGeneratorConfig (high-level org description)
and produces a fully valid OrgDefinition that passes validate_org_detailed()
with zero ERRORs.

The generation pipeline:
1. Create org-level envelope from budget/limits
2. For each department: derive department envelope via EnvelopeDeriver
3. For each team: derive team envelope, resolve roles from RoleCatalog
4. For each agent: derive agent envelope from role + team envelope
5. Auto-inject coordinator agent per team (Task 6033)
6. Validate the complete org — raise ValueError if validation fails

Key invariants:
- Monotonic tightening is enforced by construction (EnvelopeDeriver)
- Every agent's capabilities are a subset of their envelope's allowed_actions
- Every team has a coordinator agent with SUPERVISED posture
- The generated org NEVER fails validate_org_detailed()
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

from pact_platform.build.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    DepartmentConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TeamConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    WorkspaceConfig,
)
from pact_platform.build.org.builder import OrgDefinition
from pact_platform.build.org.envelope_deriver import EnvelopeDeriver
from pact_platform.build.org.role_catalog import RoleCatalog, RoleDefinition
from pact_platform.build.org.utils import _slugify

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config models for the generator input
# ---------------------------------------------------------------------------


class TeamSpec(BaseModel):
    """Specification for a team within a department.

    Attributes:
        name: Human-readable team name.
        roles: List of role_ids from the RoleCatalog.
        custom_agents: Optional list of custom AgentConfig overrides.
    """

    name: str = Field(description="Human-readable team name")
    roles: list[str] = Field(description="Role IDs from the RoleCatalog")
    custom_agents: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional custom agent definitions (override role defaults)",
    )


class DepartmentSpec(BaseModel):
    """Specification for a department within an organization.

    Attributes:
        name: Human-readable department name.
        teams: List of TeamSpec definitions.
    """

    name: str = Field(description="Human-readable department name")
    teams: list[TeamSpec] = Field(description="Team specifications within this department")

    @field_validator("teams")
    @classmethod
    def validate_teams_not_empty(cls, v: list[TeamSpec]) -> list[TeamSpec]:
        if not v:
            raise ValueError(
                "Department must have at least one team. Received an empty teams list."
            )
        return v


class OrgGeneratorConfig(BaseModel):
    """High-level organization definition input for the auto-generation engine.

    This is the user-facing configuration that describes what the organization
    should look like. The OrgGenerator converts this into a fully valid
    OrgDefinition.

    Attributes:
        org_id: Unique organization identifier.
        org_name: Human-readable organization name.
        authority_id: Genesis authority identifier.
        org_budget: Total organization budget (USD).
        org_max_actions_per_day: Total org-wide daily action limit.
        departments: List of department specifications.
    """

    org_id: str = Field(description="Unique organization identifier")
    org_name: str = Field(description="Human-readable organization name")
    authority_id: str = Field(description="Genesis authority identifier")
    org_budget: float = Field(gt=0, description="Total organization budget (USD)")
    org_max_actions_per_day: int = Field(gt=0, description="Total org-wide daily action limit")
    departments: list[DepartmentSpec] = Field(description="Department specifications")

    @field_validator("departments")
    @classmethod
    def validate_departments_not_empty(cls, v: list[DepartmentSpec]) -> list[DepartmentSpec]:
        if not v:
            raise ValueError(
                "Organization must have at least one department. "
                "Received an empty departments list."
            )
        return v


COORDINATOR_CAPABILITIES: frozenset[str] = frozenset(
    {"bridge_management", "cross_team_communication", "task_routing"}
)


# ---------------------------------------------------------------------------
# OrgGenerator
# ---------------------------------------------------------------------------


class OrgGenerator:
    """Auto-generates valid organizations from high-level definitions.

    Uses RoleCatalog to resolve roles, EnvelopeDeriver to create the
    envelope hierarchy, and auto-injects coordinator agents per team.

    Usage:
        generator = OrgGenerator()
        org = generator.generate(config)
        # org is guaranteed to pass validate_org_detailed()
    """

    def __init__(
        self,
        *,
        catalog: RoleCatalog | None = None,
        deriver: EnvelopeDeriver | None = None,
    ) -> None:
        self._catalog = catalog or RoleCatalog()
        self._deriver = deriver or EnvelopeDeriver()

    def generate(self, config: OrgGeneratorConfig) -> OrgDefinition:
        """Generate a valid OrgDefinition from a high-level config.

        Pipeline:
        1. Create org-level envelope
        2. For each department: derive department envelope
        3. For each team: derive team envelope, create agents from roles
        4. Auto-inject coordinator per team
        5. Validate — raise ValueError if validation fails

        Args:
            config: The OrgGeneratorConfig describing the desired org.

        Returns:
            A fully validated OrgDefinition.

        Raises:
            ValueError: If any role_id is not found in the catalog,
                        or if the generated org fails validation.
        """
        # Pre-validate: check all role_ids exist in catalog
        for dept_spec in config.departments:
            for team_spec in dept_spec.teams:
                for role_id in team_spec.roles:
                    self._catalog.get(role_id)  # Raises ValueError if not found

        # Step 1: Create org-level envelope
        # Collect all unique role capabilities to build org allowed_actions
        all_capabilities: set[str] = set()
        for dept_spec in config.departments:
            for team_spec in dept_spec.teams:
                for role_id in team_spec.roles:
                    role = self._catalog.get(role_id)
                    all_capabilities.update(role.default_capabilities)

        # Add coordinator capabilities
        all_capabilities.update(COORDINATOR_CAPABILITIES)

        org_envelope = ConstraintEnvelopeConfig(
            id=f"{config.org_id}-org-envelope",
            description=f"Organization-level envelope for '{config.org_name}'",
            financial=FinancialConstraintConfig(
                max_spend_usd=config.org_budget,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=sorted(all_capabilities),
                max_actions_per_day=config.org_max_actions_per_day,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="00:00",
                active_hours_end="23:59",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["/*"],
                write_paths=["/*"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=False,
                external_requires_approval=True,
            ),
        )

        envelopes: list[ConstraintEnvelopeConfig] = [org_envelope]
        agents: list[AgentConfig] = []
        teams: list[TeamConfig] = []
        workspaces: list[WorkspaceConfig] = []
        departments: list[DepartmentConfig] = []

        # Step 2-4: Process each department
        for dept_spec in config.departments:
            dept_slug = _slugify(dept_spec.name)
            dept_id = f"{config.org_id}-{dept_slug}"

            # Derive department envelope
            dept_envelope = self._deriver.derive_department_envelope(org_envelope, dept_spec.name)
            envelopes.append(dept_envelope)

            team_ids_for_dept: list[str] = []
            first_agent_in_dept: str | None = None

            for team_spec in dept_spec.teams:
                team_slug = _slugify(team_spec.name)
                team_id = f"{dept_id}-{team_slug}"
                workspace_id = f"ws-{team_id}"

                # Derive team envelope
                team_envelope = self._deriver.derive_team_envelope(dept_envelope, team_spec.name)
                envelopes.append(team_envelope)

                # Create workspace for the team
                workspaces.append(
                    WorkspaceConfig(
                        id=workspace_id,
                        path=f"workspaces/{team_id}/",
                        description=f"Workspace for team '{team_spec.name}'",
                    )
                )

                team_agent_ids: list[str] = []

                # --- Phase 1: Collect all capabilities and create agent envelopes ---
                # We need to know all capabilities before creating the team lead,
                # because the lead must be a superset of all members.
                role_agents: list[tuple[str, RoleDefinition, ConstraintEnvelopeConfig]] = []
                all_team_capabilities: set[str] = set()

                for role_id in team_spec.roles:
                    role = self._catalog.get(role_id)
                    agent_id = f"{team_id}-{_slugify(role_id)}"

                    # Derive agent envelope
                    agent_envelope = self._deriver.derive_agent_envelope(team_envelope, role)
                    agent_envelope_id = f"{agent_id}-envelope"
                    agent_envelope = ConstraintEnvelopeConfig(
                        id=agent_envelope_id,
                        description=agent_envelope.description,
                        financial=agent_envelope.financial,
                        operational=agent_envelope.operational,
                        temporal=agent_envelope.temporal,
                        data_access=agent_envelope.data_access,
                        communication=agent_envelope.communication,
                    )
                    role_agents.append((agent_id, role, agent_envelope))
                    all_team_capabilities.update(agent_envelope.operational.allowed_actions)

                # Add coordinator capabilities to the team lead's superset
                all_team_capabilities.update(COORDINATOR_CAPABILITIES)

                # Coordinator envelope (created early so lead can account for it)
                coordinator_id = f"{team_id}-coordinator"
                coord_envelope = self._deriver.derive_coordinator_envelope(team_envelope, team_id)

                # --- Phase 2: Create team lead with superset capabilities ---
                # The team lead gets the team envelope directly (broadest in team)
                # with ALL capabilities from all roles + coordinator.
                team_lead_id = f"{team_id}-lead"
                team_lead_envelope_id = f"{team_lead_id}-envelope"

                # Lead financial: use team envelope financial (broadest)
                lead_financial = team_envelope.financial

                # Lead rate limit: must be >= all members' rate limits
                max_member_rate = 0
                for _, role, a_env in role_agents:
                    member_rate = a_env.operational.max_actions_per_day or 0
                    max_member_rate = max(max_member_rate, member_rate)
                coord_rate = coord_envelope.operational.max_actions_per_day or 0
                max_member_rate = max(max_member_rate, coord_rate)
                # Lead rate is at least as high as any member
                lead_rate = max(
                    max_member_rate,
                    team_envelope.operational.max_actions_per_day or max_member_rate,
                )
                # But capped by team envelope rate
                if team_envelope.operational.max_actions_per_day is not None:
                    lead_rate = min(lead_rate, team_envelope.operational.max_actions_per_day)

                # Lead data access: same as team envelope (broadest in team)
                lead_read_paths = (
                    list(team_envelope.data_access.read_paths) if team_envelope.data_access else []
                )
                all_lead_read = set(lead_read_paths)
                lead_write_paths = (
                    list(team_envelope.data_access.write_paths) if team_envelope.data_access else []
                )

                team_lead_envelope = ConstraintEnvelopeConfig(
                    id=team_lead_envelope_id,
                    description=f"Team lead envelope for '{team_spec.name}'",
                    financial=lead_financial,
                    operational=OperationalConstraintConfig(
                        allowed_actions=sorted(all_team_capabilities),
                        max_actions_per_day=lead_rate if lead_rate > 0 else None,
                    ),
                    temporal=team_envelope.temporal,
                    data_access=DataAccessConstraintConfig(
                        read_paths=sorted(all_lead_read),
                        write_paths=lead_write_paths,
                    ),
                    communication=team_envelope.communication,
                )
                envelopes.append(team_lead_envelope)

                # Use the first role for lead's description
                first_role = role_agents[0][1] if role_agents else None
                lead_agent = AgentConfig(
                    id=team_lead_id,
                    name=f"Team Lead ({team_spec.name})",
                    role=f"Team lead for {team_spec.name}",
                    constraint_envelope=team_lead_envelope_id,
                    initial_posture=TrustPostureLevel.SUPERVISED,
                    capabilities=sorted(all_team_capabilities),
                )
                agents.append(lead_agent)
                team_agent_ids.append(team_lead_id)

                if first_agent_in_dept is None:
                    first_agent_in_dept = team_lead_id

                # --- Phase 3: Create role agents (non-lead members) ---
                for agent_id, role, agent_envelope in role_agents:
                    envelopes.append(agent_envelope)
                    agent_capabilities = list(agent_envelope.operational.allowed_actions)
                    agent = AgentConfig(
                        id=agent_id,
                        name=f"{role.name} ({team_spec.name})",
                        role=role.description,
                        constraint_envelope=agent_envelope.id,
                        initial_posture=role.default_posture,
                        capabilities=agent_capabilities,
                    )
                    agents.append(agent)
                    team_agent_ids.append(agent_id)

                # --- Phase 4 (Task 6033): Auto-inject coordinator agent ---
                envelopes.append(coord_envelope)
                coordinator_capabilities = list(coord_envelope.operational.allowed_actions)
                coordinator = AgentConfig(
                    id=coordinator_id,
                    name=f"Coordinator ({team_spec.name})",
                    role="Cross-Functional Bridge interaction manager",
                    constraint_envelope=coord_envelope.id,
                    initial_posture=TrustPostureLevel.SUPERVISED,
                    capabilities=coordinator_capabilities,
                )
                agents.append(coordinator)
                team_agent_ids.append(coordinator_id)

                # Create team
                team = TeamConfig(
                    id=team_id,
                    name=team_spec.name,
                    workspace=workspace_id,
                    team_lead=team_lead_id,
                    agents=team_agent_ids,
                )
                teams.append(team)
                team_ids_for_dept.append(team_id)

            # Create department
            department = DepartmentConfig(
                department_id=dept_id,
                name=dept_spec.name,
                description=f"Auto-generated department '{dept_spec.name}'",
                teams=team_ids_for_dept,
                head_agent_id=first_agent_in_dept,
                envelope=dept_envelope,
            )
            departments.append(department)

        # Build OrgDefinition
        org = OrgDefinition(
            org_id=config.org_id,
            name=config.org_name,
            authority_id=config.authority_id,
            org_envelope=org_envelope,
            departments=departments,
            teams=teams,
            agents=agents,
            envelopes=envelopes,
            workspaces=workspaces,
        )

        # Step 5: Validate — NEVER return an org that fails validation
        results = org.validate_org_detailed()
        errors = [r for r in results if r.is_error]
        if errors:
            error_msgs = "\n".join(f"  [{r.code}] {r.message}" for r in errors)
            raise ValueError(
                f"Generated organization '{config.org_id}' failed validation "
                f"with {len(errors)} error(s):\n{error_msgs}"
            )

        logger.info(
            "Generated organization '%s' with %d departments, %d teams, %d agents, %d envelopes",
            config.org_id,
            len(departments),
            len(teams),
            len(agents),
            len(envelopes),
        )
        return org
