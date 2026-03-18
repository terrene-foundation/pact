# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the verification circuit breaker."""

import time

import pytest

from care_platform.trust.constraint.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)


class TestNormalOperation:
    def test_starts_in_closed_state(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        assert cb.state == CircuitState.CLOSED

    def test_successful_call_in_closed_state(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)

        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_multiple_successes_stay_closed(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)

        for _ in range(10):
            result = cb.call(lambda: "ok")
            assert result == "ok"

        assert cb.state == CircuitState.CLOSED

    def test_failures_below_threshold_stay_closed(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)

        for _ in range(4):
            with pytest.raises(RuntimeError):
                cb.call(_raise_runtime_error)

        assert cb.state == CircuitState.CLOSED


class TestTripping:
    def test_trips_to_open_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call(_raise_runtime_error)

        assert cb.state == CircuitState.OPEN

    def test_open_raises_circuit_breaker_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0)

        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(_raise_runtime_error)

        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: "should not execute")

    def test_open_state_reason_includes_context(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0)

        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(_raise_runtime_error)

        with pytest.raises(CircuitBreakerOpen, match="Circuit breaker is OPEN"):
            cb.call(lambda: "nope")

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        # 2 failures, then a success
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(_raise_runtime_error)

        cb.call(lambda: "success")

        # 2 more failures should not trip (count was reset)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(_raise_runtime_error)

        assert cb.state == CircuitState.CLOSED


class TestFailSafeWhenOpen:
    def test_call_blocked_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0)

        with pytest.raises(RuntimeError):
            cb.call(_raise_runtime_error)

        assert cb.state == CircuitState.OPEN

        # All calls should be blocked
        for _ in range(5):
            with pytest.raises(CircuitBreakerOpen):
                cb.call(lambda: "blocked")


class TestRecovery:
    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        with pytest.raises(RuntimeError):
            cb.call(_raise_runtime_error)
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_one_request(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        with pytest.raises(RuntimeError):
            cb.call(_raise_runtime_error)

        time.sleep(0.15)

        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        with pytest.raises(RuntimeError):
            cb.call(_raise_runtime_error)

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        with pytest.raises(RuntimeError):
            cb.call(_raise_runtime_error)

        assert cb.state == CircuitState.OPEN

    def test_recovery_timeout_respected(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.2)

        with pytest.raises(RuntimeError):
            cb.call(_raise_runtime_error)

        time.sleep(0.05)
        # Should still be OPEN (timeout not elapsed)
        assert cb.state == CircuitState.OPEN

        time.sleep(0.2)
        # Should now be HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN


class TestCircuitBreakerValidation:
    def test_failure_threshold_must_be_positive(self):
        with pytest.raises(ValueError, match="failure_threshold must be a positive integer"):
            CircuitBreaker(failure_threshold=0, recovery_timeout=30.0)

    def test_recovery_timeout_must_be_positive(self):
        with pytest.raises(ValueError, match="recovery_timeout must be positive"):
            CircuitBreaker(failure_threshold=5, recovery_timeout=0.0)

    def test_failure_count_exposed(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        assert cb.failure_count == 0

        with pytest.raises(RuntimeError):
            cb.call(_raise_runtime_error)

        assert cb.failure_count == 1


def _raise_runtime_error():
    raise RuntimeError("test failure")
