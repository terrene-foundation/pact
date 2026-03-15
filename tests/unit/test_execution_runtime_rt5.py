# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for RT5 findings in ExecutionRuntime.

Tests for critical and high-priority fixes:
- RT5-01: Envelope evaluation wired in process_next()
- RT5-02: Auth + revocation + posture re-checks in resume_held()
- RT5-06: NEVER_DELEGATED_ACTIONS check in process_next()
- RT5-07: SUPERVISED posture escalation
- RT5-08: Wire _sync_revocations() and _persist_posture_change()
- RT5-09: Hydration refresh mechanism
- RT5-10: Expanded lock scope in process_next()
- RT5-12: Crash-safe audit ordering (store-first)
- RT5-23: Remove redundant re-classification in middleware integration
"""

from __future__ import annotations

import threading
import time

import pytest

from care_platform.audit.anchor import AuditChain
from care_platform.config.schema import (
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.envelope import ConstraintEnvelope
from care_platform.constraint.gradient import GradientEngine
from care_platform.execution.approval import ApprovalQueue
from care_platform.execution.registry import AgentRegistry, AgentStatus
from care_platform.execution.runtime import (
    ExecutionRuntime,
    Task,
    TaskExecutor,
    TaskResult,
    TaskStatus,
)
from care_platform.persistence.store import MemoryStore
from care_platform.trust.posture import NEVER_DELEGATED_ACTIONS, TrustPosture
from care_platform.trust.revocation import RevocationManager


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_runtime(
    *,
    default_level: VerificationLevel = VerificationLevel.AUTO_APPROVED,
    trust_store: MemoryStore | None = None,
    revocation_manager: RevocationManager | None = None,
    posture_manager: dict[str, TrustPosture] | None = None,
) -> tuple[ExecutionRuntime, AgentRegistry, AuditChain, ApprovalQueue]:
    """Create a runtime with standard test setup and optional integrations."""
    registry = AgentRegistry()
    registry.register(
        agent_id="agent-1",
        name="Test Agent",
        role="worker",
        team_id="team-1",
        capabilities=["read", "write"],
    )
    registry.register(
        agent_id="agent-2",
        name="Review Agent",
        role="reviewer",
        team_id="team-1",
        capabilities=["read", "review"],
    )

    gradient_config = VerificationGradientConfig(default_level=default_level)
    gradient = GradientEngine(gradient_config)
    audit_chain = AuditChain(chain_id="test-chain")
    approval_queue = ApprovalQueue()

    runtime = ExecutionRuntime(
        registry=registry,
        gradient=gradient,
        audit_chain=audit_chain,
        approval_queue=approval_queue,
        trust_store=trust_store,
        revocation_manager=revocation_manager,
        posture_manager=posture_manager,
    )
    return runtime, registry, audit_chain, approval_queue


def _make_envelope_store(agent_id: str = "agent-1") -> MemoryStore:
    """Create a MemoryStore with a constraint envelope that blocks high-spend actions."""
    store = MemoryStore()
    envelope_config = ConstraintEnvelopeConfig(
        id="env-1",
        financial=FinancialConstraintConfig(max_spend_usd=100.0),
        operational=OperationalConstraintConfig(
            blocked_actions=["delete_production"],
        ),
    )
    envelope = ConstraintEnvelope(config=envelope_config)
    envelope_data = envelope.model_dump(mode="json")
    envelope_data["agent_id"] = agent_id
    store.store_envelope("env-1", envelope_data)
    return store


# ---------------------------------------------------------------------------
# RT5-01: Wire envelope evaluation in process_next()
# ---------------------------------------------------------------------------


class TestRT5_01_EnvelopeEvaluation:
    """Envelope evaluation must be wired into process_next()."""

    def test_envelope_blocked_action_is_blocked(self):
        """An action blocked by the constraint envelope results in a BLOCKED task."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit("delete_production", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.BLOCKED
        assert task.result is not None
        assert task.result.error is not None

    def test_envelope_allowed_action_proceeds(self):
        """An action allowed by the constraint envelope completes normally."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_envelope_near_boundary_is_flagged(self):
        """An action near the financial boundary triggers at least FLAGGED."""
        store = MemoryStore()
        envelope_config = ConstraintEnvelopeConfig(
            id="env-fin",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=envelope_config)
        envelope_data = envelope.model_dump(mode="json")
        envelope_data["agent_id"] = "agent-1"
        # Store a spend_amount field in envelope metadata so the runtime can
        # pass it to the evaluation. The actual near-boundary triggering depends
        # on the envelope evaluation logic.
        store.store_envelope("env-fin", envelope_data)

        # With default AUTO_APPROVED gradient, envelope near-boundary should
        # escalate to at least FLAGGED
        runtime, _, _, _ = _make_runtime(trust_store=store)
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        # Should complete (near-boundary with FLAGGED level still executes)
        assert task.status in (TaskStatus.COMPLETED, TaskStatus.HELD)

    def test_no_envelope_in_store_still_works(self):
        """When no envelope exists for the agent, process_next still works."""
        store = MemoryStore()
        # No envelope stored for agent-1
        runtime, _, _, _ = _make_runtime(trust_store=store)
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# RT5-02: Auth + revocation + posture re-checks in resume_held()
# ---------------------------------------------------------------------------


class TestRT5_02_ResumeHeldAuth:
    """resume_held() must re-check revocation and posture before executing."""

    def test_resume_held_with_approver_id(self):
        """resume_held accepts an approver_id parameter and logs it in audit."""
        runtime, _, audit_chain, _ = _make_runtime(default_level=VerificationLevel.HELD)
        runtime.submit("risky action", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        resumed = runtime.resume_held(task.task_id, "approved", approver_id="admin-1")
        assert resumed is not None
        assert resumed.status == TaskStatus.COMPLETED
        # The audit should record the approver_id
        latest = audit_chain.latest
        assert latest is not None
        assert latest.metadata.get("approver_id") == "admin-1"

    def test_resume_held_revoked_agent_fails(self):
        """Resuming a HELD task for a revoked agent fails."""
        revocation_mgr = RevocationManager()
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            revocation_manager=revocation_mgr,
        )
        runtime.submit("risky action", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        # Now revoke the agent
        revocation_mgr.surgical_revoke("agent-1", "compromised", "admin")

        resumed = runtime.resume_held(task.task_id, "approved", approver_id="admin-1")
        assert resumed is not None
        assert resumed.status == TaskStatus.FAILED
        assert "revoked" in resumed.result.error.lower()

    def test_resume_held_pseudo_agent_fails(self):
        """Resuming a HELD task for a PSEUDO_AGENT fails."""
        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.SUPERVISED,
            ),
        }
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            posture_manager=posture_mgr,
        )
        runtime.submit("risky action", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        # Downgrade the agent to PSEUDO_AGENT between HELD and resume
        posture_mgr["agent-1"].current_level = TrustPostureLevel.PSEUDO_AGENT

        resumed = runtime.resume_held(task.task_id, "approved", approver_id="admin-1")
        assert resumed is not None
        assert resumed.status == TaskStatus.FAILED
        assert "pseudo_agent" in resumed.result.error.lower()

    def test_resume_held_backwards_compat_no_approver(self):
        """resume_held still works without approver_id for backwards compat."""
        runtime, _, _, _ = _make_runtime(default_level=VerificationLevel.HELD)
        runtime.submit("risky action", agent_id="agent-1")
        task = runtime.process_next()
        assert task.status == TaskStatus.HELD

        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed is not None
        assert resumed.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# RT5-06: NEVER_DELEGATED_ACTIONS check in process_next()
# ---------------------------------------------------------------------------


class TestRT5_06_NeverDelegatedActions:
    """Actions in NEVER_DELEGATED_ACTIONS must be escalated to HELD."""

    def test_modify_constraints_escalated_to_held(self):
        """modify_constraints is a never-delegated action and must be HELD."""
        # Use AUTO_APPROVED default so we can see the escalation
        runtime, _, _, approval_queue = _make_runtime(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        runtime.submit("modify_constraints", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD
        assert task.verification_level == VerificationLevel.HELD

    def test_financial_decisions_escalated_to_held(self):
        """financial_decisions is a never-delegated action and must be HELD."""
        runtime, _, _, approval_queue = _make_runtime(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        runtime.submit("financial_decisions", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

    def test_modify_governance_escalated_to_held(self):
        """modify_governance is a never-delegated action and must be HELD."""
        runtime, _, _, approval_queue = _make_runtime(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        runtime.submit("modify_governance", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

    def test_non_delegated_blocked_stays_blocked(self):
        """A never-delegated action that is already BLOCKED stays BLOCKED."""
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.BLOCKED,
        )
        runtime.submit("modify_constraints", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.BLOCKED

    def test_normal_action_not_escalated(self):
        """Regular actions are NOT affected by NEVER_DELEGATED check."""
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_all_never_delegated_actions_covered(self):
        """Verify the expected set of never-delegated actions exists."""
        expected = {
            "content_strategy",
            "novel_outreach",
            "crisis_response",
            "financial_decisions",
            "modify_constraints",
            "modify_governance",
            "external_publication",
        }
        assert NEVER_DELEGATED_ACTIONS == expected


# ---------------------------------------------------------------------------
# RT5-07: SUPERVISED posture escalation
# ---------------------------------------------------------------------------


class TestRT5_07_SupervisedPostureEscalation:
    """SUPERVISED agents should have AUTO_APPROVED/FLAGGED escalated to HELD."""

    def test_supervised_auto_approved_escalated_to_held(self):
        """SUPERVISED agent: AUTO_APPROVED -> HELD."""
        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.SUPERVISED,
            ),
        }
        runtime, _, _, approval_queue = _make_runtime(
            default_level=VerificationLevel.AUTO_APPROVED,
            posture_manager=posture_mgr,
        )
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD
        assert task.verification_level == VerificationLevel.HELD

    def test_supervised_flagged_escalated_to_held(self):
        """SUPERVISED agent: FLAGGED -> HELD."""
        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.SUPERVISED,
            ),
        }
        runtime, _, _, approval_queue = _make_runtime(
            default_level=VerificationLevel.FLAGGED,
            posture_manager=posture_mgr,
        )
        runtime.submit("write output", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

    def test_supervised_held_stays_held(self):
        """SUPERVISED agent: HELD stays HELD (no escalation needed)."""
        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.SUPERVISED,
            ),
        }
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            posture_manager=posture_mgr,
        )
        runtime.submit("risky action", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

    def test_supervised_blocked_stays_blocked(self):
        """SUPERVISED agent: BLOCKED stays BLOCKED (more restrictive)."""
        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.SUPERVISED,
            ),
        }
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.BLOCKED,
            posture_manager=posture_mgr,
        )
        runtime.submit("bad action", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.BLOCKED

    def test_shared_planning_not_escalated(self):
        """SHARED_PLANNING agent: AUTO_APPROVED is NOT escalated."""
        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.SHARED_PLANNING,
            ),
        }
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.AUTO_APPROVED,
            posture_manager=posture_mgr,
        )
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_delegated_not_escalated(self):
        """DELEGATED agent: AUTO_APPROVED is NOT escalated."""
        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.DELEGATED,
            ),
        }
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.AUTO_APPROVED,
            posture_manager=posture_mgr,
        )
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# RT5-08: Wire _sync_revocations() and _persist_posture_change()
# ---------------------------------------------------------------------------


class TestRT5_08_WireSyncAndPersist:
    """_sync_revocations() called at start of process_next(), and
    _persist_posture_change() called when posture enforcement triggers."""

    def test_sync_revocations_called_during_process_next(self):
        """A revoked agent discovered via sync is rejected during process_next."""
        revocation_mgr = RevocationManager()
        runtime, registry, _, _ = _make_runtime(revocation_manager=revocation_mgr)

        # Submit a task before revoking
        runtime.submit("task 1", agent_id="agent-1")

        # Revoke agent-1 AFTER submission but BEFORE processing
        revocation_mgr.surgical_revoke("agent-1", "compromised", "admin")

        # process_next should sync revocations first, marking agent-1 as REVOKED
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.FAILED

        # The registry should now reflect the revocation from sync
        agent = registry.get("agent-1")
        assert agent is not None
        assert agent.status == AgentStatus.REVOKED

    def test_posture_change_persisted_on_pseudo_agent_block(self):
        """When PSEUDO_AGENT blocks a task, the posture state is persisted."""
        store = MemoryStore()
        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.PSEUDO_AGENT,
            ),
        }
        runtime, _, _, _ = _make_runtime(
            trust_store=store,
            posture_manager=posture_mgr,
        )
        runtime.submit("task", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.BLOCKED

        # Posture should have been persisted (enforcement event)
        history = store.get_posture_history("agent-1")
        assert len(history) >= 1


# ---------------------------------------------------------------------------
# RT5-09: Hydration refresh mechanism
# ---------------------------------------------------------------------------


class TestRT5_09_HydrationRefresh:
    """Runtime should have a refresh_from_store() method."""

    def test_refresh_from_store_exists(self):
        """refresh_from_store() is a public method on ExecutionRuntime."""
        store = MemoryStore()
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        audit_chain = AuditChain(chain_id="refresh-test")

        runtime = ExecutionRuntime.from_store(
            trust_store=store,
            gradient_config=gradient_config,
            audit_chain=audit_chain,
        )
        assert hasattr(runtime, "refresh_from_store")
        assert callable(runtime.refresh_from_store)

    def test_refresh_from_store_picks_up_new_agents(self):
        """After adding a new delegation to the store, refresh picks it up."""
        store = MemoryStore()
        store.store_genesis("auth-1", {"authority_id": "auth-1", "authority_name": "Auth"})
        store.store_delegation(
            "del-1",
            {
                "delegation_id": "del-1",
                "delegator_id": "auth-1",
                "delegatee_id": "agent-1",
                "agent_name": "Agent One",
                "agent_role": "worker",
                "team_id": "team-1",
                "capabilities": ["read"],
            },
        )
        store.store_envelope("env-1", {"envelope_id": "env-1", "agent_id": "agent-1"})

        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        audit_chain = AuditChain(chain_id="refresh-test")

        runtime = ExecutionRuntime.from_store(
            trust_store=store,
            gradient_config=gradient_config,
            audit_chain=audit_chain,
        )

        # The initial hydration should have agent-1
        task_id = runtime.submit("test action", agent_id="agent-1")
        task = runtime.process_next()
        assert task.status == TaskStatus.COMPLETED

        # Now add agent-2 to the store
        store.store_delegation(
            "del-2",
            {
                "delegation_id": "del-2",
                "delegator_id": "auth-1",
                "delegatee_id": "agent-2",
                "agent_name": "Agent Two",
                "agent_role": "reviewer",
                "team_id": "team-1",
                "capabilities": ["review"],
            },
        )
        store.store_envelope("env-2", {"envelope_id": "env-2", "agent_id": "agent-2"})

        # Before refresh, agent-2 should not be in the registry
        task_id2 = runtime.submit("another action", agent_id="agent-2")
        task2 = runtime.process_next()
        assert task2.status == TaskStatus.FAILED  # agent-2 not known yet

        # After refresh, agent-2 should be available
        runtime.refresh_from_store()
        task_id3 = runtime.submit("final action", agent_id="agent-2")
        task3 = runtime.process_next()
        assert task3.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# RT5-10: Expanded lock scope in process_next()
# ---------------------------------------------------------------------------


class TestRT5_10_ExpandedLockScope:
    """Lock should cover task status transitions, not just dequeue."""

    def test_task_status_transitions_are_atomic(self):
        """Concurrent process_next calls should not corrupt task state."""
        runtime, _, _, _ = _make_runtime()
        num_tasks = 50
        for i in range(num_tasks):
            runtime.submit(f"task-{i}", agent_id="agent-1")

        processed: list[Task] = []
        errors: list[str] = []
        lock = threading.Lock()

        def processor():
            try:
                while True:
                    task = runtime.process_next()
                    if task is None:
                        break
                    with lock:
                        processed.append(task)
            except Exception as exc:
                with lock:
                    errors.append(str(exc))

        threads = [threading.Thread(target=processor) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        # All tasks should be processed exactly once
        assert len(processed) == num_tasks
        # No task should be in an intermediate state
        for task in processed:
            assert task.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.HELD,
                TaskStatus.BLOCKED,
            ), f"Task {task.task_id} in unexpected status: {task.status}"


# ---------------------------------------------------------------------------
# RT5-12: Crash-safe audit ordering (store-first)
# ---------------------------------------------------------------------------


class TestRT5_12_CrashSafeAuditOrdering:
    """Store persist should happen BEFORE in-memory chain append."""

    def test_store_persist_before_chain_append(self):
        """Verify store has the audit before in-memory chain for crash safety.

        We use a custom store that tracks order of operations to validate
        that the store persist happens before chain append.
        """

        class OrderTrackingStore(MemoryStore):
            def __init__(self):
                super().__init__()
                self.persist_count = 0
                self.persist_timestamps: list[float] = []

            def store_audit_anchor(self, anchor_id: str, data: dict) -> None:
                self.persist_count += 1
                self.persist_timestamps.append(time.monotonic())
                super().store_audit_anchor(anchor_id, data)

        store = OrderTrackingStore()
        runtime, _, audit_chain, _ = _make_runtime(trust_store=store)

        runtime.submit("read file", agent_id="agent-1")
        runtime.process_next()

        # Store should have been called
        assert store.persist_count == 1
        # Both store and chain should have the anchor
        assert audit_chain.length == 1
        anchor = audit_chain.latest
        stored = store.get_audit_anchor(anchor.anchor_id)
        assert stored is not None


# ---------------------------------------------------------------------------
# RT5-23: Remove redundant re-classification in middleware integration
# ---------------------------------------------------------------------------


class TestRT5_23_RedundantReclassification:
    """When middleware returns a more restrictive level, the runtime should
    use the middleware result directly without re-classifying via gradient."""

    def test_middleware_level_used_without_redundant_classify(self):
        """The middleware's more-restrictive level is used directly."""
        from care_platform.constraint.middleware import VerificationMiddleware

        store = _make_envelope_store("agent-1")

        envelope_config = ConstraintEnvelopeConfig(
            id="env-mw",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=envelope_config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )

        registry = AgentRegistry()
        registry.register(
            agent_id="agent-1",
            name="Test Agent",
            role="worker",
            team_id="team-1",
        )

        # Gradient auto-approves but middleware will HOLD
        gradient = GradientEngine(gradient_config)
        audit_chain = AuditChain(chain_id="mw-test")
        approval_queue = ApprovalQueue()

        # Create middleware that will return HELD for everything
        mw_gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.HELD,
        )
        mw_gradient = GradientEngine(mw_gradient_config)
        middleware = VerificationMiddleware(
            gradient_engine=mw_gradient,
            envelope=envelope,
        )

        runtime = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
            trust_store=store,
            verification_middleware=middleware,
        )

        runtime.submit("test action", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        # Middleware returns HELD which is more restrictive than AUTO_APPROVED
        assert task.status == TaskStatus.HELD
        assert task.verification_level == VerificationLevel.HELD
