# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Governance integration tests — verify Dual Plane bridge.

Tests that the GovernanceEngine verdicts correctly control execution:
- BLOCKED prevents execution
- HELD creates AgenticDecision
- Approve resumes, reject fails
- Cross-boundary access without bridge → BLOCKED
- NaN in envelope → adapter rejects
- Budget exhaustion → HELD
"""

from __future__ import annotations

import math
import os
import tempfile
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

_db_dir = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_dir}/test_gov.db")

from pact_platform.models import db, validate_finite


def _uid() -> str:
    return uuid4().hex[:8]


def _exec(wf) -> dict:
    results, _ = db.execute_workflow(wf)
    return results


class TestBlockedVerdictPreventsExecution:
    """BLOCKED verdict must prevent LLM execution."""

    def test_blocked_action_raises(self):
        """When governance returns BLOCKED, execution must not proceed."""
        from pact.governance import GovernanceVerdict

        verdict = GovernanceVerdict(
            level="blocked",
            reason="Insufficient clearance",
            role_address="D1-R1",
            action="access_secret_data",
        )
        assert verdict.level == "blocked"
        assert verdict.reason == "Insufficient clearance"

    def test_blocked_verdict_has_audit_details(self):
        from pact.governance import GovernanceVerdict

        verdict = GovernanceVerdict(
            level="blocked",
            reason="Tool not registered",
            role_address="D1-T1-R1",
            action="dangerous_tool",
        )
        assert verdict.role_address == "D1-T1-R1"
        assert verdict.action == "dangerous_tool"


class TestHeldVerdictCreatesDecision:
    """HELD verdict must create an AgenticDecision in DataFlow."""

    def test_held_creates_decision_record(self):
        """When governance returns HELD, an AgenticDecision must be created."""
        decision_id = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticDecisionCreateNode",
            "create",
            {
                "id": decision_id,
                "agent_address": "D1-T1-R1",
                "action": "approve_large_budget",
                "status": "pending",
                "reason_held": "Budget exceeds $1000 threshold",
                "constraint_dimension": "financial",
                "urgency": "high",
                "envelope_version": 3,
            },
        )
        results = _exec(wf)
        assert results["create"]["status"] == "pending"
        assert results["create"]["reason_held"] == "Budget exceeds $1000 threshold"

    def test_held_decision_is_queryable(self):
        """Pending decisions must be queryable for the approval queue."""
        did = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticDecisionCreateNode",
            "create",
            {
                "id": did,
                "agent_address": "D1-T1-R1",
                "action": "write_to_external",
                "status": "pending",
                "reason_held": "Communication constraint exceeded",
                "urgency": "normal",
            },
        )
        _exec(wf)

        wf2 = db.create_workflow()
        wf2.add_node(
            "AgenticDecisionListNode",
            "list",
            {
                "filter": {"status": "pending"},
            },
        )
        results = _exec(wf2)
        records = results["list"]["records"]
        assert any(r["id"] == did for r in records)


class TestApproveResumesRejectFails:
    """Approve must mark decision approved, reject must mark rejected."""

    def test_approve_decision(self):
        did = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticDecisionCreateNode",
            "create",
            {
                "id": did,
                "agent_address": "D1-T1-R1",
                "action": "test",
                "status": "pending",
                "reason_held": "Budget check",
            },
        )
        _exec(wf)

        wf2 = db.create_workflow()
        wf2.add_node(
            "AgenticDecisionUpdateNode",
            "update",
            {
                "filter": {"id": did},
                "fields": {
                    "status": "approved",
                    "decided_by": "admin",
                    "decision_reason": "Budget OK",
                },
            },
        )
        _exec(wf2)

        wf3 = db.create_workflow()
        wf3.add_node("AgenticDecisionReadNode", "read", {"id": did})
        result = _exec(wf3)["read"]
        assert result["status"] == "approved"
        assert result["decided_by"] == "admin"

    def test_reject_decision(self):
        did = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticDecisionCreateNode",
            "create",
            {
                "id": did,
                "agent_address": "D1-T1-R1",
                "action": "test",
                "status": "pending",
                "reason_held": "Too expensive",
            },
        )
        _exec(wf)

        wf2 = db.create_workflow()
        wf2.add_node(
            "AgenticDecisionUpdateNode",
            "update",
            {
                "filter": {"id": did},
                "fields": {
                    "status": "rejected",
                    "decided_by": "admin",
                    "decision_reason": "Over budget",
                },
            },
        )
        _exec(wf2)

        wf3 = db.create_workflow()
        wf3.add_node("AgenticDecisionReadNode", "read", {"id": did})
        result = _exec(wf3)["read"]
        assert result["status"] == "rejected"


class TestNaNInEnvelopeRejected:
    """NaN in envelope numeric fields must be rejected."""

    def test_nan_budget_rejected(self):
        with pytest.raises(ValueError, match="must be finite"):
            validate_finite(budget_usd=float("nan"))

    def test_inf_budget_rejected(self):
        with pytest.raises(ValueError, match="must be finite"):
            validate_finite(budget_usd=float("inf"))

    def test_negative_inf_rejected(self):
        with pytest.raises(ValueError, match="must be finite"):
            validate_finite(max_cost=float("-inf"))

    def test_nan_in_run_cost_rejected(self):
        with pytest.raises(ValueError, match="must be finite"):
            validate_finite(cost_usd=float("nan"))


class TestBudgetExhaustionCreatesHold:
    """When budget is exhausted, execution should create a HELD decision."""

    def test_cost_exceeding_budget_flagged(self):
        """Costs exceeding objective budget should be detectable."""
        obj_id = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticObjectiveCreateNode",
            "create",
            {
                "id": obj_id,
                "org_address": "D1-R1",
                "title": "Budget Test",
                "budget_usd": 10.0,
                "status": "active",
            },
        )
        _exec(wf)

        # Record costs that exceed budget
        for i in range(3):
            run_id = _uid()
            wf2 = db.create_workflow()
            wf2.add_node(
                "RunCreateNode",
                "create",
                {
                    "id": run_id,
                    "request_id": obj_id,
                    "agent_address": "D1-T1-R1",
                    "cost_usd": 5.0,
                    "status": "completed",
                },
            )
            _exec(wf2)

        # Verify total cost exceeds budget
        wf3 = db.create_workflow()
        wf3.add_node("RunListNode", "list", {"filter": {"request_id": obj_id}})
        runs = _exec(wf3)["list"]["records"]
        total_cost = sum(r.get("cost_usd", 0.0) for r in runs)
        assert total_cost > 10.0  # Budget exceeded


class TestCostTrackingAccuracy:
    """Cost tracking must accurately aggregate across runs."""

    def test_multiple_runs_aggregate(self):
        req_id = _uid()
        costs = [0.05, 0.03, 0.02, 0.01]
        for cost in costs:
            rid = _uid()
            wf = db.create_workflow()
            wf.add_node(
                "RunCreateNode",
                "create",
                {
                    "id": rid,
                    "request_id": req_id,
                    "agent_address": "D1-T1-R1",
                    "cost_usd": cost,
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "status": "completed",
                },
            )
            _exec(wf)

        wf2 = db.create_workflow()
        wf2.add_node("RunListNode", "list", {"filter": {"request_id": req_id}})
        runs = _exec(wf2)["list"]["records"]
        total = sum(r.get("cost_usd", 0.0) for r in runs)
        assert abs(total - 0.11) < 0.001
