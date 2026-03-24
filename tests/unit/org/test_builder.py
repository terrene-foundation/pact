# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Organization Builder (Tasks 701-703, M19 5029-5035).

Validates that OrgDefinition, OrgBuilder, and OrgTemplate correctly create,
validate, and manage organization definitions with proper constraint enforcement.

M19 adds deep semantic validation: capability-envelope alignment, monotonic
constraint tightening, team lead superset checks, verification gradient coverage,
temporal/data path consistency, multi-team validation, and severity levels.
"""

import pytest

from pact_platform.build.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    PactConfig,
    TeamConfig,
    TemporalConstraintConfig,
    VerificationGradientConfig,
    VerificationLevel,
    WorkspaceConfig,
)
from pact_platform.build.org.builder import (
    OrgBuilder,
    OrgDefinition,
    OrgTemplate,
    ValidationResult,
    ValidationSeverity,
)


class TestOrgDefinition:
    """OrgDefinition model correctness."""

    def test_minimal_org_definition(self):
        """An org with just an id and name is valid."""
        org = OrgDefinition(org_id="test-org", name="Test Organization")
        assert org.org_id == "test-org"
        assert org.name == "Test Organization"
        assert org.teams == []
        assert org.agents == []
        assert org.envelopes == []
        assert org.workspaces == []

    def test_org_definition_with_authority(self):
        org = OrgDefinition(
            org_id="terrene",
            name="Terrene Foundation",
            authority_id="terrene.foundation",
        )
        assert org.authority_id == "terrene.foundation"


class TestOrgBuilder:
    """Test 701: OrgBuilder creates valid organization definitions."""

    def test_builder_creates_valid_org(self):
        """Building a fully-wired org should produce a valid OrgDefinition."""
        org = (
            OrgBuilder("test-org", "Test Organization")
            .add_workspace(WorkspaceConfig(id="ws-1", path="workspaces/test/"))
            .add_envelope(ConstraintEnvelopeConfig(id="env-1"))
            .add_agent(
                AgentConfig(
                    id="agent-1",
                    name="Agent One",
                    role="Testing",
                    constraint_envelope="env-1",
                )
            )
            .add_team(
                TeamConfig(
                    id="team-1",
                    name="Team One",
                    workspace="ws-1",
                    agents=["agent-1"],
                )
            )
            .build()
        )
        assert isinstance(org, OrgDefinition)
        assert org.org_id == "test-org"
        assert len(org.agents) == 1
        assert len(org.teams) == 1
        assert len(org.envelopes) == 1
        assert len(org.workspaces) == 1

    def test_builder_returns_self_for_chaining(self):
        """Each add_* method must return the builder for fluent chaining."""
        builder = OrgBuilder("chain-test", "Chain Test")
        result = builder.add_workspace(WorkspaceConfig(id="ws", path="workspaces/ws/"))
        assert result is builder
        result = builder.add_envelope(ConstraintEnvelopeConfig(id="env"))
        assert result is builder
        result = builder.add_agent(
            AgentConfig(id="a", name="A", role="R", constraint_envelope="env")
        )
        assert result is builder
        result = builder.add_team(TeamConfig(id="t", name="T", workspace="ws"))
        assert result is builder


class TestOrgValidationMissingEnvelope:
    """Test 702: Validation catches missing envelope references."""

    def test_validation_catches_missing_envelope_reference(self):
        """An agent referencing a non-existent envelope must fail validation."""
        org = OrgDefinition(
            org_id="bad-org",
            name="Bad Org",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="nonexistent-envelope",
                )
            ],
            envelopes=[],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any(
            "nonexistent-envelope" in e for e in errors
        ), f"Expected error about 'nonexistent-envelope', got: {errors}"

    def test_validation_catches_missing_workspace_reference(self):
        """A team referencing a non-existent workspace must fail validation."""
        org = OrgDefinition(
            org_id="bad-org",
            name="Bad Org",
            teams=[TeamConfig(id="team-1", name="Team", workspace="nonexistent-ws")],
            workspaces=[],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any(
            "nonexistent-ws" in e for e in errors
        ), f"Expected error about 'nonexistent-ws', got: {errors}"


class TestOrgValidationDuplicateIDs:
    """Test 703: Validation catches duplicate IDs."""

    def test_validation_catches_duplicate_agent_ids(self):
        org = OrgDefinition(
            org_id="dup-org",
            name="Dup Org",
            agents=[
                AgentConfig(id="dup", name="A", role="R", constraint_envelope="e"),
                AgentConfig(id="dup", name="B", role="R", constraint_envelope="e"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("dup" in e.lower() for e in errors)

    def test_validation_catches_duplicate_team_ids(self):
        org = OrgDefinition(
            org_id="dup-org",
            name="Dup Org",
            teams=[
                TeamConfig(id="dup", name="A", workspace="ws"),
                TeamConfig(id="dup", name="B", workspace="ws"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("dup" in e.lower() for e in errors)

    def test_validation_catches_duplicate_envelope_ids(self):
        org = OrgDefinition(
            org_id="dup-org",
            name="Dup Org",
            envelopes=[
                ConstraintEnvelopeConfig(id="dup"),
                ConstraintEnvelopeConfig(id="dup"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("dup" in e.lower() for e in errors)

    def test_validation_catches_duplicate_workspace_ids(self):
        org = OrgDefinition(
            org_id="dup-org",
            name="Dup Org",
            workspaces=[
                WorkspaceConfig(id="dup", path="workspaces/a/"),
                WorkspaceConfig(id="dup", path="workspaces/b/"),
            ],
        )
        valid, errors = org.validate_org()
        assert valid is False
        assert any("dup" in e.lower() for e in errors)


class TestOrgFromConfigRoundTrip:
    """Test 704: from_config round-trips correctly."""

    def test_from_config_round_trips(self):
        """Creating an OrgDefinition from PactConfig should preserve all data."""
        platform = PactConfig(
            name="Round Trip Org",
            genesis=GenesisConfig(
                authority="test.org",
                authority_name="Test Organization",
            ),
            constraint_envelopes=[
                ConstraintEnvelopeConfig(id="env-1"),
            ],
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent One",
                    role="Testing",
                    constraint_envelope="env-1",
                ),
            ],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team One",
                    workspace="ws-1",
                    agents=["agent-1"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/test/"),
            ],
        )
        org = OrgBuilder.from_config(platform)
        assert isinstance(org, OrgDefinition)
        assert org.name == "Round Trip Org"
        assert org.authority_id == "test.org"
        assert len(org.agents) == 1
        assert len(org.teams) == 1
        assert len(org.envelopes) == 1
        assert len(org.workspaces) == 1
        assert org.agents[0].id == "agent-1"
        assert org.teams[0].id == "team-1"
        assert org.envelopes[0].id == "env-1"
        assert org.workspaces[0].id == "ws-1"


class TestOrgTemplateMinimal:
    """Test 705: Minimal template is a valid org."""

    def test_minimal_template_is_valid(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert isinstance(org, OrgDefinition)
        valid, errors = org.validate_org()
        assert valid is True, f"Minimal template invalid: {errors}"

    def test_minimal_template_has_name(self):
        org = OrgTemplate.minimal_template("My Org")
        assert org.name == "My Org"

    def test_minimal_template_has_at_least_one_agent(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert len(org.agents) >= 1

    def test_minimal_template_has_at_least_one_team(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert len(org.teams) >= 1

    def test_minimal_template_has_at_least_one_workspace(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert len(org.workspaces) >= 1

    def test_minimal_template_has_at_least_one_envelope(self):
        org = OrgTemplate.minimal_template("Minimal Org")
        assert len(org.envelopes) >= 1


class TestOrgGetTeamAgents:
    """Test 707: get_team_agents returns the correct subset of agents."""

    def test_get_team_agents_returns_correct_subset(self):
        org = OrgDefinition(
            org_id="test-org",
            name="Test Org",
            agents=[
                AgentConfig(id="a-1", name="A1", role="R", constraint_envelope="e"),
                AgentConfig(id="a-2", name="A2", role="R", constraint_envelope="e"),
                AgentConfig(id="a-3", name="A3", role="R", constraint_envelope="e"),
            ],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team One",
                    workspace="ws",
                    agents=["a-1", "a-2"],
                ),
                TeamConfig(
                    id="team-2",
                    name="Team Two",
                    workspace="ws",
                    agents=["a-3"],
                ),
            ],
        )
        team1_agents = org.get_team_agents("team-1")
        assert len(team1_agents) == 2
        agent_ids = {a.id for a in team1_agents}
        assert agent_ids == {"a-1", "a-2"}

    def test_get_team_agents_unknown_team_raises(self):
        org = OrgDefinition(org_id="test-org", name="Test Org")
        with pytest.raises(ValueError, match="not found"):
            org.get_team_agents("nonexistent-team")

    def test_get_team_agents_empty_team(self):
        org = OrgDefinition(
            org_id="test-org",
            name="Test Org",
            teams=[
                TeamConfig(id="empty-team", name="Empty", workspace="ws", agents=[]),
            ],
        )
        agents = org.get_team_agents("empty-team")
        assert agents == []


class TestOrgBuildValidation:
    """build() must validate and raise on invalid configurations."""

    def test_build_raises_on_missing_envelope(self):
        """OrgBuilder.build() must raise ValueError when an agent references a missing envelope."""
        with pytest.raises(ValueError, match="nonexistent-envelope"):
            (
                OrgBuilder("bad-org", "Bad Org")
                .add_agent(
                    AgentConfig(
                        id="agent-1",
                        name="Agent",
                        role="Role",
                        constraint_envelope="nonexistent-envelope",
                    )
                )
                .build()
            )

    def test_build_raises_on_missing_workspace(self):
        """OrgBuilder.build() must raise ValueError when a team references a missing workspace."""
        with pytest.raises(ValueError, match="nonexistent-ws"):
            (
                OrgBuilder("bad-org", "Bad Org")
                .add_team(TeamConfig(id="team-1", name="Team", workspace="nonexistent-ws"))
                .build()
            )


# ---------------------------------------------------------------------------
# M19 Validation Hardening Tests (Tasks 5029-5035)
# ---------------------------------------------------------------------------


class TestValidationResultModel:
    """Task 5035: ValidationResult dataclass and severity levels."""

    def test_validation_result_has_severity_message_code(self):
        """ValidationResult must have severity, message, and code fields."""
        result = ValidationResult(
            severity=ValidationSeverity.ERROR,
            message="Something went wrong",
            code="ERR_TEST",
        )
        assert result.severity == ValidationSeverity.ERROR
        assert result.message == "Something went wrong"
        assert result.code == "ERR_TEST"

    def test_validation_severity_has_error_and_warning(self):
        """ValidationSeverity must have at least ERROR and WARNING levels."""
        assert hasattr(ValidationSeverity, "ERROR")
        assert hasattr(ValidationSeverity, "WARNING")
        assert ValidationSeverity.ERROR != ValidationSeverity.WARNING

    def test_validation_result_is_error_helper(self):
        """ValidationResult must have an is_error property."""
        error = ValidationResult(
            severity=ValidationSeverity.ERROR,
            message="bad",
            code="E001",
        )
        warning = ValidationResult(
            severity=ValidationSeverity.WARNING,
            message="careful",
            code="W001",
        )
        assert error.is_error is True
        assert warning.is_error is False


class TestValidateOrgReturnsValidationResults:
    """Task 5035: validate_org() returns list[ValidationResult] alongside legacy tuple."""

    def test_validate_org_detailed_returns_validation_results(self):
        """validate_org_detailed() must return list[ValidationResult]."""
        org = OrgDefinition(org_id="ok-org", name="OK Org")
        results = org.validate_org_detailed()
        assert isinstance(results, list)
        # An empty org is valid — no errors
        assert all(isinstance(r, ValidationResult) for r in results)

    def test_validate_org_detailed_errors_have_codes(self):
        """Each ValidationResult from validate_org_detailed() must have a non-empty code."""
        org = OrgDefinition(
            org_id="bad-org",
            name="Bad Org",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="nonexistent-envelope",
                )
            ],
        )
        results = org.validate_org_detailed()
        errors = [r for r in results if r.is_error]
        assert len(errors) >= 1
        for err in errors:
            assert err.code, f"Error missing code: {err}"

    def test_validate_org_legacy_still_works(self):
        """validate_org() must still return (bool, list[str]) for backward compat."""
        org = OrgDefinition(org_id="ok-org", name="OK Org")
        result = org.validate_org()
        assert isinstance(result, tuple)
        assert len(result) == 2
        valid, errors = result
        assert valid is True
        assert isinstance(errors, list)

    def test_build_allows_warnings_but_blocks_errors(self):
        """build() must succeed when only WARNINGs exist, fail when ERRORs exist."""
        # This org is structurally valid (no errors) but an agent has a capability
        # not covered by any gradient rule, producing a WARNING.
        org_with_warning = (
            OrgBuilder("warn-org", "Warning Org")
            .add_workspace(WorkspaceConfig(id="ws-1", path="workspaces/test/"))
            .add_envelope(
                ConstraintEnvelopeConfig(
                    id="env-1",
                    operational=OperationalConstraintConfig(
                        allowed_actions=["read_data", "write_data"],
                    ),
                )
            )
            .add_agent(
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                    capabilities=["read_data", "write_data"],
                    verification_gradient=VerificationGradientConfig(
                        rules=[
                            GradientRuleConfig(
                                pattern="read_*",
                                level=VerificationLevel.AUTO_APPROVED,
                            ),
                            # write_data is NOT covered by any rule -> WARNING
                        ],
                        default_level=VerificationLevel.HELD,
                    ),
                )
            )
            .add_team(
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    agents=["agent-1"],
                )
            )
            .build()  # Must succeed — WARNINGs do not block build
        )
        assert isinstance(org_with_warning, OrgDefinition)


class TestCapabilityEnvelopeAlignment:
    """Task 5029: Agent capabilities must be subset of envelope's allowed_actions."""

    def test_aligned_capabilities_pass(self):
        """Agent capabilities that are a subset of allowed_actions should pass."""
        org = OrgDefinition(
            org_id="cap-test",
            name="Cap Test",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                    capabilities=["read_data", "write_data"],
                ),
            ],
            envelopes=[
                ConstraintEnvelopeConfig(
                    id="env-1",
                    operational=OperationalConstraintConfig(
                        allowed_actions=["read_data", "write_data", "delete_data"],
                    ),
                ),
            ],
        )
        results = org.validate_org_detailed()
        cap_errors = [r for r in results if r.code == "CAP_NOT_IN_ENVELOPE" and r.is_error]
        assert len(cap_errors) == 0

    def test_capability_outside_envelope_is_error(self):
        """Agent capability not in envelope's allowed_actions must produce an ERROR."""
        org = OrgDefinition(
            org_id="cap-test",
            name="Cap Test",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                    capabilities=["read_data", "write_data", "launch_missile"],
                ),
            ],
            envelopes=[
                ConstraintEnvelopeConfig(
                    id="env-1",
                    operational=OperationalConstraintConfig(
                        allowed_actions=["read_data", "write_data"],
                    ),
                ),
            ],
        )
        results = org.validate_org_detailed()
        cap_errors = [r for r in results if r.code == "CAP_NOT_IN_ENVELOPE" and r.is_error]
        assert len(cap_errors) >= 1
        assert "launch_missile" in cap_errors[0].message
        assert "agent-1" in cap_errors[0].message

    def test_empty_allowed_actions_skips_check(self):
        """If envelope has empty allowed_actions, skip capability alignment check."""
        org = OrgDefinition(
            org_id="cap-test",
            name="Cap Test",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                    capabilities=["anything"],
                ),
            ],
            envelopes=[
                ConstraintEnvelopeConfig(
                    id="env-1",
                    operational=OperationalConstraintConfig(
                        allowed_actions=[],
                    ),
                ),
            ],
        )
        results = org.validate_org_detailed()
        cap_errors = [r for r in results if r.code == "CAP_NOT_IN_ENVELOPE"]
        assert len(cap_errors) == 0

    def test_empty_capabilities_skips_check(self):
        """If agent has no capabilities, skip capability alignment check."""
        org = OrgDefinition(
            org_id="cap-test",
            name="Cap Test",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                    capabilities=[],
                ),
            ],
            envelopes=[
                ConstraintEnvelopeConfig(
                    id="env-1",
                    operational=OperationalConstraintConfig(
                        allowed_actions=["read_data"],
                    ),
                ),
            ],
        )
        results = org.validate_org_detailed()
        cap_errors = [r for r in results if r.code == "CAP_NOT_IN_ENVELOPE"]
        assert len(cap_errors) == 0


