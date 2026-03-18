# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Graceful shutdown management for the CARE Platform API server.

Provides a ``ShutdownManager`` that tracks active WebSocket connections
and coordinates clean shutdown:

1. Sets a shutdown flag to reject new connections
2. Closes all active WebSocket connections gracefully
3. Allows in-flight HTTP requests to complete

Usage:
    manager = ShutdownManager()
    manager.register_connection(websocket)
    # ... later ...
    manager.trigger_shutdown()
    await manager.close_all_connections()
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class ShutdownManager:
    """Manages graceful shutdown for the CARE Platform API server.

    Tracks active WebSocket connections and provides a mechanism to
    signal shutdown, stop accepting new connections, and close existing
    connections gracefully.

    Thread-safe for concurrent connection registration/unregistration.
    """

    def __init__(self, max_connections: int = 100) -> None:
        self._shutting_down = False
        self._connections: list[Any] = []
        self._lock = threading.Lock()
        # L2-FIX: Bound connection count to prevent unbounded memory growth.
        self._max_connections = max_connections

    @property
    def is_shutting_down(self) -> bool:
        """Whether shutdown has been triggered."""
        return self._shutting_down

    @property
    def active_connection_count(self) -> int:
        """Number of currently tracked WebSocket connections."""
        with self._lock:
            return len(self._connections)

    def trigger_shutdown(self) -> None:
        """Signal that shutdown should begin.

        After this is called:
        - ``should_accept_connection()`` returns False
        - ``close_all_connections()`` should be awaited to clean up
        """
        self._shutting_down = True
        logger.info("Shutdown triggered — no new connections will be accepted")

    def should_accept_connection(self) -> bool:
        """Whether new WebSocket connections should be accepted.

        Returns False after ``trigger_shutdown()`` has been called.
        """
        return not self._shutting_down

    def register_connection(self, websocket: Any) -> None:
        """Track a WebSocket connection for graceful shutdown.

        Args:
            websocket: The WebSocket connection to track. Must have an
                async ``close(code, reason)`` method.

        Raises:
            RuntimeError: If the maximum number of connections has been reached.
        """
        with self._lock:
            if len(self._connections) >= self._max_connections:
                raise RuntimeError(
                    f"Max connection limit reached ({self._max_connections}). "
                    f"Cannot accept new connections."
                )
            self._connections.append(websocket)

    def unregister_connection(self, websocket: Any) -> None:
        """Stop tracking a WebSocket connection (e.g., after disconnect).

        Args:
            websocket: The WebSocket connection to remove from tracking.
        """
        with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def close_all_connections(
        self, code: int = 1001, reason: str = "Server shutting down"
    ) -> None:
        """Close all tracked WebSocket connections gracefully.

        Args:
            code: WebSocket close code (default 1001 = Going Away).
            reason: Human-readable close reason.
        """
        with self._lock:
            connections = list(self._connections)
            self._connections.clear()

        closed_count = 0
        for ws in connections:
            try:
                await ws.close(code=code, reason=reason)
                closed_count += 1
            except Exception as exc:
                logger.warning("Error closing WebSocket during shutdown: %s", exc)

        logger.info(
            "Closed %d/%d WebSocket connections during shutdown",
            closed_count,
            len(connections),
        )
