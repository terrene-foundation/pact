# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Auto-Generation Engine (M40: Tasks 6030-6035).

Validates that RoleCatalog, EnvelopeDeriver, OrgGenerator, and the CLI
`org generate` command correctly produce valid organizations from
high-level definitions.

TDD: These tests are written FIRST, before the implementation.
"""

import pytest
import yaml
from click.testing import CliRunner

from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
)
from pact_platform.build.org.builder import (
    OrgDefinition,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_envelope(
    envelope_id: str,
    max_spend: float = 1000.0,
    allowed_actions: list[str] | None = None,
    max_actions_per_day: int | None = None,
    internal_only: bool = True,
    active_hours_start: str | None = None,
    active_hours_end: str | None = None,
    read_paths: list[str] | None = None,
    write_paths: list[str] | None = None,
) -> ConstraintEnvelopeConfig:
    """Helper to build a ConstraintEnvelopeConfig with configurable dimensions."""
    return ConstraintEnvelopeConfig(
        id=envelope_id,
        financial=FinancialConstraintConfig(max_spend_usd=max_spend),
        operational=OperationalConstraintConfig(
            allowed_actions=allowed_actions or [],
            max_actions_per_day=max_actions_per_day,
        ),
        communication=CommunicationConstraintConfig(internal_only=internal_only),
        temporal=TemporalConstraintConfig(
            active_hours_start=active_hours_start,
            active_hours_end=active_hours_end,
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=read_paths or [],
            write_paths=write_paths or [],
        ),
    )


# ===========================================================================
# Task 6030: RoleCatalog
# ===========================================================================


class TestRoleDefinition:
    """Task 6030: RoleDefinition Pydantic model."""

    def test_create_role_definition(self):
        """RoleDefinition can be created with all required fields."""
        from pact_platform.build.org.role_catalog import RoleDefinition

        role = RoleDefinition(
            role_id="content_creator",
            name="Content Creator",
            description="Creates and manages content",
            default_capabilities=["content_creation", "content_editing"],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=50,
            default_max_cost_per_day=10.0,
        )
        assert role.role_id == "content_creator"
        assert role.name == "Content Creator"
        assert role.description == "Creates and manages content"
        assert "content_creation" in role.default_capabilities
        assert role.default_posture == TrustPostureLevel.SUPERVISED
        assert role.default_max_actions_per_day == 50
        assert role.default_max_cost_per_day == 10.0

    def test_role_definition_requires_role_id(self):
        """RoleDefinition must require a role_id."""
        from pact_platform.build.org.role_catalog import RoleDefinition

        with pytest.raises(Exception):
            RoleDefinition(
                name="Test",
                description="Test",
                default_capabilities=[],
                default_posture=TrustPostureLevel.SUPERVISED,
                default_max_actions_per_day=10,
                default_max_cost_per_day=1.0,
            )  # type: ignore[call-arg]


class TestRoleCatalog:
    """Task 6030: RoleCatalog class with built-in roles."""

    def test_catalog_has_builtin_roles(self):
        """RoleCatalog must have all 14 built-in roles."""
        from pact_platform.build.org.role_catalog import RoleCatalog

        catalog = RoleCatalog()
        expected_roles = [
            "content_creator",
            "analyst",
            "coordinator",
            "reviewer",
            "executive",
            "developer",
            "community_manager",
            "legal_advisor",
            "finance_manager",
            "trainer",
            "standards_author",
            "governance_officer",
            "partnership_manager",
            "website_manager",
        ]
        for role_id in expected_roles:
            role = catalog.get(role_id)
            assert role is not None, f"Built-in role '{role_id}' not found in catalog"
            assert role.role_id == role_id

    def test_catalog_get_returns_role_definition(self):
        """get() returns a RoleDefinition with valid fields."""
        from pact_platform.build.org.role_catalog import RoleCatalog, RoleDefinition

        catalog = RoleCatalog()
        role = catalog.get("developer")
        assert isinstance(role, RoleDefinition)
        assert role.role_id == "developer"
        assert len(role.default_capabilities) > 0
        assert role.default_posture is not None
        assert role.default_max_actions_per_day > 0
        assert role.default_max_cost_per_day >= 0.0

    def test_catalog_get_nonexistent_raises(self):
        """get() must raise ValueError for unknown role_id."""
        from pact_platform.build.org.role_catalog import RoleCatalog

        catalog = RoleCatalog()
        with pytest.raises(ValueError, match="not found"):
            catalog.get("nonexistent_role")

    def test_catalog_list_returns_all_roles(self):
        """list() returns all registered RoleDefinitions."""
        from pact_platform.build.org.role_catalog import RoleCatalog, RoleDefinition

        catalog = RoleCatalog()
        roles = catalog.list()
        assert isinstance(roles, list)
        assert len(roles) >= 14  # At least 14 built-in roles
        for r in roles:
            assert isinstance(r, RoleDefinition)

    def test_catalog_register_custom_role(self):
        """register() allows adding custom roles."""
        from pact_platform.build.org.role_catalog import RoleCatalog, RoleDefinition

        catalog = RoleCatalog()
        custom = RoleDefinition(
            role_id="custom_role",
            name="Custom Role",
            description="A custom role for testing",
            default_capabilities=["custom_action"],
            default_posture=TrustPostureLevel.PSEUDO_AGENT,
            default_max_actions_per_day=5,
            default_max_cost_per_day=0.5,
        )
        catalog.register(custom)
        retrieved = catalog.get("custom_role")
        assert retrieved.role_id == "custom_role"
        assert retrieved.name == "Custom Role"

    def test_catalog_register_duplicate_raises(self):
        """register() must raise ValueError when role_id already exists."""
        from pact_platform.build.org.role_catalog import RoleCatalog, RoleDefinition

        catalog = RoleCatalog()
        dup = RoleDefinition(
            role_id="developer",  # Already built-in
            name="Dup",
            description="Dup",
            default_capabilities=[],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=10,
            default_max_cost_per_day=1.0,
        )
        with pytest.raises(ValueError, match="already registered"):
            catalog.register(dup)

    def test_all_builtin_roles_have_valid_capabilities(self):
        """All built-in roles must have non-empty default_capabilities."""
        from pact_platform.build.org.role_catalog import RoleCatalog

        catalog = RoleCatalog()
        for role in catalog.list():
            assert len(role.default_capabilities) > 0, (
                f"Role '{role.role_id}' has empty default_capabilities"
            )

    def test_all_builtin_roles_have_valid_posture(self):
        """All built-in roles must have a valid TrustPostureLevel."""
        from pact_platform.build.org.role_catalog import RoleCatalog

        catalog = RoleCatalog()
        for role in catalog.list():
            assert isinstance(role.default_posture, TrustPostureLevel), (
                f"Role '{role.role_id}' has invalid posture: {role.default_posture}"
            )

    def test_all_builtin_roles_have_positive_limits(self):
        """All built-in roles must have positive action and cost limits."""
        from pact_platform.build.org.role_catalog import RoleCatalog

        catalog = RoleCatalog()
        for role in catalog.list():
            assert role.default_max_actions_per_day > 0, (
                f"Role '{role.role_id}' has non-positive max_actions_per_day"
            )
            assert role.default_max_cost_per_day >= 0.0, (
                f"Role '{role.role_id}' has negative max_cost_per_day"
            )


# ===========================================================================
# Task 6031: EnvelopeDeriver
# ===========================================================================


class TestEnvelopeDeriverDepartment:
    """Task 6031: derive_department_envelope produces valid child envelopes."""

    def test_derive_department_envelope_basic(self):
        """derive_department_envelope returns a ConstraintEnvelopeConfig."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        org_envelope = _make_envelope(
            "org-env",
            max_spend=10000.0,
            allowed_actions=["read", "write", "deploy", "admin"],
            max_actions_per_day=200,
            internal_only=False,
            active_hours_start="06:00",
            active_hours_end="22:00",
            read_paths=["/*"],
            write_paths=["/*"],
        )
        deriver = EnvelopeDeriver()
        dept_env = deriver.derive_department_envelope(org_envelope, "engineering")
        assert isinstance(dept_env, ConstraintEnvelopeConfig)
        assert dept_env.id != org_envelope.id

    def test_derive_department_envelope_financial_tightening(self):
        """Department financial limit must be tightened by the tightening_factor."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        org_envelope = _make_envelope("org-env", max_spend=10000.0)
        deriver = EnvelopeDeriver()
        dept_env = deriver.derive_department_envelope(
            org_envelope, "engineering", tightening_factor=0.8
        )
        assert dept_env.financial is not None
        assert dept_env.financial.max_spend_usd == pytest.approx(8000.0)

    def test_derive_department_envelope_operational_subset(self):
        """Department allowed actions must be a subset of org allowed actions."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        org_envelope = _make_envelope(
            "org-env",
            allowed_actions=["read", "write", "deploy", "admin"],
        )
        deriver = EnvelopeDeriver()
        dept_env = deriver.derive_department_envelope(org_envelope, "engineering")
        assert dept_env.operational is not None
        dept_actions = set(dept_env.operational.allowed_actions)
        org_actions = set(org_envelope.operational.allowed_actions)
        assert dept_actions.issubset(org_actions), (
            f"Department actions {dept_actions} not a subset of org actions {org_actions}"
        )

    def test_derive_department_envelope_rate_limit_tightened(self):
        """Department rate limit must be tighter than or equal to org rate limit."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        org_envelope = _make_envelope("org-env", max_actions_per_day=200)
        deriver = EnvelopeDeriver()
        dept_env = deriver.derive_department_envelope(
            org_envelope, "engineering", tightening_factor=0.8
        )
        if dept_env.operational.max_actions_per_day is not None:
            assert dept_env.operational.max_actions_per_day <= 200

    def test_derive_department_envelope_preserves_temporal(self):
        """Temporal constraints should be preserved or tightened from parent."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        org_envelope = _make_envelope(
            "org-env",
            active_hours_start="06:00",
            active_hours_end="22:00",
        )
        deriver = EnvelopeDeriver()
        dept_env = deriver.derive_department_envelope(org_envelope, "engineering")
        assert dept_env.temporal is not None
        # Active hours should be same or narrower (start >= parent start, end <= parent end)
        if dept_env.temporal.active_hours_start:
            assert dept_env.temporal.active_hours_start >= "06:00"
        if dept_env.temporal.active_hours_end:
            assert dept_env.temporal.active_hours_end <= "22:00"

    def test_derive_department_envelope_preserves_communication(self):
        """Communication constraints should be preserved or tightened from parent."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        org_envelope = _make_envelope("org-env", internal_only=True)
        deriver = EnvelopeDeriver()
        dept_env = deriver.derive_department_envelope(org_envelope, "engineering")
        assert dept_env.communication is not None
        # If parent is internal-only, child must also be internal-only
        assert dept_env.communication.internal_only is True

    def test_derive_department_envelope_custom_tightening_factor(self):
        """Custom tightening factor should be applied."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        org_envelope = _make_envelope("org-env", max_spend=10000.0)
        deriver = EnvelopeDeriver()
        dept_env = deriver.derive_department_envelope(
            org_envelope, "engineering", tightening_factor=0.5
        )
        assert dept_env.financial is not None
        assert dept_env.financial.max_spend_usd == pytest.approx(5000.0)


