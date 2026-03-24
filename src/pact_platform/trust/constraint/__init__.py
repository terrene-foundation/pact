# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Constraint evaluation — envelope evaluation, verification gradient, middleware, signing,
caching, circuit breaker, and adaptive verification level selection."""

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
from pact_platform.trust.constraint.enforcement import (
    CareEnforcementPipeline,
    EnforcementResult,
    care_result_to_eatp_result,
    create_approval_held_callback,
    verdict_to_care_level,
)
from pact_platform.trust.constraint.enforcer import (
    ConstraintEnforcer,
    EnforcerRequiredError,
)
from pact_platform.trust.constraint.envelope import (
    ConstraintEnvelope,
    DimensionEvaluation,
    EnvelopeEvaluation,
    EvaluationResult,
)
from pact_platform.trust.constraint.gradient import (
    GradientEngine,
    VerificationResult,
    VerificationThoroughness,
)
from pact_platform.trust.constraint.middleware import (
    ActionOutcome,
    ApprovalRequest,
    MiddlewareResult,
    VerificationMiddleware,
)
from pact_platform.trust.constraint.resolution import (
    ConstraintResolutionError,
    resolve_constraints,
)
from pact_platform.trust.constraint.signing import (
    EnvelopeVersionHistory,
    SignedEnvelope,
)
from pact_platform.trust.constraint.verification_level import (
    select_verification_level,
)

__all__ = [
    "ActionOutcome",
    "ApprovalRequest",
    "BridgeSharingPolicy",
    "CachedVerification",
    "CacheStats",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
    "CareEnforcementPipeline",
    "ConstraintEnforcer",
    "ConstraintResolutionError",
    "EnforcerRequiredError",
    "EnforcementResult",
    "ConstraintEnvelope",
    "DimensionEvaluation",
    "EnvelopeEvaluation",
    "EnvelopeVersionHistory",
    "EvaluationResult",
    "FieldSharingRule",
    "GradientEngine",
    "MiddlewareResult",
    "SharingMode",
    "SignedEnvelope",
    "VerificationCache",
    "VerificationMiddleware",
    "VerificationResult",
    "VerificationThoroughness",
    "compute_bridge_envelope",
    "resolve_constraints",
    "select_verification_level",
    "care_result_to_eatp_result",
    "create_approval_held_callback",
    "validate_bridge_tightening",
    "verdict_to_care_level",
]
