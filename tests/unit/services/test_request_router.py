# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for RequestRouterService — governance-gated request dispatch.

Tests cover all code paths:
1. No governance engine (fail-closed BLOCKED)
2. Engine returns ``blocked`` verdict
3. Engine returns ``held`` verdict (creates AgenticDecision record)
4. Engine returns ``auto_approved`` verdict (assigns to pool)
5. Engine returns ``flagged`` verdict (warns, then assigns to pool)
6. Empty request_id / org_address raise ValueError
7. NaN / Inf cost in context raises ValueError via validate_finite
8. Engine raises exception (fail-closed BLOCKED)
9. Pool assignment when no pool found (returns "unassigned")
10. Pool assignment when pool found (updates request assignment)
"""

from __future__ import annotations

import logging
import math
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pact.governance import GovernanceVerdict
from pact_platform.use.services.request_router import RequestRouterService


# ---------------------------------------------------------------------------
# Test helpers — mock DataFlow that tracks workflow executions
# ---------------------------------------------------------------------------


class _WorkflowStub:
    """Lightweight stand-in for a DataFlow workflow object."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.nodes: list[dict[str, Any]] = []


class MockDataFlow:
    """Minimal DataFlow double that records create/add/execute calls.

    ``execute_results`` maps workflow names to the (results, run_id) tuples
    that ``execute_workflow`` returns.  If not configured for a given
    workflow, a safe empty default is returned.
    """

    def __init__(self, execute_results: dict[str, tuple[dict, str]] | None = None) -> None:
        self.created_workflows: list[_WorkflowStub] = []
        self.added_nodes: list[dict[str, Any]] = []
        self.executed_workflows: list[_WorkflowStub] = []
        self._execute_results = execute_results or {}

    def create_workflow(self, name: str = "") -> _WorkflowStub:
        wf = _WorkflowStub(name)
        self.created_workflows.append(wf)
        return wf

    def add_node(
        self, wf: _WorkflowStub, model: str, operation: str, node_id: str, params: dict
    ) -> None:
        entry = {
            "workflow": wf.name,
            "model": model,
            "operation": operation,
            "node_id": node_id,
            "params": params,
        }
        wf.nodes.append(entry)
        self.added_nodes.append(entry)

    def execute_workflow(self, wf: _WorkflowStub) -> tuple[dict, str]:
        self.executed_workflows.append(wf)
        if wf.name in self._execute_results:
            return self._execute_results[wf.name]
        return ({}, "run-test")


