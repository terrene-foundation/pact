# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Template Library Expansion (M20: Tasks 5036-5040).

5036: Engineering team template
5037: Executive/leadership team template
5038: Custom template from YAML (load_from_yaml)
5039: Multi-team template composition (OrgBuilder.compose_from_templates)
5040: Template validation on registration
"""

from pathlib import Path

import pytest
import yaml

from pact_platform.build.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    TeamConfig,
)
from pact_platform.build.org.builder import OrgBuilder, OrgDefinition
from pact_platform.build.templates.registry import (
    TeamTemplate,
    TemplateRegistry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry():
    """Fresh TemplateRegistry with all built-in templates loaded."""
    return TemplateRegistry()


@pytest.fixture()
def tmp_yaml_dir(tmp_path):
    """Directory for temporary YAML template files."""
    return tmp_path


# ===========================================================================
# Task 5036: Engineering team template
# ===========================================================================


class TestEngineeringTemplate:
    """Engineering/development team template with 4 agents."""

    def test_engineering_template_exists(self, registry):
        """Registry lists 'engineering' as an available template."""
        assert "engineering" in registry.list()

    def test_engineering_template_returns_team_template(self, registry):
        """get('engineering') returns a TeamTemplate instance."""
        tpl = registry.get("engineering")
        assert isinstance(tpl, TeamTemplate)
        assert tpl.name == "engineering"

    def test_engineering_has_four_agents(self, registry):
        """Engineering template defines exactly 4 agents."""
        tpl = registry.get("engineering")
        assert len(tpl.agents) == 4

    def test_engineering_agent_roles(self, registry):
        """Engineering template contains team lead, code reviewer, testing, deployment agents."""
        tpl = registry.get("engineering")
        agent_ids = {a.id for a in tpl.agents}
        assert "engineering-team-lead" in agent_ids
        assert "engineering-code-reviewer" in agent_ids
        assert "engineering-testing-agent" in agent_ids
        assert "engineering-deployment-agent" in agent_ids

    def test_engineering_has_four_envelopes(self, registry):
        """Engineering template defines one envelope per agent."""
        tpl = registry.get("engineering")
        assert len(tpl.envelopes) == 4

    def test_engineering_envelope_references_resolve(self, registry):
        """Every agent's constraint_envelope references an existing envelope."""
        tpl = registry.get("engineering")
        envelope_ids = {e.id for e in tpl.envelopes}
        for agent in tpl.agents:
            assert agent.constraint_envelope in envelope_ids, (
                f"Agent '{agent.id}' references '{agent.constraint_envelope}' not in {envelope_ids}"
            )

    def test_engineering_agents_listed_in_team(self, registry):
        """All agents appear in the team's agents list."""
        tpl = registry.get("engineering")
        team_agent_ids = set(tpl.team.agents)
        for agent in tpl.agents:
            assert agent.id in team_agent_ids

    def test_engineering_team_has_lead(self, registry):
        """Team lead is set to engineering-team-lead."""
        tpl = registry.get("engineering")
        assert tpl.team.team_lead == "engineering-team-lead"

    def test_engineering_code_read_write_access(self, registry):
        """Lead envelope allows code read/write paths."""
        tpl = registry.get("engineering")
        lead_env = next(e for e in tpl.envelopes if "lead" in e.id)
        read_paths = lead_env.data_access.read_paths
        write_paths = lead_env.data_access.write_paths
        # Lead should have broad code access
        assert any("code" in p or "src" in p or "engineering" in p for p in read_paths), (
            f"Lead envelope should have code read access, got read_paths={read_paths}"
        )
        assert any("code" in p or "src" in p or "engineering" in p for p in write_paths), (
            f"Lead envelope should have code write access, got write_paths={write_paths}"
        )

    def test_engineering_ci_trigger_access(self, registry):
        """At least one agent has CI trigger capability."""
        tpl = registry.get("engineering")
        all_capabilities = set()
        for agent in tpl.agents:
            all_capabilities.update(agent.capabilities)
        assert any(
            "ci" in cap or "deploy" in cap or "trigger" in cap for cap in all_capabilities
        ), f"Engineering template should include CI trigger capability, got {all_capabilities}"

    def test_engineering_deployment_blocked_without_approval(self, registry):
        """Deployment agent's envelope blocks production deploy."""
        tpl = registry.get("engineering")
        deploy_env = next(e for e in tpl.envelopes if "deployment" in e.id)
        blocked = deploy_env.operational.blocked_actions
        assert any("production" in action or "prod_deploy" in action for action in blocked), (
            f"Deployment envelope should block production deploy, blocked={blocked}"
        )

    def test_engineering_internal_only_communication(self, registry):
        """All engineering envelopes enforce internal-only communication."""
        tpl = registry.get("engineering")
        for env in tpl.envelopes:
            assert env.communication.internal_only is True, (
                f"Engineering envelope '{env.id}' should be internal_only"
            )

    def test_engineering_template_description(self, registry):
        """Engineering template has a non-empty description."""
        tpl = registry.get("engineering")
        assert tpl.description
        assert len(tpl.description) > 10


