# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for ExecutionRuntime governance path and emergency halt.

Covers: halt blocks processing, resume unblocks, is_halted property,
empty-reason halt rejection, governance engine error fail-closed,
missing role address fail-closed, governance verdict happy paths
(auto_approved, flagged, held, blocked), cumulative budget injection,
and rate limit enforcement.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from pact_platform.build.config.schema import VerificationLevel
from pact_platform.trust.audit.anchor import AuditChain
from pact_platform.use.execution.registry import AgentRegistry
from pact_platform.use.execution.runtime import (
    ExecutionRuntime,
    Task,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# Mock governance engine
# ---------------------------------------------------------------------------


class _MockVerdict:
    """Minimal verdict object returned by the mock engine."""

    def __init__(
        self,
        level: str,
        reason: str = "",
        audit_details: dict[str, Any] | None = None,
        effective_envelope_snapshot: dict[str, Any] | None = None,
    ):
        self.level = level
        self.reason = reason
        self.audit_details = audit_details if audit_details is not None else {}
        self.effective_envelope_snapshot = effective_envelope_snapshot


class _MockEnvelopeConfig:
    """Minimal envelope config returned by compute_envelope().

    Mimics the Pydantic model_dump() interface used by the runtime's
    _check_rate_limit method.
    """

    def __init__(self, operational: dict[str, Any] | None = None) -> None:
        self._operational = operational or {}

    def model_dump(self) -> dict[str, Any]:
        return {"operational": self._operational}


class _MockGovernanceEngine:
    """Mock GovernanceEngine for testing runtime governance paths.

    Set ``verdict`` to control verify_action() responses.
    Set ``should_raise`` to make it throw on the next call.
    Set ``envelope_config`` to control compute_envelope() responses.
    """

    def __init__(self, verdict: _MockVerdict | None = None) -> None:
        self.verdict = verdict or _MockVerdict("auto_approved")
        self.should_raise: Exception | None = None
        self.call_count: int = 0
        self.last_context: dict[str, Any] | None = None
        self.last_role_address: str | None = None
        self.last_action: str | None = None
        self.envelope_config: _MockEnvelopeConfig | None = None

    def verify_action(
        self,
        role_address: str,
        action: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> _MockVerdict:
        self.call_count += 1
        self.last_role_address = role_address
        self.last_action = action
        self.last_context = context
        if self.should_raise is not None:
            raise self.should_raise
        return self.verdict

    def compute_envelope(self, role_address: str) -> _MockEnvelopeConfig | None:
        """Return a mock envelope config for rate limit checks."""
        return self.envelope_config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry() -> AgentRegistry:
    """A fresh AgentRegistry with a single active agent."""
    reg = AgentRegistry()
    reg.register(agent_id="agent-1", name="Test Agent", role="analyst")
    return reg


@pytest.fixture()
def audit_chain() -> AuditChain:
    return AuditChain(chain_id="test-chain")


@pytest.fixture()
def runtime(registry: AgentRegistry, audit_chain: AuditChain) -> ExecutionRuntime:
    """Runtime without a governance engine (for halt tests)."""
    return ExecutionRuntime(registry=registry, audit_chain=audit_chain)


# ---------------------------------------------------------------------------
# Test: emergency halt
# ---------------------------------------------------------------------------


class TestEmergencyHalt:
    """Verify the halt/resume mechanism on ExecutionRuntime."""

    def test_halt_blocks_process_next(
        self,
        runtime: ExecutionRuntime,
    ) -> None:
        """When halted, process_next() must return None even if tasks are queued."""
        runtime.submit("read_docs", agent_id="agent-1")
        runtime.halt("security incident")

        result = runtime.process_next()

        assert result is None
        assert runtime.queue_depth == 1, "Task should remain in the queue"

    def test_resume_unblocks(
        self,
        runtime: ExecutionRuntime,
    ) -> None:
        """After halt then resume, process_next() should process the task."""
        task_id = runtime.submit("read_docs", agent_id="agent-1")
        runtime.halt("investigating")
        runtime.resume()

        task = runtime.process_next()

        assert task is not None
        assert task.task_id == task_id
        assert task.status in (TaskStatus.COMPLETED, TaskStatus.EXECUTING)

    def test_is_halted_property(
        self,
        runtime: ExecutionRuntime,
    ) -> None:
        """is_halted must reflect the current halt state."""
        assert runtime.is_halted is False

        runtime.halt("test halt")
        assert runtime.is_halted is True

        runtime.resume()
        assert runtime.is_halted is False

    def test_halt_requires_reason(
        self,
        runtime: ExecutionRuntime,
    ) -> None:
        """An empty reason string must raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            runtime.halt("")


# ---------------------------------------------------------------------------
# Test: governance error path (fail-closed)
# ---------------------------------------------------------------------------


class TestGovernanceErrorPath:
    """Verify that governance engine errors result in BLOCKED tasks."""

    def test_governance_error_returns_blocked(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """When the governance engine raises, the task must be BLOCKED (fail-closed)."""
        engine = _MockGovernanceEngine()
        engine.should_raise = RuntimeError("engine unavailable")

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        # Map the agent to a role address so the governance path is entered
        rt.set_agent_role_address("agent-1", "D1-R1")

        task_id = rt.submit("summarize_report", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.status == TaskStatus.BLOCKED
        assert task.verification_level == VerificationLevel.BLOCKED
        assert task.result is not None
        assert "fail-closed" in task.result.error

    def test_missing_role_address_blocks(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Governance engine configured but no role_address for agent -> BLOCKED."""
        engine = _MockGovernanceEngine()

        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        # Deliberately do NOT set a role address for agent-1

        task_id = rt.submit("do_something", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.status == TaskStatus.BLOCKED
        assert task.verification_level == VerificationLevel.BLOCKED
        assert task.result is not None
        assert "no governance role address" in task.result.error.lower()
        # The engine should NOT have been called since there is no address
        assert engine.call_count == 0


# ---------------------------------------------------------------------------
# Test: governance verification happy paths
# ---------------------------------------------------------------------------


class TestGovernanceVerificationHappyPath:
    """Verify that each governance verdict level maps to the correct task state.

    The runtime's _run_governance_verification method converts the governance
    engine verdict into task status + verification_level. These tests cover
    the four verdict levels: auto_approved, flagged, held, and blocked.
    """

    def _make_governed_runtime(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
        verdict: _MockVerdict,
    ) -> tuple[ExecutionRuntime, _MockGovernanceEngine]:
        """Create a runtime with a governance engine returning the given verdict."""
        engine = _MockGovernanceEngine(verdict=verdict)
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")
        return rt, engine

    def test_auto_approved_proceeds_to_completion(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """When governance returns auto_approved, the task proceeds and completes."""
        rt, engine = self._make_governed_runtime(
            registry,
            audit_chain,
            _MockVerdict("auto_approved", reason="within envelope"),
        )

        task_id = rt.submit("read_data", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.verification_level == VerificationLevel.AUTO_APPROVED
        assert task.status == TaskStatus.COMPLETED
        assert engine.call_count == 1

    def test_flagged_proceeds_to_completion(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """When governance returns flagged, the task proceeds (with a warning) and completes."""
        rt, engine = self._make_governed_runtime(
            registry,
            audit_chain,
            _MockVerdict("flagged", reason="nearing budget limit"),
        )

        task_id = rt.submit("process_report", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.verification_level == VerificationLevel.FLAGGED
        assert task.status == TaskStatus.COMPLETED
        assert engine.call_count == 1

    def test_held_enters_approval_queue(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """When governance returns held, the task enters HELD status and is queued for approval."""
        rt, engine = self._make_governed_runtime(
            registry,
            audit_chain,
            _MockVerdict("held", reason="high-value action requires approval"),
        )

        task_id = rt.submit("transfer_funds", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.verification_level == VerificationLevel.HELD
        assert task.status == TaskStatus.HELD
        # Task should NOT have a result error — it is pending approval, not failed
        assert task.result is None or (task.result is not None and task.result.error is None)
        assert engine.call_count == 1

    def test_blocked_sets_error_with_reason(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """When governance returns blocked, the task is BLOCKED with an error carrying the reason."""
        rt, engine = self._make_governed_runtime(
            registry,
            audit_chain,
            _MockVerdict("blocked", reason="action outside envelope"),
        )

        task_id = rt.submit("delete_database", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.verification_level == VerificationLevel.BLOCKED
        assert task.status == TaskStatus.BLOCKED
        assert task.result is not None
        assert task.result.error is not None
        assert "action outside envelope" in task.result.error
        assert engine.call_count == 1


# ---------------------------------------------------------------------------
# Test: reasoning trace attachment (TODO-13)
# ---------------------------------------------------------------------------


class TestReasoningTraceAttachment:
    """Verify that HELD and BLOCKED verdicts attach a reasoning_trace to task metadata.

    TODO-13: When GovernanceEngine.verify_action() returns a HELD or BLOCKED
    verdict, the platform should attach a reasoning trace dict explaining WHY
    the constraint triggered.
    """

    def _make_governed_runtime(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
        verdict: _MockVerdict,
    ) -> tuple[ExecutionRuntime, _MockGovernanceEngine]:
        engine = _MockGovernanceEngine(verdict=verdict)
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")
        return rt, engine

    def test_blocked_verdict_has_reasoning_trace(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """BLOCKED verdict populates task.metadata['reasoning_trace']."""
        snapshot = {"financial": {"max_spend_per_action": 50.0}}
        rt, engine = self._make_governed_runtime(
            registry,
            audit_chain,
            _MockVerdict(
                "blocked",
                reason="budget exceeded",
                effective_envelope_snapshot=snapshot,
            ),
        )

        rt.submit("expensive_action", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.status == TaskStatus.BLOCKED
        trace = task.metadata.get("reasoning_trace")
        assert trace is not None
        assert trace["verdict"] == "blocked"
        assert trace["reason"] == "budget exceeded"
        assert trace["role_address"] == "D1-R1"
        assert trace["action"] == "expensive_action"
        assert trace["envelope_snapshot"] == snapshot
        assert "timestamp" in trace

    def test_held_verdict_has_reasoning_trace(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """HELD verdict populates task.metadata['reasoning_trace']."""
        rt, engine = self._make_governed_runtime(
            registry,
            audit_chain,
            _MockVerdict(
                "held",
                reason="requires human approval",
                effective_envelope_snapshot=None,
            ),
        )

        rt.submit("sensitive_action", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.status == TaskStatus.HELD
        trace = task.metadata.get("reasoning_trace")
        assert trace is not None
        assert trace["verdict"] == "held"
        assert trace["reason"] == "requires human approval"
        assert trace["role_address"] == "D1-R1"
        assert trace["action"] == "sensitive_action"
        assert trace["envelope_snapshot"] is None
        assert "timestamp" in trace

    def test_auto_approved_has_no_reasoning_trace(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """AUTO_APPROVED verdict does NOT attach a reasoning trace."""
        rt, engine = self._make_governed_runtime(
            registry,
            audit_chain,
            _MockVerdict("auto_approved"),
        )

        rt.submit("read_docs", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.metadata.get("reasoning_trace") is None

    def test_flagged_has_no_reasoning_trace(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """FLAGGED verdict does NOT attach a reasoning trace."""
        rt, engine = self._make_governed_runtime(
            registry,
            audit_chain,
            _MockVerdict("flagged", reason="near boundary"),
        )

        rt.submit("moderate_action", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        assert task.metadata.get("reasoning_trace") is None

    def test_reasoning_trace_timestamp_is_iso_format(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """The reasoning trace timestamp should be a valid ISO-8601 string."""
        from datetime import datetime as dt

        rt, engine = self._make_governed_runtime(
            registry,
            audit_chain,
            _MockVerdict("blocked", reason="test"),
        )

        rt.submit("test_action", agent_id="agent-1")
        task = rt.process_next()

        assert task is not None
        trace = task.metadata.get("reasoning_trace")
        assert trace is not None
        # Should parse without error
        parsed = dt.fromisoformat(trace["timestamp"])
        assert parsed is not None


# ---------------------------------------------------------------------------
# Test: cumulative budget injection into governance context
# ---------------------------------------------------------------------------


class TestCumulativeBudgetInjection:
    """Verify that cumulative_spend_usd and action_count_today are injected
    into the context dict passed to GovernanceEngine.verify_action().

    Per governance.md Rule 12, cumulative budget MUST be injected so the
    engine can enforce per-agent budget caps across multiple actions.
    """

    def test_context_contains_cumulative_spend_and_action_count(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """First task: cumulative_spend_usd=0.0 and action_count_today=0."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit("analyze_data", agent_id="agent-1", metadata={"cost": 5.0})
        rt.process_next()

        assert engine.last_context is not None
        assert (
            "cumulative_spend_usd" in engine.last_context
        ), "cumulative_spend_usd must be injected into governance context"
        assert (
            "action_count_today" in engine.last_context
        ), "action_count_today must be injected into governance context"
        # First task: no prior spend, no prior actions
        assert engine.last_context["cumulative_spend_usd"] == 0.0
        assert engine.last_context["action_count_today"] == 0

    def test_cost_metadata_forwarded_in_context(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """The cost value from task metadata must appear in the governance context."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit("expensive_action", agent_id="agent-1", metadata={"cost": 42.5})
        rt.process_next()

        assert engine.last_context is not None
        assert engine.last_context["cost"] == 42.5

    def test_cumulative_spend_accumulates_across_tasks(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """After completing a task with cost, the next task's context must reflect
        the accumulated cumulative_spend_usd."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        # Task 1: costs $10
        rt.submit("task_one", agent_id="agent-1", metadata={"cost": 10.0})
        rt.process_next()
        first_context = engine.last_context
        assert first_context is not None
        assert first_context["cumulative_spend_usd"] == 0.0  # no prior spend

        # Task 2: costs $25 — cumulative spend should reflect task 1's $10
        rt.submit("task_two", agent_id="agent-1", metadata={"cost": 25.0})
        rt.process_next()
        second_context = engine.last_context
        assert second_context is not None
        assert second_context["cumulative_spend_usd"] == 10.0

        # Task 3: cumulative should now be $35 ($10 + $25)
        rt.submit("task_three", agent_id="agent-1", metadata={"cost": 5.0})
        rt.process_next()
        third_context = engine.last_context
        assert third_context is not None
        assert third_context["cumulative_spend_usd"] == 35.0

    def test_action_count_today_increments(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """action_count_today must increment after each completed task."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        # Task 1: 0 prior actions
        rt.submit("first", agent_id="agent-1")
        rt.process_next()
        assert engine.last_context is not None
        assert engine.last_context["action_count_today"] == 0

        # Task 2: 1 prior action (task 1 completed)
        rt.submit("second", agent_id="agent-1")
        rt.process_next()
        assert engine.last_context is not None
        assert engine.last_context["action_count_today"] == 1

        # Task 3: 2 prior actions
        rt.submit("third", agent_id="agent-1")
        rt.process_next()
        assert engine.last_context is not None
        assert engine.last_context["action_count_today"] == 2


# ---------------------------------------------------------------------------
# Test: rate limit enforcement
# ---------------------------------------------------------------------------


class TestRateLimitEnforcement:
    """Verify that the runtime enforces per-agent rate limits from the
    governance envelope's operational.max_actions_per_day field.

    The runtime reads the envelope via compute_envelope(), checks the
    rolling 24-hour action count, and BLOCKs the task when exceeded.
    """

    def test_rate_limit_blocks_after_max_actions(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """When an agent exceeds max_actions_per_day, the next task is BLOCKED."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        engine.envelope_config = _MockEnvelopeConfig(
            operational={"max_actions_per_day": 2},
        )
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        # Task 1: within limit (0 prior actions)
        rt.submit("action_one", agent_id="agent-1")
        task1 = rt.process_next()
        assert task1 is not None
        assert task1.status == TaskStatus.COMPLETED

        # Task 2: within limit (1 prior action)
        rt.submit("action_two", agent_id="agent-1")
        task2 = rt.process_next()
        assert task2 is not None
        assert task2.status == TaskStatus.COMPLETED

        # Task 3: should be BLOCKED (2 actions already in rolling window, limit is 2)
        rt.submit("action_three", agent_id="agent-1")
        task3 = rt.process_next()
        assert task3 is not None
        assert task3.status == TaskStatus.BLOCKED
        assert task3.verification_level == VerificationLevel.BLOCKED
        assert task3.result is not None
        assert task3.result.error is not None
        assert "rate limit" in task3.result.error.lower()
        assert "2/2" in task3.result.error

    def test_rate_limit_not_enforced_when_no_envelope(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """When compute_envelope returns None, no rate limit is enforced."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        engine.envelope_config = None  # No envelope -> no rate limit
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        # Should succeed regardless of action count
        for i in range(5):
            rt.submit(f"action_{i}", agent_id="agent-1")
            task = rt.process_next()
            assert task is not None
            assert task.status == TaskStatus.COMPLETED

    def test_rate_limit_not_enforced_when_max_actions_not_set(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """When operational.max_actions_per_day is None, no rate limit is enforced."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        engine.envelope_config = _MockEnvelopeConfig(
            operational={"max_actions_per_day": None},
        )
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        for i in range(5):
            rt.submit(f"action_{i}", agent_id="agent-1")
            task = rt.process_next()
            assert task is not None
            assert task.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# Test: dimension context forwarding (TODO-19 wiring)
# ---------------------------------------------------------------------------


class TestDimensionContextForwarding:
    """Verify that dimension-specific context keys from task.metadata are
    forwarded to GovernanceEngine.verify_action().

    kailash-pact 0.4.1 enforces temporal, data-access, and communication
    dimensions in _evaluate_against_envelope(). The runtime must forward
    the relevant context keys so the engine can evaluate them.
    """

    def test_data_access_keys_forwarded(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """resource_path, access_type, data_type must reach verify_action context."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit(
            "read_file",
            agent_id="agent-1",
            metadata={
                "resource_path": "/data/reports/q1",
                "access_type": "read",
                "data_type": "financial",
            },
        )
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert ctx["resource_path"] == "/data/reports/q1"
        assert ctx["access_type"] == "read"
        assert ctx["data_type"] == "financial"

    def test_communication_keys_forwarded(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """is_external and channel must reach verify_action context."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit(
            "send_message",
            agent_id="agent-1",
            metadata={
                "is_external": True,
                "channel": "slack",
            },
        )
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert ctx["is_external"] is True
        assert ctx["channel"] == "slack"

    def test_dimension_keys_absent_when_not_in_metadata(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """When task.metadata omits dimension keys, they must not appear in context."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit("simple_action", agent_id="agent-1")
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert "resource_path" not in ctx
        assert "access_type" not in ctx
        assert "is_external" not in ctx
        assert "channel" not in ctx

    def test_is_external_false_forwarded(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """is_external=False must be forwarded (engine checks 'is not False')."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit(
            "internal_call",
            agent_id="agent-1",
            metadata={"is_external": False, "channel": "internal"},
        )
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert ctx["is_external"] is False
        assert ctx["channel"] == "internal"

    def test_all_dimension_keys_together(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """All five dimension keys can be forwarded simultaneously."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit(
            "complex_action",
            agent_id="agent-1",
            metadata={
                "cost": 100.0,
                "resource_path": "/data/sensitive",
                "access_type": "write",
                "data_type": "pii",
                "is_external": True,
                "channel": "email",
            },
        )
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert ctx["cost"] == 100.0
        assert ctx["resource_path"] == "/data/sensitive"
        assert ctx["access_type"] == "write"
        assert ctx["data_type"] == "pii"
        assert ctx["is_external"] is True
        assert ctx["channel"] == "email"
        # Financial/operational keys also present
        assert "cumulative_spend_usd" in ctx
        assert "action_count_today" in ctx


# ---------------------------------------------------------------------------
# Test: envelope snapshot redaction (H6)
# ---------------------------------------------------------------------------


class TestEnvelopeSnapshotRedaction:
    """Verify that envelope snapshots in reasoning traces are redacted."""

    def test_redaction_function_redacts_sensitive_keys(self):
        from pact_platform.use.execution.runtime import _redact_envelope_snapshot

        snapshot = {
            "financial": {
                "max_budget": 10000.0,
                "max_cost_per_action": 500.0,
                "currency": "USD",
            },
            "data_access": {
                "read_paths": ["/data/public", "/data/internal"],
                "write_paths": ["/data/public"],
                "denied_paths": ["/data/secret"],
                "blocked_data_types": ["pii", "phi"],
            },
            "communication": {
                "internal_only": True,
                "allowed_channels": ["slack", "email"],
            },
            "operational": {
                "max_actions_per_day": 100,
            },
        }

        redacted = _redact_envelope_snapshot(snapshot)
        assert redacted is not None

        # Sensitive fields are redacted
        assert redacted["financial"]["max_budget"] == "[REDACTED]"
        assert redacted["financial"]["max_cost_per_action"] == "[REDACTED]"
        assert redacted["data_access"]["read_paths"] == "[REDACTED]"
        assert redacted["data_access"]["write_paths"] == "[REDACTED]"
        assert redacted["data_access"]["denied_paths"] == "[REDACTED]"
        assert redacted["data_access"]["blocked_data_types"] == "[REDACTED]"
        assert redacted["communication"]["allowed_channels"] == "[REDACTED]"

        # Non-sensitive fields are preserved
        assert redacted["financial"]["currency"] == "USD"
        assert redacted["communication"]["internal_only"] is True
        assert redacted["operational"]["max_actions_per_day"] == 100

    def test_redaction_function_returns_none_for_none(self):
        from pact_platform.use.execution.runtime import _redact_envelope_snapshot

        assert _redact_envelope_snapshot(None) is None

    def test_blocked_verdict_has_redacted_snapshot(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """BLOCKED verdicts must have redacted envelope snapshots in reasoning traces."""
        envelope_snapshot = {
            "financial": {"max_budget": 5000.0},
            "operational": {"max_actions_per_day": 50},
        }
        engine = _MockGovernanceEngine(
            verdict=_MockVerdict(
                "blocked",
                reason="Budget exceeded",
                effective_envelope_snapshot=envelope_snapshot,
            ),
        )
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit("expensive_action", agent_id="agent-1", metadata={"cost": 10000.0})
        task = rt.process_next()

        assert task is not None
        trace = task.metadata.get("reasoning_trace")
        assert trace is not None
        assert trace["envelope_snapshot"]["financial"]["max_budget"] == "[REDACTED]"
        # Non-sensitive field preserved
        assert trace["envelope_snapshot"]["operational"]["max_actions_per_day"] == 50


# ---------------------------------------------------------------------------
# Test: H1/H2 input validation on governance context
# ---------------------------------------------------------------------------


class TestGovernanceContextValidation:
    """Verify that dimension context values are validated before L1 forwarding."""

    def test_nan_cost_sanitized(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """NaN cost must be replaced with 0.0, not forwarded to engine."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit("action", agent_id="agent-1", metadata={"cost": float("nan")})
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert ctx["cost"] == 0.0

    def test_negative_cost_sanitized(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit("action", agent_id="agent-1", metadata={"cost": -100.0})
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert ctx["cost"] == 0.0

    def test_path_traversal_normalized(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """resource_path with '../' is normalized (posixpath.normpath resolves it)."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        # /data/../secrets/keys contains ".." — blocked by path traversal guard.
        # normalize_resource_path preserves ".." (doesn't collapse it),
        # and the traversal check correctly blocks the path.
        rt.submit(
            "action",
            agent_id="agent-1",
            metadata={"resource_path": "/data/../secrets/keys", "access_type": "read"},
        )
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert "resource_path" not in ctx  # Blocked — contains ".."

    def test_leading_traversal_blocked(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """resource_path with leading '../' that escapes root must be blocked."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit(
            "action",
            agent_id="agent-1",
            metadata={"resource_path": "../../../etc/passwd", "access_type": "read"},
        )
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert "resource_path" not in ctx  # Blocked — still has '..' after normpath

    def test_invalid_access_type_dropped(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """access_type must be 'read' or 'write' — other values dropped."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit(
            "action",
            agent_id="agent-1",
            metadata={"access_type": "admin"},
        )
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert "access_type" not in ctx

    def test_is_external_coerced_to_bool(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """is_external must be coerced to bool."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit(
            "action",
            agent_id="agent-1",
            metadata={"is_external": "true"},
        )
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert ctx["is_external"] is True  # coerced from string
        assert isinstance(ctx["is_external"], bool)

    def test_channel_truncated(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
    ) -> None:
        """Channel strings must be truncated to 256 chars."""
        engine = _MockGovernanceEngine(verdict=_MockVerdict("auto_approved"))
        rt = ExecutionRuntime(
            registry=registry,
            audit_chain=audit_chain,
            governance_engine=engine,
        )
        rt.set_agent_role_address("agent-1", "D1-R1")

        rt.submit(
            "action",
            agent_id="agent-1",
            metadata={"channel": "x" * 500},
        )
        rt.process_next()

        ctx = engine.last_context
        assert ctx is not None
        assert len(ctx["channel"]) == 256
