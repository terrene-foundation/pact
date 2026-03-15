# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Verification cache — LRU cache with TTL eviction for verification results.

Stores recent verification results so that high-frequency agent actions
(e.g., Analytics Agent's continuous monitoring) can use QUICK verification
(~1ms) when a recent result is still valid, rather than re-running STANDARD
or FULL verification every time.

Cache key: (agent_id, action, envelope_content_hash)
Cache value: CachedVerification(trust_score, posture, expiry, verification_result)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict

from pydantic import BaseModel, Field

from care_platform.config.schema import TrustPostureLevel

logger = logging.getLogger(__name__)


class CachedVerification(BaseModel):
    """A cached verification result."""

    trust_score: float = Field(ge=0.0, le=1.0, description="Trust score at time of verification")
    posture: TrustPostureLevel = Field(description="Trust posture at time of verification")
    verification_result: str = Field(description="The verification outcome (e.g. 'auto_approved')")


class CacheStats(BaseModel):
    """Statistics for the verification cache."""

    hits: int = Field(default=0, ge=0, description="Number of cache hits")
    misses: int = Field(default=0, ge=0, description="Number of cache misses")
    evictions: int = Field(default=0, ge=0, description="Number of LRU evictions")
    size: int = Field(default=0, ge=0, description="Current number of entries in cache")


# Internal entry wrapper that holds the value and its expiry timestamp.
class _CacheEntry:
    __slots__ = ("value", "expiry")

    def __init__(self, value: CachedVerification, expiry: float) -> None:
        self.value = value
        self.expiry = expiry


class VerificationCache:
    """LRU cache with per-entry TTL eviction for verification results.

    Thread-safe via a simple lock. Designed for in-memory use — not persisted.
    """

    def __init__(self, max_size: int) -> None:
        if max_size <= 0:
            raise ValueError(
                f"max_size must be a positive integer, got {max_size}. "
                "A verification cache with zero or negative capacity cannot store entries."
            )
        self._max_size = max_size
        self._store: OrderedDict[tuple[str, ...], _CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: tuple[str, ...]) -> CachedVerification | None:
        """Look up a cached verification result.

        Returns None if the key is missing or the entry has expired.
        A hit moves the entry to the most-recently-used position.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            # Check TTL expiry
            if time.monotonic() > entry.expiry:
                # Expired — remove silently, count as miss
                del self._store[key]
                self._misses += 1
                logger.debug(
                    "Cache entry expired: agent_id=%s envelope_version=%s",
                    key[0],
                    key[1],
                )
                return None

            # Move to end (most recently used)
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    def put(
        self,
        key: tuple[str, ...],
        value: CachedVerification,
        ttl_seconds: float,
    ) -> None:
        """Insert or update a verification result in the cache.

        Args:
            key: (agent_id, envelope_version) tuple.
            value: The verification result to cache.
            ttl_seconds: Time-to-live in seconds for this entry.

        Raises:
            ValueError: If ttl_seconds is not positive.
        """
        if ttl_seconds <= 0:
            raise ValueError(
                f"ttl_seconds must be positive, got {ttl_seconds}. "
                "A zero or negative TTL would make the entry immediately expired."
            )

        expiry = time.monotonic() + ttl_seconds
        entry = _CacheEntry(value=value, expiry=expiry)

        with self._lock:
            # If key exists, remove it first so reinsertion goes to end
            if key in self._store:
                del self._store[key]

            self._store[key] = entry

            # Evict LRU entries if over capacity
            while len(self._store) > self._max_size:
                evicted_key, _ = self._store.popitem(last=False)
                self._evictions += 1
                logger.debug(
                    "Cache LRU eviction: agent_id=%s envelope_version=%s",
                    evicted_key[0],
                    evicted_key[1],
                )

    def invalidate(self, agent_id: str) -> None:
        """Remove all cached entries for a given agent.

        This is used when an agent's constraint envelope changes or
        their trust posture is updated, invalidating all cached results.
        """
        with self._lock:
            keys_to_remove = [k for k in self._store if k[0] == agent_id]
            for key in keys_to_remove:
                del self._store[key]

            if keys_to_remove:
                logger.info(
                    "Invalidated %d cache entries for agent_id=%s",
                    len(keys_to_remove),
                    agent_id,
                )

    def clear(self) -> None:
        """Remove all entries and reset statistics."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            logger.info("Verification cache cleared")

    def stats(self) -> CacheStats:
        """Return current cache statistics."""
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                size=len(self._store),
            )