class TestMonotonicConstraintTightening:
    """Task 5030: Sub-agent envelopes must be tighter than team lead across all 5 dimensions."""

    def _make_org_with_lead_and_sub(
        self,
        lead_envelope: ConstraintEnvelopeConfig,
        sub_envelope: ConstraintEnvelopeConfig,
    ) -> OrgDefinition:
        """Helper to create a two-agent org with lead and subordinate."""
        return OrgDefinition(
            org_id="mono-test",
            name="Monotonic Test",
            agents=[
                AgentConfig(
                    id="lead",
                    name="Lead",
                    role="Lead",
                    constraint_envelope=lead_envelope.id,
                ),
                AgentConfig(
                    id="sub",
                    name="Sub",
                    role="Sub",
                    constraint_envelope=sub_envelope.id,
                ),
            ],
            envelopes=[lead_envelope, sub_envelope],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    team_lead="lead",
                    agents=["lead", "sub"],
                ),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/test/"),
            ],
        )

    def test_tighter_sub_envelope_passes(self):
        """Sub-agent with tighter constraints than lead should pass."""
        lead_env = ConstraintEnvelopeConfig(
            id="lead-env",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write", "delete"],
                max_actions_per_day=200,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="06:00",
                active_hours_end="22:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/*", "analytics/*"],
                write_paths=["workspaces/*"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
            ),
        )
        sub_env = ConstraintEnvelopeConfig(
            id="sub-env",
            financial=FinancialConstraintConfig(max_spend_usd=50.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
                max_actions_per_day=100,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="20:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/*"],
                write_paths=["workspaces/drafts/*"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
            ),
        )
        org = self._make_org_with_lead_and_sub(lead_env, sub_env)
        results = org.validate_org_detailed()
        tightening_errors = [r for r in results if "TIGHTENING" in r.code and r.is_error]
        assert len(tightening_errors) == 0

    def test_sub_higher_financial_limit_is_error(self):
        """Sub-agent with higher max_spend_usd than lead must produce ERROR."""
        lead_env = ConstraintEnvelopeConfig(
            id="lead-env",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        sub_env = ConstraintEnvelopeConfig(
            id="sub-env",
            financial=FinancialConstraintConfig(max_spend_usd=200.0),
        )
        org = self._make_org_with_lead_and_sub(lead_env, sub_env)
        results = org.validate_org_detailed()
        fin_errors = [r for r in results if r.code == "FINANCIAL_TIGHTENING" and r.is_error]
        assert len(fin_errors) >= 1
        assert "sub" in fin_errors[0].message.lower() or "sub-env" in fin_errors[0].message

    def test_sub_more_actions_than_lead_is_error(self):
        """Sub-agent with allowed_actions not in lead's actions must produce ERROR."""
        lead_env = ConstraintEnvelopeConfig(
            id="lead-env",
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
            ),
        )
        sub_env = ConstraintEnvelopeConfig(
            id="sub-env",
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write", "delete"],
            ),
        )
        org = self._make_org_with_lead_and_sub(lead_env, sub_env)
        results = org.validate_org_detailed()
        op_errors = [r for r in results if r.code == "OPERATIONAL_TIGHTENING" and r.is_error]
        assert len(op_errors) >= 1
        assert "delete" in op_errors[0].message

    def test_sub_higher_rate_limit_than_lead_is_error(self):
        """Sub-agent with higher max_actions_per_day than lead must produce ERROR."""
        lead_env = ConstraintEnvelopeConfig(
            id="lead-env",
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        sub_env = ConstraintEnvelopeConfig(
            id="sub-env",
            operational=OperationalConstraintConfig(max_actions_per_day=200),
        )
        org = self._make_org_with_lead_and_sub(lead_env, sub_env)
        results = org.validate_org_detailed()
        rate_errors = [r for r in results if r.code == "OPERATIONAL_TIGHTENING" and r.is_error]
        assert len(rate_errors) >= 1

    def test_sub_external_when_lead_internal_only_is_error(self):
        """Sub allowing external comms when lead is internal-only must produce ERROR."""
        lead_env = ConstraintEnvelopeConfig(
            id="lead-env",
            communication=CommunicationConstraintConfig(internal_only=True),
        )
        sub_env = ConstraintEnvelopeConfig(
            id="sub-env",
            communication=CommunicationConstraintConfig(internal_only=False),
        )
        org = self._make_org_with_lead_and_sub(lead_env, sub_env)
        results = org.validate_org_detailed()
        comm_errors = [r for r in results if r.code == "COMMUNICATION_TIGHTENING" and r.is_error]
        assert len(comm_errors) >= 1

    def test_no_team_lead_skips_tightening(self):
        """Teams without a team_lead should skip monotonic tightening checks."""
        org = OrgDefinition(
            org_id="no-lead",
            name="No Lead",
            agents=[
                AgentConfig(id="agent-1", name="A1", role="R", constraint_envelope="env-1"),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    team_lead=None,
                    agents=["agent-1"],
                ),
            ],
            workspaces=[WorkspaceConfig(id="ws-1", path="workspaces/test/")],
        )
        results = org.validate_org_detailed()
        tightening = [r for r in results if "TIGHTENING" in r.code]
        assert len(tightening) == 0


