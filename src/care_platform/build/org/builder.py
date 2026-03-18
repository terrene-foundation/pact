# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Organization definition and builder — enables defining any team structure.

OrgDefinition is the data model for a complete organization.
OrgBuilder provides a fluent builder API for constructing org definitions.
OrgTemplate provides predefined templates for common org structures.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from care_platform.build.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    PlatformConfig,
    TeamConfig,
    WorkspaceConfig,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation result model (Task 5035)
# ---------------------------------------------------------------------------


class ValidationSeverity(enum.Enum):
    """Severity level for org validation results."""

    ERROR = "error"
    WARNING = "warning"


class ValidationResult(BaseModel):
    """A single validation finding with severity, message, and error code."""

    severity: ValidationSeverity
    message: str
    code: str

    @property
    def is_error(self) -> bool:
        """Whether this result is a blocking error."""
        return self.severity == ValidationSeverity.ERROR


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

    def validate_org_detailed(self) -> list[ValidationResult]:
        """Validate org definition with detailed results including severity levels.

        Returns a list of ValidationResult objects with ERROR or WARNING severity.
        ERRORs are structural issues that prevent building (duplicate IDs, dangling refs).
        WARNINGs are coverage gaps that allow building with notification.

        Returns:
            List of ValidationResult findings (empty means fully valid).
        """
        results: list[ValidationResult] = []

        # --- Structural checks (ERROR severity) ---

        # Duplicate agent IDs
        seen_agents: set[str] = set()
        for a in self.agents:
            if a.id in seen_agents:
                results.append(
                    ValidationResult(
                        severity=ValidationSeverity.ERROR,
                        message=f"Duplicate agent ID: '{a.id}'",
                        code="ERR_DUPLICATE_AGENT",
                    )
                )
            seen_agents.add(a.id)

        # Duplicate team IDs
        seen_teams: set[str] = set()
        for t in self.teams:
            if t.id in seen_teams:
                results.append(
                    ValidationResult(
                        severity=ValidationSeverity.ERROR,
                        message=f"Duplicate team ID: '{t.id}'",
                        code="ERR_DUPLICATE_TEAM",
                    )
                )
            seen_teams.add(t.id)

        # Duplicate envelope IDs
        seen_envelopes: set[str] = set()
        for e in self.envelopes:
            if e.id in seen_envelopes:
                results.append(
                    ValidationResult(
                        severity=ValidationSeverity.ERROR,
                        message=f"Duplicate envelope ID: '{e.id}'",
                        code="ERR_DUPLICATE_ENVELOPE",
                    )
                )
            seen_envelopes.add(e.id)

        # Duplicate workspace IDs
        seen_workspaces: set[str] = set()
        for w in self.workspaces:
            if w.id in seen_workspaces:
                results.append(
                    ValidationResult(
                        severity=ValidationSeverity.ERROR,
                        message=f"Duplicate workspace ID: '{w.id}'",
                        code="ERR_DUPLICATE_WORKSPACE",
                    )
                )
            seen_workspaces.add(w.id)

        # Envelope references
        envelope_ids = {e.id for e in self.envelopes}
        for agent in self.agents:
            if agent.constraint_envelope not in envelope_ids:
                results.append(
                    ValidationResult(
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Agent '{agent.id}' references envelope "
                            f"'{agent.constraint_envelope}' which does not exist"
                        ),
                        code="ERR_DANGLING_ENVELOPE_REF",
                    )
                )

        # Workspace references
        workspace_ids = {w.id for w in self.workspaces}
        for team in self.teams:
            if team.workspace not in workspace_ids:
                results.append(
                    ValidationResult(
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Team '{team.id}' references workspace "
                            f"'{team.workspace}' which does not exist"
                        ),
                        code="ERR_DANGLING_WORKSPACE_REF",
                    )
                )

        # --- Capability-envelope alignment (5029) ---
        envelope_index = {e.id: e for e in self.envelopes}
        for agent in self.agents:
            env = envelope_index.get(agent.constraint_envelope)
            if env and env.operational and env.operational.allowed_actions:
                allowed = set(env.operational.allowed_actions)
                for cap in getattr(agent, "capabilities", []) or []:
                    if cap not in allowed:
                        results.append(
                            ValidationResult(
                                severity=ValidationSeverity.ERROR,
                                message=(
                                    f"Agent '{agent.id}' has capability '{cap}' "
                                    f"not in envelope '{env.id}' allowed_actions"
                                ),
                                code="CAP_NOT_IN_ENVELOPE",
                            )
                        )

        # --- Team lead superset check (5031) ---
        for team in self.teams:
            team_agents = [a for a in self.agents if a.id in team.agents]
            leads = [
                a for a in team_agents if "lead" in a.id.lower() or "lead" in (a.role or "").lower()
            ]
            non_leads = [a for a in team_agents if a not in leads]
            for lead in leads:
                lead_caps = set(getattr(lead, "capabilities", []) or [])
                for member in non_leads:
                    member_caps = set(getattr(member, "capabilities", []) or [])
                    missing = member_caps - lead_caps
                    if missing:
                        results.append(
                            ValidationResult(
                                severity=ValidationSeverity.ERROR,
                                message=(
                                    f"Team lead '{lead.id}' missing capabilities "
                                    f"held by '{member.id}': {sorted(missing)}"
                                ),
                                code="LEAD_MISSING_CAPABILITY",
                            )
                        )

        # --- Gradient coverage (5032) ---
        # Build team gradient lookup for fallback
        agent_to_team: dict[str, TeamConfig] = {}
        for team in self.teams:
            for aid in team.agents:
                agent_to_team[aid] = team

        for agent in self.agents:
            gradient = getattr(agent, "verification_gradient", None)
            # Fall back to team gradient if agent has none
            if not gradient or not gradient.rules:
                team = agent_to_team.get(agent.id)
                if team:
                    gradient = getattr(team, "verification_gradient", None)
            if gradient and gradient.rules:
                rule_patterns = [r.pattern for r in gradient.rules]
                for cap in getattr(agent, "capabilities", []) or []:
                    covered = any(
                        cap == pattern
                        or pattern == "*"
                        or (pattern.endswith("*") and cap.startswith(pattern[:-1]))
                        for pattern in rule_patterns
                    )
                    if not covered:
                        results.append(
                            ValidationResult(
                                severity=ValidationSeverity.WARNING,
                                message=(
                                    f"Agent '{agent.id}' capability '{cap}' "
                                    f"has no matching gradient rule"
                                ),
                                code="GRADIENT_UNCOVERED_CAPABILITY",
                            )
                        )

        # --- Helper: glob-aware path containment ---
        def _path_covered_by(child: str, parent_paths: set[str]) -> bool:
            for p in parent_paths:
                if child == p:
                    return True
                if p.endswith("*") and child.startswith(p[:-1]):
                    return True
            return False

        # --- Monotonic constraint tightening (5030) ---
        agent_index = {a.id: a for a in self.agents}
        for team in self.teams:
            lead_id = team.team_lead
            if not lead_id or lead_id not in agent_index:
                continue
            lead_agent = agent_index[lead_id]
            lead_env = envelope_index.get(lead_agent.constraint_envelope)
            if not lead_env:
                continue

            for member_id in team.agents:
                if member_id == lead_id or member_id not in agent_index:
                    continue
                member_agent = agent_index[member_id]
                sub_env = envelope_index.get(member_agent.constraint_envelope)
                if not sub_env:
                    continue

                # Financial tightening
                if (
                    lead_env.financial
                    and sub_env.financial
                    and lead_env.financial.max_spend_usd is not None
                    and sub_env.financial.max_spend_usd is not None
                    and sub_env.financial.max_spend_usd > lead_env.financial.max_spend_usd
                ):
                    results.append(
                        ValidationResult(
                            severity=ValidationSeverity.ERROR,
                            message=(
                                f"Agent '{member_id}' financial limit "
                                f"(${sub_env.financial.max_spend_usd}) exceeds "
                                f"lead '{lead_id}' (${lead_env.financial.max_spend_usd})"
                            ),
                            code="FINANCIAL_TIGHTENING",
                        )
                    )

                # Operational tightening — allowed actions
                if lead_env.operational and sub_env.operational:
                    lead_actions = set(lead_env.operational.allowed_actions or [])
                    sub_actions = set(sub_env.operational.allowed_actions or [])
                    if lead_actions and sub_actions:
                        extra = sub_actions - lead_actions
                        if extra:
                            results.append(
                                ValidationResult(
                                    severity=ValidationSeverity.ERROR,
                                    message=(
                                        f"Agent '{member_id}' has actions {sorted(extra)} "
                                        f"not in lead '{lead_id}' envelope"
                                    ),
                                    code="OPERATIONAL_TIGHTENING",
                                )
                            )

                    # Operational tightening — rate limit
                    lead_rate = lead_env.operational.max_actions_per_day
                    sub_rate = sub_env.operational.max_actions_per_day
                    if lead_rate and sub_rate and sub_rate > lead_rate:
                        results.append(
                            ValidationResult(
                                severity=ValidationSeverity.ERROR,
                                message=(
                                    f"Agent '{member_id}' rate limit ({sub_rate}/day) "
                                    f"exceeds lead '{lead_id}' ({lead_rate}/day)"
                                ),
                                code="OPERATIONAL_TIGHTENING",
                            )
                        )

                # Communication tightening
                if lead_env.communication and sub_env.communication:
                    if (
                        lead_env.communication.internal_only
                        and not sub_env.communication.internal_only
                    ):
                        results.append(
                            ValidationResult(
                                severity=ValidationSeverity.ERROR,
                                message=(
                                    f"Agent '{member_id}' allows external communication "
                                    f"but lead '{lead_id}' is internal-only"
                                ),
                                code="COMMUNICATION_TIGHTENING",
                            )
                        )

                # Temporal tightening (5033)
                if lead_env.temporal and sub_env.temporal:
                    if (
                        lead_env.temporal.active_hours_start
                        and sub_env.temporal.active_hours_start
                        and sub_env.temporal.active_hours_start
                        < lead_env.temporal.active_hours_start
                    ):
                        results.append(
                            ValidationResult(
                                severity=ValidationSeverity.ERROR,
                                message=(
                                    f"Agent '{member_id}' starts at {sub_env.temporal.active_hours_start} "
                                    f"before lead '{lead_id}' ({lead_env.temporal.active_hours_start})"
                                ),
                                code="TEMPORAL_TIGHTENING",
                            )
                        )
                    if (
                        lead_env.temporal.active_hours_end
                        and sub_env.temporal.active_hours_end
                        and sub_env.temporal.active_hours_end > lead_env.temporal.active_hours_end
                    ):
                        results.append(
                            ValidationResult(
                                severity=ValidationSeverity.ERROR,
                                message=(
                                    f"Agent '{member_id}' ends at {sub_env.temporal.active_hours_end} "
                                    f"after lead '{lead_id}' ({lead_env.temporal.active_hours_end})"
                                ),
                                code="TEMPORAL_TIGHTENING",
                            )
                        )

                # Data access tightening (5033) — glob-aware path containment
                if lead_env.data_access and sub_env.data_access:
                    lead_read = set(lead_env.data_access.read_paths or [])
                    sub_read = set(sub_env.data_access.read_paths or [])
                    if lead_read and sub_read:
                        uncovered = [p for p in sub_read if not _path_covered_by(p, lead_read)]
                        if uncovered:
                            results.append(
                                ValidationResult(
                                    severity=ValidationSeverity.ERROR,
                                    message=(
                                        f"Agent '{member_id}' has read paths {sorted(uncovered)} "
                                        f"outside lead '{lead_id}' scope"
                                    ),
                                    code="DATA_ACCESS_TIGHTENING",
                                )
                            )

                    lead_write = set(lead_env.data_access.write_paths or [])
                    sub_write = set(sub_env.data_access.write_paths or [])
                    if lead_write and sub_write:
                        uncovered = [p for p in sub_write if not _path_covered_by(p, lead_write)]
                        if uncovered:
                            results.append(
                                ValidationResult(
                                    severity=ValidationSeverity.ERROR,
                                    message=(
                                        f"Agent '{member_id}' has write paths {sorted(uncovered)} "
                                        f"outside lead '{lead_id}' scope"
                                    ),
                                    code="DATA_ACCESS_TIGHTENING",
                                )
                            )

        # --- Multi-team validation (5034) ---
        agent_team_map: dict[str, list[str]] = {}
        for team in self.teams:
            for agent_id in team.agents:
                agent_team_map.setdefault(agent_id, []).append(team.id)

        for agent_id, team_list in agent_team_map.items():
            if len(team_list) > 1:
                results.append(
                    ValidationResult(
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Agent '{agent_id}' appears in multiple teams: {sorted(team_list)}"
                        ),
                        code="AGENT_IN_MULTIPLE_TEAMS",
                    )
                )

        # Workspace path conflicts
        ws_paths: dict[str, list[str]] = {}
        for ws in self.workspaces:
            ws_paths.setdefault(ws.path, []).append(ws.id)

        for path, ws_ids in ws_paths.items():
            if len(ws_ids) > 1:
                results.append(
                    ValidationResult(
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Workspace path '{path}' used by multiple workspaces: {sorted(ws_ids)}"
                        ),
                        code="CONFLICTING_WORKSPACE_PATHS",
                    )
                )

        return results


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

    @staticmethod
    def compose_from_templates(
        template_names: list[str],
        *,
        org_id: str,
        org_name: str,
        registry: object,
    ) -> OrgDefinition:
        """Compose an OrgDefinition from multiple team templates (M20/5039).

        Retrieves each template from the registry, combines all agents, teams,
        envelopes, and workspaces into a single OrgDefinition. Handles namespace
        conflicts by prefixing IDs with a counter-based suffix when a template
        name appears more than once.

        Args:
            template_names: List of template names to compose. Must not be empty.
            org_id: Organization ID for the resulting OrgDefinition.
            org_name: Organization name for the resulting OrgDefinition.
            registry: A TemplateRegistry instance providing get().

        Returns:
            An OrgDefinition containing all resources from all templates.

        Raises:
            ValueError: If template_names is empty, or if a template name
                        is not found in the registry.
        """
        if not template_names:
            raise ValueError(
                "compose_from_templates() requires at least one template name. "
                "Received an empty list."
            )

        from care_platform.build.templates.registry import TeamTemplate

        all_agents: list[AgentConfig] = []
        all_teams: list[TeamConfig] = []
        all_envelopes: list[ConstraintEnvelopeConfig] = []
        all_workspaces: list[WorkspaceConfig] = []

        # Track how many times each template name has been used (for dedup)
        name_counts: dict[str, int] = {}

        for tpl_name in template_names:
            # get() raises ValueError if not found — propagate as-is
            tpl: TeamTemplate = registry.get(tpl_name)  # type: ignore[union-attr]

            count = name_counts.get(tpl_name, 0)
            name_counts[tpl_name] = count + 1

            if count > 0:
                # Namespace collision — prefix all IDs with "{name}-{count}-"
                prefix = f"{tpl_name}-{count}"
                tpl = _prefix_template(tpl, prefix)

            # Add workspace for this template's team
            ws = WorkspaceConfig(
                id=tpl.team.workspace,
                path=f"workspaces/{tpl.team.workspace.replace('ws-', '')}/",
                description=f"Workspace for {tpl.team.name}",
            )

            all_agents.extend(tpl.agents)
            all_envelopes.extend(tpl.envelopes)
            all_teams.append(tpl.team)
            all_workspaces.append(ws)

        return OrgDefinition(
            org_id=org_id,
            name=org_name,
            teams=all_teams,
            agents=all_agents,
            envelopes=all_envelopes,
            workspaces=all_workspaces,
        )


