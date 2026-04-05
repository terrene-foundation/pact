# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for enforcement mode wiring in SupervisorOrchestrator (PactEngine migration).

Validates:
1. Enforcement mode flows from PlatformSettings through to PactEngine
2. PactEngine receives the correct enforcement mode when wrapping a GovernanceEngine
3. PactEngine passed directly preserves its own enforcement mode
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest

from pact.engine import PactEngine
from pact.enforcement import EnforcementMode
from pact.governance import (
    CompiledOrg,
    GovernanceEngine,
    NodeType,
    OrgNode,
)
from pact.work import WorkResult
from pact_platform.engine.orchestrator import SupervisorOrchestrator, _PlatformHeldCallback
from pact_platform.engine.settings import (
    PlatformSettings,
    set_platform_settings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockExpressSync:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, model: str, data: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"method": "create", "model": model, "data": data})
        return dict(data)


class _MockDB:
    def __init__(self) -> None:
        self.express_sync = _MockExpressSync()


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


def _make_work_result(success: bool = True) -> WorkResult:
    """Create a simple WorkResult."""
    return WorkResult(success=success, results={}, cost_usd=0.01)


# ---------------------------------------------------------------------------
# Tests: Enforcement mode wiring through PactEngine
# ---------------------------------------------------------------------------


class TestEnforcementModeWiring:
    """Verify orchestrator passes enforcement mode to PactEngine."""

    def setup_method(self) -> None:
        """Reset platform settings before each test."""
        set_platform_settings(PlatformSettings())

    def teardown_method(self) -> None:
        """Reset platform settings after each test."""
        set_platform_settings(PlatformSettings())
        os.environ.pop("PACT_ALLOW_DISABLED_MODE", None)

    def test_enforce_mode_wired_to_pact_engine(self):
        """Default 'enforce' mode should be wired into the PactEngine."""
        set_platform_settings(PlatformSettings(enforcement_mode="enforce"))

        engine = _make_engine()
        db = _MockDB()
        orch = SupervisorOrchestrator(engine, db)

        assert orch._pact.enforcement_mode == EnforcementMode.ENFORCE

    def test_shadow_mode_wired_to_pact_engine(self):
        """Shadow mode should be wired into the PactEngine."""
        set_platform_settings(PlatformSettings(enforcement_mode="shadow"))

        engine = _make_engine()
        db = _MockDB()
        orch = SupervisorOrchestrator(engine, db)

        assert orch._pact.enforcement_mode == EnforcementMode.SHADOW

    def test_disabled_mode_wired_to_pact_engine(self):
        """Disabled mode should be wired into the PactEngine."""
        os.environ["PACT_ALLOW_DISABLED_MODE"] = "true"
        set_platform_settings(PlatformSettings(enforcement_mode="disabled"))

        engine = _make_engine()
        db = _MockDB()
        orch = SupervisorOrchestrator(engine, db)

        assert orch._pact.enforcement_mode == EnforcementMode.DISABLED

    def test_enforce_mode_executes_with_governance(self, caplog):
        """In enforce mode, PactEngine should apply governance checks."""
        set_platform_settings(PlatformSettings(enforcement_mode="enforce"))

        engine = _make_engine()
        db = _MockDB()
        orch = SupervisorOrchestrator(engine, db)

        work_result = _make_work_result(success=True)
        with patch.object(orch, "_submit_sync", return_value=work_result):
            result = orch.execute_request(
                request_id="req-enforce",
                role_address="D1-R1",
                objective="test enforce",
            )

        assert result["success"] is True

    def test_shadow_mode_executes_without_blocking(self, caplog):
        """In shadow mode, PactEngine evaluates but never blocks."""
        set_platform_settings(PlatformSettings(enforcement_mode="shadow"))

        engine = _make_engine()
        db = _MockDB()
        orch = SupervisorOrchestrator(engine, db)

        work_result = _make_work_result(success=True)
        with patch.object(orch, "_submit_sync", return_value=work_result):
            result = orch.execute_request(
                request_id="req-shadow",
                role_address="D1-R1",
                objective="test shadow",
            )

        assert result["success"] is True

    def test_disabled_mode_skips_governance(self, caplog):
        """In disabled mode, PactEngine skips governance entirely."""
        os.environ["PACT_ALLOW_DISABLED_MODE"] = "true"
        set_platform_settings(PlatformSettings(enforcement_mode="disabled"))

        engine = _make_engine()
        db = _MockDB()
        orch = SupervisorOrchestrator(engine, db)

        work_result = _make_work_result(success=True)
        with patch.object(orch, "_submit_sync", return_value=work_result):
            result = orch.execute_request(
                request_id="req-disabled",
                role_address="D1-R1",
                objective="test disabled",
            )

        assert result["success"] is True


