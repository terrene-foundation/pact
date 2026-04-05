# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for degenerate envelope warning via PactEngine (TODO-21).

Validates:
1. PactEngine (wrapped by orchestrator) logs warnings for degenerate envelopes
2. Non-degenerate envelopes produce no warning
3. Orchestrator doesn't crash when no envelopes are configured
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from pact.governance import (
    CompiledOrg,
    GovernanceEngine,
    NodeType,
    OrgNode,
    RoleEnvelope,
)
from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
)
from pact_platform.engine.orchestrator import SupervisorOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockExpressSync:
    def create(self, model: str, data: dict[str, Any]) -> dict[str, Any]:
        return dict(data)


class _MockDB:
    def __init__(self) -> None:
        self.express_sync = _MockExpressSync()


def _make_engine_with_envelope(
    envelope: ConstraintEnvelopeConfig | None = None,
) -> GovernanceEngine:
    """Create a GovernanceEngine with one role and an optional envelope."""
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
    engine = GovernanceEngine(compiled)

    if envelope is not None:
        role_env = RoleEnvelope(
            id="env-test",
            defining_role_address="D1-R1",
            target_role_address="D1-R1",
            envelope=envelope,
        )
        engine.set_role_envelope(role_env)

    return engine


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDegenerateEnvelopeWarning:
    """Verify that PactEngine (via orchestrator) logs degenerate warnings."""

    def test_degenerate_envelope_detected_at_init(self, caplog):
        """PactEngine should log a warning for degenerate envelopes at init."""
        env = ConstraintEnvelopeConfig(
            id="env-degenerate",
            financial=FinancialConstraintConfig(max_spend_usd=0.0),
            operational=OperationalConstraintConfig(allowed_actions=[]),
        )
        engine = _make_engine_with_envelope(env)

        with caplog.at_level(logging.WARNING):
            SupervisorOrchestrator(
                engine,
                db=_MockDB(),
            )

        # PactEngine._detect_degenerate_envelopes() logs warnings
        degenerate_logs = [
            r for r in caplog.records if "degenerate" in r.message.lower() or "D1-R1" in r.message
        ]
        assert len(degenerate_logs) > 0, "Expected degenerate envelope warning in logs"

    def test_non_degenerate_envelope_no_warning(self, caplog):
        """A permissive envelope should not trigger degenerate warnings."""
        env = ConstraintEnvelopeConfig(
            id="env-permissive",
            financial=FinancialConstraintConfig(max_spend_usd=10000.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write", "execute"],
                max_actions_per_day=1000,
            ),
            communication=CommunicationConstraintConfig(
                allowed_channels=["slack", "email"],
            ),
        )
        engine = _make_engine_with_envelope(env)

        with caplog.at_level(logging.WARNING):
            SupervisorOrchestrator(
                engine,
                db=_MockDB(),
            )

        degenerate_logs = [
            r for r in caplog.records if "degenerate" in r.message.lower() and "D1-R1" in r.message
        ]
        assert (
            len(degenerate_logs) == 0
        ), "Permissive envelope should not produce degenerate warning"

    def test_no_envelope_set_no_crash(self):
        """Orchestrator should not crash when no envelopes are configured."""
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
        engine = GovernanceEngine(compiled)

        # Should not crash
        orch = SupervisorOrchestrator(
            engine,
            db=_MockDB(),
        )
        assert orch.pact_engine is not None
