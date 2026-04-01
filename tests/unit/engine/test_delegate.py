# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for GovernedDelegate.

Covers:
- AUTO_APPROVED verdict -> returns approved dict
- FLAGGED verdict -> returns approved dict with flagged level
- BLOCKED verdict -> raises GovernanceBlockedError
- HELD verdict -> creates AgenticDecision via ApprovalBridge, raises GovernanceHeldError
- Per-node role address override from context
- NaN/Inf guard on cost and daily_total context fields
- _VerifierWrapper restricts engine to verify_action only
"""

from __future__ import annotations

import math
import os
import tempfile
from typing import Any
from unittest.mock import MagicMock

import pytest

# Override DATABASE_URL before any pact_platform.models import
_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_dir}/test_delegate.db"

from pact.governance import (
    CompiledOrg,
    GovernanceBlockedError,
    GovernanceEngine,
    GovernanceHeldError,
    GovernanceVerdict,
    NodeType,
    OrgNode,
)
from pact_platform.engine.approval_bridge import ApprovalBridge
from pact_platform.engine.delegate import GovernedDelegate, _VerifierWrapper
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


class _StubEngine:
    """Stub engine that returns a configurable verdict from verify_action."""

    def __init__(self, verdict: GovernanceVerdict) -> None:
        self._verdict = verdict

    def verify_action(
        self,
        role_address: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> GovernanceVerdict:
        return self._verdict


# ---------------------------------------------------------------------------
# Tests: AUTO_APPROVED
# ---------------------------------------------------------------------------


class TestAutoApproved:
    """When governance returns AUTO_APPROVED, delegate must return approved dict."""

    def test_returns_approved_true(self):
        verdict = GovernanceVerdict(
            level="auto_approved",
            reason="Within envelope",
            role_address="D1-R1",
            action="read_data",
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        result = delegate("node-1", "read_data", {})
        assert result["approved"] is True
        assert result["level"] == "auto_approved"
        assert result["reason"] == "Within envelope"


# ---------------------------------------------------------------------------
# Tests: FLAGGED
# ---------------------------------------------------------------------------


class TestFlagged:
    """When governance returns FLAGGED, delegate proceeds but flags it."""

    def test_flagged_returns_approved_true(self):
        verdict = GovernanceVerdict(
            level="flagged",
            reason="Near budget limit",
            role_address="D1-R1",
            action="expensive_call",
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        result = delegate("node-1", "expensive_call", {})
        assert result["approved"] is True
        assert result["level"] == "flagged"
        assert result["reason"] == "Near budget limit"


# ---------------------------------------------------------------------------
# Tests: BLOCKED
# ---------------------------------------------------------------------------


class TestBlocked:
    """When governance returns BLOCKED, delegate must raise GovernanceBlockedError."""

    def test_blocked_raises_error(self):
        verdict = GovernanceVerdict(
            level="blocked",
            reason="Insufficient clearance",
            role_address="D1-R1",
            action="access_secret",
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        with pytest.raises(GovernanceBlockedError):
            delegate("node-1", "access_secret", {})


# ---------------------------------------------------------------------------
# Tests: HELD
# ---------------------------------------------------------------------------


class TestHeld:
    """When governance returns HELD, delegate creates a decision and raises GovernanceHeldError."""

    def test_held_raises_error(self):
        verdict = GovernanceVerdict(
            level="held",
            reason="Budget threshold exceeded -- human review required",
            role_address="D1-R1",
            action="large_purchase",
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        with pytest.raises(GovernanceHeldError):
            delegate(
                "node-1",
                "large_purchase",
                {"request_id": "req-123", "session_id": "sess-1"},
            )

    def test_held_creates_decision_record(self):
        """A HELD verdict must persist an AgenticDecision via the bridge."""
        verdict = GovernanceVerdict(
            level="held",
            reason="Near operational limit",
            role_address="D1-R1",
            action="risky_op",
            audit_details={"dimension": "financial"},
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        with pytest.raises(GovernanceHeldError):
            delegate(
                "node-2",
                "risky_op",
                {"request_id": "req-456"},
            )

        # Verify the decision was created in DataFlow
        pending = bridge.get_pending(limit=100)
        found = [d for d in pending if d.get("action") == "risky_op"]
        assert len(found) >= 1
        decision = found[0]
        assert decision["status"] == "pending"
        assert decision["agent_address"] == "D1-R1"
        assert decision["decision_type"] == "governance_hold"


# ---------------------------------------------------------------------------
# Tests: Per-node role address override
# ---------------------------------------------------------------------------


class TestRoleAddressOverride:
    """Context can provide a per-node role_address override."""

    def test_context_role_overrides_delegate_default(self):
        verdict = GovernanceVerdict(
            level="auto_approved",
            reason="ok",
            role_address="D1-R2",
            action="read",
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        # Override role via context -- the delegate should pass the overridden address
        result = delegate("node-1", "read", {"role_address": "D1-R2"})
        assert result["approved"] is True


# ---------------------------------------------------------------------------
# Tests: NaN/Inf guard
# ---------------------------------------------------------------------------


class TestNaNGuard:
    """Cost and daily_total context fields must be NaN/Inf guarded."""

    def test_nan_cost_raises_value_error(self):
        verdict = GovernanceVerdict(
            level="auto_approved",
            reason="ok",
            role_address="D1-R1",
            action="call",
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        with pytest.raises(ValueError, match="finite"):
            delegate("node-1", "call", {"cost": float("nan")})

    def test_inf_cost_raises_value_error(self):
        verdict = GovernanceVerdict(
            level="auto_approved",
            reason="ok",
            role_address="D1-R1",
            action="call",
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        with pytest.raises(ValueError, match="finite"):
            delegate("node-1", "call", {"cost": float("inf")})

    def test_nan_daily_total_raises_value_error(self):
        verdict = GovernanceVerdict(
            level="auto_approved",
            reason="ok",
            role_address="D1-R1",
            action="call",
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        with pytest.raises(ValueError, match="finite"):
            delegate("node-1", "call", {"daily_total": float("nan")})

    def test_finite_cost_passes_through(self):
        verdict = GovernanceVerdict(
            level="auto_approved",
            reason="ok",
            role_address="D1-R1",
            action="call",
        )
        engine = _StubEngine(verdict)
        bridge = ApprovalBridge(db)
        delegate = GovernedDelegate(engine, bridge, role_address="D1-R1")

        result = delegate("node-1", "call", {"cost": 0.05})
        assert result["approved"] is True


# ---------------------------------------------------------------------------
# Tests: _VerifierWrapper security
# ---------------------------------------------------------------------------


class TestVerifierWrapper:
    """_VerifierWrapper must expose ONLY verify_action, not engine mutations."""

    def test_wrapper_exposes_verify_action(self):
        engine = _make_engine()
        wrapper = _VerifierWrapper(engine)
        verdict = wrapper.verify_action(role_address="D1-R1", action="test_action")
        assert verdict.level in ("auto_approved", "blocked", "flagged", "held")

    def test_wrapper_has_no_set_role_envelope(self):
        engine = _make_engine()
        wrapper = _VerifierWrapper(engine)
        assert not hasattr(wrapper, "set_role_envelope")

    def test_wrapper_has_no_grant_clearance(self):
        engine = _make_engine()
        wrapper = _VerifierWrapper(engine)
        assert not hasattr(wrapper, "grant_clearance")

    def test_wrapper_has_no_compute_envelope(self):
        engine = _make_engine()
        wrapper = _VerifierWrapper(engine)
        assert not hasattr(wrapper, "compute_envelope")

    def test_wrapper_uses_slots(self):
        """Slots prevent adding arbitrary attributes at runtime."""
        engine = _make_engine()
        wrapper = _VerifierWrapper(engine)
        with pytest.raises(AttributeError):
            wrapper.engine = engine  # type: ignore[attr-defined]
