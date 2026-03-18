# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Verification circuit breaker — fail-safe protection for the verification system.

When the verification system is slow or unavailable, the circuit breaker
transitions to OPEN state and returns fail-safe BLOCKED for all verification
requests, rather than allowing unverified actions to proceed.

States:
- CLOSED: Normal operation. Failures are counted.
- OPEN: Failing. All calls are rejected immediately with CircuitBreakerOpen.
- HALF_OPEN: Testing recovery. One call is allowed through.
  - If it succeeds: transition to CLOSED.
  - If it fails: transition back to OPEN.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when a call is attempted while the circuit breaker is OPEN.

    This signals that the verification system is unavailable and the
    fail-safe response (BLOCKED) should be used.
    """


class CircuitBreaker:
    """Circuit breaker for the verification system.

    Tracks consecutive failures and transitions between states to protect
    against cascading failures in the verification pipeline.

    Note: All state (failure count, circuit state, last failure time) is held
    in memory. On process restart, the circuit breaker resets to CLOSED with
    zero failures. For deployments where state must survive restarts, persist
    the failure count and state externally and restore them on initialization.
    """

    def __init__(
        self,
        failure_threshold: int,
        recovery_timeout: float,
    ) -> None:
        """Initialize the circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before tripping to OPEN.
            recovery_timeout: Seconds to wait in OPEN before transitioning to HALF_OPEN.

        Raises:
            ValueError: If failure_threshold is not a positive integer or
                        recovery_timeout is not positive.
        """
        if failure_threshold <= 0:
            raise ValueError(
                f"failure_threshold must be a positive integer, got {failure_threshold}. "
                "A circuit breaker with zero threshold would trip immediately."
            )
        if recovery_timeout <= 0:
            raise ValueError(
                f"recovery_timeout must be positive, got {recovery_timeout}. "
                "A zero or negative timeout would never allow recovery."
            )

        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit breaker state, accounting for recovery timeout."""
        with self._lock:
            return self._effective_state()

    @property
    def failure_count(self) -> int:
        """Current consecutive failure count."""
        with self._lock:
            return self._failure_count

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function through the circuit breaker.

        Args:
            func: The callable to execute.
            *args: Positional arguments for func.
            **kwargs: Keyword arguments for func.

        Returns:
            The return value of func.

        Raises:
            CircuitBreakerOpen: If the circuit is OPEN and recovery timeout
                has not elapsed.
            Exception: Any exception raised by func (also recorded as a failure).
        """
        with self._lock:
            effective = self._effective_state()

            if effective == CircuitState.OPEN:
                logger.warning(
                    "Circuit breaker is OPEN: rejecting call. failure_count=%d threshold=%d",
                    self._failure_count,
                    self._failure_threshold,
                )
                raise CircuitBreakerOpen(
                    f"Circuit breaker is OPEN after {self._failure_count} consecutive failures. "
                    f"Recovery timeout: {self._recovery_timeout}s. "
                    "Fail-safe: all verification requests are BLOCKED."
                )

            # For HALF_OPEN, we allow one request through
            if effective == CircuitState.HALF_OPEN:
                logger.info("Circuit breaker HALF_OPEN: allowing test request through")

        # Execute outside the lock to avoid holding it during potentially slow calls
        try:
            result = func(*args, **kwargs)
        except Exception:
            with self._lock:
                self._record_failure()
            raise

        # Success
        with self._lock:
            self._record_success()

        return result

    def _effective_state(self) -> CircuitState:
        """Compute the effective state, checking recovery timeout.

        Must be called while holding self._lock.
        """
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    def _record_failure(self) -> None:
        """Record a failure. Must be called while holding self._lock."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._failure_count >= self._failure_threshold:
            previous_state = self._state
            self._state = CircuitState.OPEN
            if previous_state != CircuitState.OPEN:
                logger.warning(
                    "Circuit breaker tripped: %s -> OPEN after %d consecutive failures "
                    "(threshold=%d)",
                    previous_state.value,
                    self._failure_count,
                    self._failure_threshold,
                )

    def _record_success(self) -> None:
        """Record a success. Must be called while holding self._lock."""
        previous_state = self._state
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = None

        if previous_state != CircuitState.CLOSED:
            logger.info(
                "Circuit breaker recovered: %s -> CLOSED",
                previous_state.value,
            )
