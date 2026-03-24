# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Department Layer (M39: Tasks 6020-6024).

Validates that DepartmentConfig, OrgBuilder.add_department(), 3-level monotonic
constraint tightening (org -> department -> team -> agent), and template
department grouping all work correctly.

TDD: These tests are written FIRST, before the implementation.
"""

import pytest

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
    WorkspaceConfig,
)
from pact_platform.build.org.builder import (
    OrgBuilder,
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


def _make_org_with_departments(
    *,
    org_envelope: ConstraintEnvelopeConfig | None = None,
    dept_envelope: ConstraintEnvelopeConfig | None = None,
    team_envelope: ConstraintEnvelopeConfig | None = None,
    agent_envelope: ConstraintEnvelopeConfig | None = None,
    departments: list[DepartmentConfig] | None = None,
) -> OrgDefinition:
    """Build an OrgDefinition with org/dept/team/agent envelope hierarchy."""
    org_env = org_envelope or _make_envelope(
        "org-envelope",
        max_spend=10000.0,
        allowed_actions=["read", "write", "deploy", "admin"],
        max_actions_per_day=200,
        internal_only=False,
        active_hours_start="06:00",
        active_hours_end="22:00",
        read_paths=["/*"],
        write_paths=["/*"],
    )
    dept_env = dept_envelope or _make_envelope(
        "dept-envelope",
        max_spend=5000.0,
        allowed_actions=["read", "write", "deploy"],
        max_actions_per_day=150,
        internal_only=True,
        active_hours_start="07:00",
        active_hours_end="21:00",
        read_paths=["/dept/*"],
        write_paths=["/dept/*"],
    )
    team_env = team_envelope or _make_envelope(
        "team-envelope",
        max_spend=1000.0,
        allowed_actions=["read", "write"],
        max_actions_per_day=100,
        internal_only=True,
        active_hours_start="08:00",
        active_hours_end="20:00",
        read_paths=["/dept/team/*"],
        write_paths=["/dept/team/*"],
    )
    agent_env = agent_envelope or _make_envelope(
        "agent-envelope",
        max_spend=500.0,
        allowed_actions=["read"],
        max_actions_per_day=50,
        internal_only=True,
        active_hours_start="09:00",
        active_hours_end="18:00",
        read_paths=["/dept/team/agent/*"],
        write_paths=["/dept/team/agent/*"],
    )

    depts = departments or [
        DepartmentConfig(
            department_id="dept-1",
            name="Engineering Department",
            teams=["team-1"],
            head_agent_id="agent-lead",
            envelope=dept_env,
        ),
    ]

    return OrgDefinition(
        org_id="test-org",
        name="Test Organization",
        org_envelope=org_env,
        departments=depts,
        agents=[
            AgentConfig(
                id="agent-lead",
                name="Lead Agent",
                role="Team Lead",
                constraint_envelope="team-envelope",
            ),
            AgentConfig(
                id="agent-worker",
                name="Worker Agent",
                role="Worker",
                constraint_envelope="agent-envelope",
            ),
        ],
        envelopes=[org_env, dept_env, team_env, agent_env],
        teams=[
            TeamConfig(
                id="team-1",
                name="Team One",
                workspace="ws-1",
                team_lead="agent-lead",
                agents=["agent-lead", "agent-worker"],
            ),
        ],
        workspaces=[
            WorkspaceConfig(id="ws-1", path="workspaces/team-1/"),
        ],
    )


# ===========================================================================
# Task 6020: DepartmentConfig Model
# ===========================================================================


class TestDepartmentConfigModel:
    """Task 6020: DepartmentConfig Pydantic model."""

    def test_create_department_config_minimal(self):
        """DepartmentConfig can be created with just department_id and name."""
        dept = DepartmentConfig(
            department_id="eng-dept",
            name="Engineering",
        )
        assert dept.department_id == "eng-dept"
        assert dept.name == "Engineering"
        assert dept.description == ""
        assert dept.teams == []
        assert dept.head_agent_id is None
        assert dept.envelope is None

    def test_create_department_config_full(self):
        """DepartmentConfig can be created with all fields populated."""
        env = _make_envelope("dept-env", max_spend=5000.0)
        dept = DepartmentConfig(
            department_id="ops-dept",
            name="Operations",
            description="Operations department handling infrastructure",
            teams=["infra-team", "platform-team"],
            head_agent_id="ops-lead",
            envelope=env,
        )
        assert dept.department_id == "ops-dept"
        assert dept.name == "Operations"
        assert dept.description == "Operations department handling infrastructure"
        assert dept.teams == ["infra-team", "platform-team"]
        assert dept.head_agent_id == "ops-lead"
        assert dept.envelope is not None
        assert dept.envelope.id == "dept-env"

    def test_department_config_is_frozen(self):
        """DepartmentConfig should be frozen (immutable) for trust-plane safety."""
        dept = DepartmentConfig(
            department_id="eng-dept",
            name="Engineering",
        )
        with pytest.raises(Exception):
            dept.department_id = "changed"  # type: ignore[misc]

    def test_department_config_empty_teams_default(self):
        """Teams defaults to an empty list, not None."""
        dept = DepartmentConfig(department_id="d", name="D")
        assert isinstance(dept.teams, list)
        assert dept.teams == []


# ===========================================================================
# Task 6021: Add departments to OrgDefinition and OrgBuilder
# ===========================================================================


class TestOrgDefinitionDepartments:
    """Task 6021: OrgDefinition includes departments field."""

    def test_org_definition_has_departments_field(self):
        """OrgDefinition must have a departments field (defaults to empty list)."""
        org = OrgDefinition(org_id="test", name="Test")
        assert hasattr(org, "departments")
        assert org.departments == []

    def test_org_definition_with_departments(self):
        """OrgDefinition can store department configs."""
        dept = DepartmentConfig(
            department_id="eng",
            name="Engineering",
            teams=["team-a"],
        )
        org = OrgDefinition(
            org_id="test",
            name="Test",
            departments=[dept],
        )
        assert len(org.departments) == 1
        assert org.departments[0].department_id == "eng"

    def test_org_definition_has_org_envelope_field(self):
        """OrgDefinition must have an org_envelope field for org-level constraints."""
        env = _make_envelope("org-env")
        org = OrgDefinition(org_id="test", name="Test", org_envelope=env)
        assert org.org_envelope is not None
        assert org.org_envelope.id == "org-env"

    def test_org_definition_org_envelope_defaults_to_none(self):
        """org_envelope defaults to None for backward compatibility."""
        org = OrgDefinition(org_id="test", name="Test")
        assert org.org_envelope is None


class TestOrgBuilderAddDepartment:
    """Task 6021: OrgBuilder.add_department() fluent API."""

    def test_add_department_returns_builder(self):
        """add_department() must return the builder for fluent chaining."""
        builder = OrgBuilder("test-org", "Test")
        dept = DepartmentConfig(department_id="eng", name="Engineering")
        result = builder.add_department(dept)
        assert result is builder

    def test_add_department_fluent_chain(self):
        """add_department() can be chained with other builder methods."""
        env = _make_envelope("env-1")
        org = (
            OrgBuilder("test-org", "Test")
            .add_workspace(WorkspaceConfig(id="ws-1", path="workspaces/test/"))
            .add_envelope(env)
            .add_agent(
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                )
            )
            .add_team(TeamConfig(id="team-1", name="Team", workspace="ws-1", agents=["agent-1"]))
            .add_department(
                DepartmentConfig(
                    department_id="dept-1",
                    name="Department",
                    teams=["team-1"],
                )
            )
            .build()
        )
        assert isinstance(org, OrgDefinition)
        assert len(org.departments) == 1

    def test_add_department_with_set_org_envelope(self):
        """OrgBuilder.set_org_envelope() sets the org-level envelope."""
        org_env = _make_envelope("org-env", max_spend=10000.0)
        env = _make_envelope("env-1")
        org = (
            OrgBuilder("test-org", "Test")
            .set_org_envelope(org_env)
            .add_workspace(WorkspaceConfig(id="ws-1", path="workspaces/test/"))
            .add_envelope(env)
            .add_agent(
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                )
            )
            .add_team(TeamConfig(id="team-1", name="Team", workspace="ws-1", agents=["agent-1"]))
            .build()
        )
        assert org.org_envelope is not None
        assert org.org_envelope.id == "org-env"

    def test_build_includes_departments(self):
        """build() includes departments in the resulting OrgDefinition."""
        env = _make_envelope("env-1")
        dept = DepartmentConfig(
            department_id="dept-1",
            name="Department",
            teams=["team-1"],
        )
        org = (
            OrgBuilder("test-org", "Test")
            .add_workspace(WorkspaceConfig(id="ws-1", path="workspaces/test/"))
            .add_envelope(env)
            .add_agent(
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                )
            )
            .add_team(TeamConfig(id="team-1", name="Team", workspace="ws-1", agents=["agent-1"]))
            .add_department(dept)
            .build()
        )
        assert len(org.departments) == 1
        assert org.departments[0].department_id == "dept-1"


# ===========================================================================
# Task 6021: validate_org() structural checks for departments
# ===========================================================================


class TestDepartmentValidationStructural:
    """Task 6021: validate_org() structural validation for departments."""

    def test_duplicate_department_ids_detected(self):
        """Duplicate department IDs must produce a validation error."""
        org = OrgDefinition(
            org_id="test",
            name="Test",
            departments=[
                DepartmentConfig(department_id="dup", name="Dept A"),
                DepartmentConfig(department_id="dup", name="Dept B"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("dup" in e.lower() for e in errors)

    def test_department_references_nonexistent_team(self):
        """Department referencing a team that doesn't exist must fail validation."""
        org = OrgDefinition(
            org_id="test",
            name="Test",
            departments=[
                DepartmentConfig(
                    department_id="dept-1",
                    name="Dept",
                    teams=["nonexistent-team"],
                ),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("nonexistent-team" in e for e in errors)

    def test_team_in_multiple_departments_detected(self):
        """A team appearing in multiple departments must produce a validation error."""
        org = OrgDefinition(
            org_id="test",
            name="Test",
            teams=[
                TeamConfig(id="shared-team", name="Shared", workspace="ws-1"),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/shared/"),
            ],
            departments=[
                DepartmentConfig(
                    department_id="dept-a",
                    name="Dept A",
                    teams=["shared-team"],
                ),
                DepartmentConfig(
                    department_id="dept-b",
                    name="Dept B",
                    teams=["shared-team"],
                ),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("shared-team" in e for e in errors)
        assert any("multiple departments" in e.lower() for e in errors)

    def test_department_head_must_be_in_department_teams(self):
        """Department head_agent_id must be an agent in one of the department's teams."""
        org = OrgDefinition(
            org_id="test",
            name="Test",
            agents=[
                AgentConfig(
                    id="agent-outside",
                    name="Outside Agent",
                    role="Role",
                    constraint_envelope="env-1",
                ),
                AgentConfig(
                    id="agent-inside",
                    name="Inside Agent",
                    role="Role",
                    constraint_envelope="env-1",
                ),
            ],
            envelopes=[_make_envelope("env-1")],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    agents=["agent-inside"],
                ),
                TeamConfig(
                    id="team-2",
                    name="Team 2",
                    workspace="ws-2",
                    agents=["agent-outside"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/t1/"),
                WorkspaceConfig(id="ws-2", path="workspaces/t2/"),
            ],
            departments=[
                DepartmentConfig(
                    department_id="dept-1",
                    name="Dept",
                    teams=["team-1"],
                    head_agent_id="agent-outside",  # NOT in team-1
                ),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("agent-outside" in e for e in errors)
        assert any("head" in e.lower() for e in errors)

    def test_department_head_in_department_team_passes(self):
        """Department head in one of the department's teams should pass validation."""
        org = OrgDefinition(
            org_id="test",
            name="Test",
            agents=[
                AgentConfig(
                    id="agent-inside",
                    name="Inside Agent",
                    role="Role",
                    constraint_envelope="env-1",
                ),
            ],
            envelopes=[_make_envelope("env-1")],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    agents=["agent-inside"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/t1/"),
            ],
            departments=[
                DepartmentConfig(
                    department_id="dept-1",
                    name="Dept",
                    teams=["team-1"],
                    head_agent_id="agent-inside",
                ),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is True, f"Validation should pass but got errors: {errors}"


class TestDepartmentValidationDetailed:
    """Task 6021: validate_org_detailed() for departments."""

    def test_duplicate_dept_ids_in_detailed_validation(self):
        """validate_org_detailed() must report duplicate department IDs with severity ERROR."""
        org = OrgDefinition(
            org_id="test",
            name="Test",
            departments=[
                DepartmentConfig(department_id="dup", name="A"),
                DepartmentConfig(department_id="dup", name="B"),
            ],
        )
        results = org.validate_org_detailed()
        dept_errors = [r for r in results if r.code == "ERR_DUPLICATE_DEPARTMENT" and r.is_error]
        assert len(dept_errors) >= 1

    def test_team_in_multiple_depts_in_detailed_validation(self):
        """validate_org_detailed() must report team in multiple departments."""
        org = OrgDefinition(
            org_id="test",
            name="Test",
            teams=[
                TeamConfig(id="shared-team", name="Shared", workspace="ws-1"),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/shared/"),
            ],
            departments=[
                DepartmentConfig(department_id="dept-a", name="A", teams=["shared-team"]),
                DepartmentConfig(department_id="dept-b", name="B", teams=["shared-team"]),
            ],
        )
        results = org.validate_org_detailed()
        multi_dept_errors = [
            r for r in results if r.code == "TEAM_IN_MULTIPLE_DEPARTMENTS" and r.is_error
        ]
        assert len(multi_dept_errors) >= 1

    def test_dept_references_missing_team_in_detailed(self):
        """validate_org_detailed() must report department referencing missing team."""
        org = OrgDefinition(
            org_id="test",
            name="Test",
            departments=[
                DepartmentConfig(department_id="dept-1", name="D", teams=["ghost-team"]),
            ],
        )
        results = org.validate_org_detailed()
        ref_errors = [r for r in results if r.code == "ERR_DANGLING_DEPT_TEAM_REF" and r.is_error]
        assert len(ref_errors) >= 1

    def test_dept_head_not_in_teams_in_detailed(self):
        """validate_org_detailed() must report department head not in department's teams."""
        org = OrgDefinition(
            org_id="test",
            name="Test",
            agents=[
                AgentConfig(id="outsider", name="Out", role="R", constraint_envelope="e"),
                AgentConfig(id="insider", name="In", role="R", constraint_envelope="e"),
            ],
            envelopes=[_make_envelope("e")],
            teams=[
                TeamConfig(id="t1", name="T1", workspace="ws", agents=["insider"]),
                TeamConfig(id="t2", name="T2", workspace="ws2", agents=["outsider"]),
            ],
            workspaces=[
                WorkspaceConfig(id="ws", path="workspaces/t1/"),
                WorkspaceConfig(id="ws2", path="workspaces/t2/"),
            ],
            departments=[
                DepartmentConfig(
                    department_id="d1",
                    name="D1",
                    teams=["t1"],
                    head_agent_id="outsider",
                ),
            ],
        )
        results = org.validate_org_detailed()
        head_errors = [r for r in results if r.code == "ERR_DEPT_HEAD_NOT_IN_TEAMS" and r.is_error]
        assert len(head_errors) >= 1


# ===========================================================================
# Task 6022: 3-Level Monotonic Tightening
# ===========================================================================


class TestMonotonicTighteningOrgToDepartment:
    """Task 6022: Department envelopes must be tighter than or equal to org envelope."""

    def test_dept_tighter_than_org_passes(self):
        """Department envelope tighter than org envelope should pass validation."""
        org = _make_org_with_departments()
        results = org.validate_org_detailed()
        tightening_errors = [r for r in results if "DEPT_ORG_TIGHTENING" in r.code]
        assert (
            len(tightening_errors) == 0
        ), f"Expected no tightening errors, got: {tightening_errors}"

    def test_dept_financial_exceeds_org_fails(self):
        """Department spending limit higher than org must fail."""
        org_env = _make_envelope("org-envelope", max_spend=1000.0)
        dept_env = _make_envelope(
            "dept-envelope",
            max_spend=5000.0,  # Exceeds org!
        )
        org = _make_org_with_departments(org_envelope=org_env, dept_envelope=dept_env)
        results = org.validate_org_detailed()
        financial_errors = [
            r
            for r in results
            if "DEPT_ORG_TIGHTENING" in r.code and "financial" in r.message.lower()
        ]
        assert len(financial_errors) >= 1

    def test_dept_operational_exceeds_org_fails(self):
        """Department with actions not in org must fail."""
        org_env = _make_envelope(
            "org-envelope",
            allowed_actions=["read", "write"],
        )
        dept_env = _make_envelope(
            "dept-envelope",
            allowed_actions=["read", "write", "deploy"],  # deploy not in org
        )
        org = _make_org_with_departments(org_envelope=org_env, dept_envelope=dept_env)
        results = org.validate_org_detailed()
        op_errors = [
            r for r in results if "DEPT_ORG_TIGHTENING" in r.code and "action" in r.message.lower()
        ]
        assert len(op_errors) >= 1

    def test_dept_communication_looser_than_org_fails(self):
        """Department allowing external communication when org is internal-only must fail."""
        org_env = _make_envelope("org-envelope", internal_only=True)
        dept_env = _make_envelope("dept-envelope", internal_only=False)
        org = _make_org_with_departments(org_envelope=org_env, dept_envelope=dept_env)
        results = org.validate_org_detailed()
        comm_errors = [
            r
            for r in results
            if "DEPT_ORG_TIGHTENING" in r.code and "communication" in r.message.lower()
        ]
        assert len(comm_errors) >= 1


class TestMonotonicTighteningDeptToTeam:
    """Task 6022: Team envelopes must be tighter than or equal to department envelope."""

    def test_team_tighter_than_dept_passes(self):
        """Team envelope tighter than department envelope should pass validation."""
        org = _make_org_with_departments()
        results = org.validate_org_detailed()
        tightening_errors = [r for r in results if "TEAM_DEPT_TIGHTENING" in r.code]
        assert (
            len(tightening_errors) == 0
        ), f"Expected no tightening errors, got: {tightening_errors}"

    def test_team_financial_exceeds_dept_fails(self):
        """Team spending limit higher than department must fail."""
        dept_env = _make_envelope("dept-envelope", max_spend=1000.0)
        team_env = _make_envelope("team-envelope", max_spend=5000.0)  # Exceeds dept
        org = _make_org_with_departments(dept_envelope=dept_env, team_envelope=team_env)
        results = org.validate_org_detailed()
        financial_errors = [
            r
            for r in results
            if "TEAM_DEPT_TIGHTENING" in r.code and "financial" in r.message.lower()
        ]
        assert len(financial_errors) >= 1

    def test_team_operational_exceeds_dept_fails(self):
        """Team with actions not in department must fail."""
        dept_env = _make_envelope("dept-envelope", allowed_actions=["read", "write"])
        team_env = _make_envelope("team-envelope", allowed_actions=["read", "write", "deploy"])
        org = _make_org_with_departments(dept_envelope=dept_env, team_envelope=team_env)
        results = org.validate_org_detailed()
        op_errors = [
            r for r in results if "TEAM_DEPT_TIGHTENING" in r.code and "action" in r.message.lower()
        ]
        assert len(op_errors) >= 1

    def test_team_rate_limit_exceeds_dept_fails(self):
        """Team rate limit higher than department rate limit must fail."""
        dept_env = _make_envelope("dept-envelope", max_actions_per_day=50)
        team_env = _make_envelope("team-envelope", max_actions_per_day=100)
        org = _make_org_with_departments(dept_envelope=dept_env, team_envelope=team_env)
        results = org.validate_org_detailed()
        rate_errors = [
            r for r in results if "TEAM_DEPT_TIGHTENING" in r.code and "rate" in r.message.lower()
        ]
        assert len(rate_errors) >= 1


class TestMonotonicTighteningFullChain:
    """Task 6022: Full chain org -> dept -> team -> agent must be monotonically tighter."""

    def test_valid_full_chain_passes(self):
        """Valid org -> dept -> team -> agent tightening should produce no tightening errors."""
        org = _make_org_with_departments()
        results = org.validate_org_detailed()
        tightening_errors = [r for r in results if "TIGHTENING" in r.code and r.is_error]
        assert (
            len(tightening_errors) == 0
        ), f"Expected no tightening errors, got: {tightening_errors}"

    def test_agent_looser_than_team_still_caught(self):
        """Agent envelope looser than team envelope is caught by existing team-level checks."""
        # Existing monotonic tightening logic checks team lead -> member.
        # This test verifies that our 3-level chain does not break existing checks.
        org = _make_org_with_departments(
            team_envelope=_make_envelope("team-envelope", max_spend=100.0),
            agent_envelope=_make_envelope("agent-envelope", max_spend=500.0),
        )
        results = org.validate_org_detailed()
        # The existing lead-member check should still catch agent > team
        financial_errors = [r for r in results if "FINANCIAL_TIGHTENING" in r.code and r.is_error]
        assert len(financial_errors) >= 1


class TestBackwardCompatibilityNoDepartments:
    """Task 6022: Orgs without departments must still validate exactly as before."""

    def test_org_without_departments_validates(self):
        """An org without any departments should validate like before."""
        org = OrgDefinition(
            org_id="legacy-org",
            name="Legacy Org",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                ),
            ],
            envelopes=[_make_envelope("env-1")],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    agents=["agent-1"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/t1/"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is True, f"Legacy org validation failed: {errors}"

    def test_org_without_departments_no_department_errors(self):
        """An org without departments should produce no department-related errors."""
        org = OrgDefinition(
            org_id="legacy-org",
            name="Legacy Org",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                ),
            ],
            envelopes=[_make_envelope("env-1")],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    agents=["agent-1"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/t1/"),
            ],
        )
        results = org.validate_org_detailed()
        dept_errors = [r for r in results if "DEPT" in r.code or "DEPARTMENT" in r.code]
        assert len(dept_errors) == 0

    def test_teams_not_in_any_department_skip_dept_tightening(self):
        """Teams not in any department should not be checked against department envelopes."""
        org_env = _make_envelope("org-env", max_spend=10000.0)
        team_env = _make_envelope("team-env", max_spend=5000.0)
        org = OrgDefinition(
            org_id="test",
            name="Test",
            org_envelope=org_env,
            agents=[
                AgentConfig(
                    id="a1",
                    name="A",
                    role="R",
                    constraint_envelope="team-env",
                ),
            ],
            envelopes=[org_env, team_env],
            teams=[
                TeamConfig(
                    id="free-team",
                    name="Free Team",
                    workspace="ws-1",
                    agents=["a1"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/free/"),
            ],
            departments=[],  # No departments
        )
        results = org.validate_org_detailed()
        dept_tightening = [r for r in results if "TEAM_DEPT_TIGHTENING" in r.code]
        assert len(dept_tightening) == 0

    def test_from_config_preserves_departments(self):
        """from_config() should still work (no departments in PactConfig)."""
        from pact_platform.build.config.schema import GenesisConfig, PactConfig

        platform = PactConfig(
            name="Round Trip",
            genesis=GenesisConfig(authority="test.org", authority_name="Test"),
            constraint_envelopes=[_make_envelope("env-1")],
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                ),
            ],
            teams=[
                TeamConfig(id="team-1", name="Team", workspace="ws-1", agents=["agent-1"]),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/test/"),
            ],
        )
        org = OrgBuilder.from_config(platform)
        assert isinstance(org, OrgDefinition)
        assert org.departments == []


# ===========================================================================
# Task 6023: Template Department Field
# ===========================================================================


class TestTemplateDepartmentField:
    """Task 6023: TeamTemplate has optional department field."""

    def test_team_template_has_department_field(self):
        """TeamTemplate must have an optional department field."""
        from pact_platform.build.templates.registry import TeamTemplate

        tpl = TeamTemplate(
            name="test-template",
            description="Test template",
            agents=[],
            envelopes=[],
            team=TeamConfig(id="t1", name="T", workspace="ws-1"),
            department="engineering",
        )
        assert tpl.department == "engineering"

    def test_team_template_department_defaults_to_none(self):
        """TeamTemplate department field defaults to None."""
        from pact_platform.build.templates.registry import TeamTemplate

        tpl = TeamTemplate(
            name="test-template",
            agents=[],
            envelopes=[],
            team=TeamConfig(id="t1", name="T", workspace="ws-1"),
        )
        assert tpl.department is None

    def test_existing_templates_still_work(self):
        """Existing built-in templates (media, governance, etc.) should still load."""
        from pact_platform.build.templates.registry import TemplateRegistry

        registry = TemplateRegistry()
        templates = registry.list()
        assert "media" in templates
        assert "governance" in templates
        for name in templates:
            tpl = registry.get(name)
            assert tpl is not None


# ===========================================================================
# Task 6024: Comprehensive Integration Tests
# ===========================================================================


class TestDepartmentIntegration:
    """Task 6024: Full integration tests for department layer."""

    def test_multi_department_org_validates(self):
        """An org with multiple departments, each with teams, should validate."""
        org_env = _make_envelope(
            "org-env",
            max_spend=50000.0,
            allowed_actions=["read", "write", "deploy", "admin", "review", "schedule"],
            max_actions_per_day=1000,
            internal_only=False,
            active_hours_start="00:00",
            active_hours_end="23:59",
            read_paths=["/*"],
            write_paths=["/*"],
        )
        eng_dept_env = _make_envelope(
            "eng-dept-env",
            max_spend=20000.0,
            allowed_actions=["read", "write", "deploy"],
            max_actions_per_day=500,
            internal_only=True,
            active_hours_start="06:00",
            active_hours_end="22:00",
        )
        ops_dept_env = _make_envelope(
            "ops-dept-env",
            max_spend=15000.0,
            allowed_actions=["read", "write", "admin"],
            max_actions_per_day=300,
            internal_only=True,
            active_hours_start="06:00",
            active_hours_end="22:00",
        )
        team1_env = _make_envelope(
            "team1-env",
            max_spend=5000.0,
            allowed_actions=["read", "write"],
            max_actions_per_day=100,
            internal_only=True,
            active_hours_start="08:00",
            active_hours_end="20:00",
        )
        team2_env = _make_envelope(
            "team2-env",
            max_spend=3000.0,
            allowed_actions=["read", "admin"],
            max_actions_per_day=100,
            internal_only=True,
            active_hours_start="08:00",
            active_hours_end="20:00",
        )

        org = OrgDefinition(
            org_id="multi-dept-org",
            name="Multi-Department Org",
            org_envelope=org_env,
            agents=[
                AgentConfig(
                    id="eng-lead",
                    name="Eng Lead",
                    role="Engineering Lead",
                    constraint_envelope="team1-env",
                ),
                AgentConfig(
                    id="eng-dev",
                    name="Developer",
                    role="Developer",
                    constraint_envelope="team1-env",
                ),
                AgentConfig(
                    id="ops-lead",
                    name="Ops Lead",
                    role="Operations Lead",
                    constraint_envelope="team2-env",
                ),
            ],
            envelopes=[org_env, eng_dept_env, ops_dept_env, team1_env, team2_env],
            teams=[
                TeamConfig(
                    id="eng-team",
                    name="Engineering Team",
                    workspace="ws-eng",
                    team_lead="eng-lead",
                    agents=["eng-lead", "eng-dev"],
                ),
                TeamConfig(
                    id="ops-team",
                    name="Operations Team",
                    workspace="ws-ops",
                    team_lead="ops-lead",
                    agents=["ops-lead"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-eng", path="workspaces/eng/"),
                WorkspaceConfig(id="ws-ops", path="workspaces/ops/"),
            ],
            departments=[
                DepartmentConfig(
                    department_id="eng-dept",
                    name="Engineering",
                    teams=["eng-team"],
                    head_agent_id="eng-lead",
                    envelope=eng_dept_env,
                ),
                DepartmentConfig(
                    department_id="ops-dept",
                    name="Operations",
                    teams=["ops-team"],
                    head_agent_id="ops-lead",
                    envelope=ops_dept_env,
                ),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is True, f"Multi-department org failed validation: {errors}"

    def test_tightening_chain_violation_at_every_level(self):
        """Violations at every level of the chain are all reported."""
        org_env = _make_envelope("org-env", max_spend=1000.0)
        # Dept exceeds org
        dept_env = _make_envelope("dept-env", max_spend=5000.0)
        # Team exceeds dept (but since dept already exceeds org, both should be caught)
        team_env = _make_envelope("team-env", max_spend=10000.0)
        agent_env = _make_envelope("agent-env", max_spend=500.0)

        org = OrgDefinition(
            org_id="test",
            name="Test",
            org_envelope=org_env,
            agents=[
                AgentConfig(id="lead", name="L", role="R", constraint_envelope="team-env"),
                AgentConfig(id="worker", name="W", role="R", constraint_envelope="agent-env"),
            ],
            envelopes=[org_env, dept_env, team_env, agent_env],
            teams=[
                TeamConfig(
                    id="t1",
                    name="T",
                    workspace="ws",
                    team_lead="lead",
                    agents=["lead", "worker"],
                ),
            ],
            workspaces=[WorkspaceConfig(id="ws", path="workspaces/t/")],
            departments=[
                DepartmentConfig(
                    department_id="d1",
                    name="D",
                    teams=["t1"],
                    head_agent_id="lead",
                    envelope=dept_env,
                ),
            ],
        )
        results = org.validate_org_detailed()
        # Should have at least 2 tightening violations:
        # 1) dept exceeds org  2) team exceeds dept
        tightening_errors = [r for r in results if "TIGHTENING" in r.code and r.is_error]
        assert len(tightening_errors) >= 2, (
            f"Expected at least 2 tightening errors, got {len(tightening_errors)}: "
            f"{[r.message for r in tightening_errors]}"
        )

    def test_department_no_envelope_skips_dept_tightening(self):
        """Department without an envelope skips dept-level tightening checks."""
        org_env = _make_envelope("org-env", max_spend=10000.0)
        team_env = _make_envelope("team-env", max_spend=5000.0)

        org = OrgDefinition(
            org_id="test",
            name="Test",
            org_envelope=org_env,
            agents=[
                AgentConfig(id="a1", name="A", role="R", constraint_envelope="team-env"),
            ],
            envelopes=[org_env, team_env],
            teams=[
                TeamConfig(id="t1", name="T", workspace="ws", agents=["a1"]),
            ],
            workspaces=[WorkspaceConfig(id="ws", path="workspaces/t/")],
            departments=[
                DepartmentConfig(
                    department_id="d1",
                    name="D",
                    teams=["t1"],
                    envelope=None,  # No department envelope
                ),
            ],
        )
        results = org.validate_org_detailed()
        dept_tightening = [r for r in results if "DEPT" in r.code and "TIGHTENING" in r.code]
        assert len(dept_tightening) == 0
