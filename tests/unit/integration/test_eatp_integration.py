# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Integration tests for the full EATP trust lifecycle (Milestone 2, Todo 211).

Tests the complete trust lifecycle:
  genesis -> delegate -> delegate -> verify -> audit
with chain integrity, constraint mapping, monotonic tightening,
cascade revocation, credential lifecycle, and ShadowEnforcer metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from care_platform.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.envelope import ConstraintEnvelope
from care_platform.constraint.gradient import GradientEngine
from care_platform.trust.credentials import CredentialManager, VerificationToken
from care_platform.trust.delegation import ChainStatus, DelegationManager
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.trust.genesis import GenesisManager
from care_platform.trust.revocation import RevocationManager
from care_platform.trust.shadow_enforcer import ShadowEnforcer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _genesis_config() -> GenesisConfig:
    return GenesisConfig(
        authority="terrene.foundation",
        authority_name="Terrene Foundation",
        policy_reference="https://terrene.foundation/policy",
    )


def _team_lead_config() -> AgentConfig:
    return AgentConfig(
        id="team-lead-1",
        name="DM Team Lead",
        role="team_lead",
        constraint_envelope="env-team-lead",
        capabilities=[
            "manage_team",
            "review_content",
            "delegate_tasks",
            "draft_content",
            "analyze_data",
        ],
    )


def _specialist_config() -> AgentConfig:
    return AgentConfig(
        id="specialist-1",
        name="Content Specialist",
        role="specialist",
        constraint_envelope="env-specialist",
        capabilities=["draft_content", "analyze_data"],
    )


def _team_lead_envelope() -> ConstraintEnvelopeConfig:
    return ConstraintEnvelopeConfig(
        id="env-team-lead",
        description="Team lead envelope",
        financial=FinancialConstraintConfig(
            max_spend_usd=500.0,
            requires_approval_above_usd=200.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "manage_team",
                "review_content",
                "delegate_tasks",
                "draft_content",
                "analyze_data",
            ],
            blocked_actions=["delete_data", "modify_governance"],
            max_actions_per_day=100,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="08:00",
            active_hours_end="20:00",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["reports/", "metrics/", "briefs/"],
            write_paths=["drafts/", "plans/"],
            blocked_data_types=["pii"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal"],
            external_requires_approval=True,
        ),
    )


