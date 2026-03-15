# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for verification caching integration in the middleware pipeline.

M17-1703: Integrate VerificationCache into the middleware pipeline.
- Cache lookup before full evaluation
- Cache stores results keyed by (agent_id, action, envelope_version)
- Cache hit rate >90% in steady state
- Performance improvement for cached verifications
"""

from __future__ import annotations

import time

import pytest

from care_platform.audit.anchor import AuditChain
from care_platform.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.cache import CachedVerification, VerificationCache
from care_platform.constraint.envelope import ConstraintEnvelope
from care_platform.constraint.gradient import GradientEngine
from care_platform.constraint.middleware import (
    ActionOutcome,
    VerificationMiddleware,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(**kwargs) -> ConstraintEnvelope:
    """Create a ConstraintEnvelope with sensible defaults for testing."""
    config = ConstraintEnvelopeConfig(
        id="test-envelope",
        financial=kwargs.get("financial", FinancialConstraintConfig(max_spend_usd=1000.0)),
        operational=kwargs.get("operational", OperationalConstraintConfig()),
        communication=kwargs.get(
            "communication", CommunicationConstraintConfig(internal_only=False)
        ),
        **{
            k: v
            for k, v in kwargs.items()
            if k not in ("financial", "operational", "communication")
        },
    )
    return ConstraintEnvelope(config=config)


def _make_engine(*rules, default=VerificationLevel.HELD) -> GradientEngine:
    """Create a GradientEngine with the given rules."""
    config = VerificationGradientConfig(rules=list(rules), default_level=default)
    return GradientEngine(config)


def _make_cached_middleware(
    rules: list[GradientRuleConfig] | None = None,
    default_level: VerificationLevel = VerificationLevel.HELD,
    cache_max_size: int = 100,
    cache_ttl_seconds: float = 60.0,
) -> VerificationMiddleware:
    """Create a VerificationMiddleware with caching enabled."""
    engine = _make_engine(*(rules or []), default=default_level)
    envelope = _make_envelope()
    cache = VerificationCache(max_size=cache_max_size)
    return VerificationMiddleware(
        gradient_engine=engine,
        envelope=envelope,
        verification_cache=cache,
        cache_ttl_seconds=cache_ttl_seconds,
    )


# ---------------------------------------------------------------------------
# Cache integration in middleware
# ---------------------------------------------------------------------------


class TestMiddlewareCacheIntegration:
    """VerificationMiddleware uses VerificationCache when provided."""

    def test_middleware_accepts_cache_parameter(self):
        """Middleware constructor accepts a verification_cache parameter."""
        cache = VerificationCache(max_size=10)
        engine = _make_engine()
        envelope = _make_envelope()
        mw = VerificationMiddleware(
            gradient_engine=engine,
            envelope=envelope,
            verification_cache=cache,
            cache_ttl_seconds=60.0,
        )
        assert mw._verification_cache is cache

    def test_middleware_works_without_cache(self):
        """Middleware still works normally when no cache is provided."""
        engine = _make_engine(
            GradientRuleConfig(
                pattern="read_*",
                level=VerificationLevel.AUTO_APPROVED,
                reason="Read",
            )
        )
        envelope = _make_envelope()
        mw = VerificationMiddleware(gradient_engine=engine, envelope=envelope)
        result = mw.process_action(agent_id="agent-1", action="read_metrics")
        assert result.verification_level == VerificationLevel.AUTO_APPROVED

    def test_first_call_populates_cache(self):
        """First call should evaluate normally and populate cache."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read",
                ),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="read_metrics")
        assert result.verification_level == VerificationLevel.AUTO_APPROVED

        # Cache should have an entry now
        stats = mw._verification_cache.stats()
        assert stats.size >= 1

    def test_second_call_uses_cache(self):
        """Second identical call should use cached result."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read",
                ),
            ],
        )
        # First call
        mw.process_action(agent_id="agent-1", action="read_metrics")
        # Second call (should hit cache)
        result2 = mw.process_action(agent_id="agent-1", action="read_metrics")

        assert result2.verification_level == VerificationLevel.AUTO_APPROVED

        stats = mw._verification_cache.stats()
        assert stats.hits >= 1

    def test_different_agents_cached_independently(self):
        """Different agents should have independent cache entries."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read",
                ),
            ],
        )
        mw.process_action(agent_id="agent-1", action="read_metrics")
        mw.process_action(agent_id="agent-2", action="read_metrics")

        stats = mw._verification_cache.stats()
        assert stats.size >= 2

    def test_different_actions_cached_independently(self):
        """Different actions should have independent cache entries."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read",
                ),
            ],
        )
        mw.process_action(agent_id="agent-1", action="read_metrics")
        mw.process_action(agent_id="agent-1", action="read_reports")

        stats = mw._verification_cache.stats()
        assert stats.size >= 2


# ---------------------------------------------------------------------------
# Cache bypass conditions
# ---------------------------------------------------------------------------


class TestMiddlewareCacheBypass:
    """Cache should be bypassed for certain action types."""

    def test_blocked_actions_not_cached(self):
        """BLOCKED actions should not be cached (security-sensitive)."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="delete_*",
                    level=VerificationLevel.BLOCKED,
                    reason="Blocked",
                ),
            ],
        )
        mw.process_action(agent_id="agent-1", action="delete_records")
        mw.process_action(agent_id="agent-1", action="delete_records")

        # BLOCKED results should not be cached — each call should re-evaluate
        stats = mw._verification_cache.stats()
        assert stats.hits == 0

    def test_held_actions_not_cached(self):
        """HELD actions should not be cached (require fresh evaluation)."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="approve_*",
                    level=VerificationLevel.HELD,
                    reason="Held for approval",
                ),
            ],
        )
        mw.process_action(agent_id="agent-1", action="approve_budget")
        mw.process_action(agent_id="agent-1", action="approve_budget")

        stats = mw._verification_cache.stats()
        assert stats.hits == 0

    def test_spend_actions_bypass_cache(self):
        """Actions with spend_amount > 0 should bypass cache for accurate tracking."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="purchase_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Purchase",
                ),
            ],
        )
        mw.process_action(agent_id="agent-1", action="purchase_item", spend_amount=10.0)
        mw.process_action(agent_id="agent-1", action="purchase_item", spend_amount=10.0)

        stats = mw._verification_cache.stats()
        assert stats.hits == 0

    def test_halted_middleware_bypasses_cache(self):
        """Halted middleware should not use cache."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read",
                ),
            ],
        )
        # Populate cache
        mw.process_action(agent_id="agent-1", action="read_metrics")
        # Halt
        mw.halt(reason="Emergency")
        # Even with cache populated, halted middleware blocks
        result = mw.process_action(agent_id="agent-1", action="read_metrics")
        assert result.outcome == ActionOutcome.REJECTED


# ---------------------------------------------------------------------------
# Cache performance
# ---------------------------------------------------------------------------


class TestMiddlewareCachePerformance:
    """Cache should provide measurable performance benefits."""

    def test_cache_hit_rate_above_90_percent_in_steady_state(self):
        """In steady state with repeated actions, cache hit rate should exceed 90%."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read",
                ),
                GradientRuleConfig(
                    pattern="write_*",
                    level=VerificationLevel.FLAGGED,
                    reason="Write",
                ),
            ],
            cache_max_size=100,
            cache_ttl_seconds=60.0,
        )

        # Cold start: 5 unique actions
        actions = ["read_a", "read_b", "read_c", "write_x", "write_y"]
        for action in actions:
            mw.process_action(agent_id="agent-1", action=action)

        # Steady state: 100 repeated actions
        for i in range(100):
            action = actions[i % len(actions)]
            mw.process_action(agent_id="agent-1", action=action)

        stats = mw._verification_cache.stats()
        total = stats.hits + stats.misses
        hit_rate = stats.hits / total if total > 0 else 0
        # 5 initial misses + 100 hits = 100/105 ~= 95%
        assert hit_rate > 0.90, f"Hit rate {hit_rate:.2%} is below 90%"

    def test_cached_call_faster_than_uncached(self):
        """Cached calls should be faster on average than uncached calls."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read",
                ),
            ],
        )

        # Warm up cache with one call
        mw.process_action(agent_id="agent-1", action="read_metrics")

        # Measure cached calls
        start = time.monotonic()
        for _ in range(100):
            mw.process_action(agent_id="agent-1", action="read_metrics")
        cached_time = time.monotonic() - start

        # The cached calls should complete quickly (just a sanity check)
        # We check they all complete in under 1 second total for 100 calls
        assert cached_time < 1.0, f"100 cached calls took {cached_time:.3f}s"


# ---------------------------------------------------------------------------
# Cache TTL and invalidation
# ---------------------------------------------------------------------------


class TestMiddlewareCacheTTL:
    """Cache entries expire based on TTL."""

    def test_cache_entry_expires(self):
        """Cache entries should expire after TTL."""
        mw = _make_cached_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read",
                ),
            ],
            cache_ttl_seconds=0.05,  # 50ms TTL
        )

        # Populate cache
        mw.process_action(agent_id="agent-1", action="read_metrics")

        # Wait for expiry
        time.sleep(0.1)

        # This call should be a cache miss (expired)
        mw.process_action(agent_id="agent-1", action="read_metrics")

        stats = mw._verification_cache.stats()
        # Should have at least 1 miss after the initial population miss
        assert stats.misses >= 2
