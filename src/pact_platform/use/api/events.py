# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Event bus for real-time platform updates via WebSocket.

Supports publishing events for:
- Audit anchor creation (new actions recorded)
- Held action submissions (actions awaiting approval)
- Trust posture changes (agent posture transitions)
- Bridge status changes (bridge lifecycle events)
- Verification gradient results (action classification)

Subscribers receive JSON-serializable event dicts pushed through
WebSocket connections managed by the EventBus.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of real-time events the platform can emit."""

    AUDIT_ANCHOR = "audit_anchor"
    HELD_ACTION = "held_action"
    POSTURE_CHANGE = "posture_change"
    BRIDGE_STATUS = "bridge_status"
    VERIFICATION_RESULT = "verification_result"
    WORKSPACE_TRANSITION = "workspace_transition"


class PlatformEvent:
    """A single event emitted by the platform.

    Args:
        event_type: The type of event.
        data: Event payload (must be JSON-serializable).
        source_agent_id: Optional agent that caused the event.
        source_team_id: Optional team context for the event.
    """

    def __init__(
        self,
        event_type: EventType,
        data: dict[str, Any],
        *,
        source_agent_id: str = "",
        source_team_id: str = "",
    ) -> None:
        self.event_id = f"evt-{uuid4().hex[:8]}"
        self.event_type = event_type
        self.data = data
        self.source_agent_id = source_agent_id
        self.source_team_id = source_team_id
        self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a JSON-compatible dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "data": self.data,
            "source_agent_id": self.source_agent_id,
            "source_team_id": self.source_team_id,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Serialize event to a JSON string."""
        return json.dumps(self.to_dict())


class EventBus:
    """In-memory event bus for broadcasting real-time platform events.

    WebSocket connections register as subscribers. When an event is
    published, it is broadcast to all connected subscribers.

    Thread-safe for publishing (uses asyncio.Queue per subscriber).
    """

    def __init__(self, max_subscribers: int = 100) -> None:
        self._subscribers: list[asyncio.Queue[PlatformEvent]] = []
        self._lock = asyncio.Lock()
        # L2-FIX: Bound subscriber count to prevent unbounded memory growth.
        self._max_subscribers = max_subscribers

    async def subscribe(self) -> asyncio.Queue[PlatformEvent]:
        """Register a new subscriber and return their event queue.

        Returns:
            An asyncio.Queue that will receive PlatformEvent objects.

        Raises:
            RuntimeError: If the maximum number of subscribers has been reached.
        """
        queue: asyncio.Queue[PlatformEvent] = asyncio.Queue(maxsize=1000)
        async with self._lock:
            if len(self._subscribers) >= self._max_subscribers:
                raise RuntimeError(
                    f"Max subscriber limit reached ({self._max_subscribers}). "
                    f"Cannot accept new subscriptions."
                )
            self._subscribers.append(queue)
        logger.info("EventBus: new subscriber added (total: %d)", len(self._subscribers))
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[PlatformEvent]) -> None:
        """Remove a subscriber.

        Args:
            queue: The subscriber's event queue to remove.
        """
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
        logger.info("EventBus: subscriber removed (total: %d)", len(self._subscribers))

    async def publish(self, event: PlatformEvent) -> int:
        """Publish an event to all subscribers.

        Args:
            event: The event to broadcast.

        Returns:
            Number of subscribers the event was sent to.
        """
        async with self._lock:
            subscribers = list(self._subscribers)

        sent = 0
        for queue in subscribers:
            try:
                queue.put_nowait(event)
                sent += 1
            except asyncio.QueueFull:
                logger.warning(
                    "EventBus: subscriber queue full, dropping event %s",
                    event.event_id,
                )

        if sent > 0:
            logger.debug(
                "EventBus: published event %s (%s) to %d subscribers",
                event.event_id,
                event.event_type.value,
                sent,
            )

        return sent

    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers.

        RT11-M1 / RT13: Returns a snapshot of the subscriber list length.
        Since this is accessed from the asyncio event loop (single-threaded),
        ``len()`` on a list is atomic under CPython. The lock is not acquired
        here to avoid requiring this to be an async method, which would break
        the property interface used by callers like the WebSocket endpoint.
        The list is only mutated under ``self._lock`` in subscribe/unsubscribe,
        so reads see a consistent length.
        """
        # Safe: list.__len__ is atomic under CPython GIL, and all mutations
        # happen on the same event loop thread under asyncio.Lock.
        return len(self._subscribers)

    # ------------------------------------------------------------------
    # Convenience publishers for common event types
    # ------------------------------------------------------------------

    async def emit_audit_anchor(
        self,
        agent_id: str,
        action: str,
        result: str,
        *,
        team_id: str = "",
    ) -> PlatformEvent:
        """Emit an audit anchor event.

        Args:
            agent_id: The agent that performed the action.
            action: The action that was audited.
            result: The action outcome (SUCCESS, FAILURE, DENIED).
            team_id: Optional team context.

        Returns:
            The emitted PlatformEvent.
        """
        event = PlatformEvent(
            EventType.AUDIT_ANCHOR,
            {"agent_id": agent_id, "action": action, "result": result},
            source_agent_id=agent_id,
            source_team_id=team_id,
        )
        await self.publish(event)
        return event

    async def emit_held_action(
        self,
        agent_id: str,
        action_id: str,
        action: str,
        reason: str,
        *,
        team_id: str = "",
    ) -> PlatformEvent:
        """Emit a held action event (action awaiting human approval).

        Args:
            agent_id: The agent whose action was held.
            action_id: The pending action ID.
            action: The action that was held.
            reason: Why the action was held.
            team_id: Optional team context.

        Returns:
            The emitted PlatformEvent.
        """
        event = PlatformEvent(
            EventType.HELD_ACTION,
            {
                "agent_id": agent_id,
                "action_id": action_id,
                "action": action,
                "reason": reason,
            },
            source_agent_id=agent_id,
            source_team_id=team_id,
        )
        await self.publish(event)
        return event

    async def emit_posture_change(
        self,
        agent_id: str,
        from_posture: str,
        to_posture: str,
        *,
        team_id: str = "",
    ) -> PlatformEvent:
        """Emit a trust posture change event.

        Args:
            agent_id: The agent whose posture changed.
            from_posture: Previous posture level.
            to_posture: New posture level.
            team_id: Optional team context.

        Returns:
            The emitted PlatformEvent.
        """
        event = PlatformEvent(
            EventType.POSTURE_CHANGE,
            {
                "agent_id": agent_id,
                "from_posture": from_posture,
                "to_posture": to_posture,
            },
            source_agent_id=agent_id,
            source_team_id=team_id,
        )
        await self.publish(event)
        return event


# Module-level singleton for easy access across the application
event_bus = EventBus()
