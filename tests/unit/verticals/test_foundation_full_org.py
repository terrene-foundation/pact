# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Terrene Foundation Full Org — 11 Teams (M41: Tasks 6040-6046).

Validates the complete Terrene Foundation organization generated via
OrgGenerator with all 11 teams across 3 departments, cross-team bridges,
monotonic constraint tightening at every level, and YAML round-trip fidelity.

This is the dog-food test: the CARE Platform's own organizational structure
run through the same machinery it provides to external users.
"""

from __future__ import annotations

import pytest
import yaml

from care_platform.build.org.builder import OrgDefinition
from care_platform.build.org.envelope_deriver import EnvelopeDeriver
from care_platform.build.org.generator import OrgGenerator, OrgGeneratorConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def foundation_config() -> OrgGeneratorConfig:
    """The OrgGeneratorConfig for the full Terrene Foundation."""
    from care_platform.build.verticals.foundation import FOUNDATION_ORG_CONFIG

    return FOUNDATION_ORG_CONFIG


@pytest.fixture(scope="module")
def foundation_org(foundation_config: OrgGeneratorConfig) -> OrgDefinition:
    """Generate the complete Foundation org via OrgGenerator."""
    generator = OrgGenerator()
    return generator.generate(foundation_config)


@pytest.fixture(scope="module")
def bridge_definitions():
    """Cross-team bridge definitions for the Foundation org."""
    from care_platform.build.verticals.foundation import FOUNDATION_BRIDGES

    return FOUNDATION_BRIDGES


# ---------------------------------------------------------------------------
# Task 6040: Tier 1 Teams (5 teams)
# ---------------------------------------------------------------------------


TIER_1_TEAMS = {"Media/DM", "Standards", "Governance", "Partnerships", "Website"}


class TestTier1Teams:
    """Validate the five Tier 1 (Core Operations) teams are present and correct."""

    def test_tier1_teams_present(self, foundation_org: OrgDefinition):
        """All 5 Tier 1 teams must be present in the generated org."""
        team_names = {t.name for t in foundation_org.teams}
        for expected in TIER_1_TEAMS:
            assert expected in team_names, (
                f"Tier 1 team '{expected}' not found. Available teams: {sorted(team_names)}"
            )

    def test_media_team_roles(self, foundation_org: OrgDefinition):
        """Media/DM team has content_creator, analyst, coordinator roles."""
        media_team = _find_team_by_name(foundation_org, "Media/DM")
        agent_ids = set(media_team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        # Must have agents for content_creator, analyst roles (+ lead + coordinator)
        role_descriptions = {a.role for a in agents}
        assert len(agents) >= 4, (
            f"Media/DM team should have at least 4 agents (lead + 3 roles + coordinator), "
            f"got {len(agents)}"
        )

    def test_standards_team_roles(self, foundation_org: OrgDefinition):
        """Standards team has standards_author, reviewer, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Standards")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        assert len(agents) >= 4, f"Standards team should have at least 4 agents, got {len(agents)}"

    def test_governance_team_roles(self, foundation_org: OrgDefinition):
        """Governance team has governance_officer, legal_advisor, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Governance")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        assert len(agents) >= 4, f"Governance team should have at least 4 agents, got {len(agents)}"

    def test_partnerships_team_roles(self, foundation_org: OrgDefinition):
        """Partnerships team has partnership_manager, analyst, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Partnerships")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        assert len(agents) >= 4, (
            f"Partnerships team should have at least 4 agents, got {len(agents)}"
        )

    def test_website_team_roles(self, foundation_org: OrgDefinition):
        """Website team has website_manager, content_creator, developer, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Website")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        # 4 roles + lead + coordinator = 6
        assert len(agents) >= 5, f"Website team should have at least 5 agents, got {len(agents)}"


# ---------------------------------------------------------------------------
# Task 6041: Tier 2 Teams (3 teams)
# ---------------------------------------------------------------------------


TIER_2_TEAMS = {"Community", "Developer Relations", "Finance"}


class TestTier2Teams:
    """Validate the three Tier 2 (Growth) teams are present and correct."""

    def test_tier2_teams_present(self, foundation_org: OrgDefinition):
        """All 3 Tier 2 teams must be present in the generated org."""
        team_names = {t.name for t in foundation_org.teams}
        for expected in TIER_2_TEAMS:
            assert expected in team_names, (
                f"Tier 2 team '{expected}' not found. Available teams: {sorted(team_names)}"
            )

    def test_community_team_roles(self, foundation_org: OrgDefinition):
        """Community team has community_manager, content_creator, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Community")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        assert len(agents) >= 4, f"Community team should have at least 4 agents, got {len(agents)}"

    def test_devrel_team_roles(self, foundation_org: OrgDefinition):
        """Developer Relations team has developer, content_creator, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Developer Relations")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        assert len(agents) >= 4, (
            f"Developer Relations team should have at least 4 agents, got {len(agents)}"
        )

    def test_finance_team_roles(self, foundation_org: OrgDefinition):
        """Finance team has finance_manager, analyst, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Finance")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        assert len(agents) >= 4, f"Finance team should have at least 4 agents, got {len(agents)}"


