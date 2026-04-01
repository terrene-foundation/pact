# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for SupervisorOrchestrator.

Covers:
- Input validation (empty request_id, empty role_address)
- NaN/Inf guard on context cost values
- Envelope resolution failure returns generic error (H4)
- NaN-guarded budget values in _record_run
- Successful execution records Run and emits completion event
- Supervisor creation failure returns appropriate error
- Property accessors (approval_bridge, event_bridge)

Note: GovernedSupervisor is a kaizen-agents dependency that requires
LLM API keys. Tests that exercise the full pipeline mock the supervisor
import. Tests for individual sub-components (delegate, adapter, bridge)
are in their own test files.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pact.governance import (
    CompiledOrg,
    GovernanceEngine,
    GovernanceVerdict,
    NodeType,
    OrgNode,
)
from pact_platform.engine.orchestrator import SupervisorOrchestrator
from pact_platform.models import db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine() -> GovernanceEngine:
    """Create a minimal GovernanceEngine."""
    dept = OrgNode(
        address="D1",
        node_type=NodeType.DEPARTMENT,
        name="Dept 1",
        node_id="D1",
    )
    role = OrgNode(
        address="D1-R1",
        node_type=NodeType.ROLE,
        name="Role 1",
        node_id="R1",
        parent_address="D1",
    )
    compiled = CompiledOrg(org_id="test-org", nodes={"D1": dept, "D1-R1": role})
    return GovernanceEngine(compiled)


@dataclass
class _FakeSupervisorResult:
    """Mimics the result object returned by GovernedSupervisor.run()."""

    success: bool = True
    results: dict[str, Any] = field(default_factory=dict)
    budget_consumed: float = 0.05
    budget_allocated: float = 1.0
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    modifications: list[Any] = field(default_factory=list)


class _FakeSupervisor:
    """Fake GovernedSupervisor that returns a configurable result."""

    def __init__(self, result: _FakeSupervisorResult | None = None, **kwargs: Any) -> None:
        self._result = result or _FakeSupervisorResult()
        self._init_kwargs = kwargs

    def run(
        self,
        objective: str,
        context: dict[str, Any],
        execute_node: Any = None,
    ) -> _FakeSupervisorResult:
        return self._result


def _mock_kaizen_module(supervisor_class: type) -> dict[str, ModuleType]:
    """Create a fake kaizen_agents module with a given GovernedSupervisor class.

    Returns a dict suitable for ``patch.dict(sys.modules, ...)``.
    The lazy import ``from kaizen_agents import GovernedSupervisor`` inside
    ``orchestrator.py`` will resolve to the provided class.
    """
    fake_mod = ModuleType("kaizen_agents")
    fake_mod.GovernedSupervisor = supervisor_class  # type: ignore[attr-defined]
    return {"kaizen_agents": fake_mod}


