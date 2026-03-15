# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the verification cache — LRU cache with TTL eviction."""

import time

from care_platform.constraint.cache import (
    CachedVerification,
    CacheStats,
    VerificationCache,
)
from care_platform.config.schema import TrustPostureLevel


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


class TestCachePutAndGet:
    def test_put_and_get_returns_cached_value(self):
        cache = VerificationCache(max_size=10)
        key = ("agent-1", "v1")
        value = _make_cached_verification()
        cache.put(key, value, ttl_seconds=60)

        result = cache.get(key)
        assert result is not None
        assert result.trust_score == 0.85
        assert result.posture == TrustPostureLevel.SUPERVISED
        assert result.verification_result == "AUTO_APPROVED"

    def test_get_missing_key_returns_none(self):
        cache = VerificationCache(max_size=10)
        result = cache.get(("nonexistent", "v1"))
        assert result is None

    def test_put_overwrites_existing(self):
        cache = VerificationCache(max_size=10)
        key = ("agent-1", "v1")
        cache.put(key, _make_cached_verification(trust_score=0.5), ttl_seconds=60)
        cache.put(key, _make_cached_verification(trust_score=0.9), ttl_seconds=60)

        result = cache.get(key)
        assert result is not None
        assert result.trust_score == 0.9

    def test_different_keys_stored_independently(self):
        cache = VerificationCache(max_size=10)
        cache.put(("agent-1", "v1"), _make_cached_verification(trust_score=0.5), ttl_seconds=60)
        cache.put(("agent-2", "v1"), _make_cached_verification(trust_score=0.9), ttl_seconds=60)

        r1 = cache.get(("agent-1", "v1"))
        r2 = cache.get(("agent-2", "v1"))
        assert r1 is not None
        assert r2 is not None
        assert r1.trust_score == 0.5
        assert r2.trust_score == 0.9


class TestCacheHitMissTracking:
    def test_hit_increments_on_found(self):
        cache = VerificationCache(max_size=10)
        key = ("agent-1", "v1")
        cache.put(key, _make_cached_verification(), ttl_seconds=60)
        cache.get(key)
        cache.get(key)

        stats = cache.stats()
        assert stats.hits == 2
        assert stats.misses == 0

    def test_miss_increments_on_not_found(self):
        cache = VerificationCache(max_size=10)
        cache.get(("missing", "v1"))

        stats = cache.stats()
        assert stats.hits == 0
        assert stats.misses == 1

    def test_stats_size_reflects_entries(self):
        cache = VerificationCache(max_size=10)
        cache.put(("a1", "v1"), _make_cached_verification(), ttl_seconds=60)
        cache.put(("a2", "v1"), _make_cached_verification(), ttl_seconds=60)

        stats = cache.stats()
        assert stats.size == 2


class TestTTLExpiry:
    def test_expired_entry_returns_none(self):
        cache = VerificationCache(max_size=10)
        key = ("agent-1", "v1")
        cache.put(key, _make_cached_verification(), ttl_seconds=0.05)

        # Entry should be available immediately
        assert cache.get(key) is not None

        # Wait for expiry
        time.sleep(0.1)
        result = cache.get(key)
        assert result is None

    def test_expired_entry_counts_as_miss(self):
        cache = VerificationCache(max_size=10)
        key = ("agent-1", "v1")
        cache.put(key, _make_cached_verification(), ttl_seconds=0.05)
        cache.get(key)  # hit

        time.sleep(0.1)
        cache.get(key)  # miss (expired)

        stats = cache.stats()
        assert stats.hits == 1
        assert stats.misses == 1

    def test_different_ttls_per_entry(self):
        cache = VerificationCache(max_size=10)
        cache.put(("agent-1", "v1"), _make_cached_verification(trust_score=0.5), ttl_seconds=0.05)
        cache.put(("agent-2", "v1"), _make_cached_verification(trust_score=0.9), ttl_seconds=10)

        time.sleep(0.1)

        assert cache.get(("agent-1", "v1")) is None  # expired
        assert cache.get(("agent-2", "v1")) is not None  # still valid