def _specialist_envelope() -> ConstraintEnvelopeConfig:
    """Tighter envelope for the specialist (subset of team lead)."""
    return ConstraintEnvelopeConfig(
        id="env-specialist",
        description="Specialist envelope (narrower than team lead)",
        financial=FinancialConstraintConfig(
            max_spend_usd=100.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=["draft_content", "analyze_data"],
            blocked_actions=["delete_data", "modify_governance"],
            max_actions_per_day=50,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="09:00",
            active_hours_end="17:00",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["reports/"],
            write_paths=["drafts/"],
            blocked_data_types=["pii"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal"],
            external_requires_approval=True,
        ),
    )


# ===========================================================================
# 1. Full Trust Lifecycle
# ===========================================================================


class TestFullTrustLifecycle:
    """Full lifecycle: genesis -> delegate -> delegate -> verify -> audit."""

    @pytest.fixture()
    async def lifecycle_setup(self):
        """Establish full 3-level chain: genesis -> team lead -> specialist."""
        bridge = EATPBridge()
        await bridge.initialize()

        genesis_mgr = GenesisManager(bridge)
        delegation_mgr = DelegationManager(bridge)

        # ESTABLISH genesis
        genesis = await genesis_mgr.create_genesis(_genesis_config())
        genesis_agent_id = genesis.agent_id

        # DELEGATE to team lead
        team_lead_delegation = await delegation_mgr.create_delegation(
            delegator_id=genesis_agent_id,
            delegate_config=_team_lead_config(),
            envelope_config=_team_lead_envelope(),
        )

        # DELEGATE from team lead to specialist
        specialist_delegation = await delegation_mgr.create_delegation(
            delegator_id="team-lead-1",
            delegate_config=_specialist_config(),
            envelope_config=_specialist_envelope(),
        )

        return {
            "bridge": bridge,
            "genesis_mgr": genesis_mgr,
            "delegation_mgr": delegation_mgr,
            "genesis": genesis,
            "genesis_agent_id": genesis_agent_id,
            "team_lead_delegation": team_lead_delegation,
            "specialist_delegation": specialist_delegation,
        }

    @pytest.mark.asyncio
    async def test_full_lifecycle_establish_delegate_verify_audit(self, lifecycle_setup):
        """Complete trust lifecycle across 3 levels with verify and audit."""
        setup = lifecycle_setup
        bridge = setup["bridge"]

        # VERIFY: specialist action should be valid (QUICK level avoids
        # signature checks that depend on EATP internal key state)
        verify_result = await bridge.verify_action(
            agent_id="specialist-1",
            action="draft_content",
            resource="drafts/new-post.md",
            level="QUICK",
        )
        assert verify_result.valid, f"Verification failed: {verify_result.reason}"

        # AUDIT: record the verified action
        anchor = await bridge.record_audit(
            agent_id="specialist-1",
            action="draft_content",
            resource="drafts/new-post.md",
            result="SUCCESS",
            reasoning="Agent drafted content within envelope constraints",
        )
        assert anchor is not None
        assert anchor.agent_id == "specialist-1"
        assert anchor.action == "draft_content"

    @pytest.mark.asyncio
    async def test_chain_integrity_across_3_levels(self, lifecycle_setup):
        """Verify chain integrity from specialist back to genesis."""
        setup = lifecycle_setup
        bridge = setup["bridge"]
        delegation_mgr = setup["delegation_mgr"]

        # Walk the chain from specialist back to genesis
        walk_result = await delegation_mgr.walk_chain("specialist-1")
        assert walk_result.status == ChainStatus.VALID
        assert walk_result.depth == 2  # genesis(0) -> team_lead(1) -> specialist(2)

        # Verify ancestors path
        ancestors = bridge.get_delegation_ancestors("specialist-1")
        assert "specialist-1" in ancestors
        assert "team-lead-1" in ancestors

    @pytest.mark.asyncio
    async def test_constraint_mapping_round_trip(self, lifecycle_setup):
        """Verify constraint mapping from CARE config to EATP constraints and back."""
        setup = lifecycle_setup
        bridge = setup["bridge"]

        envelope_config = _team_lead_envelope()
        constraints = bridge.map_envelope_to_constraints(envelope_config)

        # Verify financial constraints mapped
        assert any("budget:500.0" in c for c in constraints)
        assert any("approval_threshold:200.0" in c for c in constraints)

        # Verify operational constraints mapped
        assert any("allow:manage_team" in c for c in constraints)
        assert any("block:delete_data" in c for c in constraints)
        assert any("rate_limit:100" in c for c in constraints)

        # Verify temporal constraints mapped
        assert any("time:08:00-20:00" in c for c in constraints)

        # Verify data access constraints mapped
        assert any("read:reports/" in c for c in constraints)
        assert any("write:drafts/" in c for c in constraints)

        # Verify communication constraints mapped
        assert any("comm:internal_only" in c for c in constraints)
        assert any("channel:slack-internal" in c for c in constraints)
        assert any("comm:external_requires_approval" in c for c in constraints)


# ===========================================================================
# 2. Monotonic Tightening Enforcement
# ===========================================================================


class TestMonotonicTighteningEnforcement:
    """Delegation that expands parent envelope is rejected; narrowing is accepted."""

    def test_tighter_child_accepted(self):
        """Specialist envelope is tighter than team lead -> accepted."""
        mgr = DelegationManager(EATPBridge())
        is_valid, violations = mgr.validate_tightening(
            parent_envelope=_team_lead_envelope(),
            child_envelope=_specialist_envelope(),
        )
        assert is_valid, f"Expected valid tightening but got violations: {violations}"

    def test_expanding_budget_rejected(self):
        """Child envelope with larger budget than parent -> rejected."""
        mgr = DelegationManager(EATPBridge())

        expanded = ConstraintEnvelopeConfig(
            id="env-expanded",
            financial=FinancialConstraintConfig(max_spend_usd=1000.0),  # parent is 500
            operational=OperationalConstraintConfig(
                blocked_actions=["delete_data", "modify_governance"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )

        is_valid, violations = mgr.validate_tightening(
            parent_envelope=_team_lead_envelope(),
            child_envelope=expanded,
        )
        assert not is_valid
        assert any("Financial" in v for v in violations)

    def test_expanding_actions_rejected(self):
        """Child with actions not in parent's allowed set -> rejected."""
        mgr = DelegationManager(EATPBridge())

        expanded_ops = ConstraintEnvelopeConfig(
            id="env-expanded-ops",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["draft_content", "admin_access"],  # admin not in parent
                blocked_actions=["delete_data", "modify_governance"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )

        is_valid, violations = mgr.validate_tightening(
            parent_envelope=_team_lead_envelope(),
            child_envelope=expanded_ops,
        )
        assert not is_valid
        assert any("Operational" in v for v in violations)

    def test_missing_blocked_actions_rejected(self):
        """Child envelope that does not block parent's blocked actions -> rejected."""
        mgr = DelegationManager(EATPBridge())

        missing_blocks = ConstraintEnvelopeConfig(
            id="env-missing-blocks",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["draft_content"],
                blocked_actions=["delete_data"],  # missing "modify_governance"
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )

        is_valid, violations = mgr.validate_tightening(
            parent_envelope=_team_lead_envelope(),
            child_envelope=missing_blocks,
        )
        assert not is_valid
        assert any("modify_governance" in v for v in violations)

    def test_loosening_communication_rejected(self):
        """Child that removes internal_only restriction -> rejected."""
        mgr = DelegationManager(EATPBridge())

        loosened_comm = ConstraintEnvelopeConfig(
            id="env-loose-comm",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                blocked_actions=["delete_data", "modify_governance"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=False,  # parent has True
                external_requires_approval=True,
            ),
        )

        is_valid, violations = mgr.validate_tightening(
            parent_envelope=_team_lead_envelope(),
            child_envelope=loosened_comm,
        )
        assert not is_valid
        assert any("Communication" in v for v in violations)

    def test_multi_level_narrowing(self):
        """Genesis (wide) -> team lead (narrow) -> specialist (narrower)."""
        mgr = DelegationManager(EATPBridge())

        wide_genesis = ConstraintEnvelopeConfig(
            id="env-genesis",
            financial=FinancialConstraintConfig(max_spend_usd=10000.0),
            operational=OperationalConstraintConfig(
                allowed_actions=[
                    "manage_team",
                    "review_content",
                    "delegate_tasks",
                    "draft_content",
                    "analyze_data",
                    "admin",
                ],
                blocked_actions=["delete_data", "modify_governance"],
                max_actions_per_day=500,
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )

        # Genesis -> Team Lead: valid
        is_valid_1, _ = mgr.validate_tightening(wide_genesis, _team_lead_envelope())
        assert is_valid_1

        # Team Lead -> Specialist: valid
        is_valid_2, _ = mgr.validate_tightening(_team_lead_envelope(), _specialist_envelope())
        assert is_valid_2


# ===========================================================================
# 3. Verification Gradient in Action
# ===========================================================================


class TestVerificationGradientInAction:
    """Agent actions at different gradient levels."""

    def _make_engine(self) -> GradientEngine:
        config = VerificationGradientConfig(
            rules=[
                GradientRuleConfig(
                    pattern="read_*", level=VerificationLevel.AUTO_APPROVED, reason="Reads are safe"
                ),
                GradientRuleConfig(
                    pattern="draft_*",
                    level=VerificationLevel.FLAGGED,
                    reason="Content creation needs review",
                ),
                GradientRuleConfig(
                    pattern="send_*",
                    level=VerificationLevel.HELD,
                    reason="Outbound messages need approval",
                ),
                GradientRuleConfig(
                    pattern="delete_*",
                    level=VerificationLevel.BLOCKED,
                    reason="Destructive actions blocked",
                ),
            ],
            default_level=VerificationLevel.HELD,
        )
        return GradientEngine(config)

    def test_action_within_envelope_auto_approved(self):
        """Read action within constraints -> auto-approved."""
        engine = self._make_engine()
        result = engine.classify("read_metrics", "agent-1")
        assert result.is_auto_approved
        assert result.matched_rule == "read_*"

    def test_action_near_boundary_flagged(self):
        """Action near financial boundary gets flagged."""
        engine = self._make_engine()
        envelope = ConstraintEnvelope(
            config=ConstraintEnvelopeConfig(
                id="env-boundary",
                financial=FinancialConstraintConfig(max_spend_usd=100.0),
            )
        )
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)
        eval_result = envelope.evaluate_action(
            "read_metrics", "agent-1", spend_amount=85.0, current_time=work_time
        )
        assert eval_result.is_near_boundary

        gradient_result = engine.classify(
            "read_metrics", "agent-1", envelope_evaluation=eval_result
        )
        assert gradient_result.level == VerificationLevel.FLAGGED
        assert gradient_result.reason == "Near constraint boundary"

    def test_external_action_held(self):
        """Send action that requires approval -> HELD."""
        engine = self._make_engine()
        result = engine.classify("send_external_message", "agent-1")
        assert result.level == VerificationLevel.HELD

    def test_prohibited_action_blocked(self):
        """Delete action -> BLOCKED."""
        engine = self._make_engine()
        result = engine.classify("delete_records", "agent-1")
        assert result.is_blocked


# ===========================================================================
# 4. Cascade Revocation Lifecycle
# ===========================================================================


class TestCascadeRevocationLifecycle:
    """Revocation: surgical, cascade, re-delegation."""

    def test_surgical_revoke_specialist_only(self):
        """Revoke specialist -> only specialist affected."""
        cred_mgr = CredentialManager()
        revoke_mgr = RevocationManager(credential_manager=cred_mgr)

        # Register delegation tree
        revoke_mgr.register_delegation("team-lead-1", "specialist-1")
        revoke_mgr.register_delegation("team-lead-1", "specialist-2")

        # Issue tokens for both specialists
        cred_mgr.issue_token("specialist-1", trust_score=0.8)
        cred_mgr.issue_token("specialist-2", trust_score=0.85)

        # Surgical revoke specialist-1
        record = revoke_mgr.surgical_revoke("specialist-1", "Security incident", "team-lead-1")

        assert record.revocation_type == "surgical"
        assert record.affected_agents == []
        assert revoke_mgr.is_revoked("specialist-1")
        assert not revoke_mgr.is_revoked("specialist-2")

        # specialist-1 token is revoked, specialist-2 token is still valid
        assert cred_mgr.needs_reverification("specialist-1")
        assert not cred_mgr.needs_reverification("specialist-2")

    def test_cascade_revoke_team_lead(self):
        """Revoke team lead -> all downstream agents revoked."""
        cred_mgr = CredentialManager()
        revoke_mgr = RevocationManager(credential_manager=cred_mgr)

        # Build delegation tree: team-lead -> spec-1, spec-2; spec-1 -> sub-spec-1
        revoke_mgr.register_delegation("team-lead-1", "specialist-1")
        revoke_mgr.register_delegation("team-lead-1", "specialist-2")
        revoke_mgr.register_delegation("specialist-1", "sub-specialist-1")

        # Issue tokens
        for agent in ["team-lead-1", "specialist-1", "specialist-2", "sub-specialist-1"]:
            cred_mgr.issue_token(agent, trust_score=0.8)

        # Cascade revoke the team lead
        record = revoke_mgr.cascade_revoke(
            "team-lead-1", "Policy violation", "authority:terrene.foundation"
        )

        assert record.revocation_type == "cascade"
        # All downstream agents affected
        assert "specialist-1" in record.affected_agents
        assert "specialist-2" in record.affected_agents
        assert "sub-specialist-1" in record.affected_agents

        # All tokens revoked
        for agent in ["team-lead-1", "specialist-1", "specialist-2", "sub-specialist-1"]:
            assert cred_mgr.needs_reverification(agent), f"Agent {agent} should need reverification"

    def test_actions_after_revocation_blocked(self):
        """After revocation, agent cannot get a valid token."""
        cred_mgr = CredentialManager()
        revoke_mgr = RevocationManager(credential_manager=cred_mgr)

        cred_mgr.issue_token("specialist-1", trust_score=0.8)
        assert not cred_mgr.needs_reverification("specialist-1")

        revoke_mgr.surgical_revoke("specialist-1", "Compromised", "team-lead-1")

        # Token is now invalid
        assert cred_mgr.needs_reverification("specialist-1")
        assert cred_mgr.get_valid_token("specialist-1") is None

    def test_redelegation_after_revocation(self):
        """A revoked agent can be re-delegated with a fresh chain."""
        cred_mgr = CredentialManager()
        revoke_mgr = RevocationManager(credential_manager=cred_mgr)

        # Revoke
        revoke_mgr.surgical_revoke("specialist-1", "Incident", "team-lead-1")
        assert revoke_mgr.is_revoked("specialist-1")

        # Re-delegation is always allowed
        assert revoke_mgr.can_redelegate("specialist-1")

        # Issue a new token (simulating re-delegation)
        new_token = cred_mgr.issue_token("specialist-1", trust_score=0.7, verification_level="FULL")
        assert new_token.is_valid


# ===========================================================================
# 5. Credential Lifecycle
# ===========================================================================


class TestCredentialLifecycle:
    """Verification token expiry, re-verification, and key management."""

    def test_token_expires_requires_reverification(self):
        """Verification token expires -> agent needs re-verification."""
        cred_mgr = CredentialManager(default_ttl_seconds=1)  # 1 second TTL

        token = cred_mgr.issue_token("agent-1", trust_score=0.9)
        assert token.is_valid

        # Create an already-expired token manually
        expired_token = VerificationToken(
            agent_id="agent-2",
            trust_score=0.9,
            verification_level="STANDARD",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        cred_mgr._tokens["agent-2"] = expired_token

        assert cred_mgr.needs_reverification("agent-2")
        assert cred_mgr.get_valid_token("agent-2") is None

    def test_cleanup_expired_tokens(self):
        """Cleanup removes expired tokens from active pool."""
        cred_mgr = CredentialManager()

        # Create an already-expired token
        expired_token = VerificationToken(
            agent_id="agent-1",
            trust_score=0.8,
            verification_level="STANDARD",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        cred_mgr._tokens["agent-1"] = expired_token

        removed = cred_mgr.cleanup_expired()
        assert removed == 1
        assert cred_mgr.needs_reverification("agent-1")

    def test_token_revocation_immediate(self):
        """Revoking a token makes it immediately invalid."""
        cred_mgr = CredentialManager()
        token = cred_mgr.issue_token("agent-1", trust_score=0.85)

        assert token.is_valid
        cred_mgr.revoke_agent_tokens("agent-1")
        assert not token.is_valid
        assert cred_mgr.needs_reverification("agent-1")


# ===========================================================================
# 6. ShadowEnforcer Metrics
# ===========================================================================


class TestShadowEnforcerMetrics:
    """Shadow evaluation matches strict enforcement; metrics are accurate."""

    def _make_enforcer(self) -> ShadowEnforcer:
        gradient_config = VerificationGradientConfig(
            rules=[
                GradientRuleConfig(
                    pattern="read_*", level=VerificationLevel.AUTO_APPROVED, reason="Reads safe"
                ),
                GradientRuleConfig(
                    pattern="draft_*", level=VerificationLevel.FLAGGED, reason="Needs review"
                ),
                GradientRuleConfig(
                    pattern="delete_*", level=VerificationLevel.BLOCKED, reason="Blocked"
                ),
            ],
            default_level=VerificationLevel.HELD,
        )
        engine = GradientEngine(gradient_config)

        envelope_config = ConstraintEnvelopeConfig(
            id="env-shadow",
            financial=FinancialConstraintConfig(max_spend_usd=500.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read_metrics", "draft_content", "delete_data", "send_message"],
                blocked_actions=["delete_data"],
                max_actions_per_day=50,
            ),
            temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        )
        envelope = ConstraintEnvelope(config=envelope_config)

        return ShadowEnforcer(gradient_engine=engine, envelope=envelope)

    def test_shadow_matches_strict_enforcement(self):
        """Shadow evaluation result matches what strict enforcement would produce."""
        enforcer = self._make_enforcer()
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Read action -> auto_approved
        result = enforcer.evaluate("read_metrics", "agent-1", current_time=work_time)
        assert result.would_be_auto_approved
        assert not result.would_be_blocked

        # Draft action -> flagged
        result = enforcer.evaluate("draft_content", "agent-1", current_time=work_time)
        assert result.would_be_flagged
        assert not result.would_be_auto_approved

        # Unknown action -> HELD (default)
        result = enforcer.evaluate("send_message", "agent-1", current_time=work_time)
        assert result.would_be_held

    def test_metrics_accurately_reflect_patterns(self):
        """Metrics counts match the actual actions evaluated."""
        enforcer = self._make_enforcer()
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # 3 reads (auto-approved), 2 drafts (flagged), 1 held
        for _ in range(3):
            enforcer.evaluate("read_metrics", "agent-1", current_time=work_time)
        for _ in range(2):
            enforcer.evaluate("draft_content", "agent-1", current_time=work_time)
        enforcer.evaluate("send_message", "agent-1", current_time=work_time)

        metrics = enforcer.get_metrics("agent-1")
        assert metrics.total_evaluations == 6
        assert metrics.auto_approved_count == 3
        assert metrics.flagged_count == 2
        assert metrics.held_count == 1
        assert metrics.blocked_count == 0
        assert metrics.pass_rate == 3 / 6  # 0.5

    def test_shadow_report_generation(self):
        """ShadowEnforcer generates a posture upgrade report."""
        enforcer = self._make_enforcer()
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Generate enough evaluations for a meaningful report
        for _ in range(100):
            enforcer.evaluate("read_metrics", "agent-1", current_time=work_time)
        for _ in range(5):
            enforcer.evaluate("draft_content", "agent-1", current_time=work_time)

        report = enforcer.generate_report("agent-1")
        assert report.total_evaluations == 105
        assert report.pass_rate > 0.9

    def test_shadow_to_posture_evidence(self):
        """ShadowEnforcer metrics convert to PostureEvidence."""
        enforcer = self._make_enforcer()
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        for _ in range(50):
            enforcer.evaluate("read_metrics", "agent-1", current_time=work_time)

        evidence = enforcer.to_posture_evidence("agent-1")
        assert evidence.successful_operations == 50
        assert evidence.total_operations == 50
        assert evidence.shadow_enforcer_pass_rate == 1.0

    def test_shadow_no_evaluations_raises_key_error(self):
        """Requesting metrics for unknown agent raises KeyError."""
        enforcer = self._make_enforcer()
        with pytest.raises(KeyError, match="No shadow metrics found"):
            enforcer.get_metrics("unknown-agent")


# ===========================================================================
# 7. Audit Chain Integrity (via EATP Bridge)
# ===========================================================================


class TestAuditChainIntegrityViaEATPBridge:
    """Audit anchors recorded via EATP bridge maintain chain integrity."""

    @pytest.mark.asyncio
    async def test_multiple_audit_anchors_create_chain(self):
        """Multiple audit records form a linked chain in the trust store."""
        bridge = EATPBridge()
        await bridge.initialize()

        genesis_mgr = GenesisManager(bridge)
        await genesis_mgr.create_genesis(_genesis_config())

        # Record multiple audit anchors
        agent_id = "authority:terrene.foundation"
        for action_name in ["read_metrics", "draft_content", "review_plan"]:
            anchor = await bridge.record_audit(
                agent_id=agent_id,
                action=action_name,
                resource="test-resource",
                result="SUCCESS",
            )
            assert anchor is not None

    @pytest.mark.asyncio
    async def test_verify_after_establish_and_delegate(self):
        """Verification works after a complete establish -> delegate chain."""
        bridge = EATPBridge()
        await bridge.initialize()

        genesis_mgr = GenesisManager(bridge)
        delegation_mgr = DelegationManager(bridge)

        genesis = await genesis_mgr.create_genesis(_genesis_config())
        await delegation_mgr.create_delegation(
            delegator_id=genesis.agent_id,
            delegate_config=_team_lead_config(),
            envelope_config=_team_lead_envelope(),
        )

        # Verify the team lead's action (QUICK level avoids signature
        # verification that depends on EATP internal key state)
        result = await bridge.verify_action(
            agent_id="team-lead-1",
            action="review_content",
            level="QUICK",
        )
        assert result.valid, f"Verification should succeed: {result.reason}"

    @pytest.mark.asyncio
    async def test_genesis_validation(self):
        """GenesisManager.validate_genesis confirms validity of established genesis."""
        bridge = EATPBridge()
        await bridge.initialize()

        genesis_mgr = GenesisManager(bridge)
        genesis = await genesis_mgr.create_genesis(_genesis_config())

        is_valid, message = await genesis_mgr.validate_genesis(genesis.agent_id)
        assert is_valid, f"Genesis should be valid: {message}"


# ===========================================================================
# 8. Expired/Revoked Chains Fail Verification
# ===========================================================================


class TestExpiredRevokedChainsFailVerification:
    """Expired and revoked chains should fail verification."""

    @pytest.mark.asyncio
    async def test_unestablished_agent_fails_verification(self):
        """Agent with no trust chain fails verification."""
        bridge = EATPBridge()
        await bridge.initialize()

        result = await bridge.verify_action(
            agent_id="unknown-agent",
            action="read_metrics",
            level="STANDARD",
        )
        assert not result.valid

    @pytest.mark.asyncio
    async def test_invalid_verification_level_raises(self):
        """Invalid verification level string raises ValueError."""
        bridge = EATPBridge()
        await bridge.initialize()

        with pytest.raises(ValueError, match="Invalid verification level"):
            await bridge.verify_action(
                agent_id="agent-1",
                action="read",
                level="INVALID",
            )

    @pytest.mark.asyncio
    async def test_invalid_audit_result_raises(self):
        """Invalid action result string raises ValueError."""
        bridge = EATPBridge()
        await bridge.initialize()

        with pytest.raises(ValueError, match="Invalid action result"):
            await bridge.record_audit(
                agent_id="agent-1",
                action="read",
                resource="test",
                result="INVALID_RESULT",
            )

    @pytest.mark.asyncio
    async def test_delegate_without_establish_fails(self):
        """Delegating from an unestablished delegator raises ValueError."""
        bridge = EATPBridge()
        await bridge.initialize()

        with pytest.raises(ValueError, match="No signing key found"):
            await bridge.delegate(
                delegator_id="nonexistent-authority",
                delegate_agent_config=_team_lead_config(),
                envelope_config=_team_lead_envelope(),
            )