# ---------------------------------------------------------------------------
# Tests: Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """execute_request must reject empty/invalid inputs."""

    def test_empty_request_id_raises(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        with pytest.raises(ValueError, match="request_id must not be empty"):
            orch.execute_request(
                request_id="",
                role_address="D1-R1",
                objective="test",
            )

    def test_empty_role_address_raises(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        with pytest.raises(ValueError, match="role_address must not be empty"):
            orch.execute_request(
                request_id="req-1",
                role_address="",
                objective="test",
            )


# ---------------------------------------------------------------------------
# Tests: NaN guard on context
# ---------------------------------------------------------------------------


class TestContextNaNGuard:
    """NaN/Inf in context cost fields must be caught before execution."""

    def test_nan_cost_in_context_raises(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        with pytest.raises(ValueError, match="finite"):
            orch.execute_request(
                request_id="req-1",
                role_address="D1-R1",
                objective="test",
                context={"cost": float("nan")},
            )

    def test_inf_daily_total_in_context_raises(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        with pytest.raises(ValueError, match="finite"):
            orch.execute_request(
                request_id="req-1",
                role_address="D1-R1",
                objective="test",
                context={"daily_total": float("inf")},
            )

    def test_nan_transaction_amount_in_context_raises(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        with pytest.raises(ValueError, match="finite"):
            orch.execute_request(
                request_id="req-1",
                role_address="D1-R1",
                objective="test",
                context={"transaction_amount": float("nan")},
            )


# ---------------------------------------------------------------------------
# Tests: Envelope resolution failure
# ---------------------------------------------------------------------------


class TestEnvelopeResolutionFailure:
    """Envelope resolution failure must return a generic error (H4 fix)."""

    def test_envelope_failure_returns_success_false(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        # Patch the adapter's adapt method to raise an exception
        with patch.object(orch._adapter, "adapt", side_effect=RuntimeError("Connection lost")):
            result = orch.execute_request(
                request_id="req-fail",
                role_address="D1-R1",
                objective="test",
            )

        assert result["success"] is False
        assert result["request_id"] == "req-fail"
        # H4: generic error, not the internal exception message
        assert result["error"] == "Envelope resolution failed"
        assert result["budget_consumed"] == 0.0

    def test_envelope_failure_records_run(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        with patch.object(orch._adapter, "adapt", side_effect=RuntimeError("DB down")):
            result = orch.execute_request(
                request_id="req-fail-run",
                role_address="D1-R1",
                objective="test",
            )

        # Verify the failed run was recorded in DataFlow
        run_id = result["run_id"]
        wf = db.create_workflow("read_run")
        db.add_node(wf, "Run", "Read", "read", {"id": run_id})
        results, _ = db.execute_workflow(wf)
        run = results["read"]
        assert run["status"] == "failed"
        assert "Envelope resolution failed" in run["error_message"]


# ---------------------------------------------------------------------------
# Tests: Supervisor creation failure
# ---------------------------------------------------------------------------


class TestSupervisorCreationFailure:
    """Supervisor creation failure must return error with allocated budget."""

    def test_supervisor_creation_failure(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        class _BrokenSupervisor:
            def __init__(self, **kwargs):
                raise RuntimeError("Invalid config")

        with (
            patch.object(
                orch._adapter,
                "adapt",
                return_value={
                    "budget_usd": 10.0,
                    "tools": [],
                    "data_clearance": "public",
                    "timeout_seconds": 300,
                    "max_children": 10,
                    "max_depth": 5,
                },
            ),
            patch.dict(sys.modules, _mock_kaizen_module(_BrokenSupervisor)),
        ):
            result = orch.execute_request(
                request_id="req-no-supervisor",
                role_address="D1-R1",
                objective="test objective",
            )

        assert result["success"] is False
        assert result["error"] == "Supervisor creation failed"


# ---------------------------------------------------------------------------
# Tests: Successful execution
# ---------------------------------------------------------------------------


class TestSuccessfulExecution:
    """Full pipeline with a fake supervisor."""

    def test_success_returns_results(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        fake_result = _FakeSupervisorResult(
            success=True,
            results={"node-1": {"output": "done"}},
            budget_consumed=0.03,
            budget_allocated=1.0,
            audit_trail=[{"action": "read", "verdict": "auto_approved"}],
            modifications=["file.txt"],
        )

        class _GoodSupervisor(_FakeSupervisor):
            def __init__(self, **kwargs):
                super().__init__(fake_result)

        with (
            patch.object(
                orch._adapter,
                "adapt",
                return_value={
                    "budget_usd": 1.0,
                    "tools": ["web_search"],
                    "data_clearance": "restricted",
                    "timeout_seconds": 300,
                    "max_children": 10,
                    "max_depth": 5,
                },
            ),
            patch.dict(sys.modules, _mock_kaizen_module(_GoodSupervisor)),
        ):
            result = orch.execute_request(
                request_id="req-success",
                role_address="D1-R1",
                objective="Analyze data",
            )

        assert result["success"] is True
        assert result["request_id"] == "req-success"
        assert result["run_id"].startswith("run-")
        assert result["budget_consumed"] == 0.03
        assert result["budget_allocated"] == 1.0
        assert result["error"] is None

    def test_success_records_run_in_dataflow(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        fake_result = _FakeSupervisorResult(
            success=True,
            results={"n1": {}},
            budget_consumed=0.01,
            budget_allocated=0.5,
        )

        class _GoodSupervisor2(_FakeSupervisor):
            def __init__(self, **kwargs):
                super().__init__(fake_result)

        with (
            patch.object(
                orch._adapter,
                "adapt",
                return_value={
                    "budget_usd": 0.5,
                    "tools": [],
                    "data_clearance": "public",
                    "timeout_seconds": 300,
                    "max_children": 10,
                    "max_depth": 5,
                },
            ),
            patch.dict(sys.modules, _mock_kaizen_module(_GoodSupervisor2)),
        ):
            result = orch.execute_request(
                request_id="req-run-check",
                role_address="D1-R1",
                objective="Quick task",
            )

        # Read back the Run record
        run_id = result["run_id"]
        wf = db.create_workflow("read_run")
        db.add_node(wf, "Run", "Read", "read", {"id": run_id})
        results, _ = db.execute_workflow(wf)
        run = results["read"]
        assert run["status"] == "completed"
        assert run["cost_usd"] == pytest.approx(0.01, abs=0.001)


# ---------------------------------------------------------------------------
# Tests: NaN budget values from supervisor result
# ---------------------------------------------------------------------------


class TestNaNBudgetFromSupervisor:
    """NaN/Inf budget values from the supervisor must be sanitized to 0.0."""

    def test_nan_budget_consumed_recorded_as_zero(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        fake_result = _FakeSupervisorResult(
            success=True,
            results={},
            budget_consumed=float("nan"),
            budget_allocated=1.0,
        )

        class _NanSupervisor(_FakeSupervisor):
            def __init__(self, **kwargs):
                super().__init__(fake_result)

        with (
            patch.object(
                orch._adapter,
                "adapt",
                return_value={
                    "budget_usd": 1.0,
                    "tools": [],
                    "data_clearance": "public",
                    "timeout_seconds": 300,
                    "max_children": 10,
                    "max_depth": 5,
                },
            ),
            patch.dict(sys.modules, _mock_kaizen_module(_NanSupervisor)),
        ):
            result = orch.execute_request(
                request_id="req-nan-budget",
                role_address="D1-R1",
                objective="NaN test",
            )

        assert result["budget_consumed"] == 0.0

    def test_inf_budget_allocated_recorded_as_zero(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        fake_result = _FakeSupervisorResult(
            success=True,
            results={},
            budget_consumed=0.0,
            budget_allocated=float("inf"),
        )

        class _InfSupervisor(_FakeSupervisor):
            def __init__(self, **kwargs):
                super().__init__(fake_result)

        with (
            patch.object(
                orch._adapter,
                "adapt",
                return_value={
                    "budget_usd": 1.0,
                    "tools": [],
                    "data_clearance": "public",
                    "timeout_seconds": 300,
                    "max_children": 10,
                    "max_depth": 5,
                },
            ),
            patch.dict(sys.modules, _mock_kaizen_module(_InfSupervisor)),
        ):
            result = orch.execute_request(
                request_id="req-inf-budget",
                role_address="D1-R1",
                objective="Inf test",
            )

        assert result["budget_allocated"] == 0.0


# ---------------------------------------------------------------------------
# Tests: _record_run NaN guards
# ---------------------------------------------------------------------------


class TestRecordRunNaNGuard:
    """_record_run must sanitize NaN/Inf in cost_usd and duration_ms."""

    def test_nan_cost_usd_recorded_as_zero(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        from datetime import UTC, datetime

        now = datetime.now(UTC)
        # Calling _record_run directly to test its NaN guard
        orch._record_run(
            run_id="run-nan-cost",
            request_id="req-nan",
            role_address="D1-R1",
            status="completed",
            started_at=now,
            cost_usd=float("nan"),
        )

        # Read back the run
        wf = db.create_workflow("read_run")
        db.add_node(wf, "Run", "Read", "read", {"id": "run-nan-cost"})
        results, _ = db.execute_workflow(wf)
        run = results["read"]
        assert run["cost_usd"] == 0.0

    def test_inf_cost_usd_recorded_as_zero(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)

        from datetime import UTC, datetime

        now = datetime.now(UTC)
        orch._record_run(
            run_id="run-inf-cost",
            request_id="req-inf",
            role_address="D1-R1",
            status="completed",
            started_at=now,
            cost_usd=float("inf"),
        )

        wf = db.create_workflow("read_run")
        db.add_node(wf, "Run", "Read", "read", {"id": "run-inf-cost"})
        results, _ = db.execute_workflow(wf)
        run = results["read"]
        assert run["cost_usd"] == 0.0


# ---------------------------------------------------------------------------
# Tests: Property accessors
# ---------------------------------------------------------------------------


class TestPropertyAccessors:
    """Verify orchestrator exposes approval_bridge and event_bridge."""

    def test_approval_bridge_accessible(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)
        assert orch.approval_bridge is not None

    def test_event_bridge_accessible(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db)
        assert orch.event_bridge is not None

    def test_event_bridge_has_no_bus_when_none(self):
        engine = _make_engine()
        orch = SupervisorOrchestrator(engine, db, event_bus=None)
        assert orch.event_bridge._bus is None


# ---------------------------------------------------------------------------
# Tests: Supervisor execution failure
# ---------------------------------------------------------------------------


class TestSupervisorExecutionFailure:
    """When supervisor.run() raises, must return error and emit completion."""

    def test_supervisor_run_exception(self):
        engine = _make_engine()

        # Track completion events
        events: list[dict[str, Any]] = []

        class _TrackingBridge:
            def on_completion_event(self, **kwargs):
                events.append(kwargs)

        orch = SupervisorOrchestrator(engine, db)
        orch._event_bridge = _TrackingBridge()

        class _ExplodingSupervisor:
            def __init__(self, **kwargs):
                pass

            def run(self, **kwargs):
                raise RuntimeError("LLM provider timeout")

        with (
            patch.object(
                orch._adapter,
                "adapt",
                return_value={
                    "budget_usd": 1.0,
                    "tools": [],
                    "data_clearance": "public",
                    "timeout_seconds": 300,
                    "max_children": 10,
                    "max_depth": 5,
                },
            ),
            patch.dict(sys.modules, _mock_kaizen_module(_ExplodingSupervisor)),
        ):
            result = orch.execute_request(
                request_id="req-explode",
                role_address="D1-R1",
                objective="Doomed task",
            )

        assert result["success"] is False
        assert result["error"] == "Supervisor execution failed"
        # Completion event should have been emitted
        assert len(events) == 1
        assert events[0]["success"] is False
