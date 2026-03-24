# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Constraint infrastructure — bridge envelopes, caching, circuit breaker, signing.

Governance decisions are made by GovernanceEngine (kailash-pact).
This package provides operational infrastructure that wraps those decisions:
bridge envelope intersection, verification caching, circuit breaking, and
envelope signing.
"""

from pact_platform.trust.constraint.bridge_envelope import (
    BridgeSharingPolicy,
    FieldSharingRule,
    SharingMode,
    compute_bridge_envelope,
    validate_bridge_tightening,
)
from pact_platform.trust.constraint.cache import (
    CachedVerification,
    CacheStats,
    VerificationCache,
)
from pact_platform.trust.constraint.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from pact_platform.trust.constraint.signing import (
    EnvelopeVersionHistory,
    SignedEnvelope,
)

__all__ = [
    "BridgeSharingPolicy",
    "CachedVerification",
    "CacheStats",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
    "EnvelopeVersionHistory",
    "FieldSharingRule",
    "SharingMode",
    "SignedEnvelope",
    "VerificationCache",
    "compute_bridge_envelope",
    "validate_bridge_tightening",
]
