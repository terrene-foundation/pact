# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Trust store health check — fail-closed behavior when store is unreachable.

Monitors the health of a TrustStore and implements fail-closed behavior:
when the store is unreachable, all actions are BLOCKED. Integrates with
the circuit breaker for automatic recovery detection.

Health statuses:
- HEALTHY: Store is operating normally.
- DEGRADED: Store is slow or intermittently failing.
- UNREACHABLE: Store is completely unavailable — all actions BLOCKED.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class StoreHealthStatus(str, Enum):
    """Health status of the trust store."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"


class TrustStoreHealthCheck:
    """Monitors trust store health and enforces fail-closed behavior.

    When the store is unreachable, should_block_all() returns True,
    indicating that all agent actions must be BLOCKED until the store
    recovers.

    Args:
        store: The trust store to monitor. Must have a health_check() method.
        circuit_breaker: Optional circuit breaker for failure tracking.

    Raises:
        ValueError: If store is None.
    """

    def __init__(
        self,
        store: Any,
        circuit_breaker: Any | None = None,
    ) -> None:
        if store is None:
            raise ValueError(
                "store is required and must not be None. "
                "TrustStoreHealthCheck needs a store to monitor."
            )
        self._store = store
        self._circuit_breaker = circuit_breaker
        self._status = StoreHealthStatus.HEALTHY
        self._lock = threading.Lock()
        self._consecutive_failures = 0

    @property
    def status(self) -> StoreHealthStatus:
        """Current health status of the store."""
        with self._lock:
            return self._status

    def is_healthy(self) -> bool:
        """Check if the store is in a healthy state."""
        with self._lock:
            return self._status == StoreHealthStatus.HEALTHY

    def should_block_all(self) -> bool:
        """Whether all actions should be BLOCKED due to store unavailability.

        Returns True when the store is UNREACHABLE, implementing fail-closed
        behavior as required by the CARE trust model.
        """
        with self._lock:
            return self._status == StoreHealthStatus.UNREACHABLE

    def check(self) -> StoreHealthStatus:
        """Probe the store health and update status.

        Calls the store's health_check() method. On success, transitions
        to HEALTHY. On failure, transitions to UNREACHABLE.

        Returns:
            The updated StoreHealthStatus.
        """
        try:
            if self._circuit_breaker is not None:
                result = self._circuit_breaker.call(self._store.health_check)
            else:
                result = self._store.health_check()

            if result:
                with self._lock:
                    self._status = StoreHealthStatus.HEALTHY
                    self._consecutive_failures = 0
                logger.debug("Trust store health check passed: HEALTHY")
            else:
                with self._lock:
                    self._consecutive_failures += 1
                    self._status = StoreHealthStatus.UNREACHABLE
                logger.warning(
                    "Trust store health check returned False: UNREACHABLE "
                    "(consecutive_failures=%d)",
                    self._consecutive_failures,
                )
        except Exception as exc:
            with self._lock:
                self._consecutive_failures += 1
                self._status = StoreHealthStatus.UNREACHABLE
            logger.warning(
                "Trust store health check failed: UNREACHABLE — %s (consecutive_failures=%d)",
                exc,
                self._consecutive_failures,
            )

        with self._lock:
            return self._status