# ===========================================================================
# Task 5037: Executive/leadership team template
# ===========================================================================


class TestExecutiveTemplate:
    """Executive/leadership team template with 3 agents."""

    def test_executive_template_exists(self, registry):
        """Registry lists 'executive' as an available template."""
        assert "executive" in registry.list()

    def test_executive_template_returns_team_template(self, registry):
        """get('executive') returns a TeamTemplate instance."""
        tpl = registry.get("executive")
        assert isinstance(tpl, TeamTemplate)
        assert tpl.name == "executive"

    def test_executive_has_three_agents(self, registry):
        """Executive template defines exactly 3 agents."""
        tpl = registry.get("executive")
        assert len(tpl.agents) == 3

    def test_executive_agent_roles(self, registry):
        """Executive template contains chief of staff, strategy analyst, reporting agent."""
        tpl = registry.get("executive")
        agent_ids = {a.id for a in tpl.agents}
        assert "executive-chief-of-staff" in agent_ids
        assert "executive-strategy-analyst" in agent_ids
        assert "executive-reporting-agent" in agent_ids

    def test_executive_has_three_envelopes(self, registry):
        """Executive template defines one envelope per agent."""
        tpl = registry.get("executive")
        assert len(tpl.envelopes) == 3

    def test_executive_envelope_references_resolve(self, registry):
        """Every agent's constraint_envelope references an existing envelope."""
        tpl = registry.get("executive")
        envelope_ids = {e.id for e in tpl.envelopes}
        for agent in tpl.agents:
            assert agent.constraint_envelope in envelope_ids

    def test_executive_agents_listed_in_team(self, registry):
        """All agents appear in the team's agents list."""
        tpl = registry.get("executive")
        team_agent_ids = set(tpl.team.agents)
        for agent in tpl.agents:
            assert agent.id in team_agent_ids

    def test_executive_team_has_lead(self, registry):
        """Team lead is set to executive-chief-of-staff."""
        tpl = registry.get("executive")
        assert tpl.team.team_lead == "executive-chief-of-staff"

    def test_executive_broader_read_access(self, registry):
        """Executive lead has broader read access (cross-workspace)."""
        tpl = registry.get("executive")
        lead_env = next(e for e in tpl.envelopes if "chief" in e.id or "lead" in e.id)
        read_paths = lead_env.data_access.read_paths
        # Executive should read across multiple workspaces
        assert any("*" in p for p in read_paths), (
            f"Executive lead should have broad read access with wildcards, got {read_paths}"
        )

    def test_executive_stricter_write_access(self, registry):
        """Executive envelopes have restricted write paths (not everything writable)."""
        tpl = registry.get("executive")
        for env in tpl.envelopes:
            write_paths = env.data_access.write_paths
            read_paths = env.data_access.read_paths
            # Write should be more restrictive than read
            assert len(write_paths) <= len(read_paths), (
                f"Envelope '{env.id}' write should be stricter than read: "
                f"write={write_paths}, read={read_paths}"
            )

    def test_executive_higher_action_limits(self, registry):
        """Executive lead has higher daily action limit than subordinates."""
        tpl = registry.get("executive")
        lead_env = next(e for e in tpl.envelopes if "chief" in e.id or "lead" in e.id)
        non_lead_envs = [e for e in tpl.envelopes if e.id != lead_env.id]
        for env in non_lead_envs:
            assert (
                lead_env.operational.max_actions_per_day >= env.operational.max_actions_per_day
            ), (
                f"Lead rate ({lead_env.operational.max_actions_per_day}) should >= "
                f"'{env.id}' rate ({env.operational.max_actions_per_day})"
            )

    def test_executive_internal_only_communication(self, registry):
        """All executive envelopes enforce internal-only communication."""
        tpl = registry.get("executive")
        for env in tpl.envelopes:
            assert env.communication.internal_only is True

    def test_executive_template_description(self, registry):
        """Executive template has a non-empty description."""
        tpl = registry.get("executive")
        assert tpl.description
        assert len(tpl.description) > 10