def _make_verdict(
    level: str,
    reason: str = "",
    role_address: str = "D1-R1",
    action: str = "write",
    envelope_version: str = "",
) -> GovernanceVerdict:
    """Helper to create a GovernanceVerdict with sensible defaults."""
    return GovernanceVerdict(
        level=level,
        reason=reason,
        role_address=role_address,
        action=action,
        envelope_version=envelope_version,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_db() -> MockDataFlow:
    """Return a MockDataFlow with default (empty) execution results."""
    return MockDataFlow(
        execute_results={
            "find_pool": (
                {"list_pools": {"records": [{"id": "pool-abc"}]}},
                "run-pool",
            ),
            "assign_request": ({}, "run-assign"),
        }
    )


@pytest.fixture()
def mock_db_no_pool() -> MockDataFlow:
    """Return a MockDataFlow where pool lookup returns no records."""
    return MockDataFlow(
        execute_results={
            "find_pool": ({"list_pools": {"records": []}}, "run-pool"),
        }
    )


@pytest.fixture()
def mock_engine() -> MagicMock:
    """Return a mock GovernanceEngine whose verify_action is configurable."""
    engine = MagicMock()
    engine.verify_action = MagicMock()
    return engine


# ---------------------------------------------------------------------------
# 1. No governance engine — fail-closed BLOCKED
# ---------------------------------------------------------------------------


class TestNoGovernanceEngine:
    """When no governance engine is configured, every request must be blocked."""

    def test_blocks_without_engine(self, mock_db: MockDataFlow) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=None)
        result = service.route_request(
            request_id="req-001",
            org_address="D1-R1",
            action="write",
        )
        assert result["status"] == "blocked"
        assert "fail-closed" in result["reason"]
        assert result["request_id"] == "req-001"

    def test_no_db_calls_when_blocked_without_engine(self, mock_db: MockDataFlow) -> None:
        """Fail-closed path must not touch the database at all."""
        service = RequestRouterService(db=mock_db, governance_engine=None)
        service.route_request(
            request_id="req-002",
            org_address="D1-R1",
            action="read",
        )
        assert len(mock_db.created_workflows) == 0
        assert len(mock_db.executed_workflows) == 0

    def test_logs_warning_on_init_without_engine(self, mock_db: MockDataFlow, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="pact_platform.use.services.request_router"):
            RequestRouterService(db=mock_db, governance_engine=None)
        assert any("without governance engine" in msg for msg in caplog.messages)

    def test_logs_warning_on_route_without_engine(self, mock_db: MockDataFlow, caplog) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=None)
        with caplog.at_level(logging.WARNING, logger="pact_platform.use.services.request_router"):
            service.route_request(
                request_id="req-003",
                org_address="D1-R1",
                action="write",
            )
        assert any("fail-closed" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# 2. Engine returns ``blocked`` verdict
# ---------------------------------------------------------------------------


class TestBlockedVerdict:
    """Engine says BLOCKED -- the service must reject immediately."""

    def test_blocked_verdict_returns_blocked_status(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(
            level="blocked", reason="Budget exceeded"
        )
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-100",
            org_address="D1-R1",
            action="spend",
        )
        assert result["status"] == "blocked"
        assert result["reason"] == "Budget exceeded"
        assert result["request_id"] == "req-100"

    def test_blocked_verdict_does_not_create_decision(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="blocked", reason="nope")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-101",
            org_address="D1-R1",
            action="write",
        )
        # No workflows should be created for a blocked verdict
        assert len(mock_db.created_workflows) == 0

    def test_blocked_verdict_does_not_assign_pool(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="blocked", reason="denied")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-102",
            org_address="D1-R1",
            action="write",
        )
        assert "assigned_to" not in result

    def test_engine_called_with_correct_args(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="blocked", reason="x")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-103",
            org_address="D2-T1-R1",
            action="deploy",
            context={"cost": 50.0, "resource": "/api/v1"},
        )
        mock_engine.verify_action.assert_called_once_with(
            role_address="D2-T1-R1",
            action="deploy",
            context={"cost": 50.0, "resource": "/api/v1"},
        )


# ---------------------------------------------------------------------------
# 3. Engine returns ``held`` verdict — creates AgenticDecision
# ---------------------------------------------------------------------------


class TestHeldVerdict:
    """Engine says HELD -- the service must persist a decision for human review."""

    def test_held_verdict_returns_held_status(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(
            level="held", reason="Needs supervisor approval", envelope_version="3"
        )
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-200",
            org_address="D1-R1",
            action="write",
        )
        assert result["status"] == "held"
        assert result["reason"] == "Needs supervisor approval"
        assert result["request_id"] == "req-200"
        assert "decision_id" in result
        assert result["decision_id"].startswith("dec-")

    def test_held_verdict_creates_decision_workflow(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(
            level="held", reason="requires review", envelope_version="5"
        )
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-201",
            org_address="D1-T1-R1",
            action="write",
        )

        # Should have created a "create_hold_decision" workflow
        decision_wfs = [wf for wf in mock_db.created_workflows if wf.name == "create_hold_decision"]
        assert len(decision_wfs) == 1

        # Should have added a node with the correct params
        decision_nodes = [n for n in mock_db.added_nodes if n["node_id"] == "create_decision"]
        assert len(decision_nodes) == 1
        params = decision_nodes[0]["params"]
        assert params["request_id"] == "req-201"
        assert params["agent_address"] == "D1-T1-R1"
        assert params["action"] == "write"
        assert params["decision_type"] == "governance_hold"
        assert params["status"] == "pending"
        assert params["reason_held"] == "requires review"
        assert params["envelope_version"] == 5  # parsed to int

    def test_held_verdict_does_not_assign_pool(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="held", reason="hold")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-202",
            org_address="D1-R1",
            action="write",
        )
        assert "assigned_to" not in result

    def test_held_with_empty_envelope_version(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        """Empty envelope_version should fall back to 0."""
        mock_engine.verify_action.return_value = _make_verdict(
            level="held", reason="hold", envelope_version=""
        )
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-203",
            org_address="D1-R1",
            action="write",
        )
        decision_nodes = [n for n in mock_db.added_nodes if n["node_id"] == "create_decision"]
        assert decision_nodes[0]["params"]["envelope_version"] == 0


