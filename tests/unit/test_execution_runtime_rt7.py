# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for RT7 findings in ExecutionRuntime.

Tests for three RT7 fixes:
- RT7-03: Lock held during TrustStore I/O in resume_held() -- pre-fetch envelopes
          outside lock to reduce lock hold time
- RT7-10: resume_held() silently continues on envelope re-evaluation exception --
          change to fail-closed behavior
- RT7-13: task.metadata values (data_paths, access_type) not type-validated before
          use in process_next() and resume_held()
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from care_platform.audit.anchor import AuditChain
from care_platform.config.schema import (
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
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
from care_platform.trust.posture import TrustPosture
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
    """Create a MemoryStore with a constraint envelope for testing."""
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


class SlowMemoryStore(MemoryStore):
    """A MemoryStore subclass that introduces artificial delay on list_envelopes.

    Used to verify that TrustStore I/O happens outside the runtime lock
    (RT7-03). If list_envelopes is called while the lock is held, concurrent
    operations will be blocked for the delay duration. If the pre-fetch
    happens outside the lock, concurrent operations can proceed.
    """

    def __init__(self, delay: float = 0.1) -> None:
        super().__init__()
        self._delay = delay
        self.list_envelopes_call_count = 0

    def list_envelopes(self, **kwargs: Any) -> list[dict]:
        self.list_envelopes_call_count += 1
        time.sleep(self._delay)
        return super().list_envelopes(**kwargs)


class ExplodingEnvelopeStore(MemoryStore):
    """A MemoryStore that raises on list_envelopes after initial setup.

    Used to test RT7-10 fail-closed behavior: when envelope re-evaluation
    throws, the task should FAIL rather than proceeding.
    """

    def __init__(self) -> None:
        super().__init__()
        self._should_explode = False

    def arm(self) -> None:
        """Arm the store to raise on subsequent list_envelopes calls."""
        self._should_explode = True

    def list_envelopes(self, **kwargs: Any) -> list[dict]:
        if self._should_explode:
            raise RuntimeError("Simulated TrustStore I/O failure")
        return super().list_envelopes(**kwargs)


# ---------------------------------------------------------------------------
# RT7-03: Lock held during TrustStore I/O in resume_held()
# ---------------------------------------------------------------------------


class TestRT7_03_LockDuringTrustStoreIO:
    """The list_envelopes() I/O should happen OUTSIDE the lock in resume_held()
    to avoid blocking other runtime operations during slow store reads."""

    def test_resume_held_prefetches_envelopes_outside_lock(self):
        """Concurrent submit() is not blocked during envelope pre-fetch.

        With a SlowMemoryStore, if list_envelopes happens under lock, a
        concurrent submit() will be delayed by the store's artificial delay.
        With proper pre-fetching outside the lock, submit() completes quickly.
        """
        slow_store = SlowMemoryStore(delay=0.2)
        # Set up envelope data in the slow store
        envelope_config = ConstraintEnvelopeConfig(
            id="env-1",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=envelope_config)
        envelope_data = envelope.model_dump(mode="json")
        envelope_data["agent_id"] = "agent-1"
        slow_store.store_envelope("env-1", envelope_data)

        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            trust_store=slow_store,
        )

        # Submit and process to get a HELD task
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        # Reset call count to track resume_held specifically
        slow_store.list_envelopes_call_count = 0

        # Time a concurrent submit during resume_held
        submit_times: list[float] = []
        submit_error: list[str] = []

        def concurrent_submit():
            start = time.monotonic()
            try:
                runtime.submit("quick action", agent_id="agent-2")
            except Exception as e:
                submit_error.append(str(e))
            submit_times.append(time.monotonic() - start)

        # Launch resume_held and a concurrent submit
        resume_thread = threading.Thread(
            target=runtime.resume_held,
            args=(task.task_id, "approved"),
        )
        submit_thread = threading.Thread(target=concurrent_submit)

        resume_thread.start()
        # Small delay to ensure resume_held starts first
        time.sleep(0.02)
        submit_thread.start()

        resume_thread.join(timeout=5)
        submit_thread.join(timeout=5)

        assert not submit_error, f"Submit failed: {submit_error}"
        assert len(submit_times) == 1

        # If envelope I/O was under the lock, submit would take ~0.2s
        # (blocked by the slow list_envelopes). With pre-fetch outside
        # the lock, submit should complete quickly (<0.1s).
        assert submit_times[0] < 0.15, (
            f"submit() took {submit_times[0]:.3f}s, suggesting list_envelopes "
            f"I/O is still blocking under the lock"
        )

    def test_resume_held_still_evaluates_envelope_correctly(self):
        """Pre-fetching doesn't break envelope evaluation.

        An envelope that denies the action should still cause FAILED status.
        We submit an allowed action (gets HELD), then change the envelope to
        block that action before resuming -- simulating constraints tightening
        while the task was held.
        """
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            trust_store=store,
        )

        # Submit an allowed action -- it passes envelope eval and gets HELD
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        # Now tighten the envelope: add "read docs" to blocked_actions
        # to simulate constraints changing while the task was held.
        tightened_config = ConstraintEnvelopeConfig(
            id="env-1",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                blocked_actions=["delete_production", "read docs"],
            ),
        )
        tightened_envelope = ConstraintEnvelope(config=tightened_config)
        tightened_data = tightened_envelope.model_dump(mode="json")
        tightened_data["agent_id"] = "agent-1"
        store.store_envelope("env-1", tightened_data)

        # Resume: envelope re-evaluation should now DENY "read docs"
        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed is not None
        assert resumed.status == TaskStatus.FAILED
        assert resumed.result is not None
        assert (
            "envelope" in resumed.result.error.lower() or "denied" in resumed.result.error.lower()
        )

    def test_resume_held_without_store_still_works(self):
        """Resume works normally when no TrustStore is configured."""
        runtime, _, _, _ = _make_runtime(default_level=VerificationLevel.HELD)

        runtime.submit("normal action", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed is not None
        assert resumed.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# RT7-10: Fail-closed on envelope re-evaluation exception in resume_held()
# ---------------------------------------------------------------------------


class TestRT7_10_FailClosedOnEnvelopeException:
    """When envelope re-evaluation throws an exception in resume_held(),
    the task MUST be set to FAILED (fail-closed), NOT allowed to proceed."""

    def test_envelope_exception_fails_task(self):
        """An exception during envelope re-evaluation sets task to FAILED."""
        store = ExplodingEnvelopeStore()
        # Set up envelope data before arming
        envelope_config = ConstraintEnvelopeConfig(
            id="env-1",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=envelope_config)
        envelope_data = envelope.model_dump(mode="json")
        envelope_data["agent_id"] = "agent-1"
        store.store_envelope("env-1", envelope_data)

        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            trust_store=store,
        )

        # Process to get HELD task (store not armed yet, works fine)
        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        # Arm the store to explode on next list_envelopes call
        store.arm()

        # Resume: envelope re-eval should throw -> fail-closed
        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed is not None
        assert resumed.status == TaskStatus.FAILED, (
            f"Expected FAILED (fail-closed) but got {resumed.status}. "
            f"The task should NOT proceed when envelope re-evaluation throws."
        )
        assert resumed.result is not None
        assert (
            "re-evaluation failed" in resumed.result.error.lower()
            or "constraint envelope" in resumed.result.error.lower()
        )

    def test_envelope_exception_records_error_detail(self):
        """The error message includes the original exception information."""
        store = ExplodingEnvelopeStore()
        envelope_config = ConstraintEnvelopeConfig(
            id="env-1",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=envelope_config)
        envelope_data = envelope.model_dump(mode="json")
        envelope_data["agent_id"] = "agent-1"
        store.store_envelope("env-1", envelope_data)

        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            trust_store=store,
        )

        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        store.arm()

        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed is not None
        assert resumed.status == TaskStatus.FAILED
        # The error should contain some reference to the original exception
        assert (
            "Simulated TrustStore I/O failure" in resumed.result.error
            or "re-evaluation failed" in resumed.result.error.lower()
        )

    def test_envelope_exception_does_not_proceed_to_execution(self):
        """Task must NOT reach EXECUTING or COMPLETED status on exception."""
        store = ExplodingEnvelopeStore()
        envelope_config = ConstraintEnvelopeConfig(
            id="env-1",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=envelope_config)
        envelope_data = envelope.model_dump(mode="json")
        envelope_data["agent_id"] = "agent-1"
        store.store_envelope("env-1", envelope_data)

        # Track whether executor was called
        executor_called = False

        class TrackingExecutor(TaskExecutor):
            def execute(self, task, agent):
                nonlocal executor_called
                executor_called = True
                return TaskResult(output="should not happen")

        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            trust_store=store,
        )
        runtime.set_executor(TrackingExecutor())

        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task.status == TaskStatus.HELD

        store.arm()

        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed.status == TaskStatus.FAILED
        assert not executor_called, (
            "Executor was called despite envelope re-evaluation exception. "
            "Fail-closed means the task should NOT be executed."
        )

    def test_successful_envelope_eval_still_works(self):
        """When envelope eval succeeds, task proceeds normally (no regression)."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            trust_store=store,
        )

        runtime.submit("read docs", agent_id="agent-1")
        task = runtime.process_next()
        assert task.status == TaskStatus.HELD

        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed is not None
        assert resumed.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# RT7-13: Type validation for task.metadata values before use
# ---------------------------------------------------------------------------


class TestRT7_13_MetadataTypeValidation:
    """task.metadata values (data_paths, access_type) must be type-validated
    before being passed to evaluate_action(). Invalid types should be
    silently excluded (not passed) rather than causing type errors."""

    def test_data_paths_valid_list_of_strings_passed(self):
        """Valid data_paths (list[str]) is passed to envelope evaluation."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"data_paths": ["/data/reports", "/data/logs"]},
        )
        task = runtime.process_next()
        assert task is not None
        # Task should complete (not crash from type error)
        assert task.status == TaskStatus.COMPLETED

    def test_data_paths_non_list_excluded(self):
        """data_paths that is NOT a list is excluded from eval_kwargs."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        # Pass a string instead of list[str]
        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"data_paths": "/data/reports"},
        )
        task = runtime.process_next()
        assert task is not None
        # Should not crash -- invalid type is excluded
        assert task.status == TaskStatus.COMPLETED

    def test_data_paths_list_with_non_strings_excluded(self):
        """data_paths that is a list but contains non-strings is excluded."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        # Pass a list with mixed types
        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"data_paths": ["/valid", 123, None]},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_data_paths_integer_excluded(self):
        """data_paths that is an integer is excluded."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"data_paths": 42},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_access_type_valid_read_passed(self):
        """access_type 'read' is a valid value and is passed through."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"access_type": "read"},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_access_type_valid_write_passed(self):
        """access_type 'write' is a valid value and is passed through."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"access_type": "write"},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_access_type_invalid_string_excluded(self):
        """access_type with an invalid string value is excluded."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        # 'execute' is not in {"read", "write"}
        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"access_type": "execute"},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_access_type_integer_excluded(self):
        """access_type that is an integer is excluded."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"access_type": 123},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_metadata_validation_in_resume_held_data_paths(self):
        """data_paths type validation also applies in resume_held() envelope eval."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            trust_store=store,
        )

        # Submit with invalid data_paths type
        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"data_paths": {"not": "a list"}},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        # Resume: should not crash on invalid data_paths type
        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed is not None
        # Should complete (or fail for envelope reasons), but NOT crash
        assert resumed.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        if resumed.status == TaskStatus.FAILED:
            # If failed, it should be for envelope reasons, not a TypeError
            assert "TypeError" not in (resumed.result.error or "")

    def test_metadata_validation_in_resume_held_access_type(self):
        """access_type type validation also applies in resume_held() envelope eval."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(
            default_level=VerificationLevel.HELD,
            trust_store=store,
        )

        # Submit with invalid access_type
        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"access_type": ["not", "a", "string"]},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.HELD

        # Resume: should not crash on invalid access_type type
        resumed = runtime.resume_held(task.task_id, "approved")
        assert resumed is not None
        assert resumed.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        if resumed.status == TaskStatus.FAILED:
            assert "TypeError" not in (resumed.result.error or "")

    def test_all_metadata_valid_passed_together(self):
        """When all metadata values are valid, they are all passed through."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={
                "data_paths": ["/data/reports"],
                "access_type": "read",
                "spend_amount": 10.0,
                "is_external": False,
            },
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_none_data_paths_not_passed(self):
        """data_paths=None (explicitly set) should not be passed."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"data_paths": None},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_none_access_type_not_passed(self):
        """access_type=None (explicitly set) should not be passed."""
        store = _make_envelope_store("agent-1")
        runtime, _, _, _ = _make_runtime(trust_store=store)

        runtime.submit(
            "read docs",
            agent_id="agent-1",
            metadata={"access_type": None},
        )
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