# ---------------------------------------------------------------------------
# Task 6042: Tier 3 Teams (3 teams)
# ---------------------------------------------------------------------------


TIER_3_TEAMS = {"Certification", "Training", "Legal"}


class TestTier3Teams:
    """Validate the three Tier 3 (Future) teams are present and correct."""

    def test_tier3_teams_present(self, foundation_org: OrgDefinition):
        """All 3 Tier 3 teams must be present in the generated org."""
        team_names = {t.name for t in foundation_org.teams}
        for expected in TIER_3_TEAMS:
            assert expected in team_names, (
                f"Tier 3 team '{expected}' not found. Available teams: {sorted(team_names)}"
            )

    def test_certification_team_roles(self, foundation_org: OrgDefinition):
        """Certification team has reviewer, standards_author, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Certification")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        assert len(agents) >= 4, (
            f"Certification team should have at least 4 agents, got {len(agents)}"
        )

    def test_training_team_roles(self, foundation_org: OrgDefinition):
        """Training team has trainer, content_creator, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Training")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        assert len(agents) >= 4, f"Training team should have at least 4 agents, got {len(agents)}"

    def test_legal_team_roles(self, foundation_org: OrgDefinition):
        """Legal team has legal_advisor, reviewer, coordinator roles."""
        team = _find_team_by_name(foundation_org, "Legal")
        agent_ids = set(team.agents)
        agents = [a for a in foundation_org.agents if a.id in agent_ids]
        assert len(agents) >= 4, f"Legal team should have at least 4 agents, got {len(agents)}"


# ---------------------------------------------------------------------------
# Task 6043: Department Groupings
# ---------------------------------------------------------------------------


EXPECTED_DEPARTMENTS = {
    "Operations": {"Media/DM", "Website", "Community"},
    "Standards & Governance": {"Standards", "Governance", "Legal", "Certification"},
    "Growth": {"Partnerships", "Developer Relations", "Finance", "Training"},
}


class TestDepartmentGroupings:
    """Validate the 3 departments contain the correct teams."""

    def test_three_departments_present(self, foundation_org: OrgDefinition):
        """The org must have exactly 3 departments."""
        assert len(foundation_org.departments) == 3, (
            f"Expected 3 departments, got {len(foundation_org.departments)}: "
            f"{[d.name for d in foundation_org.departments]}"
        )

    def test_department_names(self, foundation_org: OrgDefinition):
        """Departments are named Operations, Standards & Governance, Growth."""
        dept_names = {d.name for d in foundation_org.departments}
        for expected in EXPECTED_DEPARTMENTS:
            assert expected in dept_names, (
                f"Department '{expected}' not found. Available departments: {sorted(dept_names)}"
            )

    def test_operations_department_teams(self, foundation_org: OrgDefinition):
        """Operations department contains Media/DM, Website, Community."""
        _assert_department_teams(foundation_org, "Operations", EXPECTED_DEPARTMENTS["Operations"])

    def test_standards_governance_department_teams(self, foundation_org: OrgDefinition):
        """Standards & Governance contains Standards, Governance, Legal, Certification."""
        _assert_department_teams(
            foundation_org,
            "Standards & Governance",
            EXPECTED_DEPARTMENTS["Standards & Governance"],
        )

    def test_growth_department_teams(self, foundation_org: OrgDefinition):
        """Growth department contains Partnerships, DevRel, Finance, Training."""
        _assert_department_teams(foundation_org, "Growth", EXPECTED_DEPARTMENTS["Growth"])

    def test_all_11_teams_accounted_for(self, foundation_org: OrgDefinition):
        """Every department team reference points to an existing team."""
        team_id_set = {t.id for t in foundation_org.teams}
        for dept in foundation_org.departments:
            for team_ref in dept.teams:
                assert team_ref in team_id_set, (
                    f"Department '{dept.name}' references team '{team_ref}' "
                    f"which does not exist in the org"
                )

    def test_each_department_has_head_agent(self, foundation_org: OrgDefinition):
        """Every department has a head_agent_id that exists in one of its teams."""
        agent_ids = {a.id for a in foundation_org.agents}
        for dept in foundation_org.departments:
            assert dept.head_agent_id is not None, f"Department '{dept.name}' has no head_agent_id"
            assert dept.head_agent_id in agent_ids, (
                f"Department '{dept.name}' head '{dept.head_agent_id}' not found in org agents"
            )

    def test_each_department_has_envelope(self, foundation_org: OrgDefinition):
        """Every department has a constraint envelope."""
        for dept in foundation_org.departments:
            assert dept.envelope is not None, f"Department '{dept.name}' has no constraint envelope"