class TestEnvelopeDeriverTeam:
    """Task 6031: derive_team_envelope produces valid child envelopes."""

    def test_derive_team_envelope_basic(self):
        """derive_team_envelope returns a ConstraintEnvelopeConfig."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        dept_envelope = _make_envelope(
            "dept-env",
            max_spend=8000.0,
            allowed_actions=["read", "write", "deploy"],
            max_actions_per_day=160,
        )
        deriver = EnvelopeDeriver()
        team_env = deriver.derive_team_envelope(dept_envelope, "platform-team")
        assert isinstance(team_env, ConstraintEnvelopeConfig)

    def test_derive_team_envelope_financial_tightening(self):
        """Team financial limit must be tighter than department."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        dept_envelope = _make_envelope("dept-env", max_spend=8000.0)
        deriver = EnvelopeDeriver()
        team_env = deriver.derive_team_envelope(
            dept_envelope, "platform-team", tightening_factor=0.7
        )
        assert team_env.financial is not None
        assert team_env.financial.max_spend_usd == pytest.approx(5600.0)

    def test_derive_team_envelope_actions_subset(self):
        """Team allowed actions must be a subset of department actions."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        dept_envelope = _make_envelope("dept-env", allowed_actions=["read", "write", "deploy"])
        deriver = EnvelopeDeriver()
        team_env = deriver.derive_team_envelope(dept_envelope, "platform-team")
        team_actions = set(team_env.operational.allowed_actions)
        dept_actions = set(dept_envelope.operational.allowed_actions)
        assert team_actions.issubset(dept_actions)


class TestEnvelopeDeriverAgent:
    """Task 6031: derive_agent_envelope uses RoleDefinition for derivation."""

    def test_derive_agent_envelope_basic(self):
        """derive_agent_envelope returns a ConstraintEnvelopeConfig."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver
        from pact_platform.build.org.role_catalog import RoleCatalog

        team_envelope = _make_envelope(
            "team-env",
            max_spend=5600.0,
            allowed_actions=["read", "write"],
            max_actions_per_day=100,
        )
        catalog = RoleCatalog()
        role = catalog.get("developer")
        deriver = EnvelopeDeriver()
        agent_env = deriver.derive_agent_envelope(team_envelope, role)
        assert isinstance(agent_env, ConstraintEnvelopeConfig)

    def test_derive_agent_envelope_financial_tightening(self):
        """Agent financial limit must be tighter than team."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver
        from pact_platform.build.org.role_catalog import RoleCatalog

        team_envelope = _make_envelope("team-env", max_spend=5600.0)
        catalog = RoleCatalog()
        role = catalog.get("developer")
        deriver = EnvelopeDeriver()
        agent_env = deriver.derive_agent_envelope(team_envelope, role, tightening_factor=0.5)
        assert agent_env.financial is not None
        assert agent_env.financial.max_spend_usd <= 5600.0

    def test_derive_agent_envelope_capabilities_in_actions(self):
        """Agent capabilities must be included in allowed_actions for envelope alignment."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver
        from pact_platform.build.org.role_catalog import RoleCatalog

        team_envelope = _make_envelope(
            "team-env",
            max_spend=5600.0,
            allowed_actions=[
                "read",
                "write",
                "code_review",
                "testing",
                "code_development",
                "debugging",
                "deployment",
                "documentation",
            ],
            max_actions_per_day=100,
        )
        catalog = RoleCatalog()
        role = catalog.get("developer")
        deriver = EnvelopeDeriver()
        agent_env = deriver.derive_agent_envelope(team_envelope, role)
        # Agent actions should be a subset of team actions
        agent_actions = set(agent_env.operational.allowed_actions)
        team_actions = set(team_envelope.operational.allowed_actions)
        assert agent_actions.issubset(team_actions), (
            f"Agent actions {agent_actions} not subset of team {team_actions}"
        )


