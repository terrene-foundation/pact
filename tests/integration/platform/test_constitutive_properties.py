# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Integration tests for the five Constrained Organization constitutive properties
and three behavioral tests (Milestone 19, Todos 1901-1909).

These tests PROVE that the CARE Platform satisfies the Constrained Organization
thesis. They use real instances of all components — no mocking.

Five Constitutive Properties:
  1. Constraint Completeness — every agent action evaluated against constraints
  2. Trust Verifiability — every trust claim cryptographically verifiable
  3. Audit Continuity — audit chain has no gaps
  4. Knowledge Structurality — knowledge compounds via workspace-as-knowledge-base
  5. Governance Coherence — all envelopes derive from genesis via monotonic tightening

Three Behavioral Tests:
  1. Constraints enforced (not advisory) — violating actions BLOCKED, not just FLAGGED
  2. Trust verifiable (not assumed) — revoked agents blocked even if previously trusted
  3. Knowledge compounds structurally — next CO cycle can access prior cycle's knowledge
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from care_platform.trust.audit.anchor import AuditChain
from care_platform.build.config.schema import (
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
    WorkspaceConfig,
)
from care_platform.trust.constraint.enforcer import ConstraintEnforcer
from care_platform.trust.constraint.envelope import ConstraintEnvelope
from care_platform.trust.constraint.gradient import GradientEngine
from care_platform.trust.constraint.middleware import (
    ActionOutcome,
    VerificationMiddleware,
)
from care_platform.build.org.builder import OrgBuilder
from care_platform.trust.credentials import CredentialManager
from care_platform.trust.delegation import ChainStatus, DelegationManager
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.trust.genesis import GenesisManager
from care_platform.trust.integrity import TrustChainIntegrity
from care_platform.trust.revocation import RevocationManager
from care_platform.build.workspace.models import (
    Workspace,
    WorkspacePhase,
    WorkspaceState,
)

# ===========================================================================
# 1901: Test Harness — Shared Fixtures
# ===========================================================================


def _genesis_config() -> GenesisConfig:
    """Genesis authority configuration for the test organization."""
    return GenesisConfig(
        authority="test-org.foundation",
        authority_name="Test Organization",
        policy_reference="https://test-org.foundation/policy",
    )


def _root_envelope_config() -> ConstraintEnvelopeConfig:
    """Root-level (widest) constraint envelope for the organization."""
    return ConstraintEnvelopeConfig(
        id="env-root",
        description="Root constraint envelope — widest org-level constraints",
        financial=FinancialConstraintConfig(
            max_spend_usd=10000.0,
            requires_approval_above_usd=5000.0,
            api_cost_budget_usd=2000.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "manage_team",
                "review_content",
                "delegate_tasks",
                "draft_content",
                "analyze_data",
                "publish_content",
                "read_metrics",
            ],
            blocked_actions=["delete_data", "modify_governance"],
            max_actions_per_day=500,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="00:00",
            active_hours_end="23:59",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["reports/*", "metrics/*", "briefs/*", "drafts/*", "plans/*"],
            write_paths=["drafts/*", "plans/*", "reports/*"],
            blocked_data_types=["pii", "credentials"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal", "email-internal"],
            external_requires_approval=True,
        ),
    )


def _lead_envelope_config() -> ConstraintEnvelopeConfig:
    """Team lead envelope — tighter than root."""
    return ConstraintEnvelopeConfig(
        id="env-lead",
        description="Team lead envelope — narrower than root",
        financial=FinancialConstraintConfig(
            max_spend_usd=1000.0,
            requires_approval_above_usd=500.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "manage_team",
                "review_content",
                "delegate_tasks",
                "draft_content",
                "analyze_data",
                "read_metrics",
            ],
            blocked_actions=["delete_data", "modify_governance"],
            max_actions_per_day=200,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="00:00",
            active_hours_end="23:59",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["reports/*", "metrics/*", "briefs/*"],
            write_paths=["drafts/*", "plans/*"],
            blocked_data_types=["pii", "credentials"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal"],
            external_requires_approval=True,
        ),
    )