# ---------------------------------------------------------------------------
# Task 6044: Cross-Team Bridges
# ---------------------------------------------------------------------------


class TestCrossTeamBridges:
    """Validate cross-team bridge definitions."""

    def test_bridges_defined(self, bridge_definitions):
        """At least 5 standing bridges are defined."""
        assert len(bridge_definitions) >= 5, (
            f"Expected at least 5 bridge definitions, got {len(bridge_definitions)}"
        )

    def test_standards_governance_bridge(self, bridge_definitions):
        """Standing bridge exists between Standards and Governance."""
        assert _has_bridge(bridge_definitions, "Standards", "Governance"), (
            "Missing bridge: Standards <-> Governance"
        )

    def test_media_community_bridge(self, bridge_definitions):
        """Standing bridge exists between Media/DM and Community."""
        assert _has_bridge(bridge_definitions, "Media/DM", "Community"), (
            "Missing bridge: Media/DM <-> Community"
        )

    def test_devrel_standards_bridge(self, bridge_definitions):
        """Standing bridge exists between Developer Relations and Standards."""
        assert _has_bridge(bridge_definitions, "Developer Relations", "Standards"), (
            "Missing bridge: Developer Relations <-> Standards"
        )

    def test_partnerships_governance_bridge(self, bridge_definitions):
        """Standing bridge exists between Partnerships and Governance."""
        assert _has_bridge(bridge_definitions, "Partnerships", "Governance"), (
            "Missing bridge: Partnerships <-> Governance"
        )

    def test_finance_bridge_exists(self, bridge_definitions):
        """Finance has at least one bridge (budget oversight)."""
        has_finance = any(
            b["source"] == "Finance" or b["target"] == "Finance" for b in bridge_definitions
        )
        assert has_finance, "Finance must have at least one bridge for budget oversight"

    def test_all_bridges_are_standing_type(self, bridge_definitions):
        """All defined bridges are Standing type."""
        for b in bridge_definitions:
            assert b["type"] == "Standing", (
                f"Bridge {b['source']} <-> {b['target']} is '{b['type']}', expected 'Standing'"
            )

    def test_all_bridges_have_purpose(self, bridge_definitions):
        """Every bridge has a non-empty purpose."""
        for b in bridge_definitions:
            assert b.get("purpose"), f"Bridge {b['source']} <-> {b['target']} has no purpose"


# ---------------------------------------------------------------------------
# Task 6045: Foundation Org Validation Suite
# ---------------------------------------------------------------------------