class TestTeamLeadCapabilitySuperset:
    """Task 5031: Team leads must hold all capabilities that any sub-agent holds."""

    def test_lead_superset_passes(self):
        """Lead with all sub-agent capabilities should pass."""
        org = OrgDefinition(
            org_id="superset-test",
            name="Superset Test",
            agents=[
                AgentConfig(
                    id="lead",
                    name="Lead",
                    role="Lead",
                    constraint_envelope="env-1",
                    capabilities=["read", "write", "approve"],
                ),
                AgentConfig(
                    id="sub",
                    name="Sub",
                    role="Sub",
                    constraint_envelope="env-1",
                    capabilities=["read", "write"],
                ),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    team_lead="lead",
                    agents=["lead", "sub"],
                ),
            ],
            workspaces=[WorkspaceConfig(id="ws-1", path="workspaces/test/")],
        )
        results = org.validate_org_detailed()
        superset_errors = [r for r in results if r.code == "LEAD_MISSING_CAPABILITY" and r.is_error]
        assert len(superset_errors) == 0

    def test_lead_missing_sub_capability_is_error(self):
        """Lead missing a capability held by a sub-agent must produce ERROR."""
        org = OrgDefinition(
            org_id="superset-test",
            name="Superset Test",
            agents=[
                AgentConfig(
                    id="lead",
                    name="Lead",
                    role="Lead",
                    constraint_envelope="env-1",
                    capabilities=["read", "approve"],
                ),
                AgentConfig(
                    id="sub",
                    name="Sub",
                    role="Sub",
                    constraint_envelope="env-1",
                    capabilities=["read", "write", "hack_mainframe"],
                ),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    team_lead="lead",
                    agents=["lead", "sub"],
                ),
            ],
            workspaces=[WorkspaceConfig(id="ws-1", path="workspaces/test/")],
        )
        results = org.validate_org_detailed()
        superset_errors = [r for r in results if r.code == "LEAD_MISSING_CAPABILITY" and r.is_error]
        assert len(superset_errors) >= 1
        # Must mention the missing capabilities
        all_messages = " ".join(e.message for e in superset_errors)
        assert "write" in all_messages or "hack_mainframe" in all_messages