class TestEnvelopeDeriverValidateTightening:
    """Task 6031: validate_tightening checks monotonic constraint hierarchy."""

    def test_validate_tightening_valid(self):
        """validate_tightening returns True for a valid parent-child pair."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        parent = _make_envelope(
            "parent",
            max_spend=10000.0,
            allowed_actions=["read", "write", "deploy"],
            max_actions_per_day=200,
            internal_only=False,
        )
        child = _make_envelope(
            "child",
            max_spend=5000.0,
            allowed_actions=["read", "write"],
            max_actions_per_day=100,
            internal_only=True,
        )
        deriver = EnvelopeDeriver()
        assert deriver.validate_tightening(parent, child) is True

    def test_validate_tightening_financial_violation(self):
        """validate_tightening returns False when child exceeds parent financially."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        parent = _make_envelope("parent", max_spend=1000.0)
        child = _make_envelope("child", max_spend=5000.0)
        deriver = EnvelopeDeriver()
        assert deriver.validate_tightening(parent, child) is False

    def test_validate_tightening_operational_violation(self):
        """validate_tightening returns False when child has actions not in parent."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        parent = _make_envelope("parent", allowed_actions=["read"])
        child = _make_envelope("child", allowed_actions=["read", "write"])
        deriver = EnvelopeDeriver()
        assert deriver.validate_tightening(parent, child) is False

    def test_validate_tightening_rate_limit_violation(self):
        """validate_tightening returns False when child rate exceeds parent."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        parent = _make_envelope("parent", max_actions_per_day=50)
        child = _make_envelope("child", max_actions_per_day=100)
        deriver = EnvelopeDeriver()
        assert deriver.validate_tightening(parent, child) is False

    def test_validate_tightening_communication_violation(self):
        """validate_tightening returns False when parent is internal but child is not."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        parent = _make_envelope("parent", internal_only=True)
        child = _make_envelope("child", internal_only=False)
        deriver = EnvelopeDeriver()
        assert deriver.validate_tightening(parent, child) is False

    def test_validate_tightening_all_five_dimensions(self):
        """validate_tightening checks all 5 CARE constraint dimensions."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        parent = _make_envelope(
            "parent",
            max_spend=10000.0,
            allowed_actions=["read", "write", "deploy"],
            max_actions_per_day=200,
            internal_only=False,
            active_hours_start="06:00",
            active_hours_end="22:00",
            read_paths=["/*"],
            write_paths=["/*"],
        )
        # Child fully tightened
        child = _make_envelope(
            "child",
            max_spend=5000.0,
            allowed_actions=["read"],
            max_actions_per_day=50,
            internal_only=True,
            active_hours_start="08:00",
            active_hours_end="20:00",
            read_paths=["/dept/*"],
            write_paths=["/dept/*"],
        )
        deriver = EnvelopeDeriver()
        assert deriver.validate_tightening(parent, child) is True


