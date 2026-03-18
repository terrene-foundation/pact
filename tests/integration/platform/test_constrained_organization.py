# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""E2E test: The CARE Platform IS a Constrained Organization (Milestone 19, Todo 1910).

A single comprehensive test proving all 5 constitutive properties and
3 behavioral tests hold SIMULTANEOUSLY in a bootstrapped organization.

This test bootstraps a real organization via OrgBuilder, establishes a trust
chain via EATP, creates constraint envelopes at each delegation level, and
exercises the full verification pipeline. No mocking.

Constitutive Properties:
  P1: Constraint Completeness — every action evaluated against constraints
  P2: Trust Verifiability — every trust claim cryptographically verifiable
  P3: Audit Continuity — audit chain has no gaps
  P4: Knowledge Structurality — knowledge compounds via workspace-as-knowledge-base
  P5: Governance Coherence — all envelopes derive from genesis via monotonic tightening

Behavioral Tests:
  B1: Constraints enforced (not advisory) — violating actions BLOCKED
  B2: Trust verifiable (not assumed) — revoked agents blocked
  B3: Knowledge compounds structurally — next cycle accesses prior cycle
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
    TeamConfig,
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
)

# ===========================================================================
# Configuration
# ===========================================================================


def _genesis_cfg() -> GenesisConfig:
    return GenesisConfig(
        authority="constrained-org.test",
        authority_name="Constrained Organization Test Authority",
        policy_reference="https://constrained-org.test/policy",
    )