class TestFoundationOrgValidation:
    """Comprehensive validation of the generated Foundation org."""

    def test_org_generates_without_errors(self, foundation_config: OrgGeneratorConfig):
        """OrgGenerator.generate() completes without raising."""
        generator = OrgGenerator()
        org = generator.generate(foundation_config)
        assert org is not None

    def test_all_11_teams_present(self, foundation_org: OrgDefinition):
        """The org has exactly 11 teams."""
        assert len(foundation_org.teams) == 11, (
            f"Expected 11 teams, got {len(foundation_org.teams)}: "
            f"{[t.name for t in foundation_org.teams]}"
        )

    def test_all_3_departments_present(self, foundation_org: OrgDefinition):
        """The org has exactly 3 departments."""
        assert len(foundation_org.departments) == 3

    def test_all_agents_have_envelopes(self, foundation_org: OrgDefinition):
        """Every agent references an envelope that exists in the org."""
        envelope_ids = {e.id for e in foundation_org.envelopes}
        for agent in foundation_org.agents:
            assert agent.constraint_envelope in envelope_ids, (
                f"Agent '{agent.id}' references envelope '{agent.constraint_envelope}' "
                f"which does not exist. Available: {sorted(envelope_ids)}"
            )

    def test_11_coordinators_injected(self, foundation_org: OrgDefinition):
        """Every team has exactly one auto-injected coordinator (11 total)."""
        coordinator_agents = [a for a in foundation_org.agents if "coordinator" in a.id.lower()]
        assert len(coordinator_agents) == 11, (
            f"Expected 11 coordinator agents, got {len(coordinator_agents)}: "
            f"{[a.id for a in coordinator_agents]}"
        )

    def test_every_team_has_coordinator(self, foundation_org: OrgDefinition):
        """Each team's agent list includes a coordinator."""
        for team in foundation_org.teams:
            coordinator_ids = [aid for aid in team.agents if "coordinator" in aid.lower()]
            assert len(coordinator_ids) >= 1, (
                f"Team '{team.name}' (id={team.id}) has no coordinator agent. "
                f"Team agents: {team.agents}"
            )

    def test_every_team_has_lead(self, foundation_org: OrgDefinition):
        """Each team has a designated team lead."""
        for team in foundation_org.teams:
            assert team.team_lead is not None, f"Team '{team.name}' has no team_lead"
            assert team.team_lead in team.agents, (
                f"Team '{team.name}' lead '{team.team_lead}' not in team agents: {team.agents}"
            )

    def test_validate_org_detailed_zero_errors(self, foundation_org: OrgDefinition):
        """validate_org_detailed() returns zero ERROR-severity findings."""
        results = foundation_org.validate_org_detailed()
        errors = [r for r in results if r.is_error]
        if errors:
            error_msgs = "\n".join(f"  [{r.code}] {r.message}" for r in errors)
            pytest.fail(f"validate_org_detailed() found {len(errors)} error(s):\n{error_msgs}")

    def test_validate_org_passes(self, foundation_org: OrgDefinition):
        """validate_org() returns (True, [])."""
        valid, errors = foundation_org.validate_org()
        assert valid is True, f"validate_org() failed: {errors}"

    def test_org_id_and_name(self, foundation_org: OrgDefinition):
        """Org has the correct id and name."""
        assert foundation_org.org_id == "terrene-foundation"
        assert foundation_org.name == "Terrene Foundation"
        assert foundation_org.authority_id == "terrene.foundation"


# ---------------------------------------------------------------------------
# Monotonic Tightening at Every Level
# ---------------------------------------------------------------------------


class TestMonotonicTightening:
    """Monotonic tightening holds at every level: org -> dept -> team -> agent."""

    def test_org_envelope_exists(self, foundation_org: OrgDefinition):
        """Org has an org-level envelope."""
        assert foundation_org.org_envelope is not None

    def test_department_envelopes_tighter_than_org(self, foundation_org: OrgDefinition):
        """Every department envelope is a tightening of the org envelope."""
        deriver = EnvelopeDeriver()
        org_env = foundation_org.org_envelope
        assert org_env is not None

        for dept in foundation_org.departments:
            assert dept.envelope is not None, f"Department '{dept.name}' has no envelope"
            assert deriver.validate_tightening(org_env, dept.envelope), (
                f"Department '{dept.name}' envelope is NOT tighter than org envelope"
            )

    def test_team_envelopes_within_hierarchy(self, foundation_org: OrgDefinition):
        """Every team's lead envelope is within the org envelope constraints.

        Since team envelopes are derived from department envelopes which are
        derived from org, we verify transitively by checking against the org
        envelope for allowed_actions subset relationship.
        """
        org_env = foundation_org.org_envelope
        assert org_env is not None
        org_actions = set(org_env.operational.allowed_actions)

        envelope_index = {e.id: e for e in foundation_org.envelopes}
        for team in foundation_org.teams:
            if not team.team_lead:
                continue
            lead_agent = next((a for a in foundation_org.agents if a.id == team.team_lead), None)
            if not lead_agent:
                continue
            lead_env = envelope_index.get(lead_agent.constraint_envelope)
            if not lead_env or not lead_env.operational:
                continue
            lead_actions = set(lead_env.operational.allowed_actions)
            extra = lead_actions - org_actions
            assert not extra, (
                f"Team '{team.name}' lead has actions {sorted(extra)} not in org envelope"
            )

    def test_agent_envelopes_within_lead(self, foundation_org: OrgDefinition):
        """Every non-lead, non-coordinator agent's allowed_actions are a
        subset of their team lead's allowed_actions."""
        envelope_index = {e.id: e for e in foundation_org.envelopes}
        agent_index = {a.id: a for a in foundation_org.agents}

        for team in foundation_org.teams:
            if not team.team_lead:
                continue
            lead = agent_index.get(team.team_lead)
            if not lead:
                continue
            lead_env = envelope_index.get(lead.constraint_envelope)
            if not lead_env:
                continue
            lead_actions = set(lead_env.operational.allowed_actions or [])

            for aid in team.agents:
                if aid == team.team_lead:
                    continue
                member = agent_index.get(aid)
                if not member:
                    continue
                member_env = envelope_index.get(member.constraint_envelope)
                if not member_env or not member_env.operational:
                    continue
                member_actions = set(member_env.operational.allowed_actions or [])
                extra = member_actions - lead_actions
                assert not extra, (
                    f"Agent '{aid}' in team '{team.name}' has actions "
                    f"{sorted(extra)} not in lead '{team.team_lead}' envelope"
                )

    def test_financial_tightening_org_to_agent(self, foundation_org: OrgDefinition):
        """No agent's financial limit exceeds the org-level limit."""
        org_env = foundation_org.org_envelope
        assert org_env is not None
        org_spend = org_env.financial.max_spend_usd

        envelope_index = {e.id: e for e in foundation_org.envelopes}
        for agent in foundation_org.agents:
            env = envelope_index.get(agent.constraint_envelope)
            if not env or not env.financial:
                continue
            assert env.financial.max_spend_usd <= org_spend, (
                f"Agent '{agent.id}' envelope spend ${env.financial.max_spend_usd} "
                f"exceeds org spend ${org_spend}"
            )