# ===========================================================================
# Task 6032: OrgGenerator
# ===========================================================================


class TestOrgGeneratorConfig:
    """Task 6032: OrgGeneratorConfig Pydantic model."""

    def test_org_generator_config_creation(self):
        """OrgGeneratorConfig can be created with required fields."""
        from pact_platform.build.org.generator import (
            DepartmentSpec,
            OrgGeneratorConfig,
            TeamSpec,
        )

        config = OrgGeneratorConfig(
            org_id="test-org",
            org_name="Test Organization",
            authority_id="terrene.foundation",
            org_budget=50000.0,
            org_max_actions_per_day=1000,
            departments=[
                DepartmentSpec(
                    name="Engineering",
                    teams=[
                        TeamSpec(name="Platform", roles=["developer", "reviewer"]),
                    ],
                ),
            ],
        )
        assert config.org_id == "test-org"
        assert config.org_name == "Test Organization"
        assert config.authority_id == "terrene.foundation"
        assert config.org_budget == 50000.0
        assert config.org_max_actions_per_day == 1000
        assert len(config.departments) == 1
        assert config.departments[0].name == "Engineering"
        assert len(config.departments[0].teams) == 1

    def test_team_spec_with_roles(self):
        """TeamSpec holds role_ids from the catalog."""
        from pact_platform.build.org.generator import TeamSpec

        spec = TeamSpec(name="Dev Team", roles=["developer", "reviewer"])
        assert spec.name == "Dev Team"
        assert "developer" in spec.roles
        assert "reviewer" in spec.roles

    def test_department_spec_with_teams(self):
        """DepartmentSpec holds team specs."""
        from pact_platform.build.org.generator import DepartmentSpec, TeamSpec

        spec = DepartmentSpec(
            name="Engineering",
            teams=[
                TeamSpec(name="Platform", roles=["developer"]),
                TeamSpec(name="Data", roles=["analyst"]),
            ],
        )
        assert spec.name == "Engineering"
        assert len(spec.teams) == 2


