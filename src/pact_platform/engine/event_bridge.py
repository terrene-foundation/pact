# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""EventBridge — maps GovernedSupervisor events to platform EventBus
events for real-time WebSocket streaming.

The bridge translates supervisor lifecycle events (plan creation, cost
accrual, governance holds) into ``PlatformEvent`` instances that the
dashboard can consume via WebSocket.  Each event type is mapped to the
appropriate ``EventType`` from the platform event bus.

Thread-safe: the EventBus handles its own locking; the bridge simply
publishes.  Since the EventBus is async, the bridge provides both sync
and async publishing paths.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import TYPE_CHECKING, Any

from pact_platform.models import validate_finite

if TYPE_CHECKING:
    from pact_platform.use.api.events import EventBus

logger = logging.getLogger(__name__)

__all__ = ["EventBridge"]


class EventBridge:
    """Bridges GovernedSupervisor events to the platform EventBus.

    Converts raw supervisor event dicts into structured ``PlatformEvent``
    instances and publishes them for WebSocket broadcast.

    Args:
        event_bus: The platform ``EventBus`` instance.  May be ``None``
            to silently discard events (useful in testing or CLI mode).
    """

    def __init__(self, event_bus: EventBus | None) -> None:
        self._bus = event_bus

    def on_plan_event(self, event: dict[str, Any]) -> None:
        """Convert a supervisor plan event to a platform event and publish.

        Plan events include plan creation, node scheduling, node
        completion, and plan finalization.

        Args:
            event: Raw event dict from GovernedSupervisor.  Expected
                keys: ``"type"``, ``"node_id"``, ``"status"``, etc.
        """
        if self._bus is None:
            return

        from pact_platform.use.api.events import EventType, PlatformEvent

        platform_event = PlatformEvent(
            EventType.VERIFICATION_RESULT,
            {
                "source": "supervisor",
                "event_type": event.get("type", "plan_event"),
                "node_id": event.get("node_id", ""),
                "status": event.get("status", ""),
                "details": event,
            },
            source_agent_id=event.get("agent_id", ""),
        )

        self._publish_sync(platform_event)

    def on_cost_event(self, cost_usd: float, tokens: int) -> None:
        """Publish a cost accrual event.

        Args:
            cost_usd: Incremental cost in USD for this event.
            tokens: Number of tokens consumed.

        Raises:
            ValueError: If cost_usd is NaN or Inf.
        """
        if not math.isfinite(cost_usd):
            raise ValueError(
                f"cost_usd must be finite, got {cost_usd!r}. "
                f"NaN/Inf values bypass budget tracking."
            )
        validate_finite(cost_usd=cost_usd, tokens=tokens)

        if self._bus is None:
            return

        from pact_platform.use.api.events import EventType, PlatformEvent

        platform_event = PlatformEvent(
            EventType.AUDIT_ANCHOR,
            {
                "source": "supervisor",
                "event_type": "cost_accrual",
                "cost_usd": cost_usd,
                "tokens": tokens,
            },
        )

        self._publish_sync(platform_event)

    def on_hold_event(self, decision_id: str, reason: str) -> None:
        """Publish a governance HELD event.

        Emitted when the GovernedDelegate encounters a HELD verdict and
        creates an AgenticDecision.

        Args:
            decision_id: The ID of the created AgenticDecision record.
            reason: Human-readable reason for the hold.
        """
        if self._bus is None:
            return

        from pact_platform.use.api.events import EventType, PlatformEvent

        platform_event = PlatformEvent(
            EventType.HELD_ACTION,
            {
                "source": "supervisor",
                "event_type": "governance_hold",
                "decision_id": decision_id,
                "reason": reason,
            },
        )

        self._publish_sync(platform_event)

    def on_completion_event(
        self,
        request_id: str,
        success: bool,
        budget_consumed: float,
        budget_allocated: float,
    ) -> None:
        """Publish a supervisor completion event.

        Emitted when the full supervised execution finishes (success
        or failure).

        Args:
            request_id: The platform request ID that was executed.
            success: Whether the execution succeeded.
            budget_consumed: Total USD consumed during execution.
            budget_allocated: Total USD allocated to the supervisor.
        """
        validate_finite(
            budget_consumed=budget_consumed,
            budget_allocated=budget_allocated,
        )

        if self._bus is None:
            return

        from pact_platform.use.api.events import EventType, PlatformEvent

        platform_event = PlatformEvent(
            EventType.VERIFICATION_RESULT,
            {
                "source": "supervisor",
                "event_type": "execution_complete",
                "request_id": request_id,
                "success": success,
                "budget_consumed": budget_consumed,
                "budget_allocated": budget_allocated,
            },
        )

        self._publish_sync(platform_event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_sync(self, event: Any) -> None:
        """Publish an event, bridging sync -> async if needed.

        The EventBus.publish() is async.  This method detects whether
        an event loop is already running and schedules accordingly.
        If no loop exists, fires and forgets via a new loop.
        """
        try:
            loop = asyncio.get_running_loop()
            # We are inside an async context — schedule as a task
            loop.create_task(self._bus.publish(event))
        except RuntimeError:
            # No running loop — run synchronously in a new loop
            try:
                asyncio.run(self._bus.publish(event))
            except Exception:
                logger.warning(
                    "EventBridge: failed to publish event %s",
                    getattr(event, "event_id", "unknown"),
                    exc_info=True,
                )
