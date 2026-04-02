# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ApprovalBridge.

Covers:
- create_decision persists AgenticDecision with correct fields
- approve updates status to 'approved'
- reject updates status to 'rejected'
- get_pending returns only pending decisions
- NaN/Inf guard on constraint_details
- Validation: empty decision_id, empty decided_by
- Envelope version extraction from verdict
"""

from __future__ import annotations

from typing import Any

import pytest

from pact.governance import GovernanceVerdict
from pact_platform.engine.approval_bridge import ApprovalBridge


# ---------------------------------------------------------------------------
# Helpers — MockExpressSync
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
        # Apply simple filter
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
# Helpers — Verdict factory
# ---------------------------------------------------------------------------


def _make_verdict(
    level: str = "held",
    reason: str = "Budget threshold exceeded",
    audit_details: dict[str, Any] | None = None,
    envelope_version: str = "",
) -> GovernanceVerdict:
    return GovernanceVerdict(
        level=level,
        reason=reason,
        role_address="D1-R1",
        action="expensive_call",
        audit_details=audit_details or {},
        envelope_version=envelope_version,
    )


# ---------------------------------------------------------------------------
# Tests: create_decision
# ---------------------------------------------------------------------------


class TestCreateDecision:
    """Test that create_decision persists the correct AgenticDecision."""

    def test_creates_decision_with_pending_status(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict()

        decision_id = bridge.create_decision(
            role_address="D1-R1",
            action="expensive_call",
            verdict=verdict,
            request_id="req-100",
            session_id="sess-1",
        )

        assert decision_id.startswith("dec-")

        # Read back to verify persistence
        pending = bridge.get_pending(limit=100)
        found = [d for d in pending if d["id"] == decision_id]
        assert len(found) == 1
        dec = found[0]
        assert dec["status"] == "pending"
        assert dec["agent_address"] == "D1-R1"
        assert dec["action"] == "expensive_call"
        assert dec["decision_type"] == "governance_hold"
        assert dec["request_id"] == "req-100"
        assert dec["session_id"] == "sess-1"

    def test_creates_decision_without_request_or_session(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict()

        decision_id = bridge.create_decision(
            role_address="D1-R1",
            action="some_action",
            verdict=verdict,
        )

        pending = bridge.get_pending(limit=100)
        found = [d for d in pending if d["id"] == decision_id]
        assert len(found) == 1
        dec = found[0]
        assert dec["request_id"] == ""
        assert dec["session_id"] == ""

    def test_extracts_constraint_dimension_from_audit(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict(
            audit_details={"dimension": "financial"},
        )

        decision_id = bridge.create_decision(
            role_address="D1-R1",
            action="over_budget",
            verdict=verdict,
        )

        pending = bridge.get_pending(limit=100)
        found = [d for d in pending if d["id"] == decision_id]
        assert len(found) == 1
        assert found[0]["constraint_dimension"] == "financial"

    def test_extracts_envelope_version(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict(envelope_version="42")

        decision_id = bridge.create_decision(
            role_address="D1-R1",
            action="versioned_action",
            verdict=verdict,
        )

        pending = bridge.get_pending(limit=100)
        found = [d for d in pending if d["id"] == decision_id]
        assert len(found) == 1
        assert found[0]["envelope_version"] == 42

    def test_invalid_envelope_version_defaults_to_zero(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict(envelope_version="not-a-number")

        decision_id = bridge.create_decision(
            role_address="D1-R1",
            action="bad_version",
            verdict=verdict,
        )

        pending = bridge.get_pending(limit=100)
        found = [d for d in pending if d["id"] == decision_id]
        assert len(found) == 1
        assert found[0]["envelope_version"] == 0

    def test_reason_held_preserved(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict(reason="Agent near daily action limit")

        decision_id = bridge.create_decision(
            role_address="D1-R1",
            action="rate_limited",
            verdict=verdict,
        )

        pending = bridge.get_pending(limit=100)
        found = [d for d in pending if d["id"] == decision_id]
        assert len(found) == 1
        assert found[0]["reason_held"] == "Agent near daily action limit"


# ---------------------------------------------------------------------------
# Tests: NaN/Inf guard on constraint_details
# ---------------------------------------------------------------------------


class TestNaNGuardConstraintDetails:
    """NaN or Inf in constraint_details must raise ValueError."""

    def test_nan_in_constraint_details_raises(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict(
            audit_details={"constraint_details": {"max_budget": float("nan")}},
        )

        with pytest.raises(ValueError, match="finite"):
            bridge.create_decision(
                role_address="D1-R1",
                action="nan_action",
                verdict=verdict,
            )

    def test_inf_in_constraint_details_raises(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict(
            audit_details={"constraint_details": {"limit": float("inf")}},
        )

        with pytest.raises(ValueError, match="finite"):
            bridge.create_decision(
                role_address="D1-R1",
                action="inf_action",
                verdict=verdict,
            )

    def test_finite_constraint_details_pass(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict(
            audit_details={"constraint_details": {"max_budget": 100.0, "current_spend": 80.0}},
        )

        decision_id = bridge.create_decision(
            role_address="D1-R1",
            action="valid_action",
            verdict=verdict,
        )
        assert decision_id.startswith("dec-")


# ---------------------------------------------------------------------------
# Tests: approve
# ---------------------------------------------------------------------------


class TestApprove:
    """Test the approve method."""

    def test_approve_updates_status(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict()
        decision_id = bridge.create_decision(
            role_address="D1-R1",
            action="held_action",
            verdict=verdict,
        )

        bridge.approve(decision_id, decided_by="admin", reason="Override approved")

        # Read back to verify via the in-memory store
        dec = mock_db.express_sync.read("AgenticDecision", decision_id)
        assert dec is not None
        assert dec["status"] == "approved"
        assert dec["decided_by"] == "admin"
        assert dec["decision_reason"] == "Override approved"

    def test_approve_rejects_empty_decision_id(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        with pytest.raises(ValueError, match="decision_id must not be empty"):
            bridge.approve("", decided_by="admin", reason="test")

    def test_approve_rejects_empty_decided_by(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        with pytest.raises(ValueError, match="decided_by must not be empty"):
            bridge.approve("dec-123", decided_by="", reason="test")


# ---------------------------------------------------------------------------
# Tests: reject
# ---------------------------------------------------------------------------


class TestReject:
    """Test the reject method."""

    def test_reject_updates_status(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict()
        decision_id = bridge.create_decision(
            role_address="D1-R1",
            action="bad_action",
            verdict=verdict,
        )

        bridge.reject(decision_id, decided_by="compliance", reason="Too risky")

        dec = mock_db.express_sync.read("AgenticDecision", decision_id)
        assert dec is not None
        assert dec["status"] == "rejected"
        assert dec["decided_by"] == "compliance"
        assert dec["decision_reason"] == "Too risky"

    def test_reject_rejects_empty_decision_id(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        with pytest.raises(ValueError, match="decision_id must not be empty"):
            bridge.reject("", decided_by="admin", reason="test")

    def test_reject_rejects_empty_decided_by(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        with pytest.raises(ValueError, match="decided_by must not be empty"):
            bridge.reject("dec-123", decided_by="", reason="test")


# ---------------------------------------------------------------------------
# Tests: get_pending
# ---------------------------------------------------------------------------


class TestGetPending:
    """Test the pending decisions listing."""

    def test_get_pending_returns_only_pending(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict()

        # Create two decisions
        id_a = bridge.create_decision(
            role_address="D1-R1",
            action="action_a",
            verdict=verdict,
        )
        id_b = bridge.create_decision(
            role_address="D1-R1",
            action="action_b",
            verdict=verdict,
        )

        # Approve one
        bridge.approve(id_a, decided_by="admin", reason="ok")

        # Only the unapproved one should appear in pending
        pending = bridge.get_pending(limit=100)
        pending_ids = [d["id"] for d in pending]
        assert id_b in pending_ids
        assert id_a not in pending_ids

    def test_get_pending_respects_limit(self):
        mock_db = MockDB()
        bridge = ApprovalBridge(mock_db)
        verdict = _make_verdict()

        for i in range(5):
            bridge.create_decision(
                role_address="D1-R1",
                action=f"action_{i}",
                verdict=verdict,
            )

        limited = bridge.get_pending(limit=2)
        assert len(limited) <= 2