class TestVerificationGradientCoverage:
    """Task 5032: Warn when agent capabilities have no matching gradient rule."""

    def test_all_capabilities_covered_no_warning(self):
        """When all capabilities match a gradient rule, no warning is produced."""
        org = OrgDefinition(
            org_id="grad-test",
            name="Grad Test",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                    capabilities=["read_data", "draft_post"],
                    verification_gradient=VerificationGradientConfig(
                        rules=[
                            GradientRuleConfig(
                                pattern="read_*", level=VerificationLevel.AUTO_APPROVED
                            ),
                            GradientRuleConfig(
                                pattern="draft_*", level=VerificationLevel.AUTO_APPROVED
                            ),
                        ],
                        default_level=VerificationLevel.HELD,
                    ),
                ),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
        )
        results = org.validate_org_detailed()
        grad_warnings = [r for r in results if r.code == "GRADIENT_UNCOVERED_CAPABILITY"]
        assert len(grad_warnings) == 0

    def test_uncovered_capability_produces_warning(self):
        """Capability not matching any gradient rule must produce WARNING (not error)."""
        org = OrgDefinition(
            org_id="grad-test",
            name="Grad Test",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                    capabilities=["read_data", "launch_missile"],
                    verification_gradient=VerificationGradientConfig(
                        rules=[
                            GradientRuleConfig(
                                pattern="read_*", level=VerificationLevel.AUTO_APPROVED
                            ),
                        ],
                        default_level=VerificationLevel.HELD,
                    ),
                ),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
        )
        results = org.validate_org_detailed()
        grad_warnings = [r for r in results if r.code == "GRADIENT_UNCOVERED_CAPABILITY"]
        assert len(grad_warnings) >= 1
        assert grad_warnings[0].severity == ValidationSeverity.WARNING
        assert "launch_missile" in grad_warnings[0].message

    def test_team_gradient_used_when_agent_has_none(self):
        """When agent has no gradient but team does, team gradient is checked."""
        org = OrgDefinition(
            org_id="grad-test",
            name="Grad Test",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                    capabilities=["read_data", "unknown_action"],
                    verification_gradient=None,
                ),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    agents=["agent-1"],
                    verification_gradient=VerificationGradientConfig(
                        rules=[
                            GradientRuleConfig(
                                pattern="read_*", level=VerificationLevel.AUTO_APPROVED
                            ),
                        ],
                        default_level=VerificationLevel.HELD,
                    ),
                ),
            ],
            workspaces=[WorkspaceConfig(id="ws-1", path="workspaces/test/")],
        )
        results = org.validate_org_detailed()
        grad_warnings = [r for r in results if r.code == "GRADIENT_UNCOVERED_CAPABILITY"]
        assert len(grad_warnings) >= 1
        assert "unknown_action" in grad_warnings[0].message

    def test_no_gradient_no_check(self):
        """When neither agent nor team has a gradient, skip gradient coverage check."""
        org = OrgDefinition(
            org_id="grad-test",
            name="Grad Test",
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent",
                    role="Role",
                    constraint_envelope="env-1",
                    capabilities=["anything"],
                    verification_gradient=None,
                ),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
        )
        results = org.validate_org_detailed()
        grad_warnings = [r for r in results if r.code == "GRADIENT_UNCOVERED_CAPABILITY"]
        assert len(grad_warnings) == 0


