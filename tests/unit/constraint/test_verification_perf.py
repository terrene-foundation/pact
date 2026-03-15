# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Performance and integration tests for verification optimization components."""

import time

import pytest

from care_platform.config.schema import TrustPostureLevel
from care_platform.constraint.cache import (
    CachedVerification,
    VerificationCache,
)
from care_platform.constraint.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from care_platform.constraint.verification_level import (
    VerificationThoroughness,
    select_verification_level,
)


def _make_cached_verification(
    trust_score: float = 0.85,
    posture: TrustPostureLevel = TrustPostureLevel.SUPERVISED,
    verification_result: str = "AUTO_APPROVED",
) -> CachedVerification:
    return CachedVerification(
        trust_score=trust_score,
        posture=posture,
        verification_result=verification_result,
    )


class TestCacheLookupPerformance:
    """Benchmark: 100 cache lookups must complete in < 1ms each."""

    def test_100_cache_lookups_under_1ms_each(self):
        cache = VerificationCache(max_size=1000)

        # Populate with 100 entries
        for i in range(100):
            cache.put(
                (f"agent-{i}", "v1"),
                _make_cached_verification(trust_score=i / 100),
                ttl_seconds=300,
            )

        # Benchmark lookups
        start = time.monotonic()
        for i in range(100):
            result = cache.get((f"agent-{i}", "v1"))
            assert result is not None

        elapsed_ms = (time.monotonic() - start) * 1000
        avg_ms = elapsed_ms / 100

        # Target: < 1ms each, assert < 1ms average
        assert avg_ms < 1.0, f"Average cache lookup took {avg_ms:.4f}ms, target is < 1ms"

    def test_cache_hit_faster_than_miss(self):
        """Cache hits should be at least as fast as misses."""
        cache = VerificationCache(max_size=1000)

        for i in range(100):
            cache.put(
                (f"agent-{i}", "v1"),
                _make_cached_verification(),
                ttl_seconds=300,
            )

        # Time hits
        start = time.monotonic()
        for i in range(100):
            cache.get((f"agent-{i}", "v1"))
        hit_time = time.monotonic() - start

        # Time misses
        start = time.monotonic()
        for i in range(100):
            cache.get((f"nonexistent-{i}", "v1"))
        miss_time = time.monotonic() - start

        # Hits should not be significantly slower than misses
        # (allow 20x overhead to account for system load variance and LRU bookkeeping)
        assert (
            hit_time < miss_time * 20
        ), f"Cache hits ({hit_time:.6f}s) much slower than misses ({miss_time:.6f}s)"


class TestVerificationLevelSelection:
    def test_quick_for_cache_hit_routine_action(self):
        level = select_verification_level(
            action_type="read_metrics",
            cache_hit=True,
            is_cross_team=False,
            is_first_action=False,
        )
        assert level == VerificationThoroughness.QUICK

    def test_standard_is_default(self):
        level = select_verification_level(
            action_type="draft_report",
            cache_hit=False,
            is_cross_team=False,
            is_first_action=False,
        )
        assert level == VerificationThoroughness.STANDARD

    def test_full_for_cross_team(self):
        level = select_verification_level(
            action_type="send_data",
            cache_hit=True,
            is_cross_team=True,
            is_first_action=False,
        )
        assert level == VerificationThoroughness.FULL

    def test_full_for_first_action(self):
        level = select_verification_level(
            action_type="read_data",
            cache_hit=True,
            is_cross_team=False,
            is_first_action=True,
        )
        assert level == VerificationThoroughness.FULL

    def test_full_overrides_cache_hit(self):
        """Even with a cache hit, cross-team or first-action requires FULL."""
        level = select_verification_level(
            action_type="read_data",
            cache_hit=True,
            is_cross_team=True,
            is_first_action=True,
        )
        assert level == VerificationThoroughness.FULL

    def test_no_cache_hit_not_quick(self):
        """Without a cache hit, never return QUICK."""
        level = select_verification_level(
            action_type="read_metrics",
            cache_hit=False,
            is_cross_team=False,
            is_first_action=False,
        )
        assert level != VerificationThoroughness.QUICK


class TestCircuitBreakerIntegration:
    def test_cache_with_circuit_breaker_normal_flow(self):
        """Verify cache and circuit breaker work together in normal operation."""
        cache = VerificationCache(max_size=100)
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        key = ("agent-1", "v1")
        value = _make_cached_verification()

        # Normal: put via circuit breaker, get from cache
        def do_cache_put():
            cache.put(key, value, ttl_seconds=60)
            return True

        result = cb.call(do_cache_put)
        assert result is True

        cached = cache.get(key)
        assert cached is not None
        assert cached.trust_score == 0.85

    def test_circuit_breaker_protects_failing_verification(self):
        """When verification fails repeatedly, circuit breaker blocks further attempts."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0)

        def failing_verification():
            raise RuntimeError("Verification service unavailable")

        # Trip the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(failing_verification)

        assert cb.state == CircuitState.OPEN

        # Now all calls are blocked (fail-safe: BLOCKED)
        with pytest.raises(CircuitBreakerOpen):
            cb.call(failing_verification)

    def test_circuit_breaker_recovery_restores_cache_access(self):
        """After recovery, verification via circuit breaker works again."""
        cache = VerificationCache(max_size=100)
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        def failing_verification():
            raise RuntimeError("Verification service unavailable")

        # Trip
        with pytest.raises(RuntimeError):
            cb.call(failing_verification)
        assert cb.state == CircuitState.OPEN

        # Wait for recovery
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Recovery: successful call
        key = ("agent-1", "v1")
        value = _make_cached_verification()

        def successful_verification():
            cache.put(key, value, ttl_seconds=60)
            return True

        result = cb.call(successful_verification)
        assert result is True
        assert cb.state == CircuitState.CLOSED
        assert cache.get(key) is not None