# ===========================================================================
# Task 5038: Custom template from YAML
# ===========================================================================


class TestLoadFromYaml:
    """TemplateRegistry.load_from_yaml(path) loads a TeamTemplate from YAML."""

    def _write_yaml_template(self, directory: Path, filename: str, data: dict) -> Path:
        """Helper: write a YAML dict to a file and return the path."""
        path = directory / filename
        path.write_text(yaml.dump(data, default_flow_style=False))
        return path

    def _valid_yaml_data(self) -> dict:
        """Minimal valid YAML template data."""
        return {
            "name": "custom-team",
            "description": "A custom team loaded from YAML",
            "agents": [
                {
                    "id": "custom-lead",
                    "name": "Custom Lead",
                    "role": "Team lead for custom team",
                    "constraint_envelope": "custom-lead-envelope",
                    "capabilities": ["coordinate", "review"],
                },
            ],
            "envelopes": [
                {
                    "id": "custom-lead-envelope",
                    "description": "Custom lead envelope",
                    "operational": {
                        "allowed_actions": ["coordinate", "review"],
                        "blocked_actions": ["deploy_production"],
                        "max_actions_per_day": 50,
                    },
                    "data_access": {
                        "read_paths": ["workspaces/custom/*"],
                        "write_paths": ["workspaces/custom/*"],
                    },
                },
            ],
            "team": {
                "id": "custom-team",
                "name": "Custom Team",
                "workspace": "ws-custom",
                "team_lead": "custom-lead",
                "agents": ["custom-lead"],
            },
        }

    def test_load_from_yaml_returns_team_template(self, tmp_yaml_dir):
        """load_from_yaml() returns a TeamTemplate instance."""
        path = self._write_yaml_template(tmp_yaml_dir, "custom.yaml", self._valid_yaml_data())
        tpl = TemplateRegistry.load_from_yaml(path)
        assert isinstance(tpl, TeamTemplate)

    def test_load_from_yaml_preserves_name(self, tmp_yaml_dir):
        """Template name matches the YAML 'name' field."""
        path = self._write_yaml_template(tmp_yaml_dir, "custom.yaml", self._valid_yaml_data())
        tpl = TemplateRegistry.load_from_yaml(path)
        assert tpl.name == "custom-team"

    def test_load_from_yaml_preserves_description(self, tmp_yaml_dir):
        """Template description matches the YAML 'description' field."""
        path = self._write_yaml_template(tmp_yaml_dir, "custom.yaml", self._valid_yaml_data())
        tpl = TemplateRegistry.load_from_yaml(path)
        assert tpl.description == "A custom team loaded from YAML"

    def test_load_from_yaml_preserves_agents(self, tmp_yaml_dir):
        """All agents from YAML are present as AgentConfig instances."""
        path = self._write_yaml_template(tmp_yaml_dir, "custom.yaml", self._valid_yaml_data())
        tpl = TemplateRegistry.load_from_yaml(path)
        assert len(tpl.agents) == 1
        assert isinstance(tpl.agents[0], AgentConfig)
        assert tpl.agents[0].id == "custom-lead"

    def test_load_from_yaml_preserves_envelopes(self, tmp_yaml_dir):
        """All envelopes from YAML are present as ConstraintEnvelopeConfig instances."""
        path = self._write_yaml_template(tmp_yaml_dir, "custom.yaml", self._valid_yaml_data())
        tpl = TemplateRegistry.load_from_yaml(path)
        assert len(tpl.envelopes) == 1
        assert isinstance(tpl.envelopes[0], ConstraintEnvelopeConfig)
        assert tpl.envelopes[0].id == "custom-lead-envelope"

    def test_load_from_yaml_preserves_team(self, tmp_yaml_dir):
        """Team config from YAML is preserved."""
        path = self._write_yaml_template(tmp_yaml_dir, "custom.yaml", self._valid_yaml_data())
        tpl = TemplateRegistry.load_from_yaml(path)
        assert isinstance(tpl.team, TeamConfig)
        assert tpl.team.id == "custom-team"
        assert tpl.team.team_lead == "custom-lead"

    def test_load_from_yaml_with_str_path(self, tmp_yaml_dir):
        """load_from_yaml() accepts a string path (not just Path)."""
        path = self._write_yaml_template(tmp_yaml_dir, "custom.yaml", self._valid_yaml_data())
        tpl = TemplateRegistry.load_from_yaml(str(path))
        assert isinstance(tpl, TeamTemplate)
        assert tpl.name == "custom-team"

    def test_load_from_yaml_file_not_found_raises(self):
        """load_from_yaml() raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            TemplateRegistry.load_from_yaml("/nonexistent/path/template.yaml")

    def test_load_from_yaml_invalid_yaml_raises(self, tmp_yaml_dir):
        """load_from_yaml() raises ValueError for invalid YAML content."""
        path = tmp_yaml_dir / "bad.yaml"
        path.write_text("name: [invalid\n  broken yaml")
        with pytest.raises((ValueError, yaml.YAMLError)):
            TemplateRegistry.load_from_yaml(path)

    def test_load_from_yaml_missing_required_field_raises(self, tmp_yaml_dir):
        """load_from_yaml() raises ValueError when required fields are missing."""
        data = self._valid_yaml_data()
        del data["team"]  # 'team' is required
        path = self._write_yaml_template(tmp_yaml_dir, "incomplete.yaml", data)
        with pytest.raises((ValueError, Exception)):
            TemplateRegistry.load_from_yaml(path)

    def test_load_from_yaml_registers_in_registry(self, tmp_yaml_dir, registry):
        """A YAML-loaded template can be registered and retrieved."""
        path = self._write_yaml_template(tmp_yaml_dir, "custom.yaml", self._valid_yaml_data())
        tpl = TemplateRegistry.load_from_yaml(path)
        registry.register(tpl)
        assert "custom-team" in registry.list()
        retrieved = registry.get("custom-team")
        assert retrieved.name == "custom-team"

    def test_load_from_yaml_multi_agent(self, tmp_yaml_dir):
        """YAML template with multiple agents loads correctly."""
        data = self._valid_yaml_data()
        data["agents"].append(
            {
                "id": "custom-worker",
                "name": "Custom Worker",
                "role": "Worker agent",
                "constraint_envelope": "custom-worker-envelope",
                "capabilities": ["work"],
            }
        )
        data["envelopes"].append(
            {
                "id": "custom-worker-envelope",
                "description": "Worker envelope",
                "operational": {
                    "allowed_actions": ["work"],
                    "max_actions_per_day": 20,
                },
            }
        )
        data["team"]["agents"].append("custom-worker")
        path = self._write_yaml_template(tmp_yaml_dir, "multi.yaml", data)
        tpl = TemplateRegistry.load_from_yaml(path)
        assert len(tpl.agents) == 2
        assert len(tpl.envelopes) == 2


# ===========================================================================
# Task 5039: Multi-team template composition
# ===========================================================================


class TestComposeFromTemplates:
    """OrgBuilder.compose_from_templates() combines multiple templates into an OrgDefinition."""

    def test_compose_returns_org_definition(self, registry):
        """compose_from_templates() returns an OrgDefinition."""
        org = OrgBuilder.compose_from_templates(
            ["governance", "standards"],
            org_id="test-org",
            org_name="Test Org",
            registry=registry,
        )
        assert isinstance(org, OrgDefinition)

    def test_compose_includes_all_agents_from_all_templates(self, registry):
        """Composed org includes agents from every template."""
        org = OrgBuilder.compose_from_templates(
            ["governance", "standards"],
            org_id="test-org",
            org_name="Test Org",
            registry=registry,
        )
        # governance has 3 agents, standards has 3 agents
        assert len(org.agents) == 6

    def test_compose_includes_all_teams(self, registry):
        """Composed org includes a team from each template."""
        org = OrgBuilder.compose_from_templates(
            ["governance", "standards"],
            org_id="test-org",
            org_name="Test Org",
            registry=registry,
        )
        assert len(org.teams) == 2

    def test_compose_includes_all_envelopes(self, registry):
        """Composed org includes envelopes from every template."""
        org = OrgBuilder.compose_from_templates(
            ["governance", "standards"],
            org_id="test-org",
            org_name="Test Org",
            registry=registry,
        )
        # governance has 3 envelopes, standards has 3 envelopes
        assert len(org.envelopes) == 6

    def test_compose_creates_workspaces_for_each_template(self, registry):
        """Composed org creates a workspace for each template's team."""
        org = OrgBuilder.compose_from_templates(
            ["governance", "standards"],
            org_id="test-org",
            org_name="Test Org",
            registry=registry,
        )
        assert len(org.workspaces) >= 2
        ws_ids = {w.id for w in org.workspaces}
        # Each team's workspace should be represented
        for team in org.teams:
            assert team.workspace in ws_ids, (
                f"Team '{team.id}' workspace '{team.workspace}' not in workspaces {ws_ids}"
            )

    def test_compose_no_duplicate_ids(self, registry):
        """Composed org has no duplicate agent, team, envelope, or workspace IDs."""
        org = OrgBuilder.compose_from_templates(
            ["governance", "standards", "media"],
            org_id="test-org",
            org_name="Test Org",
            registry=registry,
        )
        agent_ids = [a.id for a in org.agents]
        assert len(agent_ids) == len(set(agent_ids)), f"Duplicate agent IDs: {agent_ids}"

        team_ids = [t.id for t in org.teams]
        assert len(team_ids) == len(set(team_ids)), f"Duplicate team IDs: {team_ids}"

        envelope_ids = [e.id for e in org.envelopes]
        assert len(envelope_ids) == len(set(envelope_ids)), (
            f"Duplicate envelope IDs: {envelope_ids}"
        )

        ws_ids = [w.id for w in org.workspaces]
        assert len(ws_ids) == len(set(ws_ids)), f"Duplicate workspace IDs: {ws_ids}"

    def test_compose_passes_validate_org(self, registry):
        """Composed org passes validate_org() with no errors."""
        org = OrgBuilder.compose_from_templates(
            ["governance", "standards"],
            org_id="test-org",
            org_name="Test Org",
            registry=registry,
        )
        valid, errors = org.validate_org()
        assert valid, f"Validation errors: {errors}"

    def test_compose_handles_namespace_conflicts(self, registry):
        """When composing templates with overlapping IDs, prefixing prevents conflicts."""
        # Compose the same template twice — IDs would collide without prefixing
        org = OrgBuilder.compose_from_templates(
            ["governance", "governance"],
            org_id="test-org",
            org_name="Test Org",
            registry=registry,
        )
        agent_ids = [a.id for a in org.agents]
        assert len(agent_ids) == len(set(agent_ids)), (
            f"Duplicate agent IDs after composing same template twice: {agent_ids}"
        )

    def test_compose_empty_list_raises(self, registry):
        """compose_from_templates([]) raises ValueError — at least one template required."""
        with pytest.raises(ValueError, match="at least one"):
            OrgBuilder.compose_from_templates(
                [],
                org_id="test-org",
                org_name="Test Org",
                registry=registry,
            )

    def test_compose_unknown_template_raises(self, registry):
        """compose_from_templates() with an unknown template name raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            OrgBuilder.compose_from_templates(
                ["governance", "nonexistent"],
                org_id="test-org",
                org_name="Test Org",
                registry=registry,
            )

    def test_compose_sets_org_id_and_name(self, registry):
        """Composed org has the specified org_id and name."""
        org = OrgBuilder.compose_from_templates(
            ["governance"],
            org_id="my-org",
            org_name="My Organization",
            registry=registry,
        )
        assert org.org_id == "my-org"
        assert org.name == "My Organization"

    def test_compose_three_templates(self, registry):
        """Composing three distinct templates includes all their resources."""
        org = OrgBuilder.compose_from_templates(
            ["governance", "standards", "partnerships"],
            org_id="test-org",
            org_name="Test Org",
            registry=registry,
        )
        # governance: 3 agents + standards: 3 agents + partnerships: 3 agents = 9
        assert len(org.agents) == 9
        assert len(org.teams) == 3


# ===========================================================================
# Task 5040: Template validation on registration
# ===========================================================================


class TestTemplateValidationOnRegistration:
    """Templates are validated via validate_org_detailed() at registration time."""

    def test_register_valid_template_succeeds(self, registry):
        """A structurally valid template registers without error."""
        tpl = TeamTemplate(
            name="valid-custom",
            description="A valid custom template",
            agents=[
                AgentConfig(
                    id="valid-agent",
                    name="Valid Agent",
                    role="Test agent",
                    constraint_envelope="valid-envelope",
                    capabilities=["do_stuff"],
                ),
            ],
            envelopes=[
                ConstraintEnvelopeConfig(
                    id="valid-envelope",
                    description="Valid envelope",
                    operational={
                        "allowed_actions": ["do_stuff"],
                        "max_actions_per_day": 10,
                    },
                ),
            ],
            team=TeamConfig(
                id="valid-team",
                name="Valid Team",
                workspace="ws-valid",
                team_lead="valid-agent",
                agents=["valid-agent"],
            ),
        )
        registry.register(tpl)
        assert "valid-custom" in registry.list()

    def test_register_template_with_dangling_envelope_raises(self, registry):
        """Registration rejects a template where agent references nonexistent envelope."""
        tpl = TeamTemplate(
            name="bad-envelope-ref",
            description="Template with dangling envelope reference",
            agents=[
                AgentConfig(
                    id="bad-agent",
                    name="Bad Agent",
                    role="Test",
                    constraint_envelope="nonexistent-envelope",
                    capabilities=["something"],
                ),
            ],
            envelopes=[
                ConstraintEnvelopeConfig(
                    id="different-envelope",
                    description="Wrong envelope",
                    operational={
                        "allowed_actions": ["something"],
                        "max_actions_per_day": 10,
                    },
                ),
            ],
            team=TeamConfig(
                id="bad-team",
                name="Bad Team",
                workspace="ws-bad",
                agents=["bad-agent"],
            ),
        )
        with pytest.raises(ValueError, match="nonexistent-envelope"):
            registry.register(tpl)

    def test_register_template_with_duplicate_agent_ids_raises(self, registry):
        """Registration rejects a template with duplicate agent IDs."""
        tpl = TeamTemplate(
            name="dupe-agents",
            description="Template with duplicate agent IDs",
            agents=[
                AgentConfig(
                    id="same-id",
                    name="Agent A",
                    role="First",
                    constraint_envelope="env-a",
                    capabilities=["action_a"],
                ),
                AgentConfig(
                    id="same-id",
                    name="Agent B",
                    role="Second",
                    constraint_envelope="env-a",
                    capabilities=["action_a"],
                ),
            ],
            envelopes=[
                ConstraintEnvelopeConfig(
                    id="env-a",
                    description="Envelope A",
                    operational={
                        "allowed_actions": ["action_a"],
                        "max_actions_per_day": 10,
                    },
                ),
            ],
            team=TeamConfig(
                id="dupe-team",
                name="Dupe Team",
                workspace="ws-dupe",
                agents=["same-id", "same-id"],
            ),
        )
        with pytest.raises(ValueError, match="Duplicate agent ID"):
            registry.register(tpl)

    def test_register_template_with_capability_not_in_envelope_raises(self, registry):
        """Registration rejects a template where agent capability is not in envelope allowed_actions."""
        tpl = TeamTemplate(
            name="bad-capability",
            description="Template with capability outside envelope",
            agents=[
                AgentConfig(
                    id="cap-agent",
                    name="Cap Agent",
                    role="Test",
                    constraint_envelope="cap-envelope",
                    capabilities=["allowed_action", "rogue_action"],
                ),
            ],
            envelopes=[
                ConstraintEnvelopeConfig(
                    id="cap-envelope",
                    description="Cap envelope",
                    operational={
                        "allowed_actions": ["allowed_action"],
                        "max_actions_per_day": 10,
                    },
                ),
            ],
            team=TeamConfig(
                id="cap-team",
                name="Cap Team",
                workspace="ws-cap",
                agents=["cap-agent"],
            ),
        )
        with pytest.raises(ValueError, match="rogue_action"):
            registry.register(tpl)

    def test_builtin_templates_all_pass_validation(self, registry):
        """All built-in templates (including new ones) pass validate_org_detailed with 0 errors."""
        for name in registry.list():
            tpl = registry.get(name)
            org = OrgDefinition(
                org_id=f"validate-{name}",
                name=f"Validate {name}",
                teams=[tpl.team],
                agents=list(tpl.agents),
                envelopes=list(tpl.envelopes),
                workspaces=[
                    {
                        "id": tpl.team.workspace,
                        "path": f"workspaces/{name}/",
                        "description": f"Workspace for {name}",
                    }
                ],
            )
            results = org.validate_org_detailed()
            errors = [r for r in results if r.is_error]
            assert len(errors) == 0, (
                f"Template '{name}' has {len(errors)} validation errors: "
                + "; ".join(r.message for r in errors)
            )

    def test_invalid_template_not_in_registry_after_rejection(self, registry):
        """A rejected template does not appear in the registry."""
        tpl = TeamTemplate(
            name="will-be-rejected",
            description="Should be rejected",
            agents=[
                AgentConfig(
                    id="reject-agent",
                    name="Reject Agent",
                    role="Test",
                    constraint_envelope="missing-envelope",
                ),
            ],
            envelopes=[],
            team=TeamConfig(
                id="reject-team",
                name="Reject Team",
                workspace="ws-reject",
                agents=["reject-agent"],
            ),
        )
        with pytest.raises(ValueError):
            registry.register(tpl)
        assert "will-be-rejected" not in registry.list()


# ===========================================================================
# Cross-cutting: Total template count after M20
# ===========================================================================


class TestTemplateCountAfterM20:
    """After M20, the registry should have 6 built-in templates."""

    def test_registry_has_six_builtins(self, registry):
        """Registry starts with 6 templates: media, governance, standards, partnerships, engineering, executive."""
        names = registry.list()
        assert len(names) == 6
        expected = {"media", "governance", "standards", "partnerships", "engineering", "executive"}
        assert set(names) == expected