class TestTemporalDataPathConsistency:
    """Task 5033: Sub-agent temporal windows within lead's, data paths are subsets."""

    def _make_temporal_org(
        self,
        lead_start: str,
        lead_end: str,
        sub_start: str,
        sub_end: str,
    ) -> OrgDefinition:
        lead_env = ConstraintEnvelopeConfig(
            id="lead-env",
            temporal=TemporalConstraintConfig(
                active_hours_start=lead_start,
                active_hours_end=lead_end,
            ),
        )
        sub_env = ConstraintEnvelopeConfig(
            id="sub-env",
            temporal=TemporalConstraintConfig(
                active_hours_start=sub_start,
                active_hours_end=sub_end,
            ),
        )
        return OrgDefinition(
            org_id="temporal-test",
            name="Temporal Test",
            agents=[
                AgentConfig(id="lead", name="Lead", role="Lead", constraint_envelope="lead-env"),
                AgentConfig(id="sub", name="Sub", role="Sub", constraint_envelope="sub-env"),
            ],
            envelopes=[lead_env, sub_env],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    team_lead="lead",
                    agents=["lead", "sub"],
                ),
            ],
            workspaces=[WorkspaceConfig(id="ws-1", path="workspaces/test/")],
        )

    def test_sub_within_lead_temporal_window_passes(self):
        """Sub-agent temporal window within lead's window should pass."""
        org = self._make_temporal_org("06:00", "22:00", "08:00", "20:00")
        results = org.validate_org_detailed()
        temporal_errors = [r for r in results if r.code == "TEMPORAL_TIGHTENING" and r.is_error]
        assert len(temporal_errors) == 0

    def test_sub_starts_before_lead_is_error(self):
        """Sub-agent starting before lead must produce ERROR."""
        org = self._make_temporal_org("08:00", "22:00", "06:00", "20:00")
        results = org.validate_org_detailed()
        temporal_errors = [r for r in results if r.code == "TEMPORAL_TIGHTENING" and r.is_error]
        assert len(temporal_errors) >= 1

    def test_sub_ends_after_lead_is_error(self):
        """Sub-agent ending after lead must produce ERROR."""
        org = self._make_temporal_org("06:00", "20:00", "08:00", "22:00")
        results = org.validate_org_detailed()
        temporal_errors = [r for r in results if r.code == "TEMPORAL_TIGHTENING" and r.is_error]
        assert len(temporal_errors) >= 1

    def test_sub_data_read_paths_subset_passes(self):
        """Sub data access read_paths that are a subset of lead's should pass."""
        lead_env = ConstraintEnvelopeConfig(
            id="lead-env",
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/*", "analytics/*"],
                write_paths=["workspaces/*"],
            ),
        )
        sub_env = ConstraintEnvelopeConfig(
            id="sub-env",
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/*"],
                write_paths=["workspaces/drafts/*"],
            ),
        )
        org = OrgDefinition(
            org_id="data-test",
            name="Data Test",
            agents=[
                AgentConfig(id="lead", name="Lead", role="Lead", constraint_envelope="lead-env"),
                AgentConfig(id="sub", name="Sub", role="Sub", constraint_envelope="sub-env"),
            ],
            envelopes=[lead_env, sub_env],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    team_lead="lead",
                    agents=["lead", "sub"],
                ),
            ],
            workspaces=[WorkspaceConfig(id="ws-1", path="workspaces/test/")],
        )
        results = org.validate_org_detailed()
        data_errors = [r for r in results if r.code == "DATA_ACCESS_TIGHTENING" and r.is_error]
        assert len(data_errors) == 0

    def test_sub_read_path_outside_lead_is_error(self):
        """Sub-agent with read_path not covered by lead must produce ERROR."""
        lead_env = ConstraintEnvelopeConfig(
            id="lead-env",
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/dm/*"],
                write_paths=["workspaces/dm/*"],
            ),
        )
        sub_env = ConstraintEnvelopeConfig(
            id="sub-env",
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/dm/*", "secrets/*"],
                write_paths=["workspaces/dm/*"],
            ),
        )
        org = OrgDefinition(
            org_id="data-test",
            name="Data Test",
            agents=[
                AgentConfig(id="lead", name="Lead", role="Lead", constraint_envelope="lead-env"),
                AgentConfig(id="sub", name="Sub", role="Sub", constraint_envelope="sub-env"),
            ],
            envelopes=[lead_env, sub_env],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    team_lead="lead",
                    agents=["lead", "sub"],
                ),
            ],
            workspaces=[WorkspaceConfig(id="ws-1", path="workspaces/test/")],
        )
        results = org.validate_org_detailed()
        data_errors = [r for r in results if r.code == "DATA_ACCESS_TIGHTENING" and r.is_error]
        assert len(data_errors) >= 1
        assert "secrets/*" in data_errors[0].message

    def test_sub_write_path_outside_lead_is_error(self):
        """Sub-agent with write_path not covered by lead must produce ERROR."""
        lead_env = ConstraintEnvelopeConfig(
            id="lead-env",
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/*"],
                write_paths=["workspaces/dm/*"],
            ),
        )
        sub_env = ConstraintEnvelopeConfig(
            id="sub-env",
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/*"],
                write_paths=["workspaces/dm/*", "workspaces/admin/*"],
            ),
        )
        org = OrgDefinition(
            org_id="data-test",
            name="Data Test",
            agents=[
                AgentConfig(id="lead", name="Lead", role="Lead", constraint_envelope="lead-env"),
                AgentConfig(id="sub", name="Sub", role="Sub", constraint_envelope="sub-env"),
            ],
            envelopes=[lead_env, sub_env],
            teams=[
                TeamConfig(
                    id="team-1",
                    name="Team",
                    workspace="ws-1",
                    team_lead="lead",
                    agents=["lead", "sub"],
                ),
            ],
            workspaces=[WorkspaceConfig(id="ws-1", path="workspaces/test/")],
        )
        results = org.validate_org_detailed()
        data_errors = [r for r in results if r.code == "DATA_ACCESS_TIGHTENING" and r.is_error]
        assert len(data_errors) >= 1
        assert "workspaces/admin/*" in data_errors[0].message


class TestMultiTeamValidation:
    """Task 5034: Cross-team validation — no overlapping agent IDs, no conflicting workspaces."""

    def test_no_overlapping_agents_passes(self):
        """Distinct agents across teams should pass."""
        org = OrgDefinition(
            org_id="multi-test",
            name="Multi Test",
            agents=[
                AgentConfig(id="a-1", name="A1", role="R", constraint_envelope="env-1"),
                AgentConfig(id="a-2", name="A2", role="R", constraint_envelope="env-1"),
                AgentConfig(id="a-3", name="A3", role="R", constraint_envelope="env-1"),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
            teams=[
                TeamConfig(id="team-1", name="Team 1", workspace="ws-1", agents=["a-1", "a-2"]),
                TeamConfig(id="team-2", name="Team 2", workspace="ws-2", agents=["a-3"]),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/t1/"),
                WorkspaceConfig(id="ws-2", path="workspaces/t2/"),
            ],
        )
        results = org.validate_org_detailed()
        overlap_errors = [r for r in results if r.code == "AGENT_IN_MULTIPLE_TEAMS"]
        assert len(overlap_errors) == 0

    def test_agent_in_multiple_teams_is_error(self):
        """An agent appearing in multiple teams must produce ERROR."""
        org = OrgDefinition(
            org_id="multi-test",
            name="Multi Test",
            agents=[
                AgentConfig(id="shared", name="Shared", role="R", constraint_envelope="env-1"),
                AgentConfig(id="a-2", name="A2", role="R", constraint_envelope="env-1"),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
            teams=[
                TeamConfig(id="team-1", name="Team 1", workspace="ws-1", agents=["shared", "a-2"]),
                TeamConfig(id="team-2", name="Team 2", workspace="ws-2", agents=["shared"]),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/t1/"),
                WorkspaceConfig(id="ws-2", path="workspaces/t2/"),
            ],
        )
        results = org.validate_org_detailed()
        overlap_errors = [r for r in results if r.code == "AGENT_IN_MULTIPLE_TEAMS" and r.is_error]
        assert len(overlap_errors) >= 1
        assert "shared" in overlap_errors[0].message

    def test_conflicting_workspace_paths_is_error(self):
        """Teams with the same workspace path must produce ERROR."""
        org = OrgDefinition(
            org_id="multi-test",
            name="Multi Test",
            agents=[
                AgentConfig(id="a-1", name="A1", role="R", constraint_envelope="env-1"),
                AgentConfig(id="a-2", name="A2", role="R", constraint_envelope="env-1"),
            ],
            envelopes=[ConstraintEnvelopeConfig(id="env-1")],
            teams=[
                TeamConfig(id="team-1", name="Team 1", workspace="ws-1", agents=["a-1"]),
                TeamConfig(id="team-2", name="Team 2", workspace="ws-2", agents=["a-2"]),
            ],
            workspaces=[
                WorkspaceConfig(id="ws-1", path="workspaces/shared/"),
                WorkspaceConfig(id="ws-2", path="workspaces/shared/"),
            ],
        )
        results = org.validate_org_detailed()
        path_errors = [r for r in results if r.code == "CONFLICTING_WORKSPACE_PATHS" and r.is_error]
        assert len(path_errors) >= 1
