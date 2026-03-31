# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for EventBridge.

Covers:
- on_plan_event publishes PlatformEvent with correct type/data
- on_cost_event validates NaN/Inf and publishes cost accrual
- on_hold_event publishes governance hold event
- on_completion_event validates NaN/Inf and publishes completion
- None event_bus silently discards all events (no crash)
- _publish_sync bridges sync -> async correctly
"""

from __future__ import annotations

import asyncio
import math
import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Override DATABASE_URL before any pact_platform.models import
_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_dir}/test_event_bridge.db"

from pact_platform.engine.event_bridge import EventBridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeEventBus:
    """Collects published events for assertion."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    async def publish(self, event: Any) -> int:
        self.events.append(event)
        return 1


# ---------------------------------------------------------------------------
# Tests: None event_bus (silent discard)
# ---------------------------------------------------------------------------


class TestNoneEventBus:
    """When event_bus is None, all event methods must succeed silently."""

    def test_on_plan_event_no_crash(self):
        bridge = EventBridge(event_bus=None)
        bridge.on_plan_event({"type": "plan_created", "node_id": "n1"})

    def test_on_cost_event_no_crash(self):
        bridge = EventBridge(event_bus=None)
        bridge.on_cost_event(cost_usd=0.05, tokens=100)

    def test_on_hold_event_no_crash(self):
        bridge = EventBridge(event_bus=None)
        bridge.on_hold_event(decision_id="dec-abc", reason="budget limit")

    def test_on_completion_event_no_crash(self):
        bridge = EventBridge(event_bus=None)
        bridge.on_completion_event(
            request_id="req-1",
            success=True,
            budget_consumed=0.05,
            budget_allocated=1.0,
        )


# ---------------------------------------------------------------------------
# Tests: NaN/Inf guards
# ---------------------------------------------------------------------------


class TestNaNGuards:
    """NaN and Inf must be rejected by cost and completion events."""

    def test_nan_cost_raises(self):
        bridge = EventBridge(event_bus=None)
        with pytest.raises(ValueError, match="finite"):
            bridge.on_cost_event(cost_usd=float("nan"), tokens=100)

    def test_inf_cost_raises(self):
        bridge = EventBridge(event_bus=None)
        with pytest.raises(ValueError, match="finite"):
            bridge.on_cost_event(cost_usd=float("inf"), tokens=100)

    def test_neg_inf_cost_raises(self):
        bridge = EventBridge(event_bus=None)
        with pytest.raises(ValueError, match="finite"):
            bridge.on_cost_event(cost_usd=float("-inf"), tokens=100)

    def test_nan_budget_consumed_raises(self):
        bridge = EventBridge(event_bus=None)
        with pytest.raises(ValueError, match="finite"):
            bridge.on_completion_event(
                request_id="req-1",
                success=True,
                budget_consumed=float("nan"),
                budget_allocated=1.0,
            )

    def test_inf_budget_allocated_raises(self):
        bridge = EventBridge(event_bus=None)
        with pytest.raises(ValueError, match="finite"):
            bridge.on_completion_event(
                request_id="req-1",
                success=True,
                budget_consumed=0.05,
                budget_allocated=float("inf"),
            )

    def test_finite_cost_passes(self):
        bridge = EventBridge(event_bus=None)
        # Must not raise
        bridge.on_cost_event(cost_usd=0.05, tokens=100)

    def test_zero_cost_passes(self):
        bridge = EventBridge(event_bus=None)
        bridge.on_cost_event(cost_usd=0.0, tokens=0)


# ---------------------------------------------------------------------------
# Tests: Event publishing with real bus
# ---------------------------------------------------------------------------


class TestEventPublishing:
    """Verify events are published to the EventBus with correct structure."""

    def test_on_plan_event_publishes(self):
        bus = _FakeEventBus()
        bridge = EventBridge(event_bus=bus)

        # Use asyncio.run because _publish_sync creates a new loop when
        # no running loop exists
        bridge.on_plan_event(
            {
                "type": "node_completed",
                "node_id": "node-1",
                "status": "success",
                "agent_id": "agent-1",
            }
        )

        assert len(bus.events) == 1
        event = bus.events[0]
        assert event.data["source"] == "supervisor"
        assert event.data["event_type"] == "node_completed"
        assert event.data["node_id"] == "node-1"
        assert event.source_agent_id == "agent-1"

    def test_on_cost_event_publishes(self):
        bus = _FakeEventBus()
        bridge = EventBridge(event_bus=bus)

        bridge.on_cost_event(cost_usd=0.12, tokens=500)

        assert len(bus.events) == 1
        event = bus.events[0]
        assert event.data["event_type"] == "cost_accrual"
        assert event.data["cost_usd"] == 0.12
        assert event.data["tokens"] == 500

    def test_on_hold_event_publishes(self):
        bus = _FakeEventBus()
        bridge = EventBridge(event_bus=bus)

        bridge.on_hold_event(decision_id="dec-xyz", reason="Over budget")

        assert len(bus.events) == 1
        event = bus.events[0]
        assert event.data["event_type"] == "governance_hold"
        assert event.data["decision_id"] == "dec-xyz"
        assert event.data["reason"] == "Over budget"

    def test_on_completion_event_publishes(self):
        bus = _FakeEventBus()
        bridge = EventBridge(event_bus=bus)

        bridge.on_completion_event(
            request_id="req-99",
            success=True,
            budget_consumed=0.50,
            budget_allocated=1.00,
        )

        assert len(bus.events) == 1
        event = bus.events[0]
        assert event.data["event_type"] == "execution_complete"
        assert event.data["request_id"] == "req-99"
        assert event.data["success"] is True
        assert event.data["budget_consumed"] == 0.50
        assert event.data["budget_allocated"] == 1.00


# ---------------------------------------------------------------------------
# Tests: Default event_type in plan events
# ---------------------------------------------------------------------------


class TestPlanEventDefaults:
    """Plan events with missing fields should use safe defaults."""

    def test_missing_type_defaults_to_plan_event(self):
        bus = _FakeEventBus()
        bridge = EventBridge(event_bus=bus)

        bridge.on_plan_event({})  # No type key

        assert len(bus.events) == 1
        assert bus.events[0].data["event_type"] == "plan_event"

    def test_missing_node_id_defaults_to_empty(self):
        bus = _FakeEventBus()
        bridge = EventBridge(event_bus=bus)

        bridge.on_plan_event({"type": "something"})

        assert bus.events[0].data["node_id"] == ""

    def test_missing_agent_id_defaults_to_empty(self):
        bus = _FakeEventBus()
        bridge = EventBridge(event_bus=bus)

        bridge.on_plan_event({"type": "something"})

        assert bus.events[0].source_agent_id == ""