# ---------------------------------------------------------------------------
# 4. Engine returns ``auto_approved`` — assigns to pool
# ---------------------------------------------------------------------------


class TestAutoApprovedVerdict:
    """Engine says AUTO_APPROVED -- assign to pool and return approved."""

    def test_auto_approved_returns_approved_status(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(
            level="auto_approved", reason="Within envelope"
        )
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-300",
            org_address="D1-R1",
            action="read",
        )
        assert result["status"] == "approved"
        assert result["assigned_to"] == "pool-abc"
        assert result["request_id"] == "req-300"

    def test_auto_approved_triggers_pool_lookup(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-301",
            org_address="D1-R1",
            action="read",
        )
        pool_wfs = [wf for wf in mock_db.created_workflows if wf.name == "find_pool"]
        assert len(pool_wfs) == 1

    def test_auto_approved_updates_request_assignment(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-302",
            org_address="D1-R1",
            action="read",
        )
        assign_wfs = [wf for wf in mock_db.created_workflows if wf.name == "assign_request"]
        assert len(assign_wfs) == 1
        assign_nodes = [n for n in mock_db.added_nodes if n["node_id"] == "assign"]
        assert len(assign_nodes) == 1
        params = assign_nodes[0]["params"]
        assert params["filter"] == {"id": "req-302"}
        assert params["fields"]["assigned_to"] == "pool-abc"
        assert params["fields"]["status"] == "assigned"

    def test_auto_approved_no_pool_returns_unassigned(
        self, mock_db_no_pool: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db_no_pool, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-303",
            org_address="D1-R1",
            action="read",
        )
        assert result["status"] == "approved"
        assert result["assigned_to"] == "unassigned"


# ---------------------------------------------------------------------------
# 5. Engine returns ``flagged`` — warns but proceeds to assignment
# ---------------------------------------------------------------------------