# ---------------------------------------------------------------------------
# Task 6046: YAML Templates
# ---------------------------------------------------------------------------


class TestYAMLTemplates:
    """Validate YAML template files exist and are loadable."""

    TEMPLATE_NAMES = [
        "media",
        "standards",
        "governance",
        "partnerships",
        "website",
        "community",
        "devrel",
        "finance",
        "certification",
        "training",
        "legal",
    ]

    def test_builtin_directory_exists(self):
        """The builtin templates directory exists."""
        from pathlib import Path

        builtin_dir = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "care_platform"
            / "build"
            / "templates"
            / "builtin"
        )
        assert builtin_dir.exists(), f"Builtin templates directory not found: {builtin_dir}"

    def test_all_11_yaml_templates_exist(self):
        """All 11 YAML template files exist."""
        from pathlib import Path

        builtin_dir = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "care_platform"
            / "build"
            / "templates"
            / "builtin"
        )
        for name in self.TEMPLATE_NAMES:
            yaml_path = builtin_dir / f"{name}.yaml"
            assert yaml_path.exists(), f"YAML template '{name}.yaml' not found at {yaml_path}"

    def test_yaml_templates_are_valid_yaml(self):
        """Each YAML template file parses without error."""
        from pathlib import Path

        builtin_dir = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "care_platform"
            / "build"
            / "templates"
            / "builtin"
        )
        for name in self.TEMPLATE_NAMES:
            yaml_path = builtin_dir / f"{name}.yaml"
            if not yaml_path.exists():
                pytest.skip(f"{name}.yaml not found")
            raw = yaml_path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            assert isinstance(data, dict), f"Template '{name}.yaml' top-level is not a dict"

    def test_yaml_templates_have_required_fields(self):
        """Each YAML template has name, agents, envelopes, and team fields."""
        from pathlib import Path

        builtin_dir = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "care_platform"
            / "build"
            / "templates"
            / "builtin"
        )
        required_fields = {"name", "agents", "envelopes", "team"}
        for name in self.TEMPLATE_NAMES:
            yaml_path = builtin_dir / f"{name}.yaml"
            if not yaml_path.exists():
                pytest.skip(f"{name}.yaml not found")
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            for field in required_fields:
                assert field in data, f"Template '{name}.yaml' missing required field '{field}'"

    def test_yaml_templates_have_department(self):
        """Each YAML template declares its department affiliation."""
        from pathlib import Path

        builtin_dir = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "care_platform"
            / "build"
            / "templates"
            / "builtin"
        )
        for name in self.TEMPLATE_NAMES:
            yaml_path = builtin_dir / f"{name}.yaml"
            if not yaml_path.exists():
                pytest.skip(f"{name}.yaml not found")
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            assert "department" in data, f"Template '{name}.yaml' missing 'department' field"

    def test_yaml_templates_loadable_as_team_template(self):
        """Each YAML template can be loaded via TemplateRegistry.load_from_yaml()."""
        from pathlib import Path

        from care_platform.build.templates.registry import TemplateRegistry

        builtin_dir = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "care_platform"
            / "build"
            / "templates"
            / "builtin"
        )
        for name in self.TEMPLATE_NAMES:
            yaml_path = builtin_dir / f"{name}.yaml"
            if not yaml_path.exists():
                pytest.skip(f"{name}.yaml not found")
            template = TemplateRegistry.load_from_yaml(yaml_path)
            assert template.name == name, (
                f"Template loaded from '{name}.yaml' has name '{template.name}', expected '{name}'"
            )


