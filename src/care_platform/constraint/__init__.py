# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Constraint evaluation — envelope evaluation, verification gradient, middleware, signing,
caching, circuit breaker, and adaptive verification level selection."""

from care_platform.constraint.cache import (
    CachedVerification,
    CacheStats,
    VerificationCache,
)
from care_platform.constraint.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from care_platform.constraint.enforcer import (
    ConstraintEnforcer,
    EnforcerRequiredError,
)
from care_platform.constraint.enforcement import (
    CareEnforcementPipeline,
    EnforcementResult,
    care_result_to_eatp_result,
    create_approval_held_callback,
    verdict_to_care_level,
)
from care_platform.constraint.envelope import (
    ConstraintEnvelope,
    DimensionEvaluation,
    EnvelopeEvaluation,
    EvaluationResult,
)
from care_platform.constraint.gradient import (
    GradientEngine,
    VerificationResult,
    VerificationThoroughness,
)
from care_platform.constraint.middleware import (
    ActionOutcome,
    ApprovalRequest,
    MiddlewareResult,
    VerificationMiddleware,
)
from care_platform.constraint.signing import (
    EnvelopeVersionHistory,
    SignedEnvelope,
)
from care_platform.constraint.bridge_envelope import (
    BridgeSharingPolicy,
    FieldSharingRule,
    SharingMode,
    compute_bridge_envelope,
    validate_bridge_tightening,
)
from care_platform.constraint.resolution import (
    ConstraintResolutionError,
    resolve_constraints,
)
from care_platform.constraint.verification_level import (
    VerificationThoroughness as VerificationThoroughness,
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