class TestFlaggedVerdict:
    """Engine says FLAGGED -- log a warning but assign to pool anyway."""

    def test_flagged_returns_approved_status(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(
            level="flagged", reason="Unusual pattern detected"
        )
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-400",
            org_address="D1-R1",
            action="write",
        )
        assert result["status"] == "approved"
        assert result["assigned_to"] == "pool-abc"

    def test_flagged_logs_warning(
        self, mock_db: MockDataFlow, mock_engine: MagicMock, caplog
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(
            level="flagged", reason="Anomaly score high"
        )
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        with caplog.at_level(logging.WARNING, logger="pact_platform.use.services.request_router"):
            service.route_request(
                request_id="req-401",
                org_address="D1-R1",
                action="write",
            )
        flagged_msgs = [msg for msg in caplog.messages if "FLAGGED" in msg]
        assert len(flagged_msgs) >= 1
        assert "Anomaly score high" in flagged_msgs[0]


# ---------------------------------------------------------------------------
# 6. Input validation — empty request_id / org_address
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Empty required fields must raise ValueError immediately."""

    def test_empty_request_id_raises(self, mock_db: MockDataFlow) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=None)
        with pytest.raises(ValueError, match="request_id must not be empty"):
            service.route_request(request_id="", org_address="D1-R1", action="write")

    def test_none_request_id_raises(self, mock_db: MockDataFlow) -> None:
        """None is falsy, should also be rejected."""
        service = RequestRouterService(db=mock_db, governance_engine=None)
        with pytest.raises(ValueError, match="request_id must not be empty"):
            service.route_request(request_id=None, org_address="D1-R1", action="write")

    def test_empty_org_address_raises(self, mock_db: MockDataFlow) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=None)
        with pytest.raises(ValueError, match="org_address must not be empty"):
            service.route_request(request_id="req-001", org_address="", action="write")

    def test_none_org_address_raises(self, mock_db: MockDataFlow) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=None)
        with pytest.raises(ValueError, match="org_address must not be empty"):
            service.route_request(request_id="req-001", org_address=None, action="write")

    def test_validation_runs_before_governance(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        """Validation errors should fire before the engine is ever consulted."""
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        with pytest.raises(ValueError):
            service.route_request(request_id="", org_address="D1-R1", action="write")
        mock_engine.verify_action.assert_not_called()


# ---------------------------------------------------------------------------
# 7. NaN / Inf cost in context — validate_finite
# ---------------------------------------------------------------------------


class TestNanInfCostValidation:
    """NaN and Inf cost values must be rejected before reaching governance."""

    def test_nan_cost_raises(self, mock_db: MockDataFlow, mock_engine: MagicMock) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        with pytest.raises(ValueError, match="must be finite"):
            service.route_request(
                request_id="req-700",
                org_address="D1-R1",
                action="write",
                context={"cost": float("nan")},
            )

    def test_positive_inf_cost_raises(self, mock_db: MockDataFlow, mock_engine: MagicMock) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        with pytest.raises(ValueError, match="must be finite"):
            service.route_request(
                request_id="req-701",
                org_address="D1-R1",
                action="write",
                context={"cost": float("inf")},
            )

    def test_negative_inf_cost_raises(self, mock_db: MockDataFlow, mock_engine: MagicMock) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        with pytest.raises(ValueError, match="must be finite"):
            service.route_request(
                request_id="req-702",
                org_address="D1-R1",
                action="write",
                context={"cost": float("-inf")},
            )

    def test_nan_cost_does_not_reach_engine(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        with pytest.raises(ValueError):
            service.route_request(
                request_id="req-703",
                org_address="D1-R1",
                action="write",
                context={"cost": float("nan")},
            )
        mock_engine.verify_action.assert_not_called()

    def test_valid_cost_passes_through(self, mock_db: MockDataFlow, mock_engine: MagicMock) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-704",
            org_address="D1-R1",
            action="write",
            context={"cost": 42.5},
        )
        assert result["status"] == "approved"

    def test_zero_cost_passes_through(self, mock_db: MockDataFlow, mock_engine: MagicMock) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-705",
            org_address="D1-R1",
            action="write",
            context={"cost": 0.0},
        )
        assert result["status"] == "approved"

    def test_none_cost_passes_through(self, mock_db: MockDataFlow, mock_engine: MagicMock) -> None:
        """context with no 'cost' key should be fine."""
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-706",
            org_address="D1-R1",
            action="write",
            context={"resource": "/api/v1"},
        )
        assert result["status"] == "approved"


# ---------------------------------------------------------------------------
# 8. Engine raises exception — fail-closed BLOCKED
# ---------------------------------------------------------------------------


class TestEngineException:
    """If the governance engine raises, the service must fail-closed to BLOCKED."""

    def test_engine_exception_returns_blocked(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.side_effect = RuntimeError("Engine crashed")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-800",
            org_address="D1-R1",
            action="write",
        )
        assert result["status"] == "blocked"
        assert (
            "internal error" in result["reason"].lower()
            or "fail-closed" in result["reason"].lower()
        )
        assert result["request_id"] == "req-800"

    def test_engine_exception_does_not_create_decision(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.side_effect = ValueError("bad input")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-801",
            org_address="D1-R1",
            action="write",
        )
        assert len(mock_db.created_workflows) == 0

    def test_engine_exception_does_not_assign_pool(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.side_effect = TypeError("unexpected")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-802",
            org_address="D1-R1",
            action="write",
        )
        assert "assigned_to" not in result

    def test_engine_exception_logs_error(
        self, mock_db: MockDataFlow, mock_engine: MagicMock, caplog
    ) -> None:
        mock_engine.verify_action.side_effect = RuntimeError("kaboom")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        with caplog.at_level(logging.ERROR, logger="pact_platform.use.services.request_router"):
            service.route_request(
                request_id="req-803",
                org_address="D1-R1",
                action="write",
            )
        assert any("fail-closed" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# 9. Pool assignment edge cases
# ---------------------------------------------------------------------------


class TestPoolAssignment:
    """Pool lookup and request assignment edge cases."""

    def test_org_id_extraction_from_address(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        """The service extracts org_id as the first segment before '-'."""
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-900",
            org_address="Engineering-Backend-SeniorDev",
            action="write",
        )
        pool_nodes = [n for n in mock_db.added_nodes if n["node_id"] == "list_pools"]
        assert len(pool_nodes) == 1
        assert pool_nodes[0]["params"]["filter"]["org_id"] == "Engineering"

    def test_simple_address_without_dash(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        """An address without '-' uses the whole string as org_id."""
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-901",
            org_address="standalone",
            action="read",
        )
        pool_nodes = [n for n in mock_db.added_nodes if n["node_id"] == "list_pools"]
        assert pool_nodes[0]["params"]["filter"]["org_id"] == "standalone"

    def test_no_pool_found_returns_unassigned(
        self, mock_db_no_pool: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db_no_pool, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-902",
            org_address="D1-R1",
            action="read",
        )
        assert result["assigned_to"] == "unassigned"

    def test_no_pool_found_logs_warning(
        self, mock_db_no_pool: MockDataFlow, mock_engine: MagicMock, caplog
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db_no_pool, governance_engine=mock_engine)
        with caplog.at_level(logging.WARNING, logger="pact_platform.use.services.request_router"):
            service.route_request(
                request_id="req-903",
                org_address="D1-R1",
                action="read",
            )
        assert any(
            "unassigned" in msg.lower() or "no active pool" in msg.lower()
            for msg in caplog.messages
        )

    def test_no_pool_found_does_not_update_request(
        self, mock_db_no_pool: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        """When no pool found, the assign_request workflow must not be created."""
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db_no_pool, governance_engine=mock_engine)
        service.route_request(
            request_id="req-904",
            org_address="D1-R1",
            action="read",
        )
        assign_wfs = [wf for wf in mock_db_no_pool.created_workflows if wf.name == "assign_request"]
        assert len(assign_wfs) == 0


# ---------------------------------------------------------------------------
# 10. Context forwarding
# ---------------------------------------------------------------------------


class TestContextForwarding:
    """Verify that context dicts are forwarded correctly to the engine."""

    def test_none_context_becomes_empty_dict(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        service.route_request(
            request_id="req-1000",
            org_address="D1-R1",
            action="read",
            context=None,
        )
        # The implementation converts empty dict to None for the engine call
        mock_engine.verify_action.assert_called_once_with(
            role_address="D1-R1",
            action="read",
            context=None,
        )

    def test_populated_context_forwarded(
        self, mock_db: MockDataFlow, mock_engine: MagicMock
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(level="auto_approved", reason="ok")
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        ctx = {"cost": 10.0, "resource": "/reports", "extra": True}
        service.route_request(
            request_id="req-1001",
            org_address="D1-R1",
            action="read",
            context=ctx,
        )
        mock_engine.verify_action.assert_called_once_with(
            role_address="D1-R1",
            action="read",
            context=ctx,
        )


# ---------------------------------------------------------------------------
# 11. Return structure consistency
# ---------------------------------------------------------------------------


class TestReturnStructure:
    """Every return dict must always contain 'status' and 'request_id'."""

    @pytest.mark.parametrize(
        "level,expected_status",
        [
            ("blocked", "blocked"),
            ("held", "held"),
            ("auto_approved", "approved"),
            ("flagged", "approved"),
        ],
    )
    def test_all_verdicts_return_status_and_request_id(
        self,
        mock_db: MockDataFlow,
        mock_engine: MagicMock,
        level: str,
        expected_status: str,
    ) -> None:
        mock_engine.verify_action.return_value = _make_verdict(
            level=level, reason="test", envelope_version="1"
        )
        service = RequestRouterService(db=mock_db, governance_engine=mock_engine)
        result = service.route_request(
            request_id="req-struct",
            org_address="D1-R1",
            action="write",
        )
        assert "status" in result
        assert result["status"] == expected_status
        assert "request_id" in result
        assert result["request_id"] == "req-struct"

    def test_no_engine_returns_status_and_request_id(self, mock_db: MockDataFlow) -> None:
        service = RequestRouterService(db=mock_db, governance_engine=None)
        result = service.route_request(
            request_id="req-struct-2",
            org_address="D1-R1",
            action="write",
        )
        assert "status" in result
        assert "request_id" in result