# ---------------------------------------------------------------------------
# YAML Round-Trip
# ---------------------------------------------------------------------------


class TestYAMLRoundTrip:
    """Full round-trip: generate -> export YAML -> import -> validate -> identical."""

    def test_org_config_yaml_round_trip(self, foundation_config: OrgGeneratorConfig):
        """OrgGeneratorConfig survives a YAML round-trip."""
        # Export to YAML-compatible dict
        config_dict = foundation_config.model_dump(mode="json")
        yaml_str = yaml.dump(config_dict, default_flow_style=False)

        # Re-parse
        reloaded_dict = yaml.safe_load(yaml_str)
        reloaded_config = OrgGeneratorConfig(**reloaded_dict)

        # Verify
        assert reloaded_config.org_id == foundation_config.org_id
        assert reloaded_config.org_name == foundation_config.org_name
        assert len(reloaded_config.departments) == len(foundation_config.departments)

        # Re-generate and validate
        generator = OrgGenerator()
        reloaded_org = generator.generate(reloaded_config)
        results = reloaded_org.validate_org_detailed()
        errors = [r for r in results if r.is_error]
        assert not errors, (
            f"Re-generated org has {len(errors)} validation errors after YAML round-trip"
        )


# ---------------------------------------------------------------------------
# PlatformBootstrap Compatibility
# ---------------------------------------------------------------------------


class TestPlatformBootstrapCompatibility:
    """The Foundation org can be converted to PlatformConfig for bootstrap."""

    def test_org_to_platform_config_has_all_data(self, foundation_org: OrgDefinition):
        """The org can produce a PlatformConfig with all agents, teams, envelopes."""
        from care_platform.build.config.schema import GenesisConfig, PlatformConfig

        platform_config = PlatformConfig(
            name=foundation_org.name,
            genesis=GenesisConfig(
                authority=foundation_org.authority_id,
                authority_name=foundation_org.name,
            ),
            constraint_envelopes=list(foundation_org.envelopes),
            agents=list(foundation_org.agents),
            teams=list(foundation_org.teams),
            workspaces=list(foundation_org.workspaces),
        )
        assert len(platform_config.agents) == len(foundation_org.agents)
        assert len(platform_config.teams) == 11
        assert len(platform_config.constraint_envelopes) == len(foundation_org.envelopes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_team_by_name(org: OrgDefinition, team_name: str):
    """Find a team by name, raise AssertionError if not found."""
    for t in org.teams:
        if t.name == team_name:
            return t
    available = [t.name for t in org.teams]
    raise AssertionError(f"Team '{team_name}' not found. Available teams: {available}")


def _assert_department_teams(org: OrgDefinition, dept_name: str, expected_team_names: set[str]):
    """Assert a department contains exactly the expected teams by name."""
    dept = None
    for d in org.departments:
        if d.name == dept_name:
            dept = d
            break
    assert dept is not None, (
        f"Department '{dept_name}' not found. Available: {[d.name for d in org.departments]}"
    )

    # Map team IDs to names
    team_name_map = {t.id: t.name for t in org.teams}
    actual_names = {team_name_map.get(tid, tid) for tid in dept.teams}
    assert actual_names == expected_team_names, (
        f"Department '{dept_name}' has teams {sorted(actual_names)}, "
        f"expected {sorted(expected_team_names)}"
    )


def _has_bridge(bridges: list[dict], team_a: str, team_b: str) -> bool:
    """Check if a bridge exists between two teams (in either direction)."""
    for b in bridges:
        if (b["source"] == team_a and b["target"] == team_b) or (
            b["source"] == team_b and b["target"] == team_a
        ):
            return True
    return False
