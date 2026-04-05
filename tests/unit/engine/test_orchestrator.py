# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for SupervisorOrchestrator (PactEngine migration).

Covers:
- Input validation (empty request_id, empty role_address)
- NaN/Inf guard on context cost values
- PactEngine submission failure returns generic error (H4)
- NaN-guarded budget values in _record_run
- Successful execution records Run and emits completion event
- Property accessors (approval_bridge, event_bridge, pact_engine)
- GovernanceEngine backward-compat wrapping

Note: PactEngine.submit() is an async method; tests mock _submit_sync
to isolate orchestrator logic from the full PactEngine pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
from pact.work import WorkResult
from pact_platform.engine.orchestrator import SupervisorOrchestrator


# ---------------------------------------------------------------------------
# Helpers -- MockExpressSync
# ---------------------------------------------------------------------------


class MockExpressSync:
    """In-memory Express sync API that tracks all calls and stores records."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._store: dict[str, list[dict[str, Any]]] = {}

    def create(self, model: str, data: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"method": "create", "model": model, "data": data})
        self._store.setdefault(model, []).append(dict(data))
        return dict(data)

    def read(self, model: str, record_id: str) -> dict[str, Any] | None:
        self.calls.append({"method": "read", "model": model, "record_id": record_id})
        for rec in self._store.get(model, []):
            if rec.get("id") == record_id:
                return dict(rec)
        return None

    def update(self, model: str, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(
            {"method": "update", "model": model, "record_id": record_id, "fields": fields}
        )
        for rec in self._store.get(model, []):
            if rec.get("id") == record_id:
                rec.update(fields)
                return dict(rec)
        return fields

    def list(
        self, model: str, filter_dict: dict[str, Any], limit: int = 100
    ) -> list[dict[str, Any]]:
        self.calls.append({"method": "list", "model": model, "filter": filter_dict, "limit": limit})
        records = self._store.get(model, [])
        matched = []
        for rec in records:
            match = True
            for k, v in filter_dict.items():
                if rec.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(dict(rec))
        return matched[:limit]


class MockDB:
    """Mock DataFlow with express_sync attribute."""

    def __init__(self) -> None:
        self.express_sync = MockExpressSync()


# ---------------------------------------------------------------------------
# Helpers -- Governance engine factory
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


def _make_work_result(
    success: bool = True,
    results: dict[str, Any] | None = None,
    cost_usd: float = 0.05,
    error: str | None = None,
    governance_verdicts: list[dict[str, Any]] | None = None,
    governance_shadow: bool = False,
) -> WorkResult:
    """Create a WorkResult for testing."""
    return WorkResult(
        success=success,
        results=results or {},
        cost_usd=cost_usd,
        error=error,
        governance_verdicts=governance_verdicts or [],
        governance_shadow=governance_shadow,
    )


# ---------------------------------------------------------------------------
# Tests: Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """execute_request must reject empty/invalid inputs."""

    def test_empty_request_id_raises(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        with pytest.raises(ValueError, match="request_id must not be empty"):
            orch.execute_request(
                request_id="",
                role_address="D1-R1",
                objective="test",
            )

    def test_empty_role_address_raises(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

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
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        with pytest.raises(ValueError, match="finite"):
            orch.execute_request(
                request_id="req-1",
                role_address="D1-R1",
                objective="test",
                context={"cost": float("nan")},
            )

    def test_inf_daily_total_in_context_raises(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        with pytest.raises(ValueError, match="finite"):
            orch.execute_request(
                request_id="req-1",
                role_address="D1-R1",
                objective="test",
                context={"daily_total": float("inf")},
            )

    def test_nan_transaction_amount_in_context_raises(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        with pytest.raises(ValueError, match="finite"):
            orch.execute_request(
                request_id="req-1",
                role_address="D1-R1",
                objective="test",
                context={"transaction_amount": float("nan")},
            )


# ---------------------------------------------------------------------------
# Tests: PactEngine submission failure
# ---------------------------------------------------------------------------


class TestSubmissionFailure:
    """PactEngine submission failure must return a generic error (H4 fix)."""

    def test_submission_failure_returns_success_false(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        with patch.object(orch, "_submit_sync", side_effect=RuntimeError("Connection lost")):
            result = orch.execute_request(
                request_id="req-fail",
                role_address="D1-R1",
                objective="test",
            )

        assert result["success"] is False
        assert result["request_id"] == "req-fail"
        # H4: generic error, not the internal exception message
        assert result["error"] == "Execution failed"
        assert result["budget_consumed"] == 0.0

    def test_submission_failure_records_run(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        with patch.object(orch, "_submit_sync", side_effect=RuntimeError("DB down")):
            result = orch.execute_request(
                request_id="req-fail-run",
                role_address="D1-R1",
                objective="test",
            )

        # Verify the failed run was recorded in DataFlow
        run_id = result["run_id"]
        run = mock_db.express_sync.read("Run", run_id)
        assert run is not None
        assert run["status"] == "failed"
        assert "PactEngine submission failed" in run["error_message"]


# ---------------------------------------------------------------------------
# Tests: Successful execution via PactEngine
# ---------------------------------------------------------------------------


class TestSuccessfulExecution:
    """Full pipeline with mocked PactEngine.submit_sync()."""

    def test_success_returns_results(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        work_result = _make_work_result(
            success=True,
            results={"node-1": {"output": "done"}},
            cost_usd=0.03,
            governance_verdicts=[{"action": "read", "verdict": "auto_approved"}],
        )

        with patch.object(orch, "_submit_sync", return_value=work_result):
            result = orch.execute_request(
                request_id="req-success",
                role_address="D1-R1",
                objective="Analyze data",
            )

        assert result["success"] is True
        assert result["request_id"] == "req-success"
        assert result["run_id"].startswith("run-")
        assert result["budget_consumed"] == pytest.approx(0.03, abs=0.001)
        assert result["error"] is None
        assert result["audit_trail"] == [{"action": "read", "verdict": "auto_approved"}]

    def test_success_records_run_in_dataflow(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        work_result = _make_work_result(
            success=True,
            results={"n1": {}},
            cost_usd=0.01,
        )

        with patch.object(orch, "_submit_sync", return_value=work_result):
            result = orch.execute_request(
                request_id="req-run-check",
                role_address="D1-R1",
                objective="Quick task",
            )

        # Read back the Run record
        run_id = result["run_id"]
        run = mock_db.express_sync.read("Run", run_id)
        assert run is not None
        assert run["status"] == "completed"
        assert run["cost_usd"] == pytest.approx(0.01, abs=0.001)

    def test_pact_engine_is_used_for_execution(self):
        """Verify that execute_request calls _submit_sync (PactEngine path)."""
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        work_result = _make_work_result(success=True)

        with patch.object(orch, "_submit_sync", return_value=work_result) as mock_submit:
            orch.execute_request(
                request_id="req-pact",
                role_address="D1-R1",
                objective="Test PactEngine path",
            )

        mock_submit.assert_called_once()
        call_args = mock_submit.call_args
        # _submit_sync is called with positional args: (objective, role, context)
        assert call_args[0][0] == "Test PactEngine path"  # objective
        assert call_args[0][1] == "D1-R1"  # role
        assert call_args[0][2]["request_id"] == "req-pact"  # context


# ---------------------------------------------------------------------------
# Tests: NaN budget values from PactEngine result
# ---------------------------------------------------------------------------


class TestNaNBudgetFromPactEngine:
    """NaN/Inf budget values from PactEngine must be sanitized to 0.0."""

    def test_nan_cost_usd_recorded_as_zero(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        work_result = _make_work_result(
            success=True,
            cost_usd=float("nan"),
        )

        with patch.object(orch, "_submit_sync", return_value=work_result):
            result = orch.execute_request(
                request_id="req-nan-budget",
                role_address="D1-R1",
                objective="NaN test",
            )

        assert result["budget_consumed"] == 0.0

    def test_inf_cost_usd_recorded_as_zero(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        work_result = _make_work_result(
            success=True,
            cost_usd=float("inf"),
        )

        with patch.object(orch, "_submit_sync", return_value=work_result):
            result = orch.execute_request(
                request_id="req-inf-budget",
                role_address="D1-R1",
                objective="Inf test",
            )

        assert result["budget_consumed"] == 0.0


# ---------------------------------------------------------------------------
# Tests: _record_run NaN guards
# ---------------------------------------------------------------------------


class TestRecordRunNaNGuard:
    """_record_run must sanitize NaN/Inf in cost_usd and duration_ms."""

    def test_nan_cost_usd_recorded_as_zero(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        now = datetime.now(UTC)
        orch._record_run(
            run_id="run-nan-cost",
            request_id="req-nan",
            role_address="D1-R1",
            status="completed",
            started_at=now,
            cost_usd=float("nan"),
        )

        run = mock_db.express_sync.read("Run", "run-nan-cost")
        assert run is not None
        assert run["cost_usd"] == 0.0

    def test_inf_cost_usd_recorded_as_zero(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        now = datetime.now(UTC)
        orch._record_run(
            run_id="run-inf-cost",
            request_id="req-inf",
            role_address="D1-R1",
            status="completed",
            started_at=now,
            cost_usd=float("inf"),
        )

        run = mock_db.express_sync.read("Run", "run-inf-cost")
        assert run is not None
        assert run["cost_usd"] == 0.0


# ---------------------------------------------------------------------------
# Tests: Property accessors
# ---------------------------------------------------------------------------


class TestPropertyAccessors:
    """Verify orchestrator exposes approval_bridge, event_bridge, pact_engine."""

    def test_approval_bridge_accessible(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)
        assert orch.approval_bridge is not None

    def test_event_bridge_accessible(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)
        assert orch.event_bridge is not None

    def test_event_bridge_has_no_bus_when_none(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db, event_bus=None)
        assert orch.event_bridge._bus is None

    def test_pact_engine_property(self):
        """The pact_engine property should return the underlying PactEngine."""
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)
        from pact.engine import PactEngine

        assert isinstance(orch.pact_engine, PactEngine)


# ---------------------------------------------------------------------------
# Tests: GovernanceEngine backward compatibility
# ---------------------------------------------------------------------------


class TestGovernanceEngineBackwardCompat:
    """Verify that passing a bare GovernanceEngine still works."""

    def test_bare_governance_engine_wraps_in_pact_engine(self):
        engine = _make_engine()
        mock_db = MockDB()
        orch = SupervisorOrchestrator(engine, mock_db)

        from pact.engine import PactEngine

        assert isinstance(orch._pact, PactEngine)
        # The admin governance should be the original engine
        assert orch._pact._admin_governance is engine

    def test_pact_engine_passed_directly(self):
        """Passing a PactEngine directly should use it as-is."""
        from pact.engine import PactEngine

        engine = _make_engine()
        compiled_org = engine.get_org()
        pact = PactEngine(
            org={
                "org_id": compiled_org.org_id,
                "name": compiled_org.org_id,
            },
        )

        mock_db = MockDB()
        orch = SupervisorOrchestrator(pact, mock_db)
        assert orch._pact is pact


# ---------------------------------------------------------------------------
# Tests: Completion event bridging
# ---------------------------------------------------------------------------


class TestCompletionEventBridging:
    """When PactEngine.submit() raises, must return error and emit completion."""

    def test_submission_exception_emits_completion(self):
        engine = _make_engine()
        mock_db = MockDB()

        events: list[dict[str, Any]] = []

        class _TrackingBridge:
            def on_completion_event(self, **kwargs: Any) -> None:
                events.append(kwargs)

        orch = SupervisorOrchestrator(engine, mock_db)
        orch._event_bridge = _TrackingBridge()

        with patch.object(orch, "_submit_sync", side_effect=RuntimeError("LLM timeout")):
            result = orch.execute_request(
                request_id="req-explode",
                role_address="D1-R1",
                objective="Doomed task",
            )

        assert result["success"] is False
        assert result["error"] == "Execution failed"
        assert len(events) == 1
        assert events[0]["success"] is False

    def test_successful_execution_emits_completion(self):
        engine = _make_engine()
        mock_db = MockDB()

        events: list[dict[str, Any]] = []

        class _TrackingBridge:
            def on_completion_event(self, **kwargs: Any) -> None:
                events.append(kwargs)

        orch = SupervisorOrchestrator(engine, mock_db)
        orch._event_bridge = _TrackingBridge()

        work_result = _make_work_result(success=True, cost_usd=0.02)

        with patch.object(orch, "_submit_sync", return_value=work_result):
            result = orch.execute_request(
                request_id="req-ok",
                role_address="D1-R1",
                objective="Good task",
            )

        assert result["success"] is True
        assert len(events) == 1
        assert events[0]["success"] is True
        assert events[0]["budget_consumed"] == pytest.approx(0.02, abs=0.001)
