# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Event-based notification dispatch service.

Fans out platform events (approvals, budget alerts, review completions,
etc.) to registered notification adapters.  Adapters are async callables
implementing the ``NotificationAdapter`` protocol.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

__all__ = ["NotificationAdapter", "NotificationDispatchService"]

# H3 fix: maximum number of registered adapters to prevent unbounded growth
MAX_ADAPTERS = 50


# ------------------------------------------------------------------
# Protocol
# ------------------------------------------------------------------


@runtime_checkable
class NotificationAdapter(Protocol):
    """Protocol for notification delivery backends.

    Implementations might push to Slack, email, webhook, in-app inbox, etc.
    """

    async def send(self, event_type: str, payload: dict[str, Any]) -> None:
        """Deliver a notification.

        Args:
            event_type: Dot-delimited event name (e.g.
                ``"approval.submitted"``, ``"budget.warning"``).
            payload: Arbitrary event data.
        """
        ...  # pragma: no cover


# ------------------------------------------------------------------
# Service
# ------------------------------------------------------------------


class NotificationDispatchService:
    """Dispatches events to all registered ``NotificationAdapter`` instances.

    Adapters are invoked concurrently via ``asyncio.gather``.  A failing
    adapter does not prevent other adapters from receiving the event.

    The adapter list is bounded to ``MAX_ADAPTERS`` to prevent unbounded
    memory growth in long-running processes (per rules/trust-plane-security.md
    Rule 4).
    """

    def __init__(self) -> None:
        self._adapters: list[NotificationAdapter] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_adapter(self, adapter: NotificationAdapter) -> None:
        """Register a notification adapter.

        Args:
            adapter: An object implementing the ``NotificationAdapter``
                protocol.

        Raises:
            TypeError: If *adapter* does not conform to the protocol.
            RuntimeError: If the maximum number of adapters has been reached.
        """
        if not isinstance(adapter, NotificationAdapter):
            raise TypeError(
                f"adapter must implement NotificationAdapter protocol, "
                f"got {type(adapter).__name__}"
            )
        # H3 fix: enforce bounded collection
        if len(self._adapters) >= MAX_ADAPTERS:
            raise RuntimeError(
                f"Maximum number of notification adapters ({MAX_ADAPTERS}) "
                f"reached. Remove an adapter before registering a new one."
            )
        self._adapters.append(adapter)
        logger.info(
            "Notification adapter registered: %s (total: %d)",
            type(adapter).__name__,
            len(self._adapters),
        )

    def unregister_adapter(self, adapter: NotificationAdapter) -> None:
        """Remove a previously registered adapter.

        Args:
            adapter: The adapter instance to remove.

        Raises:
            ValueError: If the adapter is not currently registered.
        """
        try:
            self._adapters.remove(adapter)
            logger.info(
                "Notification adapter unregistered: %s (remaining: %d)",
                type(adapter).__name__,
                len(self._adapters),
            )
        except ValueError:
            raise ValueError(f"Adapter {type(adapter).__name__} is not registered") from None

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, event_type: str, payload: dict[str, Any]) -> None:
        """Dispatch an event to all registered adapters.

        Runs each adapter's ``send()`` coroutine concurrently.  Errors in
        individual adapters are logged but do not propagate -- delivery is
        best-effort.

        If called from within a running event loop, the coroutines are
        scheduled on that loop.  Otherwise a new loop is created.

        Args:
            event_type: Event identifier (e.g. ``"approval.submitted"``).
            payload: Event data forwarded to each adapter.
        """
        if not self._adapters:
            logger.debug(
                "No adapters registered; dropping event %s",
                event_type,
            )
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Schedule on the existing loop (non-blocking fire-and-forget)
            loop.create_task(self._dispatch_async(event_type, payload))
        else:
            asyncio.run(self._dispatch_async(event_type, payload))

    async def _dispatch_async(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Internal coroutine that fans out to all adapters concurrently."""
        tasks = [self._safe_send(adapter, event_type, payload) for adapter in self._adapters]
        await asyncio.gather(*tasks)

    async def _safe_send(
        self,
        adapter: NotificationAdapter,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Invoke a single adapter, catching and logging any error."""
        adapter_name = type(adapter).__name__
        try:
            await adapter.send(event_type, payload)
            logger.debug(
                "Notification delivered via %s for event %s",
                adapter_name,
                event_type,
            )
        except Exception:
            logger.exception(
                "Notification adapter %s failed for event %s",
                adapter_name,
                event_type,
            )