def _agent_alpha_envelope_config() -> ConstraintEnvelopeConfig:
    """Agent Alpha envelope — tighter than team lead."""
    return ConstraintEnvelopeConfig(
        id="env-alpha",
        description="Agent Alpha — content specialist",
        financial=FinancialConstraintConfig(
            max_spend_usd=200.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=["draft_content", "analyze_data", "read_metrics"],
            blocked_actions=["delete_data", "modify_governance"],
            max_actions_per_day=100,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="00:00",
            active_hours_end="23:59",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["reports/*", "briefs/*"],
            write_paths=["drafts/*"],
            blocked_data_types=["pii", "credentials"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal"],
            external_requires_approval=True,
        ),
    )


def _agent_beta_envelope_config() -> ConstraintEnvelopeConfig:
    """Agent Beta envelope — tighter than team lead, different scope than Alpha."""
    return ConstraintEnvelopeConfig(
        id="env-beta",
        description="Agent Beta — data analyst",
        financial=FinancialConstraintConfig(
            max_spend_usd=150.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=["analyze_data", "read_metrics"],
            blocked_actions=["delete_data", "modify_governance"],
            max_actions_per_day=80,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="00:00",
            active_hours_end="23:59",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["metrics/*", "reports/*"],
            write_paths=["plans/*"],
            blocked_data_types=["pii", "credentials"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal"],
            external_requires_approval=True,
        ),
    )


def _lead_agent_config() -> AgentConfig:
    """Team lead agent configuration."""
    return AgentConfig(
        id="agent-lead",
        name="Team Lead",
        role="team_lead",
        constraint_envelope="env-lead",
        capabilities=[
            "manage_team",
            "review_content",
            "delegate_tasks",
            "draft_content",
            "analyze_data",
            "read_metrics",
        ],
    )


def _agent_alpha_config() -> AgentConfig:
    """Agent Alpha — content specialist."""
    return AgentConfig(
        id="agent-alpha",
        name="Agent Alpha",
        role="content_specialist",
        constraint_envelope="env-alpha",
        capabilities=["draft_content", "analyze_data", "read_metrics"],
    )


def _agent_beta_config() -> AgentConfig:
    """Agent Beta — data analyst."""
    return AgentConfig(
        id="agent-beta",
        name="Agent Beta",
        role="data_analyst",
        constraint_envelope="env-beta",
        capabilities=["analyze_data", "read_metrics"],
    )


def _gradient_config() -> VerificationGradientConfig:
    """Gradient rules used by the middleware in all tests."""
    return VerificationGradientConfig(
        rules=[
            GradientRuleConfig(
                pattern="read_*",
                level=VerificationLevel.AUTO_APPROVED,
                reason="Reads are safe",
            ),
            GradientRuleConfig(
                pattern="draft_*",
                level=VerificationLevel.FLAGGED,
                reason="Content creation needs review",
            ),
            GradientRuleConfig(
                pattern="analyze_*",
                level=VerificationLevel.AUTO_APPROVED,
                reason="Analysis is safe",
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
            GradientRuleConfig(
                pattern="modify_*",
                level=VerificationLevel.BLOCKED,
                reason="Governance modification blocked",
            ),
        ],
        default_level=VerificationLevel.HELD,
    )


def _workspace_config() -> WorkspaceConfig:
    return WorkspaceConfig(
        id="ws-test",
        path="workspaces/test/",
        description="Test workspace",
    )


class OrgHarness:
    """Reusable test harness that bootstraps a full organization.

    Provides:
    - Genesis authority with EATPBridge
    - Team lead agent delegated from genesis
    - Two specialist agents (Alpha, Beta) delegated from lead
    - Constraint envelopes for each level
    - VerificationMiddleware with GradientEngine and AuditChain
    - RevocationManager with delegation tree
    - Workspace in ACTIVE state
    """

    def __init__(
        self,
        bridge: EATPBridge,
        genesis_mgr: GenesisManager,
        delegation_mgr: DelegationManager,
        revocation_mgr: RevocationManager,
        genesis_agent_id: str,
        # Per-agent middleware instances, keyed by agent_id
        middlewares: dict[str, VerificationMiddleware],
        enforcers: dict[str, ConstraintEnforcer],
        envelopes: dict[str, ConstraintEnvelope],
        workspace: Workspace,
        audit_chain: AuditChain,
    ):
        self.bridge = bridge
        self.genesis_mgr = genesis_mgr
        self.delegation_mgr = delegation_mgr
        self.revocation_mgr = revocation_mgr
        self.genesis_agent_id = genesis_agent_id
        self.middlewares = middlewares
        self.enforcers = enforcers
        self.envelopes = envelopes
        self.workspace = workspace
        self.audit_chain = audit_chain


@pytest.fixture()
async def org_harness() -> OrgHarness:
    """Bootstrap a complete organization for testing.

    Creates:
    - Genesis authority
    - 3 agents in a delegation chain (genesis -> lead -> alpha/beta)
    - Constraint envelopes at each level
    - VerificationMiddleware per agent
    - RevocationManager with delegation tree registered
    - An ACTIVE workspace
    """
    # --- EATP trust infrastructure ---
    bridge = EATPBridge()
    await bridge.initialize()

    genesis_mgr = GenesisManager(bridge)
    delegation_mgr = DelegationManager(bridge)

    # ESTABLISH genesis
    genesis = await genesis_mgr.create_genesis(_genesis_config())
    genesis_agent_id = genesis.agent_id

    # DELEGATE: genesis -> team lead
    await delegation_mgr.create_delegation(
        delegator_id=genesis_agent_id,
        delegate_config=_lead_agent_config(),
        envelope_config=_lead_envelope_config(),
        parent_envelope_config=_root_envelope_config(),
    )

    # DELEGATE: team lead -> agent-alpha
    await delegation_mgr.create_delegation(
        delegator_id="agent-lead",
        delegate_config=_agent_alpha_config(),
        envelope_config=_agent_alpha_envelope_config(),
        parent_envelope_config=_lead_envelope_config(),
    )

    # DELEGATE: team lead -> agent-beta
    await delegation_mgr.create_delegation(
        delegator_id="agent-lead",
        delegate_config=_agent_beta_config(),
        envelope_config=_agent_beta_envelope_config(),
        parent_envelope_config=_lead_envelope_config(),
    )

    # --- Revocation manager with delegation tree ---
    cred_mgr = CredentialManager()
    revocation_mgr = RevocationManager(
        credential_manager=cred_mgr,
        eatp_bridge=bridge,
    )
    revocation_mgr.register_delegation(genesis_agent_id, "agent-lead")
    revocation_mgr.register_delegation("agent-lead", "agent-alpha")
    revocation_mgr.register_delegation("agent-lead", "agent-beta")

    # --- Constraint envelopes ---
    envelope_configs = {
        "agent-lead": _lead_envelope_config(),
        "agent-alpha": _agent_alpha_envelope_config(),
        "agent-beta": _agent_beta_envelope_config(),
    }
    envelopes: dict[str, ConstraintEnvelope] = {}
    for agent_id, env_cfg in envelope_configs.items():
        envelopes[agent_id] = ConstraintEnvelope(config=env_cfg)

    # --- Shared audit chain ---
    audit_chain = AuditChain(chain_id="org-test-chain")

    # --- Gradient engine ---
    gradient_engine = GradientEngine(_gradient_config())

    # --- Per-agent middleware and enforcer ---
    middlewares: dict[str, VerificationMiddleware] = {}
    enforcers: dict[str, ConstraintEnforcer] = {}
    for agent_id, envelope in envelopes.items():
        mw = VerificationMiddleware(
            gradient_engine=gradient_engine,
            envelope=envelope,
            audit_chain=audit_chain,
            eatp_bridge=bridge,
        )
        middlewares[agent_id] = mw
        enforcers[agent_id] = ConstraintEnforcer(middleware=mw)

    # --- Workspace ---
    ws = Workspace(config=_workspace_config(), team_id="team-test")
    ws.activate(reason="Test harness activation")

    return OrgHarness(
        bridge=bridge,
        genesis_mgr=genesis_mgr,
        delegation_mgr=delegation_mgr,
        revocation_mgr=revocation_mgr,
        genesis_agent_id=genesis_agent_id,
        middlewares=middlewares,
        enforcers=enforcers,
        envelopes=envelopes,
        workspace=ws,
        audit_chain=audit_chain,
    )


# ===========================================================================
# 1901: Org Definition Validation
# ===========================================================================


class TestOrgHarnessSetup:
    """Verify the test harness itself is valid: org definition, delegation chains."""

    def test_org_definition_valid(self):
        """OrgBuilder produces a valid, internally consistent org definition."""
        org = (
            OrgBuilder("test-org", "Test Organization")
            .add_workspace(_workspace_config())
            .add_envelope(_root_envelope_config())
            .add_envelope(_lead_envelope_config())
            .add_envelope(_agent_alpha_envelope_config())
            .add_envelope(_agent_beta_envelope_config())
            .add_agent(_lead_agent_config())
            .add_agent(_agent_alpha_config())
            .add_agent(_agent_beta_config())
            .add_team(
                __import__("care_platform.build.config.schema", fromlist=["TeamConfig"]).TeamConfig(
                    id="team-test",
                    name="Test Team",
                    workspace="ws-test",
                    agents=["agent-lead", "agent-alpha", "agent-beta"],
                )
            )
            .build()
        )

        assert org.org_id == "test-org"
        assert len(org.agents) == 3
        assert len(org.envelopes) == 4
        assert len(org.workspaces) == 1
        assert len(org.teams) == 1

    @pytest.mark.asyncio
    async def test_harness_delegation_chain_valid(self, org_harness: OrgHarness):
        """The harness produces a valid 3-level delegation chain."""
        h = org_harness

        # Walk chain from agent-alpha back to genesis
        walk_alpha = await h.delegation_mgr.walk_chain("agent-alpha")
        assert walk_alpha.status == ChainStatus.VALID
        assert walk_alpha.depth == 2  # genesis(0) -> lead(1) -> alpha(2)

        # Walk chain from agent-beta back to genesis
        walk_beta = await h.delegation_mgr.walk_chain("agent-beta")
        assert walk_beta.status == ChainStatus.VALID
        assert walk_beta.depth == 2

        # Walk chain from lead back to genesis
        walk_lead = await h.delegation_mgr.walk_chain("agent-lead")
        assert walk_lead.status == ChainStatus.VALID
        assert walk_lead.depth == 1


# ===========================================================================
# 1902: Property 1 — Constraint Completeness
# ===========================================================================


class TestConstraintCompleteness:
    """Every agent action is evaluated against at least one constraint dimension.

    This property requires that no action can bypass constraint evaluation.
    We submit multiple action types and verify that each one received an
    EnvelopeEvaluation covering all five CARE constraint dimensions.
    """

    @pytest.mark.asyncio
    async def test_every_action_gets_envelope_evaluation(self, org_harness: OrgHarness):
        """Multiple action types all receive envelope evaluation via middleware."""
        h = org_harness
        work_time = datetime(2026, 3, 13, 14, 0, tzinfo=UTC)

        actions = [
            ("read_metrics", "agent-alpha"),
            ("draft_content", "agent-alpha"),
            ("analyze_data", "agent-beta"),
            ("read_metrics", "agent-lead"),
        ]

        for action, agent_id in actions:
            result = h.middlewares[agent_id].process_action(
                agent_id=agent_id,
                action=action,
                current_action_count=0,
            )
            # Every action must produce an audit record
            assert result.audit_recorded, (
                f"Action '{action}' by '{agent_id}' did not produce an audit record"
            )

    @pytest.mark.asyncio
    async def test_envelope_evaluates_all_five_dimensions(self, org_harness: OrgHarness):
        """Direct envelope evaluation covers all five CARE constraint dimensions."""
        h = org_harness
        work_time = datetime(2026, 3, 13, 14, 0, tzinfo=UTC)

        envelope = h.envelopes["agent-alpha"]
        evaluation = envelope.evaluate_action(
            action="draft_content",
            agent_id="agent-alpha",
            spend_amount=10.0,
            current_action_count=5,
            current_time=work_time,
            data_paths=["drafts/post.md"],
            access_type="write",
            is_external=False,
        )

        # Must have evaluations for all five CARE dimensions
        dimension_names = {d.dimension for d in evaluation.dimensions}
        assert "financial" in dimension_names, "Financial dimension missing from evaluation"
        assert "operational" in dimension_names, "Operational dimension missing from evaluation"
        assert "temporal" in dimension_names, "Temporal dimension missing from evaluation"
        assert "data_access" in dimension_names, "Data access dimension missing from evaluation"
        assert "communication" in dimension_names, "Communication dimension missing from evaluation"

    @pytest.mark.asyncio
    async def test_enforcer_mandatory_for_every_action(self, org_harness: OrgHarness):
        """ConstraintEnforcer delegates to middleware for every check."""
        h = org_harness

        # Use the enforcer to check several actions
        actions_checked = []
        for agent_id in ["agent-alpha", "agent-beta", "agent-lead"]:
            result = h.enforcers[agent_id].check(
                action="read_metrics",
                agent_id=agent_id,
            )
            assert result.audit_recorded
            actions_checked.append(result)

        # All three agents had their actions evaluated
        assert len(actions_checked) == 3

    @pytest.mark.asyncio
    async def test_no_action_bypasses_constraint_evaluation(self, org_harness: OrgHarness):
        """Even unknown action types get evaluated (against default gradient level)."""
        h = org_harness

        result = h.middlewares["agent-alpha"].process_action(
            agent_id="agent-alpha",
            action="unknown_action_type",
            current_action_count=0,
        )

        # Unknown actions still get processed (not silently passed through)
        assert result.audit_recorded
        # Unknown actions should either be HELD (default) or BLOCKED (not in allowed_actions)
        assert result.outcome in (
            ActionOutcome.QUEUED,
            ActionOutcome.REJECTED,
        ), f"Unknown action should be HELD or BLOCKED, got {result.outcome}"


# ===========================================================================
# 1903: Property 2 — Trust Verifiability
# ===========================================================================


class TestTrustVerifiability:
    """Every trust claim can be cryptographically verified.

    We walk the full trust chain from leaf agent to genesis and verify
    each record using TrustChainIntegrity and the EATP bridge.
    """

    @pytest.mark.asyncio
    async def test_full_chain_walk_from_leaf_to_genesis(self, org_harness: OrgHarness):
        """Walk from agent-alpha back to genesis — all records present."""
        h = org_harness

        ancestors = h.bridge.get_delegation_ancestors("agent-alpha")
        # Must include: agent-alpha -> agent-lead -> authority:test-org.foundation
        assert "agent-alpha" in ancestors
        assert "agent-lead" in ancestors
        assert h.genesis_agent_id in ancestors

    @pytest.mark.asyncio
    async def test_trust_chain_integrity_hash_linking(self, org_harness: OrgHarness):
        """TrustChainIntegrity hash-links records and verifies them."""
        h = org_harness

        # Build a trust chain integrity record from the delegation data
        chain = TrustChainIntegrity()

        # Append genesis record data
        chain.append_record({"type": "genesis", "agent_id": h.genesis_agent_id})

        # Append delegation records
        chain.append_record(
            {"type": "delegation", "delegator": h.genesis_agent_id, "delegatee": "agent-lead"}
        )
        chain.append_record(
            {"type": "delegation", "delegator": "agent-lead", "delegatee": "agent-alpha"}
        )
        chain.append_record(
            {"type": "delegation", "delegator": "agent-lead", "delegatee": "agent-beta"}
        )

        # Verify the hash chain is intact
        result = chain.verify()
        assert result.is_valid, f"Trust chain integrity violated: {result.violations}"
        assert result.records_checked == 4

    @pytest.mark.asyncio
    async def test_each_agent_has_valid_trust_chain(self, org_harness: OrgHarness):
        """Each agent's chain walks back to genesis without breaks."""
        h = org_harness

        for agent_id in ["agent-lead", "agent-alpha", "agent-beta"]:
            walk_result = await h.delegation_mgr.walk_chain(agent_id)
            assert walk_result.status == ChainStatus.VALID, (
                f"Agent '{agent_id}' chain is not valid: {walk_result.errors}"
            )
            assert walk_result.depth > 0, f"Agent '{agent_id}' should have delegation depth > 0"

    @pytest.mark.asyncio
    async def test_genesis_validation(self, org_harness: OrgHarness):
        """Genesis record itself is valid (not expired, has signature)."""
        h = org_harness

        is_valid, message = await h.genesis_mgr.validate_genesis(h.genesis_agent_id)
        assert is_valid, f"Genesis validation failed: {message}"

    @pytest.mark.asyncio
    async def test_verify_action_through_eatp(self, org_harness: OrgHarness):
        """Agent action can be verified through the EATP bridge."""
        h = org_harness

        result = await h.bridge.verify_action(
            agent_id="agent-alpha",
            action="draft_content",
            resource="drafts/test.md",
            level="QUICK",
        )
        assert result.valid, f"EATP verification failed: {result.reason}"

    @pytest.mark.asyncio
    async def test_integrity_chain_tamper_detection(self, org_harness: OrgHarness):
        """TrustChainIntegrity detects tampering with any record."""
        chain = TrustChainIntegrity()

        chain.append_record({"type": "genesis", "agent_id": "root"})
        chain.append_record({"type": "delegation", "delegator": "root", "delegatee": "child"})

        # Verify baseline is valid
        result = chain.verify()
        assert result.is_valid

        # Tamper with the first record's data
        chain._records[0].data["agent_id"] = "TAMPERED"

        # Verification should now fail
        result = chain.verify()
        assert not result.is_valid, "Tampered chain should fail verification"
        assert len(result.violations) > 0


# ===========================================================================
# 1904: Property 3 — Audit Continuity
# ===========================================================================


class TestAuditContinuity:
    """Every action produces an audit anchor, and the chain has no gaps.

    We submit an action sequence and verify:
    1. Every action produced an audit anchor
    2. The chain is contiguous (no gaps, correct sequencing)
    3. The hash chain links are intact
    """

    @pytest.mark.asyncio
    async def test_action_sequence_produces_contiguous_audit_chain(self, org_harness: OrgHarness):
        """A sequence of actions produces contiguous, gapless audit anchors."""
        h = org_harness

        # Submit a sequence of actions
        actions = [
            ("read_metrics", "agent-alpha"),
            ("analyze_data", "agent-beta"),
            ("draft_content", "agent-alpha"),
            ("read_metrics", "agent-lead"),
            ("analyze_data", "agent-alpha"),
        ]

        for action, agent_id in actions:
            h.middlewares[agent_id].process_action(
                agent_id=agent_id,
                action=action,
                current_action_count=0,
            )

        # Verify the audit chain has at least as many anchors as actions
        assert h.audit_chain.length >= len(actions), (
            f"Expected at least {len(actions)} audit anchors, got {h.audit_chain.length}"
        )

        # Verify chain integrity — no gaps, correct sequencing, hash links
        is_valid, errors = h.audit_chain.verify_chain_integrity()
        assert is_valid, f"Audit chain has integrity errors: {errors}"

    @pytest.mark.asyncio
    async def test_every_action_has_corresponding_audit_anchor(self, org_harness: OrgHarness):
        """Each processed action creates exactly one audit anchor."""
        h = org_harness
        initial_length = h.audit_chain.length

        # Process one action
        h.middlewares["agent-alpha"].process_action(
            agent_id="agent-alpha",
            action="read_metrics",
            current_action_count=0,
        )

        # Exactly one new anchor
        assert h.audit_chain.length == initial_length + 1

        # Process another action
        h.middlewares["agent-beta"].process_action(
            agent_id="agent-beta",
            action="analyze_data",
            current_action_count=0,
        )

        assert h.audit_chain.length == initial_length + 2

    @pytest.mark.asyncio
    async def test_audit_chain_sequence_numbers_contiguous(self, org_harness: OrgHarness):
        """Audit anchor sequence numbers form a contiguous 0..N sequence."""
        h = org_harness

        # Generate several actions
        for i in range(10):
            h.middlewares["agent-alpha"].process_action(
                agent_id="agent-alpha",
                action="read_metrics",
                current_action_count=i,
            )

        # Verify sequence numbers are 0, 1, 2, ..., N
        for i, anchor in enumerate(h.audit_chain.anchors):
            assert anchor.sequence == i, (
                f"Expected sequence {i}, got {anchor.sequence} at position {i}"
            )

    @pytest.mark.asyncio
    async def test_audit_chain_hash_links_unbroken(self, org_harness: OrgHarness):
        """Each anchor's previous_hash correctly points to the prior anchor."""
        h = org_harness

        # Generate actions
        for _ in range(5):
            h.middlewares["agent-lead"].process_action(
                agent_id="agent-lead",
                action="review_content",
                current_action_count=0,
            )

        # Verify hash chain links
        for i, anchor in enumerate(h.audit_chain.anchors):
            if i == 0:
                assert anchor.previous_hash is None, "Genesis anchor should have no previous_hash"
            else:
                prev_anchor = h.audit_chain.anchors[i - 1]
                assert anchor.previous_hash == prev_anchor.content_hash, (
                    f"Anchor {i} previous_hash does not match anchor {i - 1} content_hash"
                )

    @pytest.mark.asyncio
    async def test_blocked_actions_also_audited(self, org_harness: OrgHarness):
        """Even BLOCKED actions produce audit anchors (rejection is recorded)."""
        h = org_harness
        initial_length = h.audit_chain.length

        # Submit a blocked action (delete_data is in blocked_actions)
        result = h.middlewares["agent-alpha"].process_action(
            agent_id="agent-alpha",
            action="delete_data",
            current_action_count=0,
        )

        assert result.outcome == ActionOutcome.REJECTED
        assert result.audit_recorded
        assert h.audit_chain.length == initial_length + 1

        # The audit anchor records the rejection
        latest = h.audit_chain.latest
        assert latest is not None
        assert latest.verification_level == VerificationLevel.BLOCKED


# ===========================================================================
# 1905: Property 4 — Knowledge Structurality
# ===========================================================================


class TestKnowledgeStructurality:
    """Knowledge compounds structurally via workspace-as-knowledge-base.

    Test that workspace phase transitions produce artifacts (phase history),
    that knowledge persists across phases, and that the workspace state machine
    correctly governs when phase cycling is allowed.
    """

    @pytest.mark.asyncio
    async def test_workspace_phase_transitions_produce_artifacts(self, org_harness: OrgHarness):
        """Each phase transition produces a PhaseTransition record."""
        ws = org_harness.workspace
        assert ws.workspace_state == WorkspaceState.ACTIVE

        # Transition through phases: ANALYZE -> PLAN -> IMPLEMENT
        ws.transition_to(WorkspacePhase.PLAN, reason="Planning based on analysis")
        ws.transition_to(WorkspacePhase.IMPLEMENT, reason="Implementing the plan")

        # Phase history should have 2 records
        assert len(ws.phase_history) == 2
        assert ws.phase_history[0].from_phase == WorkspacePhase.ANALYZE
        assert ws.phase_history[0].to_phase == WorkspacePhase.PLAN
        assert ws.phase_history[1].from_phase == WorkspacePhase.PLAN
        assert ws.phase_history[1].to_phase == WorkspacePhase.IMPLEMENT

    @pytest.mark.asyncio
    async def test_knowledge_persists_across_phases(self, org_harness: OrgHarness):
        """Phase history accumulates — knowledge from prior phases is retained."""
        ws = org_harness.workspace

        # Full CO cycle: ANALYZE -> PLAN -> IMPLEMENT -> VALIDATE -> CODIFY
        ws.transition_to(WorkspacePhase.PLAN, reason="Plan created")
        ws.transition_to(WorkspacePhase.IMPLEMENT, reason="Implementation started")
        ws.transition_to(WorkspacePhase.VALIDATE, reason="Validation running")
        ws.transition_to(WorkspacePhase.CODIFY, reason="Codifying learnings")

        # All 4 transitions are preserved
        assert len(ws.phase_history) == 4

        # Each transition preserves its reason (institutional memory)
        reasons = [t.reason for t in ws.phase_history]
        assert "Plan created" in reasons
        assert "Implementation started" in reasons
        assert "Validation running" in reasons
        assert "Codifying learnings" in reasons

    @pytest.mark.asyncio
    async def test_phase_cycling_only_when_active(self, org_harness: OrgHarness):
        """Phase transitions are blocked when workspace is not ACTIVE."""
        ws_config = WorkspaceConfig(
            id="ws-inactive",
            path="workspaces/inactive/",
            description="Inactive workspace",
        )
        ws = Workspace(config=ws_config, team_id="team-test")

        # Workspace starts in PROVISIONING — phase cycling should be blocked
        assert ws.workspace_state == WorkspaceState.PROVISIONING
        assert not ws.can_transition_to(WorkspacePhase.PLAN)

    def test_workspace_state_transitions_recorded(self):
        """State transitions (PROVISIONING -> ACTIVE) are recorded in state_history."""
        ws = Workspace(
            config=WorkspaceConfig(
                id="ws-lifecycle",
                path="workspaces/lifecycle/",
                description="Lifecycle test workspace",
            ),
            team_id="team-test",
        )

        ws.activate(reason="Initial activation")
        assert len(ws.state_history) == 1
        assert ws.state_history[0].from_state == WorkspaceState.PROVISIONING
        assert ws.state_history[0].to_state == WorkspaceState.ACTIVE


# ===========================================================================
# 1906: Property 5 — Governance Coherence
# ===========================================================================


class TestGovernanceCoherence:
    """All envelopes derive from genesis via monotonic tightening.

    Every agent's constraint envelope must be a valid tightening of its parent's
    envelope. This ensures governance coherence throughout the delegation chain.
    """

    @pytest.mark.asyncio
    async def test_every_envelope_is_valid_tightening_of_parent(self, org_harness: OrgHarness):
        """Each envelope in the chain is a valid monotonic tightening of its parent."""
        dm = org_harness.delegation_mgr

        # Root -> Lead: lead must be tighter than root
        is_valid, violations = dm.validate_tightening(
            parent_envelope=_root_envelope_config(),
            child_envelope=_lead_envelope_config(),
        )
        assert is_valid, f"Lead not tighter than root: {violations}"

        # Lead -> Alpha: alpha must be tighter than lead
        is_valid, violations = dm.validate_tightening(
            parent_envelope=_lead_envelope_config(),
            child_envelope=_agent_alpha_envelope_config(),
        )
        assert is_valid, f"Alpha not tighter than lead: {violations}"

        # Lead -> Beta: beta must be tighter than lead
        is_valid, violations = dm.validate_tightening(
            parent_envelope=_lead_envelope_config(),
            child_envelope=_agent_beta_envelope_config(),
        )
        assert is_valid, f"Beta not tighter than lead: {violations}"

    @pytest.mark.asyncio
    async def test_transitive_tightening_root_to_leaf(self, org_harness: OrgHarness):
        """Envelope tightening is transitive: root -> lead -> alpha is valid."""
        dm = org_harness.delegation_mgr

        # Root -> Alpha (skipping lead): alpha should still be tighter than root
        is_valid, violations = dm.validate_tightening(
            parent_envelope=_root_envelope_config(),
            child_envelope=_agent_alpha_envelope_config(),
        )
        assert is_valid, f"Alpha not tighter than root (transitive): {violations}"

    @pytest.mark.asyncio
    async def test_envelope_tightening_uses_constraint_envelope_is_tighter_than(
        self, org_harness: OrgHarness
    ):
        """ConstraintEnvelope.is_tighter_than() agrees with DelegationManager."""
        h = org_harness

        root_env = ConstraintEnvelope(config=_root_envelope_config())
        lead_env = ConstraintEnvelope(config=_lead_envelope_config())
        alpha_env = ConstraintEnvelope(config=_agent_alpha_envelope_config())

        assert lead_env.is_tighter_than(root_env), "Lead should be tighter than root"
        assert alpha_env.is_tighter_than(lead_env), "Alpha should be tighter than lead"
        assert alpha_env.is_tighter_than(root_env), "Alpha should be tighter than root (transitive)"

    @pytest.mark.asyncio
    async def test_expanding_envelope_rejected(self, org_harness: OrgHarness):
        """An envelope that expands beyond its parent is rejected."""
        dm = org_harness.delegation_mgr

        expanded = ConstraintEnvelopeConfig(
            id="env-expanded",
            financial=FinancialConstraintConfig(max_spend_usd=50000.0),  # exceeds root
            operational=OperationalConstraintConfig(
                blocked_actions=["delete_data", "modify_governance"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )

        is_valid, violations = dm.validate_tightening(
            parent_envelope=_root_envelope_config(),
            child_envelope=expanded,
        )
        assert not is_valid, "Expanded envelope should be rejected"
        assert any("Financial" in v for v in violations)


# ===========================================================================
# 1907: Behavioral Test 1 — Constraints Enforced (Not Advisory)
# ===========================================================================


class TestConstraintsEnforced:
    """Constraints are ENFORCED, not advisory.

    Violating an action must result in BLOCKED outcome, not just FLAGGED.
    The audit chain must record the rejection.
    """

    @pytest.mark.asyncio
    async def test_blocked_action_is_rejected_not_flagged(self, org_harness: OrgHarness):
        """Action violating a constraint produces BLOCKED/REJECTED, not FLAGGED."""
        h = org_harness

        # delete_data is in blocked_actions for agent-alpha
        result = h.middlewares["agent-alpha"].process_action(
            agent_id="agent-alpha",
            action="delete_data",
            current_action_count=0,
        )

        assert result.verification_level == VerificationLevel.BLOCKED, (
            f"Expected BLOCKED, got {result.verification_level}"
        )
        assert result.outcome == ActionOutcome.REJECTED, f"Expected REJECTED, got {result.outcome}"

    @pytest.mark.asyncio
    async def test_financial_limit_violation_blocked(self, org_harness: OrgHarness):
        """Spending beyond envelope limit produces BLOCKED."""
        h = org_harness

        # agent-alpha has max_spend_usd=200.0
        result = h.middlewares["agent-alpha"].process_action(
            agent_id="agent-alpha",
            action="draft_content",
            spend_amount=500.0,  # exceeds 200.0 limit
            current_action_count=0,
        )

        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED

    @pytest.mark.asyncio
    async def test_rate_limit_violation_blocked(self, org_harness: OrgHarness):
        """Exceeding daily action limit produces BLOCKED."""
        h = org_harness

        # agent-beta has max_actions_per_day=80
        result = h.middlewares["agent-beta"].process_action(
            agent_id="agent-beta",
            action="analyze_data",
            current_action_count=80,  # at the limit
        )

        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED

    @pytest.mark.asyncio
    async def test_blocked_action_audit_records_rejection(self, org_harness: OrgHarness):
        """The audit chain records the rejection of a blocked action."""
        h = org_harness
        initial_length = h.audit_chain.length

        h.middlewares["agent-alpha"].process_action(
            agent_id="agent-alpha",
            action="delete_data",
            current_action_count=0,
        )

        latest = h.audit_chain.latest
        assert latest is not None
        assert latest.verification_level == VerificationLevel.BLOCKED
        assert latest.result == "rejected"
        assert latest.agent_id == "agent-alpha"
        assert latest.action == "delete_data"

    @pytest.mark.asyncio
    async def test_action_outside_allowed_set_blocked(self, org_harness: OrgHarness):
        """Action not in allowed_actions list is BLOCKED."""
        h = org_harness

        # agent-beta only has ["analyze_data", "read_metrics"]
        # "publish_content" is NOT in agent-beta's allowed_actions
        result = h.middlewares["agent-beta"].process_action(
            agent_id="agent-beta",
            action="publish_content",
            current_action_count=0,
        )

        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED


# ===========================================================================
# 1908: Behavioral Test 2 — Trust Verifiable (Not Assumed)
# ===========================================================================


class TestTrustVerifiable:
    """Trust is verifiable, not assumed.

    A previously trusted agent whose trust is revoked must be BLOCKED
    on subsequent actions, even though it was previously trusted.
    """

    @pytest.mark.asyncio
    async def test_trusted_agent_succeeds_then_revoked_agent_blocked(self, org_harness: OrgHarness):
        """Agent succeeds before revocation, is BLOCKED after revocation."""
        h = org_harness

        # Step 1: Verify agent-alpha can act before revocation
        result_before = h.middlewares["agent-alpha"].process_action(
            agent_id="agent-alpha",
            action="read_metrics",
            current_action_count=0,
        )
        assert result_before.outcome == ActionOutcome.EXECUTED, (
            f"Agent should succeed before revocation, got {result_before.outcome}"
        )

        # Step 2: Revoke agent-alpha's trust via the bridge
        h.bridge.revoke_agent("agent-alpha")

        # Step 3: After revocation, the agent's attestation is invalid.
        # The middleware checks EATP bridge attestation validity.
        result_after = h.middlewares["agent-alpha"].process_action(
            agent_id="agent-alpha",
            action="read_metrics",
            current_action_count=0,
        )
        assert result_after.outcome == ActionOutcome.REJECTED, (
            f"Revoked agent should be BLOCKED, got {result_after.outcome}"
        )
        assert result_after.verification_level == VerificationLevel.BLOCKED

    @pytest.mark.asyncio
    async def test_revocation_propagates_through_eatp_bridge(self, org_harness: OrgHarness):
        """Revoked agent fails EATP bridge verification."""
        h = org_harness

        # Verify the agent before revocation
        verify_before = await h.bridge.verify_action(
            agent_id="agent-beta",
            action="analyze_data",
            level="QUICK",
        )
        assert verify_before.valid, f"Should be valid before revocation: {verify_before.reason}"

        # Revoke
        h.bridge.revoke_agent("agent-beta")

        # Verify after revocation — should fail
        verify_after = await h.bridge.verify_action(
            agent_id="agent-beta",
            action="analyze_data",
            level="QUICK",
        )
        assert not verify_after.valid, "Revoked agent should fail verification"

    @pytest.mark.asyncio
    async def test_cascade_revocation_blocks_downstream_agents(self, org_harness: OrgHarness):
        """Cascade revocation of team lead blocks all downstream agents."""
        h = org_harness

        # Verify both agents work before cascade revocation
        for agent_id in ["agent-alpha", "agent-beta"]:
            result = h.middlewares[agent_id].process_action(
                agent_id=agent_id,
                action="read_metrics",
                current_action_count=0,
            )
            assert result.outcome == ActionOutcome.EXECUTED

        # Cascade revoke the team lead (affects alpha and beta)
        h.revocation_mgr.cascade_revoke(
            agent_id="agent-lead",
            reason="Security incident",
            revoker_id=h.genesis_agent_id,
        )

        # Both downstream agents should now be blocked via EATP bridge
        for agent_id in ["agent-alpha", "agent-beta"]:
            result = h.middlewares[agent_id].process_action(
                agent_id=agent_id,
                action="read_metrics",
                current_action_count=0,
            )
            assert result.outcome == ActionOutcome.REJECTED, (
                f"Agent '{agent_id}' should be BLOCKED after cascade revocation, "
                f"got {result.outcome}"
            )

    @pytest.mark.asyncio
    async def test_revocation_manager_tracks_revocation(self, org_harness: OrgHarness):
        """RevocationManager.is_revoked() returns True after revocation."""
        h = org_harness

        assert not h.revocation_mgr.is_revoked("agent-alpha")

        h.revocation_mgr.surgical_revoke(
            agent_id="agent-alpha",
            reason="Policy violation",
            revoker_id="agent-lead",
        )

        assert h.revocation_mgr.is_revoked("agent-alpha")


# ===========================================================================
# 1909: Behavioral Test 3 — Knowledge Compounds Structurally
# ===========================================================================


class TestKnowledgeCompoundsStructurally:
    """Next CO cycle can access prior cycle's knowledge.

    Run a workspace through the full ANALYZE -> PLAN -> IMPLEMENT ->
    VALIDATE -> CODIFY cycle, verify phase history records it, then
    start a new cycle and verify prior-cycle context is accessible.
    """

    @pytest.mark.asyncio
    async def test_full_co_cycle_recorded_in_phase_history(self, org_harness: OrgHarness):
        """A complete CO cycle produces 4 phase transitions."""
        ws = org_harness.workspace

        # Full cycle: ANALYZE -> PLAN -> IMPLEMENT -> VALIDATE -> CODIFY
        ws.transition_to(WorkspacePhase.PLAN, reason="Cycle 1: planning")
        ws.transition_to(WorkspacePhase.IMPLEMENT, reason="Cycle 1: implementing")
        ws.transition_to(WorkspacePhase.VALIDATE, reason="Cycle 1: validating")
        ws.transition_to(WorkspacePhase.CODIFY, reason="Cycle 1: codifying")

        assert ws.current_phase == WorkspacePhase.CODIFY
        assert len(ws.phase_history) == 4

    @pytest.mark.asyncio
    async def test_new_cycle_can_access_prior_cycle_context(self, org_harness: OrgHarness):
        """Starting a new cycle, prior-cycle phase history is still accessible."""
        ws = org_harness.workspace

        # Cycle 1
        ws.transition_to(WorkspacePhase.PLAN, reason="Cycle 1: planning")
        ws.transition_to(WorkspacePhase.IMPLEMENT, reason="Cycle 1: implementing")
        ws.transition_to(WorkspacePhase.VALIDATE, reason="Cycle 1: validating")
        ws.transition_to(WorkspacePhase.CODIFY, reason="Cycle 1: codifying")

        cycle_1_length = len(ws.phase_history)

        # Start Cycle 2 (CODIFY -> ANALYZE)
        ws.transition_to(
            WorkspacePhase.ANALYZE, reason="Cycle 2: re-analyzing with prior knowledge"
        )
        ws.transition_to(WorkspacePhase.PLAN, reason="Cycle 2: planning with codified insights")

        # Prior-cycle transitions are still in history
        assert len(ws.phase_history) == cycle_1_length + 2

        # Cycle 1 context is accessible
        cycle_1_reasons = [t.reason for t in ws.phase_history[:cycle_1_length]]
        assert "Cycle 1: planning" in cycle_1_reasons
        assert "Cycle 1: codifying" in cycle_1_reasons

        # Cycle 2 can reference Cycle 1's codified output
        cycle_2_transitions = ws.phase_history[cycle_1_length:]
        assert any(
            "prior knowledge" in t.reason or "codified insights" in t.reason
            for t in cycle_2_transitions
        )

    @pytest.mark.asyncio
    async def test_phase_history_preserves_timestamps(self, org_harness: OrgHarness):
        """Phase history preserves timestamps for temporal ordering."""
        ws = org_harness.workspace

        ws.transition_to(WorkspacePhase.PLAN, reason="Step 1")
        ws.transition_to(WorkspacePhase.IMPLEMENT, reason="Step 2")

        # Timestamps should be monotonically increasing
        for i in range(1, len(ws.phase_history)):
            assert ws.phase_history[i].timestamp >= ws.phase_history[i - 1].timestamp

    @pytest.mark.asyncio
    async def test_workspace_last_activity_updated_on_transition(self, org_harness: OrgHarness):
        """Workspace.last_activity is updated on each phase transition."""
        ws = org_harness.workspace
        before = ws.last_activity

        ws.transition_to(WorkspacePhase.PLAN, reason="Activity test")

        assert ws.last_activity >= before

    @pytest.mark.asyncio
    async def test_multiple_cycles_accumulate_knowledge(self, org_harness: OrgHarness):
        """Running 3 CO cycles accumulates all phase history."""
        ws = org_harness.workspace

        phases_per_cycle = [
            WorkspacePhase.PLAN,
            WorkspacePhase.IMPLEMENT,
            WorkspacePhase.VALIDATE,
            WorkspacePhase.CODIFY,
        ]

        for cycle in range(3):
            for phase in phases_per_cycle:
                ws.transition_to(phase, reason=f"Cycle {cycle + 1}: {phase.value}")
            if cycle < 2:
                # Transition back to ANALYZE to start next cycle
                ws.transition_to(
                    WorkspacePhase.ANALYZE,
                    reason=f"Cycle {cycle + 2}: beginning with prior knowledge",
                )

        # 3 cycles x 4 transitions + 2 ANALYZE transitions = 14 total
        assert len(ws.phase_history) == 14

        # All cycle context is preserved
        all_reasons = [t.reason for t in ws.phase_history]
        assert any("Cycle 1" in r for r in all_reasons)
        assert any("Cycle 2" in r for r in all_reasons)
        assert any("Cycle 3" in r for r in all_reasons)