def _root_envelope() -> ConstraintEnvelopeConfig:
    return ConstraintEnvelopeConfig(
        id="env-org-root",
        description="Organization root envelope",
        financial=FinancialConstraintConfig(
            max_spend_usd=5000.0,
            requires_approval_above_usd=2000.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "manage_team",
                "review_content",
                "delegate_tasks",
                "draft_content",
                "analyze_data",
                "read_metrics",
                "publish_content",
            ],
            blocked_actions=["delete_data", "modify_governance", "exfiltrate_data"],
            max_actions_per_day=300,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="00:00",
            active_hours_end="23:59",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspace/*", "reports/*", "metrics/*"],
            write_paths=["workspace/*", "reports/*"],
            blocked_data_types=["pii", "credentials", "secrets"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal"],
            external_requires_approval=True,
        ),
    )


def _manager_envelope() -> ConstraintEnvelopeConfig:
    return ConstraintEnvelopeConfig(
        id="env-manager",
        description="Manager envelope — tighter than root",
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
            blocked_actions=["delete_data", "modify_governance", "exfiltrate_data"],
            max_actions_per_day=200,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="00:00",
            active_hours_end="23:59",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspace/*", "reports/*"],
            write_paths=["workspace/*"],
            blocked_data_types=["pii", "credentials", "secrets"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal"],
            external_requires_approval=True,
        ),
    )


def _worker_envelope() -> ConstraintEnvelopeConfig:
    return ConstraintEnvelopeConfig(
        id="env-worker",
        description="Worker envelope — tightest",
        financial=FinancialConstraintConfig(
            max_spend_usd=100.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=["draft_content", "analyze_data", "read_metrics"],
            blocked_actions=["delete_data", "modify_governance", "exfiltrate_data"],
            max_actions_per_day=50,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="00:00",
            active_hours_end="23:59",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspace/*"],
            write_paths=["workspace/drafts/*"],
            blocked_data_types=["pii", "credentials", "secrets"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal"],
            external_requires_approval=True,
        ),
    )


def _manager_agent() -> AgentConfig:
    return AgentConfig(
        id="co-manager",
        name="Organization Manager",
        role="manager",
        constraint_envelope="env-manager",
        capabilities=[
            "manage_team",
            "review_content",
            "delegate_tasks",
            "draft_content",
            "analyze_data",
            "read_metrics",
        ],
    )


def _worker_agent() -> AgentConfig:
    return AgentConfig(
        id="co-worker",
        name="Organization Worker",
        role="worker",
        constraint_envelope="env-worker",
        capabilities=["draft_content", "analyze_data", "read_metrics"],
    )


def _gradient_cfg() -> VerificationGradientConfig:
    return VerificationGradientConfig(
        rules=[
            GradientRuleConfig(
                pattern="read_*",
                level=VerificationLevel.AUTO_APPROVED,
                reason="Reads safe",
            ),
            GradientRuleConfig(
                pattern="analyze_*",
                level=VerificationLevel.AUTO_APPROVED,
                reason="Analysis safe",
            ),
            GradientRuleConfig(
                pattern="draft_*",
                level=VerificationLevel.FLAGGED,
                reason="Content needs review",
            ),
            GradientRuleConfig(
                pattern="delete_*",
                level=VerificationLevel.BLOCKED,
                reason="Destructive blocked",
            ),
            GradientRuleConfig(
                pattern="modify_*",
                level=VerificationLevel.BLOCKED,
                reason="Governance blocked",
            ),
            GradientRuleConfig(
                pattern="exfiltrate_*",
                level=VerificationLevel.BLOCKED,
                reason="Data exfiltration blocked",
            ),
        ],
        default_level=VerificationLevel.HELD,
    )


# ===========================================================================
# The Test
# ===========================================================================


class TestPlatformIsConstrainedOrganization:
    """Single comprehensive test proving all 5 properties + 3 behavioral tests
    hold simultaneously in a bootstrapped organization.
    """

    @pytest.mark.asyncio
    async def test_care_platform_is_constrained_organization(self):
        """PROOF: The CARE Platform satisfies all Constrained Organization requirements.

        This test executes a complete organizational lifecycle and verifies
        all five constitutive properties and three behavioral tests hold
        simultaneously on the same bootstrapped organization.
        """

        # =================================================================
        # PHASE 0: Bootstrap the Organization
        # =================================================================

        # Validate org structure via OrgBuilder
        org = (
            OrgBuilder("constrained-org", "Constrained Organization")
            .add_workspace(
                WorkspaceConfig(
                    id="ws-co",
                    path="workspaces/co/",
                    description="CO test workspace",
                )
            )
            .add_envelope(_root_envelope())
            .add_envelope(_manager_envelope())
            .add_envelope(_worker_envelope())
            .add_agent(_manager_agent())
            .add_agent(_worker_agent())
            .add_team(
                TeamConfig(
                    id="team-co",
                    name="CO Team",
                    workspace="ws-co",
                    agents=["co-manager", "co-worker"],
                )
            )
            .build()
        )
        assert org.org_id == "constrained-org"

        # EATP Trust Infrastructure
        bridge = EATPBridge()
        await bridge.initialize()

        genesis_mgr = GenesisManager(bridge)
        delegation_mgr = DelegationManager(bridge)

        # ESTABLISH genesis
        genesis = await genesis_mgr.create_genesis(_genesis_cfg())
        genesis_agent_id = genesis.agent_id

        # DELEGATE: genesis -> manager
        await delegation_mgr.create_delegation(
            delegator_id=genesis_agent_id,
            delegate_config=_manager_agent(),
            envelope_config=_manager_envelope(),
            parent_envelope_config=_root_envelope(),
        )

        # DELEGATE: manager -> worker
        await delegation_mgr.create_delegation(
            delegator_id="co-manager",
            delegate_config=_worker_agent(),
            envelope_config=_worker_envelope(),
            parent_envelope_config=_manager_envelope(),
        )

        # Revocation infrastructure
        cred_mgr = CredentialManager()
        revocation_mgr = RevocationManager(
            credential_manager=cred_mgr,
            eatp_bridge=bridge,
        )
        revocation_mgr.register_delegation(genesis_agent_id, "co-manager")
        revocation_mgr.register_delegation("co-manager", "co-worker")

        # Constraint envelopes (runtime)
        manager_env = ConstraintEnvelope(config=_manager_envelope())
        worker_env = ConstraintEnvelope(config=_worker_envelope())

        # Shared audit chain
        audit_chain = AuditChain(chain_id="co-org-chain")

        # Gradient engine
        gradient = GradientEngine(_gradient_cfg())

        # Per-agent middleware
        manager_mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=manager_env,
            audit_chain=audit_chain,
            eatp_bridge=bridge,
        )
        worker_mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=worker_env,
            audit_chain=audit_chain,
            eatp_bridge=bridge,
        )

        # Enforcers
        manager_enforcer = ConstraintEnforcer(middleware=manager_mw)
        worker_enforcer = ConstraintEnforcer(middleware=worker_mw)

        # Workspace
        ws = Workspace(
            config=WorkspaceConfig(
                id="ws-co",
                path="workspaces/co/",
                description="CO test workspace",
            ),
            team_id="team-co",
        )
        ws.activate(reason="Organization bootstrapped")

        # =================================================================
        # P5: GOVERNANCE COHERENCE
        # Every envelope derives from genesis via monotonic tightening
        # =================================================================

        # Root -> Manager: valid tightening
        p5_valid_1, p5_violations_1 = delegation_mgr.validate_tightening(
            parent_envelope=_root_envelope(),
            child_envelope=_manager_envelope(),
        )
        assert p5_valid_1, f"P5 FAILED: Manager not tighter than root: {p5_violations_1}"

        # Manager -> Worker: valid tightening
        p5_valid_2, p5_violations_2 = delegation_mgr.validate_tightening(
            parent_envelope=_manager_envelope(),
            child_envelope=_worker_envelope(),
        )
        assert p5_valid_2, f"P5 FAILED: Worker not tighter than manager: {p5_violations_2}"

        # Transitive: Root -> Worker
        p5_valid_3, p5_violations_3 = delegation_mgr.validate_tightening(
            parent_envelope=_root_envelope(),
            child_envelope=_worker_envelope(),
        )
        assert p5_valid_3, (
            f"P5 FAILED: Worker not tighter than root (transitive): {p5_violations_3}"
        )

        # ConstraintEnvelope.is_tighter_than agrees
        assert ConstraintEnvelope(config=_manager_envelope()).is_tighter_than(
            ConstraintEnvelope(config=_root_envelope())
        ), "P5 FAILED: ConstraintEnvelope.is_tighter_than disagrees for manager"
        assert ConstraintEnvelope(config=_worker_envelope()).is_tighter_than(
            ConstraintEnvelope(config=_manager_envelope())
        ), "P5 FAILED: ConstraintEnvelope.is_tighter_than disagrees for worker"

        # =================================================================
        # P2: TRUST VERIFIABILITY
        # Every trust claim can be cryptographically verified
        # =================================================================

        # Genesis is valid
        p2_genesis_valid, p2_genesis_msg = await genesis_mgr.validate_genesis(genesis_agent_id)
        assert p2_genesis_valid, f"P2 FAILED: Genesis invalid: {p2_genesis_msg}"

        # Chain from worker to genesis is valid
        p2_walk_worker = await delegation_mgr.walk_chain("co-worker")
        assert p2_walk_worker.status == ChainStatus.VALID, (
            f"P2 FAILED: Worker chain invalid: {p2_walk_worker.errors}"
        )
        assert p2_walk_worker.depth == 2

        # Chain from manager to genesis is valid
        p2_walk_manager = await delegation_mgr.walk_chain("co-manager")
        assert p2_walk_manager.status == ChainStatus.VALID

        # Ancestors are traceable
        p2_ancestors = bridge.get_delegation_ancestors("co-worker")
        assert "co-worker" in p2_ancestors
        assert "co-manager" in p2_ancestors
        assert genesis_agent_id in p2_ancestors

        # TrustChainIntegrity hash chain verifies
        integrity_chain = TrustChainIntegrity()
        integrity_chain.append_record({"type": "genesis", "agent_id": genesis_agent_id})
        integrity_chain.append_record(
            {"type": "delegation", "from": genesis_agent_id, "to": "co-manager"}
        )
        integrity_chain.append_record(
            {"type": "delegation", "from": "co-manager", "to": "co-worker"}
        )
        p2_integrity = integrity_chain.verify()
        assert p2_integrity.is_valid, (
            f"P2 FAILED: Hash chain integrity violated: {p2_integrity.violations}"
        )

        # EATP verification succeeds for valid agents
        p2_verify = await bridge.verify_action(
            agent_id="co-worker",
            action="draft_content",
            level="QUICK",
        )
        assert p2_verify.valid, f"P2 FAILED: EATP verification failed: {p2_verify.reason}"

        # =================================================================
        # P1: CONSTRAINT COMPLETENESS
        # Every agent action evaluated against at least one constraint dimension
        # =================================================================

        # Submit various action types — all must produce audit records
        p1_actions = [
            ("read_metrics", "co-worker", worker_mw),
            ("analyze_data", "co-worker", worker_mw),
            ("draft_content", "co-manager", manager_mw),
            ("read_metrics", "co-manager", manager_mw),
        ]
        for p1_action, p1_agent, p1_mw in p1_actions:
            p1_result = p1_mw.process_action(
                agent_id=p1_agent,
                action=p1_action,
                current_action_count=0,
            )
            assert p1_result.audit_recorded, (
                f"P1 FAILED: Action '{p1_action}' by '{p1_agent}' not audited"
            )

        # Direct envelope evaluation covers all 5 dimensions
        work_time = datetime(2026, 3, 13, 14, 0, tzinfo=UTC)
        p1_eval = worker_env.evaluate_action(
            action="draft_content",
            agent_id="co-worker",
            spend_amount=10.0,
            current_action_count=5,
            current_time=work_time,
            data_paths=["workspace/draft.md"],
            access_type="write",
            is_external=False,
        )
        p1_dims = {d.dimension for d in p1_eval.dimensions}
        for dim in ["financial", "operational", "temporal", "data_access", "communication"]:
            assert dim in p1_dims, f"P1 FAILED: Dimension '{dim}' missing from evaluation"

        # Unknown actions are still evaluated (not silently passed)
        p1_unknown = worker_mw.process_action(
            agent_id="co-worker",
            action="unknown_action",
            current_action_count=0,
        )
        assert p1_unknown.audit_recorded
        assert p1_unknown.outcome in (ActionOutcome.QUEUED, ActionOutcome.REJECTED)

        # =================================================================
        # P3: AUDIT CONTINUITY
        # Audit chain has no gaps
        # =================================================================

        # Verify audit chain integrity so far
        p3_valid, p3_errors = audit_chain.verify_chain_integrity()
        assert p3_valid, f"P3 FAILED: Audit chain has gaps: {p3_errors}"

        # Verify sequence numbers are contiguous
        for i, anchor in enumerate(audit_chain.anchors):
            assert anchor.sequence == i, f"P3 FAILED: Expected sequence {i}, got {anchor.sequence}"

        # Verify hash chain links
        for i in range(1, len(audit_chain.anchors)):
            assert (
                audit_chain.anchors[i].previous_hash == audit_chain.anchors[i - 1].content_hash
            ), f"P3 FAILED: Anchor {i} previous_hash does not link to anchor {i - 1}"

        # =================================================================
        # B1: CONSTRAINTS ENFORCED (NOT ADVISORY)
        # Violating actions are BLOCKED, not just FLAGGED
        # =================================================================

        # Blocked action type
        b1_blocked = worker_mw.process_action(
            agent_id="co-worker",
            action="delete_data",
            current_action_count=0,
        )
        assert b1_blocked.verification_level == VerificationLevel.BLOCKED, (
            f"B1 FAILED: delete_data should be BLOCKED, got {b1_blocked.verification_level}"
        )
        assert b1_blocked.outcome == ActionOutcome.REJECTED

        # Financial limit violation
        b1_overspend = worker_mw.process_action(
            agent_id="co-worker",
            action="draft_content",
            spend_amount=500.0,  # worker limit is 100
            current_action_count=0,
        )
        assert b1_overspend.verification_level == VerificationLevel.BLOCKED
        assert b1_overspend.outcome == ActionOutcome.REJECTED

        # Rate limit violation
        b1_ratelimit = worker_mw.process_action(
            agent_id="co-worker",
            action="read_metrics",
            current_action_count=50,  # worker limit is 50
        )
        assert b1_ratelimit.verification_level == VerificationLevel.BLOCKED
        assert b1_ratelimit.outcome == ActionOutcome.REJECTED

        # Action outside allowed set
        b1_unauthorized = worker_mw.process_action(
            agent_id="co-worker",
            action="publish_content",  # not in worker's allowed_actions
            current_action_count=0,
        )
        assert b1_unauthorized.verification_level == VerificationLevel.BLOCKED
        assert b1_unauthorized.outcome == ActionOutcome.REJECTED

        # Audit chain records all rejections
        blocked_anchors = audit_chain.filter_by_level(VerificationLevel.BLOCKED)
        assert len(blocked_anchors) >= 4, (
            f"B1 FAILED: Expected at least 4 BLOCKED audit anchors, got {len(blocked_anchors)}"
        )

        # =================================================================
        # B2: TRUST VERIFIABLE (NOT ASSUMED)
        # Revoked agents are blocked even if previously trusted
        # =================================================================

        # Worker can act before revocation
        b2_before = worker_mw.process_action(
            agent_id="co-worker",
            action="read_metrics",
            current_action_count=0,
        )
        assert b2_before.outcome == ActionOutcome.EXECUTED, (
            f"B2 FAILED: Worker should succeed before revocation, got {b2_before.outcome}"
        )

        # Revoke the worker via EATP bridge
        bridge.revoke_agent("co-worker")

        # Worker is now blocked
        b2_after = worker_mw.process_action(
            agent_id="co-worker",
            action="read_metrics",
            current_action_count=0,
        )
        assert b2_after.outcome == ActionOutcome.REJECTED, (
            f"B2 FAILED: Revoked worker should be BLOCKED, got {b2_after.outcome}"
        )
        assert b2_after.verification_level == VerificationLevel.BLOCKED

        # EATP verification also fails for revoked agent
        b2_verify = await bridge.verify_action(
            agent_id="co-worker",
            action="read_metrics",
            level="QUICK",
        )
        assert not b2_verify.valid, "B2 FAILED: Revoked agent should fail EATP verification"

        # RevocationManager tracks it
        revocation_mgr.surgical_revoke(
            agent_id="co-worker",
            reason="E2E test revocation",
            revoker_id="co-manager",
        )
        assert revocation_mgr.is_revoked("co-worker")

        # =================================================================
        # P4: KNOWLEDGE STRUCTURALITY
        # Knowledge compounds via workspace-as-knowledge-base
        # =================================================================

        # CO Cycle 1: ANALYZE -> PLAN -> IMPLEMENT -> VALIDATE -> CODIFY
        ws.transition_to(WorkspacePhase.PLAN, reason="Cycle 1: planning from analysis")
        ws.transition_to(WorkspacePhase.IMPLEMENT, reason="Cycle 1: building the plan")
        ws.transition_to(WorkspacePhase.VALIDATE, reason="Cycle 1: validating implementation")
        ws.transition_to(WorkspacePhase.CODIFY, reason="Cycle 1: codifying learnings")

        assert ws.current_phase == WorkspacePhase.CODIFY
        assert len(ws.phase_history) == 4

        # CO Cycle 2: CODIFY -> ANALYZE -> PLAN (uses prior cycle knowledge)
        ws.transition_to(
            WorkspacePhase.ANALYZE, reason="Cycle 2: re-analyzing with codified knowledge"
        )
        ws.transition_to(WorkspacePhase.PLAN, reason="Cycle 2: planning with Cycle 1 insights")

        assert len(ws.phase_history) == 6

        # Prior cycle context is accessible
        cycle_1_reasons = [t.reason for t in ws.phase_history[:4]]
        assert "Cycle 1: codifying learnings" in cycle_1_reasons, (
            "P4 FAILED: Prior cycle codification not accessible"
        )

        cycle_2_reasons = [t.reason for t in ws.phase_history[4:]]
        assert any("codified knowledge" in r or "Cycle 1 insights" in r for r in cycle_2_reasons), (
            "P4 FAILED: Cycle 2 does not reference Cycle 1 knowledge"
        )

        # =================================================================
        # B3: KNOWLEDGE COMPOUNDS STRUCTURALLY
        # Next CO cycle can access prior cycle's knowledge
        # =================================================================

        # Continue Cycle 2 to completion
        ws.transition_to(
            WorkspacePhase.IMPLEMENT, reason="Cycle 2: implementing with compound knowledge"
        )
        ws.transition_to(WorkspacePhase.VALIDATE, reason="Cycle 2: validating compound approach")
        ws.transition_to(WorkspacePhase.CODIFY, reason="Cycle 2: codifying compound learnings")

        # Start Cycle 3
        ws.transition_to(
            WorkspacePhase.ANALYZE, reason="Cycle 3: analysis informed by 2 prior cycles"
        )

        # Total transitions: 4 (C1) + 5 (C2 including back to ANALYZE) + 1 (C3 ANALYZE) = 10
        assert len(ws.phase_history) == 10

        # Knowledge from ALL prior cycles is accessible
        all_reasons = [t.reason for t in ws.phase_history]
        assert any("Cycle 1" in r for r in all_reasons), "B3 FAILED: Cycle 1 knowledge lost"
        assert any("Cycle 2" in r for r in all_reasons), "B3 FAILED: Cycle 2 knowledge lost"
        assert any("Cycle 3" in r for r in all_reasons), "B3 FAILED: Cycle 3 not started"

        # =================================================================
        # FINAL VERIFICATION: P3 still holds after all operations
        # =================================================================

        final_valid, final_errors = audit_chain.verify_chain_integrity()
        assert final_valid, f"FINAL P3 FAILED: Audit chain corrupted during test: {final_errors}"

        # =================================================================
        # SUMMARY: All 5 properties + 3 behavioral tests verified
        # =================================================================
        #
        # P1 Constraint Completeness: Every action evaluated (5 dimensions)
        # P2 Trust Verifiability: Chain walks, hash integrity, EATP verify
        # P3 Audit Continuity: Contiguous chain, no gaps, hash links
        # P4 Knowledge Structurality: Phase history persists across cycles
        # P5 Governance Coherence: Monotonic tightening at every level
        # B1 Constraints Enforced: Violations BLOCKED, not FLAGGED
        # B2 Trust Verifiable: Revoked agent BLOCKED
        # B3 Knowledge Compounds: Cycle N accesses Cycle N-1 knowledge
        #
        # The CARE Platform IS a Constrained Organization. QED.