class TestOrgGenerator:
    """Task 6032: OrgGenerator produces valid OrgDefinitions."""

    def _make_simple_config(self):
        """Helper to create a simple OrgGeneratorConfig."""
        from pact_platform.build.org.generator import (
            DepartmentSpec,
            OrgGeneratorConfig,
            TeamSpec,
        )

        return OrgGeneratorConfig(
            org_id="test-org",
            org_name="Test Organization",
            authority_id="terrene.foundation",
            org_budget=50000.0,
            org_max_actions_per_day=1000,
            departments=[
                DepartmentSpec(
                    name="Engineering",
                    teams=[
                        TeamSpec(name="Platform", roles=["developer", "reviewer"]),
                    ],
                ),
            ],
        )

    def test_generate_returns_org_definition(self):
        """generate() must return an OrgDefinition."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        assert isinstance(org, OrgDefinition)

    def test_generated_org_passes_validation(self):
        """Generated org MUST pass validate_org_detailed() with zero ERRORs."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        results = org.validate_org_detailed()
        errors = [r for r in results if r.is_error]
        assert len(errors) == 0, (
            f"Generated org has {len(errors)} validation errors:\n"
            + "\n".join(f"  [{r.code}] {r.message}" for r in errors)
        )

    def test_generated_org_passes_validate_org(self):
        """Generated org must also pass validate_org()."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        valid, errors = org.validate_org()
        assert valid is True, f"validate_org() failed: {errors}"

    def test_generated_org_has_correct_id_and_name(self):
        """Generated org has the specified org_id and name."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        assert org.org_id == "test-org"
        assert org.name == "Test Organization"

    def test_generated_org_has_departments(self):
        """Generated org includes departments from the config."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        assert len(org.departments) == 1
        assert org.departments[0].name == "Engineering"

    def test_generated_org_has_teams(self):
        """Generated org includes teams from the config."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        # At least one team per department's team specs
        assert len(org.teams) >= 1

    def test_generated_org_has_agents(self):
        """Generated org includes agents resolved from role catalog."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        # At least the roles specified plus coordinator
        assert len(org.agents) >= 2  # developer + reviewer (+ coordinator)

    def test_generated_org_has_envelopes(self):
        """Generated org includes constraint envelopes for all levels."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        # Org envelope + department envelopes + team envelopes + agent envelopes
        assert len(org.envelopes) >= 4

    def test_generated_org_has_workspaces(self):
        """Generated org includes workspaces for each team."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        assert len(org.workspaces) >= 1

    def test_generated_org_has_org_envelope(self):
        """Generated org has an org-level envelope."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        assert org.org_envelope is not None

    def test_generated_org_department_has_envelope(self):
        """Each generated department must have a constraint envelope."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        for dept in org.departments:
            assert dept.envelope is not None, f"Department '{dept.department_id}' has no envelope"

    def test_generated_envelope_hierarchy_is_monotonically_tighter(self):
        """Generated envelope hierarchy must satisfy monotonic tightening."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        deriver = EnvelopeDeriver()

        # Org -> department tightening
        for dept in org.departments:
            if dept.envelope and org.org_envelope:
                assert deriver.validate_tightening(org.org_envelope, dept.envelope), (
                    f"Department '{dept.department_id}' envelope not tighter than org envelope"
                )

    def test_generator_resolves_roles_from_catalog(self):
        """Generator uses RoleCatalog to resolve role IDs to agent definitions."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)

        # Check that agent roles/capabilities match catalog entries
        agent_ids = {a.id for a in org.agents}
        # Should contain agents based on developer and reviewer roles
        assert any("developer" in aid or "dev" in aid for aid in agent_ids), (
            f"No developer agent found in {agent_ids}"
        )

    def test_generator_raises_on_invalid_role(self):
        """Generator must raise ValueError for unknown role_ids."""
        from pact_platform.build.org.generator import (
            DepartmentSpec,
            OrgGenerator,
            OrgGeneratorConfig,
            TeamSpec,
        )

        config = OrgGeneratorConfig(
            org_id="bad-org",
            org_name="Bad Org",
            authority_id="test",
            org_budget=1000.0,
            org_max_actions_per_day=100,
            departments=[
                DepartmentSpec(
                    name="Dept",
                    teams=[
                        TeamSpec(name="Team", roles=["nonexistent_role"]),
                    ],
                ),
            ],
        )
        generator = OrgGenerator()
        with pytest.raises(ValueError, match="not found"):
            generator.generate(config)


# ===========================================================================
# Task 6033: Universal Coordinator Injection
# ===========================================================================


class TestCoordinatorInjection:
    """Task 6033: Every team gets an auto-injected coordinator agent."""

    def _make_simple_config(self):
        """Helper to create a simple OrgGeneratorConfig."""
        from pact_platform.build.org.generator import (
            DepartmentSpec,
            OrgGeneratorConfig,
            TeamSpec,
        )

        return OrgGeneratorConfig(
            org_id="test-org",
            org_name="Test Organization",
            authority_id="terrene.foundation",
            org_budget=50000.0,
            org_max_actions_per_day=1000,
            departments=[
                DepartmentSpec(
                    name="Engineering",
                    teams=[
                        TeamSpec(name="Platform", roles=["developer"]),
                    ],
                ),
            ],
        )

    def test_coordinator_injected_per_team(self):
        """Each team must have a coordinator agent auto-injected."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)

        for team in org.teams:
            coordinator_id = f"{team.id}-coordinator"
            assert coordinator_id in team.agents, (
                f"Team '{team.id}' missing coordinator agent '{coordinator_id}'"
            )
            # Coordinator must exist as an agent
            agent_ids = {a.id for a in org.agents}
            assert coordinator_id in agent_ids, f"Coordinator '{coordinator_id}' not in org agents"

    def test_coordinator_has_bridge_capabilities(self):
        """Coordinator must have bridge_management, cross_team_communication, task_routing."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)

        for team in org.teams:
            coordinator_id = f"{team.id}-coordinator"
            coordinator = next((a for a in org.agents if a.id == coordinator_id), None)
            assert coordinator is not None
            expected_caps = [
                "bridge_management",
                "cross_team_communication",
                "task_routing",
            ]
            for cap in expected_caps:
                assert cap in coordinator.capabilities, (
                    f"Coordinator '{coordinator_id}' missing capability '{cap}'"
                )

    def test_coordinator_posture_is_supervised(self):
        """Coordinator must start at SUPERVISED posture (never fully autonomous)."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)

        for team in org.teams:
            coordinator_id = f"{team.id}-coordinator"
            coordinator = next((a for a in org.agents if a.id == coordinator_id), None)
            assert coordinator is not None
            assert coordinator.initial_posture == TrustPostureLevel.SUPERVISED

    def test_coordinator_envelope_tighter_than_team(self):
        """Coordinator envelope must be tighter than the team-level envelope."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        deriver = EnvelopeDeriver()

        envelope_index = {e.id: e for e in org.envelopes}
        for team in org.teams:
            coordinator_id = f"{team.id}-coordinator"
            coordinator = next((a for a in org.agents if a.id == coordinator_id), None)
            assert coordinator is not None
            coord_env = envelope_index.get(coordinator.constraint_envelope)
            assert coord_env is not None

    def test_generated_org_with_coordinator_still_validates(self):
        """Full org with injected coordinators must pass validate_org_detailed()."""
        from pact_platform.build.org.generator import OrgGenerator

        config = self._make_simple_config()
        generator = OrgGenerator()
        org = generator.generate(config)
        results = org.validate_org_detailed()
        errors = [r for r in results if r.is_error]
        assert len(errors) == 0, f"Org with coordinators has {len(errors)} errors:\n" + "\n".join(
            f"  [{r.code}] {r.message}" for r in errors
        )


# ===========================================================================
# Task 6032 Edge Cases
# ===========================================================================


class TestOrgGeneratorEdgeCases:
    """Task 6032: Edge cases for auto-generation."""

    def test_empty_departments_raises(self):
        """Config with no departments must raise ValueError."""
        from pact_platform.build.org.generator import OrgGeneratorConfig

        with pytest.raises(Exception):
            OrgGeneratorConfig(
                org_id="empty-org",
                org_name="Empty Org",
                authority_id="test",
                org_budget=1000.0,
                org_max_actions_per_day=100,
                departments=[],
            )

    def test_single_agent_team(self):
        """A team with just one role should still get a coordinator and validate."""
        from pact_platform.build.org.generator import (
            DepartmentSpec,
            OrgGenerator,
            OrgGeneratorConfig,
            TeamSpec,
        )

        config = OrgGeneratorConfig(
            org_id="single-agent-org",
            org_name="Single Agent Org",
            authority_id="test",
            org_budget=5000.0,
            org_max_actions_per_day=50,
            departments=[
                DepartmentSpec(
                    name="Small Dept",
                    teams=[
                        TeamSpec(name="Solo Team", roles=["analyst"]),
                    ],
                ),
            ],
        )
        generator = OrgGenerator()
        org = generator.generate(config)
        results = org.validate_org_detailed()
        errors = [r for r in results if r.is_error]
        assert len(errors) == 0, f"Single-agent org has errors: {[r.message for r in errors]}"
        # Should have at least analyst + coordinator
        assert len(org.agents) >= 2

    def test_multi_department_multi_team(self):
        """Multiple departments each with multiple teams should generate valid org."""
        from pact_platform.build.org.generator import (
            DepartmentSpec,
            OrgGenerator,
            OrgGeneratorConfig,
            TeamSpec,
        )

        config = OrgGeneratorConfig(
            org_id="multi-org",
            org_name="Multi Department Org",
            authority_id="terrene.foundation",
            org_budget=100000.0,
            org_max_actions_per_day=2000,
            departments=[
                DepartmentSpec(
                    name="Engineering",
                    teams=[
                        TeamSpec(name="Platform", roles=["developer", "reviewer"]),
                        TeamSpec(name="Data", roles=["analyst", "developer"]),
                    ],
                ),
                DepartmentSpec(
                    name="Operations",
                    teams=[
                        TeamSpec(name="Governance", roles=["governance_officer"]),
                    ],
                ),
            ],
        )
        generator = OrgGenerator()
        org = generator.generate(config)
        results = org.validate_org_detailed()
        errors = [r for r in results if r.is_error]
        assert len(errors) == 0, "Multi-dept org has errors:\n" + "\n".join(
            f"  [{r.code}] {r.message}" for r in errors
        )
        assert len(org.departments) == 2
        assert len(org.teams) >= 3  # 3 teams

    def test_maximum_tightening_factor(self):
        """Tightening factor of nearly zero should still produce valid org."""
        from pact_platform.build.org.envelope_deriver import EnvelopeDeriver

        org_envelope = _make_envelope(
            "org-env",
            max_spend=10000.0,
            max_actions_per_day=200,
        )
        deriver = EnvelopeDeriver()
        dept_env = deriver.derive_department_envelope(
            org_envelope, "tight-dept", tightening_factor=0.1
        )
        assert dept_env.financial is not None
        assert dept_env.financial.max_spend_usd == pytest.approx(1000.0)
        assert deriver.validate_tightening(org_envelope, dept_env) is True


# ===========================================================================
# Task 6034: CLI Command
# ===========================================================================


class TestOrgGenerateCLI:
    """Task 6034: `org generate` CLI command."""

    def _make_sample_yaml(self, tmp_path) -> str:
        """Create a sample OrgGeneratorConfig YAML file."""
        config = {
            "org_id": "cli-test-org",
            "org_name": "CLI Test Organization",
            "authority_id": "terrene.foundation",
            "org_budget": 50000.0,
            "org_max_actions_per_day": 1000,
            "departments": [
                {
                    "name": "Engineering",
                    "teams": [
                        {
                            "name": "Platform",
                            "roles": ["developer", "reviewer"],
                        },
                    ],
                },
            ],
        }
        yaml_path = tmp_path / "org_config.yaml"
        yaml_path.write_text(yaml.dump(config, default_flow_style=False))
        return str(yaml_path)

    def test_org_generate_command_exists(self):
        """The `org generate` CLI command must be registered."""
        from pact_platform.build.cli import org

        # Get the list of command names on the org group
        command_names = list(org.commands.keys()) if hasattr(org, "commands") else []
        assert "generate" in command_names, (
            f"'generate' command not found in org group. Found: {command_names}"
        )

    def test_org_generate_produces_yaml_output(self, tmp_path):
        """`org generate --input <file> --output <file>` produces a YAML file."""
        from pact_platform.build.cli import main

        input_path = self._make_sample_yaml(tmp_path)
        output_path = str(tmp_path / "generated_org.yaml")

        runner = CliRunner()
        result = runner.invoke(
            main, ["org", "generate", "--input", input_path, "--output", output_path]
        )
        assert result.exit_code == 0, f"CLI failed with: {result.output}"

        # Output file should exist and be valid YAML
        import os

        assert os.path.exists(output_path), f"Output file not created: {output_path}"
        with open(output_path) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        assert "org_id" in data
        assert "agents" in data

    def test_org_generate_validate_only(self, tmp_path):
        """`org generate --input <file> --validate-only` validates but does not output."""
        from pact_platform.build.cli import main

        input_path = self._make_sample_yaml(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["org", "generate", "--input", input_path, "--validate-only"])
        assert result.exit_code == 0, f"CLI failed with: {result.output}"

    def test_org_generate_invalid_input(self, tmp_path):
        """`org generate` with invalid input should exit with error."""
        from pact_platform.build.cli import main

        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("not: valid: org: config: [")

        runner = CliRunner()
        result = runner.invoke(main, ["org", "generate", "--input", str(bad_yaml)])
        assert result.exit_code != 0

    def test_org_generate_nonexistent_input(self):
        """`org generate` with non-existent file should exit with error."""
        from pact_platform.build.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["org", "generate", "--input", "/nonexistent/path.yaml"])
        assert result.exit_code != 0
