# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for pact_platform DataFlow models.

Verifies CRUD operations, NaN guards, and node generation for all 11 models.
Uses the production DataFlow instance with a temp SQLite file.
"""

from __future__ import annotations

import os
import tempfile
from uuid import uuid4

import pytest

# Override DATABASE_URL before importing models
_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_dir}/test_models.db"

from pact_platform.models import db, validate_finite  # noqa: E402


def _uid() -> str:
    return str(uuid4())[:8]


def _exec(wf):
    """Execute a DataFlow workflow and return results dict."""
    results, _ = db.execute_workflow(wf)
    return results


# ---------------------------------------------------------------------------
# Node generation tests
# ---------------------------------------------------------------------------


class TestNodeGeneration:
    def test_objective_has_create_node(self):
        nodes = db.get_generated_nodes("AgenticObjective")
        assert "create" in nodes

    def test_objective_has_list_node(self):
        nodes = db.get_generated_nodes("AgenticObjective")
        assert "list" in nodes

    def test_request_has_update_node(self):
        nodes = db.get_generated_nodes("AgenticRequest")
        assert "update" in nodes

    def test_decision_has_delete_node(self):
        nodes = db.get_generated_nodes("AgenticDecision")
        assert "delete" in nodes

    def test_run_has_read_node(self):
        nodes = db.get_generated_nodes("Run")
        assert "read" in nodes

    def test_all_11_models_registered(self):
        model_names = [
            "AgenticObjective",
            "AgenticRequest",
            "AgenticWorkSession",
            "AgenticArtifact",
            "AgenticDecision",
            "AgenticReviewDecision",
            "AgenticFinding",
            "AgenticPool",
            "AgenticPoolMembership",
            "Run",
            "ExecutionMetric",
        ]
        for name in model_names:
            nodes = db.get_generated_nodes(name)
            assert (
                nodes is not None and len(nodes) >= 9
            ), f"{name}: {len(nodes) if nodes else 0} nodes"


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


class TestObjectiveCRUD:
    def test_create_and_read(self):
        oid = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticObjectiveCreateNode",
            "create",
            {
                "id": oid,
                "org_address": "D1-R1",
                "title": "Test Objective",
            },
        )
        results = _exec(wf)
        assert results["create"]["id"] == oid

        wf2 = db.create_workflow()
        wf2.add_node("AgenticObjectiveReadNode", "read", {"id": oid})
        results2 = _exec(wf2)
        assert results2["read"]["title"] == "Test Objective"

    def test_list_by_status(self):
        oid1, oid2 = _uid(), _uid()
        for oid, title, status in [(oid1, "Active", "active"), (oid2, "Draft", "draft")]:
            wf = db.create_workflow()
            wf.add_node(
                "AgenticObjectiveCreateNode",
                "c",
                {
                    "id": oid,
                    "org_address": "D1-R1",
                    "title": title,
                    "status": status,
                },
            )
            _exec(wf)

        wf3 = db.create_workflow()
        wf3.add_node("AgenticObjectiveListNode", "list", {"filter": {"status": "active"}})
        results = _exec(wf3)
        records = results["list"]["records"]
        assert any(r["id"] == oid1 for r in records)

    def test_update(self):
        oid = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticObjectiveCreateNode",
            "create",
            {
                "id": oid,
                "org_address": "D1-R1",
                "title": "Original",
            },
        )
        _exec(wf)

        wf2 = db.create_workflow()
        wf2.add_node(
            "AgenticObjectiveUpdateNode",
            "update",
            {
                "filter": {"id": oid},
                "fields": {"title": "Updated", "status": "active"},
            },
        )
        _exec(wf2)

        wf3 = db.create_workflow()
        wf3.add_node("AgenticObjectiveReadNode", "read", {"id": oid})
        results = _exec(wf3)
        assert results["read"]["title"] == "Updated"

    def test_delete(self):
        oid = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticObjectiveCreateNode",
            "create",
            {
                "id": oid,
                "org_address": "D1-R1",
                "title": "To Delete",
            },
        )
        _exec(wf)

        wf2 = db.create_workflow()
        wf2.add_node("AgenticObjectiveDeleteNode", "delete", {"id": oid})
        _exec(wf2)


class TestRequestCRUD:
    def test_create_and_filter_by_objective(self):
        oid, rid1, rid2 = _uid(), _uid(), _uid()
        for rid in [rid1, rid2]:
            wf = db.create_workflow()
            wf.add_node(
                "AgenticRequestCreateNode",
                "create",
                {
                    "id": rid,
                    "objective_id": oid,
                    "title": f"Request {rid}",
                },
            )
            _exec(wf)

        wf2 = db.create_workflow()
        wf2.add_node("AgenticRequestListNode", "list", {"filter": {"objective_id": oid}})
        results = _exec(wf2)
        records = results["list"]["records"]
        assert len(records) >= 2


class TestDecisionCRUD:
    def test_create_pending_decision(self):
        did = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticDecisionCreateNode",
            "create",
            {
                "id": did,
                "agent_address": "D1-T1-R1",
                "action": "approve_budget",
                "status": "pending",
                "reason_held": "Budget exceeds threshold",
                "urgency": "high",
                "envelope_version": 3,
            },
        )
        results = _exec(wf)
        assert results["create"]["status"] == "pending"

    def test_approve_decision(self):
        did = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "AgenticDecisionCreateNode",
            "create",
            {
                "id": did,
                "agent_address": "D1-T1-R1",
                "action": "approve_budget",
            },
        )
        _exec(wf)

        wf2 = db.create_workflow()
        wf2.add_node(
            "AgenticDecisionUpdateNode",
            "update",
            {
                "filter": {"id": did},
                "fields": {"status": "approved", "decided_by": "human-admin"},
            },
        )
        _exec(wf2)

        wf3 = db.create_workflow()
        wf3.add_node("AgenticDecisionReadNode", "read", {"id": did})
        results = _exec(wf3)
        assert results["read"]["status"] == "approved"


class TestRunCRUD:
    def test_create_and_read(self):
        rid = _uid()
        wf = db.create_workflow()
        wf.add_node(
            "RunCreateNode",
            "create",
            {
                "id": rid,
                "agent_address": "D1-T1-R1",
                "status": "running",
                "cost_usd": 0.05,
                "input_tokens": 1000,
                "output_tokens": 500,
            },
        )
        results = _exec(wf)
        assert results["create"]["cost_usd"] == 0.05


# ---------------------------------------------------------------------------
# NaN/Inf guard tests
# ---------------------------------------------------------------------------


class TestNaNGuard:
    def test_nan_rejected(self):
        with pytest.raises(ValueError, match="must be finite"):
            validate_finite(budget_usd=float("nan"))

    def test_inf_rejected(self):
        with pytest.raises(ValueError, match="must be finite"):
            validate_finite(cost_usd=float("inf"))

    def test_negative_inf_rejected(self):
        with pytest.raises(ValueError, match="must be finite"):
            validate_finite(value=float("-inf"))

    def test_valid_float_passes(self):
        validate_finite(budget_usd=100.50, cost_usd=0.0, value=-5.0)

    def test_none_passes(self):
        validate_finite(budget_usd=None)

    def test_int_passes(self):
        validate_finite(count=42)


# ---------------------------------------------------------------------------
# Model import smoke tests
# ---------------------------------------------------------------------------


class TestModuleImports:
    def test_import_all_models(self):
        from pact_platform.models import (
            AgenticObjective,
            AgenticRequest,
            AgenticWorkSession,
            AgenticArtifact,
            AgenticDecision,
            AgenticReviewDecision,
            AgenticFinding,
            AgenticPool,
            AgenticPoolMembership,
            Run,
            ExecutionMetric,
        )

        assert AgenticObjective is not None
        assert ExecutionMetric is not None
