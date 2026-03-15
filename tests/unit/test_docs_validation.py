# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Documentation validation tests (Task 808).

Validates that all public classes mentioned in documentation can be imported,
instantiated, and have the key methods/properties that docs reference.
This ensures documentation stays accurate as the code evolves.
"""

from datetime import UTC, datetime

import pytest

from care_platform.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintDimension,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    PlatformConfig,
    TeamConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
    WorkspaceConfig,
)


# ---------------------------------------------------------------------------
# Config layer: all schema classes instantiate and have documented fields
# ---------------------------------------------------------------------------


class TestPlatformConfigInstantiation:
    """PlatformConfig is referenced in getting-started.md and cookbook.md."""

    def test_minimal_instantiation(self):
        config = PlatformConfig(
            name="Test Org",
            genesis=GenesisConfig(
                authority="test.example",
                authority_name="Test Org",
            ),
        )
        assert config.name == "Test Org"
        assert config.genesis.authority == "test.example"

    def test_has_lookup_methods(self):
        """Docs reference get_envelope, get_agent, get_team, get_workspace."""
        config = PlatformConfig(
            name="Test",
            genesis=GenesisConfig(authority="t", authority_name="T"),
        )
        assert callable(config.get_envelope)
        assert callable(config.get_agent)
        assert callable(config.get_team)
        assert callable(config.get_workspace)

    def test_default_posture(self):
        config = PlatformConfig(
            name="Test",
            genesis=GenesisConfig(authority="t", authority_name="T"),
        )
        assert config.default_posture == TrustPostureLevel.SUPERVISED

    def test_with_full_structure(self):
        """Docs show configs with envelopes, agents, teams, workspaces."""
        config = PlatformConfig(
            name="Full Org",
            genesis=GenesisConfig(
                authority="full.example",
                authority_name="Full Org",
            ),
            constraint_envelopes=[
                ConstraintEnvelopeConfig(id="env-1", description="test"),
            ],
            agents=[
                AgentConfig(
                    id="agent-1",
                    name="Agent One",
                    role="tester",
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
        assert config.get_envelope("env-1") is not None
        assert config.get_agent("agent-1") is not None
        assert config.get_team("team-1") is not None
        assert config.get_workspace("ws-1") is not None
        assert config.get_envelope("nonexistent") is None


class TestConstraintEnvelopeConfigInstantiation:
    """ConstraintEnvelopeConfig is referenced throughout getting-started and cookbook."""

    def test_minimal(self):
        config = ConstraintEnvelopeConfig(id="test-env")
        assert config.id == "test-env"
        assert config.financial is not None
        assert config.operational is not None
        assert config.temporal is not None
        assert config.data_access is not None
        assert config.communication is not None

    def test_all_five_dimensions(self):
        config = ConstraintEnvelopeConfig(
            id="full-env",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read"],
                blocked_actions=["delete"],
                max_actions_per_day=10,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="18:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["data/"],
                write_paths=["output/"],
                blocked_data_types=["pii"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )
        assert config.financial.max_spend_usd == 100.0
        assert config.operational.max_actions_per_day == 10
        assert config.temporal.active_hours_start == "09:00"
        assert "data/" in config.data_access.read_paths
        assert config.communication.internal_only is True


class TestGenesisConfigInstantiation:
    """GenesisConfig is referenced in getting-started as the root of trust."""

    def test_instantiation(self):
        genesis = GenesisConfig(
            authority="test.example",
            authority_name="Test",
        )
        assert genesis.authority == "test.example"
        assert genesis.authority_name == "Test"
        assert genesis.policy_reference == ""


# ---------------------------------------------------------------------------
# Constraint layer: envelope evaluation and gradient engine
# ---------------------------------------------------------------------------


class TestConstraintEnvelopeInstantiation:
    """ConstraintEnvelope is demonstrated in getting-started and cookbook."""

    def test_instantiation(self):
        from care_platform import ConstraintEnvelope

        envelope = ConstraintEnvelope(
            config=ConstraintEnvelopeConfig(id="test"),
        )
        assert envelope.id == "test"
        assert envelope.version == 1
        assert not envelope.is_expired

    def test_evaluate_action_method_exists(self):
        from care_platform import ConstraintEnvelope

        envelope = ConstraintEnvelope(
            config=ConstraintEnvelopeConfig(id="test"),
        )
        assert callable(envelope.evaluate_action)

    def test_is_tighter_than_method_exists(self):
        """Cookbook Example 4 uses is_tighter_than."""
        from care_platform import ConstraintEnvelope

        envelope = ConstraintEnvelope(
            config=ConstraintEnvelopeConfig(id="test"),
        )
        assert callable(envelope.is_tighter_than)

    def test_content_hash_method_exists(self):
        from care_platform import ConstraintEnvelope

        envelope = ConstraintEnvelope(
            config=ConstraintEnvelopeConfig(id="test"),
        )
        h = envelope.content_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_evaluate_action_returns_envelope_evaluation(self):
        """Docs show accessing result.overall_result, result.is_allowed, result.dimensions."""
        from care_platform import ConstraintEnvelope, EvaluationResult

        envelope = ConstraintEnvelope(
            config=ConstraintEnvelopeConfig(
                id="eval-test",
                operational=OperationalConstraintConfig(
                    allowed_actions=["read"],
                    blocked_actions=["delete"],
                ),
            ),
        )
        result = envelope.evaluate_action(
            "read",
            "agent-1",
            current_time=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        )
        assert hasattr(result, "overall_result")
        assert hasattr(result, "is_allowed")
        assert hasattr(result, "dimensions")
        assert result.overall_result == EvaluationResult.ALLOWED
        assert result.is_allowed is True


class TestGradientEngineInstantiation:
    """GradientEngine is referenced in getting-started (verification gradient concept)."""

    def test_instantiation(self):
        from care_platform import GradientEngine

        engine = GradientEngine(
            config=VerificationGradientConfig(
                rules=[
                    GradientRuleConfig(
                        pattern="collect_*",
                        level=VerificationLevel.AUTO_APPROVED,
                        reason="Data collection is auto-approved",
                    ),
                ],
                default_level=VerificationLevel.HELD,
            ),
        )
        assert engine is not None

    def test_classify_method_exists(self):
        from care_platform import GradientEngine

        engine = GradientEngine(
            config=VerificationGradientConfig(
                default_level=VerificationLevel.HELD,
            ),
        )
        assert callable(engine.classify)

    def test_classify_returns_verification_result(self):
        from care_platform import GradientEngine
        from care_platform.constraint.gradient import VerificationResult

        engine = GradientEngine(
            config=VerificationGradientConfig(
                rules=[
                    GradientRuleConfig(
                        pattern="collect_*",
                        level=VerificationLevel.AUTO_APPROVED,
                    ),
                ],
                default_level=VerificationLevel.HELD,
            ),
        )
        result = engine.classify("collect_metrics", "agent-1")
        assert isinstance(result, VerificationResult)
        assert result.level == VerificationLevel.AUTO_APPROVED


# ---------------------------------------------------------------------------
# Trust layer: posture, attestation, scoring
# ---------------------------------------------------------------------------


class TestTrustPostureInstantiation:
    """TrustPosture is referenced in getting-started (trust posture concept)."""

    def test_instantiation(self):
        from care_platform import TrustPosture

        posture = TrustPosture(agent_id="test-agent")
        assert posture.agent_id == "test-agent"
        assert posture.current_level == TrustPostureLevel.SUPERVISED

    def test_has_upgrade_and_downgrade(self):
        from care_platform import TrustPosture

        posture = TrustPosture(agent_id="test-agent")
        assert callable(posture.can_upgrade)
        assert callable(posture.upgrade)
        assert callable(posture.downgrade)

    def test_is_action_always_held(self):
        from care_platform import TrustPosture

        posture = TrustPosture(agent_id="test-agent")
        assert callable(posture.is_action_always_held)
        # These actions must always be held per the CARE model
        assert posture.is_action_always_held("modify_constraints")
        assert not posture.is_action_always_held("collect_metrics")


class TestCapabilityAttestationInstantiation:
    """CapabilityAttestation is EATP Element 4, referenced in trust chain docs."""

    def test_instantiation(self):
        from care_platform import CapabilityAttestation

        attestation = CapabilityAttestation(
            attestation_id="att-001",
            agent_id="test-agent",
            delegation_id="del-001",
            constraint_envelope_id="env-001",
            capabilities=["read", "write"],
            issuer_id="genesis",
        )
        assert attestation.agent_id == "test-agent"
        assert attestation.is_valid is True
        assert attestation.has_capability("read")
        assert not attestation.has_capability("delete")

    def test_has_key_methods(self):
        from care_platform import CapabilityAttestation

        attestation = CapabilityAttestation(
            attestation_id="att-002",
            agent_id="agent",
            delegation_id="del",
            constraint_envelope_id="env",
            capabilities=["read"],
            issuer_id="issuer",
        )
        assert callable(attestation.content_hash)
        assert callable(attestation.revoke)
        assert callable(attestation.verify_consistency)

    def test_revocation(self):
        from care_platform import CapabilityAttestation

        attestation = CapabilityAttestation(
            attestation_id="att-003",
            agent_id="agent",
            delegation_id="del",
            constraint_envelope_id="env",
            capabilities=["read"],
            issuer_id="issuer",
        )
        assert attestation.is_valid
        attestation.revoke("test revocation")
        assert not attestation.is_valid
        assert attestation.revoked is True


class TestTrustScoringInstantiation:
    """Trust scoring is demonstrated in getting-started step 7 and cookbook."""

    def test_calculate_trust_score(self):
        from care_platform import TrustScore, calculate_trust_score
        from care_platform.trust.scoring import TrustFactors

        factors = TrustFactors(
            has_genesis=True,
            has_delegation=True,
            has_envelope=True,
            has_attestation=True,
            has_audit_anchor=True,
            delegation_depth=1,
            dimensions_configured=5,
            posture_level=TrustPostureLevel.SUPERVISED,
            newest_attestation_age_days=7,
        )
        score = calculate_trust_score("test-agent", factors)
        assert isinstance(score, TrustScore)
        assert score.agent_id == "test-agent"
        assert 0.0 <= score.overall_score <= 1.0
        assert score.grade is not None

    def test_trust_score_has_factors_dict(self):
        """Docs show iterating score.factors.items()."""
        from care_platform import calculate_trust_score
        from care_platform.trust.scoring import TrustFactors

        factors = TrustFactors(has_genesis=True)
        score = calculate_trust_score("agent", factors)
        assert isinstance(score.factors, dict)
        assert "chain_completeness" in score.factors
        assert "delegation_depth" in score.factors
        assert "constraint_coverage" in score.factors
        assert "posture_level" in score.factors
        assert "chain_recency" in score.factors


# ---------------------------------------------------------------------------
# Audit layer: anchor and chain
# ---------------------------------------------------------------------------


class TestAuditChainInstantiation:
    """AuditChain is demonstrated in getting-started step 8 and cookbook examples 5-6."""

    def test_instantiation(self):
        from care_platform import AuditChain

        chain = AuditChain(chain_id="test-chain")
        assert chain.chain_id == "test-chain"
        assert chain.length == 0
        assert chain.latest is None

    def test_append_and_verify(self):
        from care_platform import AuditChain

        chain = AuditChain(chain_id="test-chain")
        anchor = chain.append(
            agent_id="agent-1",
            action="test_action",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="success",
        )
        assert chain.length == 1
        assert anchor.is_sealed
        assert anchor.verify_integrity()

        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid
        assert errors == []

    def test_chain_has_filter_methods(self):
        """Cookbook shows filter_by_agent and filter_by_level."""
        from care_platform import AuditChain

        chain = AuditChain(chain_id="test")
        assert callable(chain.filter_by_agent)
        assert callable(chain.filter_by_level)

    def test_chain_has_export_method(self):
        """Cookbook Example 6 uses chain.export()."""
        from care_platform import AuditChain

        chain = AuditChain(chain_id="test")
        chain.append(
            agent_id="agent",
            action="action",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="ok",
        )
        exported = chain.export()
        assert isinstance(exported, list)
        assert len(exported) == 1
        assert isinstance(exported[0], dict)

    def test_chain_integrity_detects_tampering(self):
        """Getting-started troubleshooting section references chain verification."""
        from care_platform import AuditChain

        chain = AuditChain(chain_id="tamper-test")
        chain.append(
            agent_id="agent",
            action="action1",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="ok",
        )
        chain.append(
            agent_id="agent",
            action="action2",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="ok",
        )
        # Tamper with the first anchor
        chain.anchors[0].result = "TAMPERED"
        is_valid, errors = chain.verify_chain_integrity()
        assert not is_valid
        assert len(errors) > 0


class TestAuditAnchorInstantiation:
    """AuditAnchor is referenced in cookbook Example 5 chain walk."""

    def test_instantiation(self):
        from care_platform import AuditAnchor

        anchor = AuditAnchor(
            anchor_id="a-0",
            sequence=0,
            agent_id="agent",
            action="test",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert anchor.anchor_id == "a-0"
        assert not anchor.is_sealed

    def test_seal_and_verify(self):
        from care_platform import AuditAnchor

        anchor = AuditAnchor(
            anchor_id="a-0",
            sequence=0,
            agent_id="agent",
            action="test",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.seal()
        assert anchor.is_sealed
        assert anchor.verify_integrity()


# ---------------------------------------------------------------------------
# Execution layer: agent definition, team definition, approval queue, sessions
# ---------------------------------------------------------------------------


class TestAgentDefinitionInstantiation:
    """AgentDefinition is referenced in architecture discussions."""

    def test_from_config(self):
        from care_platform import AgentDefinition

        agent = AgentDefinition.from_config(
            AgentConfig(
                id="test-agent",
                name="Test Agent",
                role="tester",
                constraint_envelope="env-1",
            ),
        )
        assert agent.id == "test-agent"
        assert agent.name == "Test Agent"
        assert agent.is_operational
        assert agent.posture.current_level == TrustPostureLevel.SUPERVISED

    def test_revoke(self):
        from care_platform import AgentDefinition

        agent = AgentDefinition.from_config(
            AgentConfig(
                id="revoke-test",
                name="Revoke Test",
                role="tester",
                constraint_envelope="env-1",
            ),
        )
        assert agent.is_operational
        agent.revoke("test revocation")
        assert not agent.active


class TestTeamDefinitionInstantiation:
    """TeamDefinition is referenced in architecture discussions."""

    def test_instantiation(self):
        from care_platform import TeamDefinition

        team = TeamDefinition(
            config=TeamConfig(
                id="team-1",
                name="Test Team",
                workspace="ws-1",
            ),
        )
        assert team.id == "team-1"
        assert team.name == "Test Team"
        assert team.active
        assert team.operational_agents == []

    def test_add_and_revoke_agent(self):
        from care_platform import AgentDefinition, TeamDefinition

        team = TeamDefinition(
            config=TeamConfig(id="t", name="T", workspace="w"),
        )
        agent = AgentDefinition.from_config(
            AgentConfig(id="a", name="A", role="r", constraint_envelope="e"),
        )
        team.add_agent(agent)
        assert len(team.operational_agents) == 1

        team.revoke_agent("a", "test")
        assert len(team.operational_agents) == 0


class TestApprovalQueueInstantiation:
    """ApprovalQueue is referenced in the approval workflow."""

    def test_instantiation(self):
        from care_platform import ApprovalQueue

        queue = ApprovalQueue()
        assert queue.queue_depth == 0
        assert queue.pending == []

    def test_submit_approve_reject(self):
        from care_platform import ApprovalQueue

        queue = ApprovalQueue()
        pa = queue.submit(
            agent_id="agent",
            action="publish",
            reason="Held by gradient",
        )
        assert queue.queue_depth == 1

        queue.approve(pa.action_id, "human-approver", "looks good")
        assert queue.queue_depth == 0

    def test_capacity_metrics(self):
        from care_platform import ApprovalQueue

        queue = ApprovalQueue()
        metrics = queue.get_capacity_metrics()
        assert "pending_count" in metrics
        assert "resolved_count" in metrics
        assert "avg_resolution_seconds" in metrics


class TestSessionManagementInstantiation:
    """SessionManager, PlatformSession, SessionCheckpoint are referenced in session docs."""

    def test_session_manager(self):
        from care_platform import SessionManager

        mgr = SessionManager()
        assert mgr.current_session is None

        session = mgr.start_session()
        assert mgr.current_session is not None
        assert session.state.value == "active"

    def test_checkpoint(self):
        from care_platform import SessionManager

        mgr = SessionManager()
        mgr.start_session()
        cp = mgr.checkpoint(
            active_teams=["team-1"],
            pending_approvals=3,
            notes="test checkpoint",
        )
        assert cp.session_id == mgr.current_session.session_id
        assert cp.active_teams == ["team-1"]
        assert cp.pending_approvals == 3

    def test_end_session_and_briefing(self):
        from care_platform import SessionManager

        mgr = SessionManager()
        mgr.start_session()
        mgr.checkpoint(active_teams=["team-1"])
        mgr.end_session(notes="done")
        assert mgr.current_session is None

        # end_session creates a final checkpoint, so the briefing reflects that
        briefing = mgr.generate_briefing()
        assert isinstance(briefing, str)
        assert "Session ended: done" in briefing


# ---------------------------------------------------------------------------
# Workspace layer
# ---------------------------------------------------------------------------


class TestWorkspaceInstantiation:
    """Workspace and WorkspaceRegistry are referenced in architecture docs."""

    def test_workspace(self):
        from care_platform import Workspace, WorkspacePhase

        ws = Workspace(
            config=WorkspaceConfig(id="test-ws", path="workspaces/test/"),
        )
        assert ws.id == "test-ws"
        assert ws.current_phase == WorkspacePhase.ANALYZE

    def test_phase_transitions(self):
        from care_platform import Workspace, WorkspacePhase

        ws = Workspace(
            config=WorkspaceConfig(id="test-ws", path="workspaces/test/"),
        )
        # Workspace must be ACTIVE for phase transitions
        ws.activate(reason="ready")
        assert ws.can_transition_to(WorkspacePhase.PLAN)
        assert not ws.can_transition_to(WorkspacePhase.IMPLEMENT)

        ws.transition_to(WorkspacePhase.PLAN, reason="analysis complete")
        assert ws.current_phase == WorkspacePhase.PLAN

    def test_workspace_registry(self):
        from care_platform import Workspace, WorkspaceRegistry

        registry = WorkspaceRegistry()
        ws = Workspace(
            config=WorkspaceConfig(id="ws-1", path="workspaces/one/"),
            team_id="team-1",
        )
        registry.register(ws)
        assert registry.get("ws-1") is not None
        assert registry.get_by_team("team-1") is not None
        assert len(registry.list_active()) == 1


# ---------------------------------------------------------------------------
# Enum completeness: verify enums have the values docs reference
# ---------------------------------------------------------------------------


class TestEnumValues:
    """Verify enum values that docs reference exist."""

    def test_trust_posture_levels(self):
        """Getting-started references these posture levels."""
        assert TrustPostureLevel.PSEUDO_AGENT.value == "pseudo_agent"
        assert TrustPostureLevel.SUPERVISED.value == "supervised"
        assert TrustPostureLevel.SHARED_PLANNING.value == "shared_planning"
        assert TrustPostureLevel.CONTINUOUS_INSIGHT.value == "continuous_insight"
        assert TrustPostureLevel.DELEGATED.value == "delegated"

    def test_verification_levels(self):
        """Getting-started references these verification levels."""
        assert VerificationLevel.AUTO_APPROVED.value == "AUTO_APPROVED"
        assert VerificationLevel.FLAGGED.value == "FLAGGED"
        assert VerificationLevel.HELD.value == "HELD"
        assert VerificationLevel.BLOCKED.value == "BLOCKED"

    def test_constraint_dimensions(self):
        """Getting-started references the five constraint dimensions."""
        dims = {d.value for d in ConstraintDimension}
        assert dims == {"financial", "operational", "temporal", "data_access", "communication"}

    def test_evaluation_result_values(self):
        """Cookbook references these evaluation results."""
        from care_platform import EvaluationResult

        assert EvaluationResult.ALLOWED.value == "allowed"
        assert EvaluationResult.DENIED.value == "denied"
        assert EvaluationResult.NEAR_BOUNDARY.value == "near_boundary"