class TestLRUEviction:
    def test_evicts_least_recently_used(self):
        cache = VerificationCache(max_size=2)
        cache.put(("a1", "v1"), _make_cached_verification(trust_score=0.1), ttl_seconds=60)
        cache.put(("a2", "v1"), _make_cached_verification(trust_score=0.2), ttl_seconds=60)

        # Access a1 so it becomes recently used, then add a3
        cache.get(("a1", "v1"))
        cache.put(("a3", "v1"), _make_cached_verification(trust_score=0.3), ttl_seconds=60)

        # a2 should be evicted (least recently used)
        assert cache.get(("a2", "v1")) is None
        assert cache.get(("a1", "v1")) is not None
        assert cache.get(("a3", "v1")) is not None

    def test_eviction_increments_stats(self):
        cache = VerificationCache(max_size=2)
        cache.put(("a1", "v1"), _make_cached_verification(), ttl_seconds=60)
        cache.put(("a2", "v1"), _make_cached_verification(), ttl_seconds=60)
        cache.put(("a3", "v1"), _make_cached_verification(), ttl_seconds=60)

        stats = cache.stats()
        assert stats.evictions >= 1
        assert stats.size == 2

    def test_max_size_respected(self):
        cache = VerificationCache(max_size=3)
        for i in range(10):
            cache.put((f"a{i}", "v1"), _make_cached_verification(), ttl_seconds=60)

        stats = cache.stats()
        assert stats.size <= 3


class TestInvalidation:
    def test_invalidate_removes_all_entries_for_agent(self):
        cache = VerificationCache(max_size=10)
        cache.put(("agent-1", "v1"), _make_cached_verification(), ttl_seconds=60)
        cache.put(("agent-1", "v2"), _make_cached_verification(), ttl_seconds=60)
        cache.put(("agent-2", "v1"), _make_cached_verification(), ttl_seconds=60)

        cache.invalidate("agent-1")

        assert cache.get(("agent-1", "v1")) is None
        assert cache.get(("agent-1", "v2")) is None
        assert cache.get(("agent-2", "v1")) is not None

    def test_invalidate_nonexistent_agent_is_safe(self):
        cache = VerificationCache(max_size=10)
        cache.invalidate("nonexistent")  # Should not raise

    def test_clear_removes_all_entries(self):
        cache = VerificationCache(max_size=10)
        cache.put(("a1", "v1"), _make_cached_verification(), ttl_seconds=60)
        cache.put(("a2", "v1"), _make_cached_verification(), ttl_seconds=60)

        cache.clear()

        assert cache.get(("a1", "v1")) is None
        assert cache.get(("a2", "v1")) is None

        stats = cache.stats()
        assert stats.size == 0

    def test_clear_resets_stats(self):
        cache = VerificationCache(max_size=10)
        cache.put(("a1", "v1"), _make_cached_verification(), ttl_seconds=60)
        cache.get(("a1", "v1"))
        cache.get(("missing", "v1"))

        cache.clear()
        stats = cache.stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.size == 0


class TestCacheStatsModel:
    def test_stats_returns_cache_stats_instance(self):
        cache = VerificationCache(max_size=10)
        stats = cache.stats()
        assert isinstance(stats, CacheStats)
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.size == 0


class TestCacheValidation:
    def test_max_size_must_be_positive(self):
        import pytest

        with pytest.raises(ValueError, match="max_size must be a positive integer"):
            VerificationCache(max_size=0)

    def test_ttl_must_be_positive(self):
        import pytest

        cache = VerificationCache(max_size=10)
        with pytest.raises(ValueError, match="ttl_seconds must be positive"):
            cache.put(("a1", "v1"), _make_cached_verification(), ttl_seconds=-1)