def _prefix_template(tpl: object, prefix: str) -> object:
    """Create a copy of a TeamTemplate with all IDs prefixed to avoid collisions.

    Args:
        tpl: The TeamTemplate to prefix.
        prefix: The prefix string (e.g., "governance-1").

    Returns:
        A new TeamTemplate with prefixed IDs.
    """
    from care_platform.build.templates.registry import TeamTemplate

    # Build mapping from old IDs to new IDs
    agent_map: dict[str, str] = {}
    for a in tpl.agents:  # type: ignore[union-attr]
        new_id = f"{prefix}-{a.id}"
        agent_map[a.id] = new_id

    envelope_map: dict[str, str] = {}
    for e in tpl.envelopes:  # type: ignore[union-attr]
        new_id = f"{prefix}-{e.id}"
        envelope_map[e.id] = new_id

    new_team_id = f"{prefix}-{tpl.team.id}"  # type: ignore[union-attr]
    new_workspace = f"{prefix}-{tpl.team.workspace}"  # type: ignore[union-attr]

    # Rebuild envelopes with new IDs
    new_envelopes = []
    for e in tpl.envelopes:  # type: ignore[union-attr]
        data = e.model_dump()
        data["id"] = envelope_map[e.id]
        new_envelopes.append(ConstraintEnvelopeConfig(**data))

    # Rebuild agents with new IDs and updated envelope references
    new_agents = []
    for a in tpl.agents:  # type: ignore[union-attr]
        data = a.model_dump()
        data["id"] = agent_map[a.id]
        data["constraint_envelope"] = envelope_map.get(a.constraint_envelope, a.constraint_envelope)
        new_agents.append(AgentConfig(**data))

    # Rebuild team with new IDs
    team_data = tpl.team.model_dump()  # type: ignore[union-attr]
    team_data["id"] = new_team_id
    team_data["workspace"] = new_workspace
    team_data["agents"] = [agent_map.get(aid, aid) for aid in team_data["agents"]]
    if team_data.get("team_lead"):
        team_data["team_lead"] = agent_map.get(team_data["team_lead"], team_data["team_lead"])
    new_team = TeamConfig(**team_data)

    return TeamTemplate(
        name=f"{prefix}-{tpl.name}",  # type: ignore[union-attr]
        description=tpl.description,  # type: ignore[union-attr]
        agents=new_agents,
        envelopes=new_envelopes,
        team=new_team,
    )


class OrgTemplate:
    """Predefined organization templates for common structures."""

    @staticmethod
    def foundation_template() -> OrgDefinition:
        """Terrene Foundation template with standard teams.

        Includes the DM team as the first vertical, with all agents, envelopes,
        and workspaces pre-configured.
        """
        from care_platform.build.verticals.dm_team import get_dm_team_config

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