# ---------------------------------------------------------------------------
# Tests: PactEngine passed directly preserves enforcement mode
# ---------------------------------------------------------------------------


class TestPactEngineDirectMode:
    """When PactEngine is passed directly, its enforcement mode is preserved."""

    def test_pact_engine_enforce_mode_preserved(self):
        """PactEngine with enforce mode is used as-is."""
        engine = _make_engine()
        compiled_org = engine.get_org()

        pact = PactEngine(
            org={"org_id": compiled_org.org_id, "name": compiled_org.org_id},
            enforcement_mode=EnforcementMode.ENFORCE,
        )

        db = _MockDB()
        orch = SupervisorOrchestrator(pact, db)

        assert orch._pact is pact
        assert orch._pact.enforcement_mode == EnforcementMode.ENFORCE

    def test_pact_engine_shadow_mode_preserved(self):
        """PactEngine with shadow mode is used as-is."""
        engine = _make_engine()
        compiled_org = engine.get_org()

        pact = PactEngine(
            org={"org_id": compiled_org.org_id, "name": compiled_org.org_id},
            enforcement_mode=EnforcementMode.SHADOW,
        )

        db = _MockDB()
        orch = SupervisorOrchestrator(pact, db)

        assert orch._pact.enforcement_mode == EnforcementMode.SHADOW


# ---------------------------------------------------------------------------
# Tests: HELD callback wiring
# ---------------------------------------------------------------------------


class TestHeldCallbackWiring:
    """Verify that _PlatformHeldCallback is wired into PactEngine."""

    def test_governance_engine_wrapping_wires_held_callback(self):
        """When wrapping GovernanceEngine, on_held should be set."""
        engine = _make_engine()
        db = _MockDB()
        orch = SupervisorOrchestrator(engine, db)

        assert orch._pact._on_held is not None
        assert isinstance(orch._pact._on_held, _PlatformHeldCallback)

    def test_held_callback_creates_decision(self):
        """_PlatformHeldCallback should call ApprovalBridge.create_decision."""
        import asyncio

        mock_bridge = _MockApprovalBridge()
        callback = _PlatformHeldCallback(mock_bridge)

        mock_verdict = type("Verdict", (), {"level": "held", "reason": "near limit"})()

        result = asyncio.run(
            callback(
                verdict=mock_verdict,
                role="D1-R1",
                action="deploy",
                context={"request_id": "req-1", "session_id": "sess-1"},
            )
        )

        assert result is False  # Block until human approves
        assert mock_bridge.created_count == 1

    def test_held_callback_returns_false(self):
        """_PlatformHeldCallback should return False to block execution."""
        import asyncio

        mock_bridge = _MockApprovalBridge()
        callback = _PlatformHeldCallback(mock_bridge)

        mock_verdict = type("Verdict", (), {"level": "held", "reason": "budget"})()
        result = asyncio.run(
            callback(
                verdict=mock_verdict,
                role="D1-R1",
                action="write",
                context={},
            )
        )
        assert result is False


class _MockApprovalBridge:
    """Mock ApprovalBridge that tracks create_decision calls."""

    def __init__(self) -> None:
        self.created_count = 0

    def create_decision(self, **kwargs: Any) -> str:
        self.created_count += 1
        return f"decision-{self.created_count}"
