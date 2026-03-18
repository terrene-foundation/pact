# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for ExecutionRuntime — task processing with verification pipeline.

Tests verify the full task lifecycle: submit → verify → execute → audit.
"""

from __future__ import annotations

import threading

import pytest

from care_platform.trust.audit.anchor import AuditChain
from care_platform.build.config.schema import (
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.trust.constraint.gradient import GradientEngine
from care_platform.use.execution.approval import ApprovalQueue
from care_platform.use.execution.approver_auth import AuthenticatedApprovalQueue
from care_platform.use.execution.registry import AgentRegistry, AgentStatus
from care_platform.use.execution.runtime import (
    ExecutionRuntime,
    Task,
    TaskExecutor,
    TaskResult,
    TaskStatus,
)
from care_platform.trust.store.store import MemoryStore
from care_platform.trust.revocation import RevocationManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_runtime(
    *,
    default_level: VerificationLevel = VerificationLevel.AUTO_APPROVED,
) -> tuple[ExecutionRuntime, AgentRegistry, AuditChain, ApprovalQueue]:
    """Create a runtime with standard test setup."""
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
    )
    return runtime, registry, audit_chain, approval_queue


# ---------------------------------------------------------------------------
# Task submission
# ---------------------------------------------------------------------------


class TestTaskSubmission:
    """Tasks can be submitted and tracked."""

    def test_submit_returns_task_id(self):
        runtime, *_ = _make_runtime()
        task_id = runtime.submit("read docs/report.md", agent_id="agent-1")
        assert task_id.startswith("task-")

    def test_submitted_task_is_pending(self):
        runtime, *_ = _make_runtime()
        task_id = runtime.submit("read docs/report.md")
        task = runtime.get_task(task_id)
        assert task is not None
        assert task.status == TaskStatus.PENDING

    def test_queue_depth(self):
        runtime, *_ = _make_runtime()
        assert runtime.queue_depth == 0
        runtime.submit("task 1")
        runtime.submit("task 2")
        assert runtime.queue_depth == 2

    def test_priority_ordering(self):
        runtime, *_ = _make_runtime()
        runtime.submit("low priority", priority=1)
        runtime.submit("high priority", priority=10)
        # High priority should be processed first
        task = runtime.process_next()
        assert task is not None
        assert task.action == "high priority"


# ---------------------------------------------------------------------------
# Verification pipeline
# ---------------------------------------------------------------------------


class TestVerificationPipeline:
    """Tasks go through the verification gradient."""

    def test_auto_approved_executes(self):
        runtime, _, audit_chain, _ = _make_runtime(default_level=VerificationLevel.AUTO_APPROVED)
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.verification_level == VerificationLevel.AUTO_APPROVED
        assert audit_chain.length == 1

    def test_flagged_executes(self):
        runtime, *_ = _make_runtime(default_level=VerificationLevel.FLAGGED)
        runtime.submit("write output", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.verification_level == VerificationLevel.FLAGGED

    def test_held_enters_approval_queue(self):
        runtime, _, _, approval_queue = _make_runtime(default_level=VerificationLevel.HELD)
        runtime.submit("deploy production", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD
        assert approval_queue.queue_depth == 1

    def test_blocked_is_rejected(self):
        runtime, *_ = _make_runtime(default_level=VerificationLevel.BLOCKED)
        runtime.submit("delete everything", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.BLOCKED
        assert task.result is not None
        assert task.result.error is not None
        assert "blocked" in task.result.error.lower()


# ---------------------------------------------------------------------------
# Agent selection
# ---------------------------------------------------------------------------


class TestAgentSelection:
    """Runtime selects agents for tasks."""

    def test_specified_agent(self):
        runtime, *_ = _make_runtime()
        runtime.submit("read file", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.assigned_agent_id == "agent-1"

    def test_auto_select_from_team(self):
        runtime, *_ = _make_runtime()
        runtime.submit("read file", team_id="team-1")
        task = runtime.process_next()
        assert task is not None
        assert task.assigned_agent_id in ("agent-1", "agent-2")

    def test_unavailable_agent_fails(self):
        runtime, registry, *_ = _make_runtime()
        registry.update_status("agent-1", AgentStatus.REVOKED)
        runtime.submit("task", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert task.result is not None
        assert "revoked" in task.result.error.lower()

    def test_no_agents_available(self):
        runtime, registry, *_ = _make_runtime()
        registry.update_status("agent-1", AgentStatus.REVOKED)
        registry.update_status("agent-2", AgentStatus.REVOKED)
        runtime.submit("task")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.FAILED


# ---------------------------------------------------------------------------
# Task execution
# ---------------------------------------------------------------------------


class TestTaskExecution:
    """Custom executors can be used."""

    def test_default_executor(self):
        runtime, *_ = _make_runtime()
        runtime.submit("read file", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.result is not None
        assert task.result.output == "executed"

    def test_custom_executor(self):
        runtime, *_ = _make_runtime()

        class MockExecutor(TaskExecutor):
            def execute(self, task: Task, agent) -> TaskResult:
                return TaskResult(output=f"Processed: {task.action}")

        runtime.set_executor(MockExecutor())
        runtime.submit("summarize report", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.result is not None
        assert task.result.output == "Processed: summarize report"

    def test_executor_exception_fails_task(self):
        runtime, *_ = _make_runtime()

        class FailingExecutor(TaskExecutor):
            def execute(self, task: Task, agent) -> TaskResult:
                raise RuntimeError("Agent crashed")

        runtime.set_executor(FailingExecutor())
        runtime.submit("dangerous task", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert task.result is not None
        assert "Agent crashed" in task.result.error


# ---------------------------------------------------------------------------
# Audit recording
# ---------------------------------------------------------------------------


class TestAuditRecording:
    """Every task execution produces an audit anchor."""

    def test_completed_task_audited(self):
        runtime, _, audit_chain, _ = _make_runtime()
        runtime.submit("read file", agent_id="agent-1")
        runtime.process_next()
        assert audit_chain.length == 1
        anchor = audit_chain.latest
        assert anchor is not None
        assert anchor.agent_id == "agent-1"
        assert anchor.action == "read file"

    def test_blocked_task_audited(self):
        runtime, _, audit_chain, _ = _make_runtime(default_level=VerificationLevel.BLOCKED)
        runtime.submit("bad action", agent_id="agent-1")
        runtime.process_next()
        assert audit_chain.length == 1
        anchor = audit_chain.latest
        assert anchor is not None
        assert anchor.verification_level == VerificationLevel.BLOCKED

    def test_held_task_audited(self):
        runtime, _, audit_chain, _ = _make_runtime(default_level=VerificationLevel.HELD)
        runtime.submit("risky action", agent_id="agent-1")
        runtime.process_next()
        assert audit_chain.length == 1

    def test_failed_task_audited(self):
        runtime, registry, audit_chain, _ = _make_runtime()
        registry.update_status("agent-1", AgentStatus.REVOKED)
        registry.update_status("agent-2", AgentStatus.REVOKED)
        runtime.submit("orphan task")
        runtime.process_next()
        assert audit_chain.length == 1


# ---------------------------------------------------------------------------
# Process all
# ---------------------------------------------------------------------------


class TestProcessAll:
    """Batch processing of tasks."""

    def test_process_all(self):
        runtime, *_ = _make_runtime()
        runtime.submit("task 1", agent_id="agent-1")
        runtime.submit("task 2", agent_id="agent-1")
        runtime.submit("task 3", agent_id="agent-1")
        processed = runtime.process_all()
        assert len(processed) == 3
        assert all(t.status == TaskStatus.COMPLETED for t in processed)
        assert runtime.queue_depth == 0

    def test_empty_queue(self):
        runtime, *_ = _make_runtime()
        assert runtime.process_next() is None
        assert runtime.process_all() == []


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """Task lifecycle timestamps."""

    def test_timestamps_set(self):
        runtime, *_ = _make_runtime()
        runtime.submit("task", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.submitted_at is not None
        assert task.started_at is not None
        assert task.completed_at is not None

    def test_all_tasks_accessible(self):
        runtime, *_ = _make_runtime()
        runtime.submit("a")
        runtime.submit("b")
        assert len(runtime.all_tasks) == 2


# ---------------------------------------------------------------------------
# RT4-M9: Thread-safe task queue
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """Concurrent submissions do not corrupt internal state."""

    def test_concurrent_submit_no_corruption(self):
        """Multiple threads submitting simultaneously produce correct counts."""
        runtime, *_ = _make_runtime()
        num_threads = 10
        submissions_per_thread = 20
        errors: list[str] = []

        def worker():
            try:
                for _ in range(submissions_per_thread):
                    runtime.submit("concurrent task", agent_id="agent-1")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        expected = num_threads * submissions_per_thread
        assert len(runtime.all_tasks) == expected
        assert runtime.queue_depth == expected

    def test_concurrent_submit_and_process(self):
        """Submitting and processing concurrently does not raise."""
        runtime, *_ = _make_runtime()
        errors: list[str] = []

        def submitter():
            try:
                for _ in range(20):
                    runtime.submit("task", agent_id="agent-1")
            except Exception as exc:
                errors.append(f"submit: {exc}")

        def processor():
            try:
                for _ in range(20):
                    runtime.process_next()
            except Exception as exc:
                errors.append(f"process: {exc}")

        t1 = threading.Thread(target=submitter)
        t2 = threading.Thread(target=processor)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert errors == [], f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# RT4-C2: Store-to-runtime hydration (from_store class method)
# ---------------------------------------------------------------------------


class TestFromStoreHydration:
    """ExecutionRuntime.from_store populates registry from a TrustStore."""

    def test_from_store_creates_runtime(self):
        """from_store reads trust objects and produces a working runtime."""
        store = MemoryStore()
        # Store a genesis record
        store.store_genesis(
            "authority-1",
            {
                "authority_id": "authority-1",
                "authority_name": "Test Authority",
            },
        )
        # Store a delegation (which implies an agent)
        store.store_delegation(
            "del-1",
            {
                "delegation_id": "del-1",
                "delegator_id": "authority-1",
                "delegatee_id": "agent-1",
                "agent_name": "Agent One",
                "agent_role": "worker",
                "team_id": "team-1",
                "capabilities": ["read", "write"],
            },
        )
        # Store an envelope for the agent
        store.store_envelope(
            "env-1",
            {
                "envelope_id": "env-1",
                "agent_id": "agent-1",
            },
        )

        gradient_config = VerificationGradientConfig(default_level=VerificationLevel.AUTO_APPROVED)
        audit_chain = AuditChain(chain_id="hydration-test")

        runtime = ExecutionRuntime.from_store(
            trust_store=store,
            gradient_config=gradient_config,
            audit_chain=audit_chain,
        )

        assert runtime is not None
        # The agent should have been hydrated into the registry
        task_id = runtime.submit("test action", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.assigned_agent_id == "agent-1"

    def test_from_store_no_delegations_empty_registry(self):
        """from_store with empty store creates runtime with no agents."""
        store = MemoryStore()
        gradient_config = VerificationGradientConfig(default_level=VerificationLevel.AUTO_APPROVED)
        audit_chain = AuditChain(chain_id="empty-test")

        runtime = ExecutionRuntime.from_store(
            trust_store=store,
            gradient_config=gradient_config,
            audit_chain=audit_chain,
        )

        task_id = runtime.submit("orphan task")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.FAILED


# ---------------------------------------------------------------------------
# RT4-H2: Persist audit anchors to TrustStore
# ---------------------------------------------------------------------------


class TestAuditPersistence:
    """Audit anchors are persisted to the TrustStore when configured."""

    def test_audit_anchor_persisted_to_store(self):
        """Completing a task writes an audit anchor to the trust store."""
        store = MemoryStore()
        runtime, _, audit_chain, _ = _make_runtime()
        # Attach the store to the runtime
        runtime._trust_store = store

        runtime.submit("read file", agent_id="agent-1")
        runtime.process_next()

        # The in-memory chain should have the anchor
        assert audit_chain.length == 1
        # The store should also have it
        anchor = audit_chain.latest
        stored = store.get_audit_anchor(anchor.anchor_id)
        assert stored is not None
        assert stored["agent_id"] == "agent-1"
        assert stored["action"] == "read file"

    def test_audit_not_persisted_without_store(self):
        """Without a trust store, audit only goes to the in-memory chain."""
        runtime, _, audit_chain, _ = _make_runtime()
        runtime.submit("task", agent_id="agent-1")
        runtime.process_next()
        assert audit_chain.length == 1
        # No store, no crash
        assert runtime._trust_store is None


# ---------------------------------------------------------------------------
# RT4-H3: Revocation check in _assign_agent
# ---------------------------------------------------------------------------


class TestRevocationCheck:
    """Revoked agents are rejected during assignment."""

    def test_revoked_agent_not_assigned(self):
        """An agent marked revoked in RevocationManager cannot execute tasks."""
        revocation_mgr = RevocationManager()
        revocation_mgr.surgical_revoke("agent-1", "compromised", "admin")

        runtime, _, _, _ = _make_runtime()
        runtime._revocation_manager = revocation_mgr

        runtime.submit("task", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert "revoked" in task.result.error.lower()

    def test_non_revoked_agent_assigned(self):
        """An agent not revoked proceeds normally."""
        revocation_mgr = RevocationManager()

        runtime, _, _, _ = _make_runtime()
        runtime._revocation_manager = revocation_mgr

        runtime.submit("task", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# RT4-H4: Posture checks — PSEUDO_AGENT blocked
# ---------------------------------------------------------------------------


class TestPostureCheck:
    """Agents at PSEUDO_AGENT posture are blocked from executing."""

    def test_pseudo_agent_blocked(self):
        """PSEUDO_AGENT posture blocks execution."""
        from care_platform.trust.posture import TrustPosture

        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.PSEUDO_AGENT,
            ),
        }

        runtime, _, _, _ = _make_runtime()
        runtime._posture_manager = posture_mgr

        runtime.submit("task", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.BLOCKED
        assert "pseudo_agent" in task.result.error.lower()

    def test_supervised_agent_escalated_to_held(self):
        """SUPERVISED posture escalates AUTO_APPROVED to HELD (RT5-07)."""
        from care_platform.trust.posture import TrustPosture

        posture_mgr: dict[str, TrustPosture] = {
            "agent-1": TrustPosture(
                agent_id="agent-1",
                current_level=TrustPostureLevel.SUPERVISED,
            ),
        }

        runtime, _, _, _ = _make_runtime()
        runtime._posture_manager = posture_mgr

        runtime.submit("task", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD
        assert task.verification_level == VerificationLevel.HELD


# ---------------------------------------------------------------------------
# RT4-M1: HELD task resumption
# ---------------------------------------------------------------------------


class TestHeldTaskResumption:
    """HELD tasks can be resumed with approve/reject decisions."""

    def test_resume_held_approved(self):
        """Approving a HELD task executes it."""
        runtime, _, audit_chain, _ = _make_runtime(default_level=VerificationLevel.HELD)
        runtime.submit("risky action", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        # Resume with approval
        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed is not None
        assert resumed.status == TaskStatus.COMPLETED
        # Should have audited both the HELD and the resume
        assert audit_chain.length >= 2

    def test_resume_held_rejected(self):
        """Rejecting a HELD task marks it FAILED."""
        runtime, *_ = _make_runtime(default_level=VerificationLevel.HELD)
        runtime.submit("risky action", agent_id="agent-1")
        task = runtime.process_next()
        assert task.status == TaskStatus.HELD

        resumed = runtime.resume_held(task.task_id, "rejected")
        assert resumed is not None
        assert resumed.status == TaskStatus.FAILED
        assert resumed.result is not None
        assert "rejected" in resumed.result.error.lower()

    def test_resume_non_held_returns_none(self):
        """Resuming a non-HELD task returns None."""
        runtime, *_ = _make_runtime()
        runtime.submit("ok task", agent_id="agent-1")
        task = runtime.process_next()
        assert task.status == TaskStatus.COMPLETED

        result = runtime.resume_held(task.task_id, "approved")
        assert result is None

    def test_resume_nonexistent_returns_none(self):
        """Resuming a task that does not exist returns None."""
        runtime, *_ = _make_runtime()
        result = runtime.resume_held("task-nonexistent", "approved")
        assert result is None


# ---------------------------------------------------------------------------
# RT4-M8: Task retry mechanism
# ---------------------------------------------------------------------------


class TestTaskRetry:
    """Failed tasks with retries remaining are re-enqueued."""

    def test_task_retried_on_failure(self):
        """A failing task with max_retries > 0 is re-enqueued."""
        runtime, *_ = _make_runtime()
        call_count = 0

        class FailOnceExecutor(TaskExecutor):
            def execute(self, task: Task, agent) -> TaskResult:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("Transient failure")
                return TaskResult(output="success on retry")

        runtime.set_executor(FailOnceExecutor())

        task_id = runtime.submit("flaky task", agent_id="agent-1", max_retries=2)
        # First process: fails, should re-enqueue with decremented retries
        task = runtime.process_next()
        assert task is not None
        # The task should have been re-enqueued
        assert runtime.queue_depth == 1

        # Second process: should succeed
        task2 = runtime.process_next()
        assert task2 is not None
        assert task2.status == TaskStatus.COMPLETED
        assert task2.result.output == "success on retry"

    def test_task_no_retry_when_exhausted(self):
        """A failing task with max_retries=0 stays FAILED."""
        runtime, *_ = _make_runtime()

        class AlwaysFails(TaskExecutor):
            def execute(self, task: Task, agent) -> TaskResult:
                raise RuntimeError("Permanent failure")

        runtime.set_executor(AlwaysFails())
        runtime.submit("doomed task", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert runtime.queue_depth == 0


# ---------------------------------------------------------------------------
# RT4-M11: BLOCKED task deduplication
# ---------------------------------------------------------------------------


class TestBlockedDeduplication:
    """Duplicate BLOCKED tasks are rejected."""

    def test_duplicate_blocked_rejected(self):
        """Submitting the same action+agent that is already BLOCKED is rejected."""
        runtime, *_ = _make_runtime(default_level=VerificationLevel.BLOCKED)
        runtime.submit("bad action", agent_id="agent-1")
        runtime.process_next()  # This will be BLOCKED

        with pytest.raises(ValueError, match="[Dd]uplicate"):
            runtime.submit("bad action", agent_id="agent-1")

    def test_different_action_not_deduplicated(self):
        """Different actions for the same agent are not deduplicated."""
        runtime, *_ = _make_runtime(default_level=VerificationLevel.BLOCKED)
        runtime.submit("bad action 1", agent_id="agent-1")
        runtime.process_next()

        # Different action should succeed
        task_id = runtime.submit("bad action 2", agent_id="agent-1")
        assert task_id is not None


# ---------------------------------------------------------------------------
# RT4-M2: Type-enforce AuthenticatedApprovalQueue
# ---------------------------------------------------------------------------


class TestApprovalQueueTyping:
    """Runtime accepts both ApprovalQueue and AuthenticatedApprovalQueue."""

    def test_accepts_plain_approval_queue(self):
        """Plain ApprovalQueue still works."""
        registry = AgentRegistry()
        registry.register(agent_id="a1", name="A1", role="worker", team_id="t1")
        gradient_config = VerificationGradientConfig(default_level=VerificationLevel.AUTO_APPROVED)
        gradient = GradientEngine(gradient_config)
        audit_chain = AuditChain(chain_id="test")
        queue = ApprovalQueue()

        runtime = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=queue,
        )
        task_id = runtime.submit("task", agent_id="a1")
        task = runtime.process_next()
        assert task.status == TaskStatus.COMPLETED

    def test_accepts_authenticated_approval_queue(self):
        """AuthenticatedApprovalQueue is accepted via the approval_queue param."""
        from care_platform.use.execution.approver_auth import ApproverRegistry

        registry = AgentRegistry()
        registry.register(agent_id="a1", name="A1", role="worker", team_id="t1")
        gradient_config = VerificationGradientConfig(default_level=VerificationLevel.AUTO_APPROVED)
        gradient = GradientEngine(gradient_config)
        audit_chain = AuditChain(chain_id="test")
        inner_queue = ApprovalQueue()
        approver_registry = ApproverRegistry()
        auth_queue = AuthenticatedApprovalQueue(queue=inner_queue, registry=approver_registry)

        runtime = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=auth_queue,
        )
        task_id = runtime.submit("task", agent_id="a1")
        task = runtime.process_next()
        assert task.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# RT4-M5: Cascade revocation updates AgentRegistry
# ---------------------------------------------------------------------------


class TestRevocationSync:
    """Revocations sync into the AgentRegistry."""

    def test_sync_revocations_updates_registry(self):
        """_sync_revocations marks revoked agents in the registry."""
        revocation_mgr = RevocationManager()
        revocation_mgr.surgical_revoke("agent-1", "compromised", "admin")

        runtime, registry, _, _ = _make_runtime()
        runtime._revocation_manager = revocation_mgr

        runtime._sync_revocations()

        agent = registry.get("agent-1")
        assert agent is not None
        assert agent.status == AgentStatus.REVOKED

    def test_sync_revocations_no_op_without_manager(self):
        """_sync_revocations does nothing when no revocation manager is set."""
        runtime, registry, _, _ = _make_runtime()
        runtime._sync_revocations()
        agent = registry.get("agent-1")
        assert agent.status == AgentStatus.ACTIVE


# ---------------------------------------------------------------------------
# RT4-M7: Posture changes auto-persisted
# ---------------------------------------------------------------------------


class TestPosturePersistence:
    """Posture changes are auto-persisted to TrustStore when available."""

    def test_posture_change_persisted(self):
        """Calling _persist_posture_change stores to trust store."""
        store = MemoryStore()
        runtime, _, _, _ = _make_runtime()
        runtime._trust_store = store

        runtime._persist_posture_change(
            "agent-1",
            {
                "agent_id": "agent-1",
                "from_posture": "supervised",
                "to_posture": "shared_planning",
                "reason": "evidence-based upgrade",
            },
        )

        history = store.get_posture_history("agent-1")
        assert len(history) == 1
        assert history[0]["from_posture"] == "supervised"

    def test_posture_change_not_persisted_without_store(self):
        """Without a trust store, posture persistence is a no-op."""
        runtime, _, _, _ = _make_runtime()
        # Should not raise
        runtime._persist_posture_change("agent-1", {"test": "data"})
