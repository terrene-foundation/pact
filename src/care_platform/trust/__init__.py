# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Trust layer — postures, attestations, scoring, credentials, revocation, reasoning, messaging, integrity, and bridge trust."""

from care_platform.trust.attestation import CapabilityAttestation
from care_platform.trust.authorization import AuthorizationCheck, AuthorizationResult
from care_platform.trust.credentials import CredentialManager, VerificationToken
from care_platform.trust.decorators import (
    CareTrustOpsProvider,
    care_audited,
    care_shadow,
    care_verified,
)
from care_platform.trust.delegation import ChainStatus, ChainWalkResult, DelegationManager
from care_platform.trust.dual_binding import DualBinding
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.trust.genesis import GenesisManager
from care_platform.trust.integrity import (
    IntegrityCheckResult,
    IntegrityViolation,
    TrustChainIntegrity,
    TrustRecordHash,
)
from care_platform.trust.jcs import canonical_hash, canonical_serialize
from care_platform.trust.messaging import (
    AgentMessage,
    MessageChannel,
    MessageRouter,
    MessageType,
)
from care_platform.trust.posture import (
    NEVER_DELEGATED_ACTIONS,
    PostureChange,
    PostureEvidence,
    TrustPosture,
)
from care_platform.trust.reasoning import (
    ConfidentialityLevel,
    ReasoningTrace,
    ReasoningTraceStore,
)
from care_platform.trust.bridge_posture import bridge_verification_level, effective_posture
from care_platform.trust.bridge_trust import (
    BridgeDelegation,
    BridgeTrustManager,
    BridgeTrustRecord,
)
from care_platform.trust.revocation import RevocationManager, RevocationRecord
from care_platform.trust.scoring import (
    TrustFactors,
    TrustGrade,
    TrustScore,
    calculate_trust_score,
)
from care_platform.trust.sd_jwt import SDJWTBuilder, SelectiveDisclosureJWT
from care_platform.trust.shadow_enforcer import (
    ShadowEnforcer,
    ShadowMetrics,
    ShadowReport,
    ShadowResult,
)
from care_platform.trust.uncertainty import (
    ActionMetadata,
    ClassificationResult,
    UncertaintyClassifier,
    UncertaintyLevel,
)

__all__ = [
    "ActionMetadata",
    "AgentMessage",
    "AuthorizationCheck",
    "AuthorizationResult",
    "BridgeDelegation",
    "BridgeTrustManager",
    "BridgeTrustRecord",
    "CapabilityAttestation",
    "CareTrustOpsProvider",
    "ChainStatus",
    "ChainWalkResult",
    "ClassificationResult",
    "ConfidentialityLevel",
    "CredentialManager",
    "DelegationManager",
    "DualBinding",
    "EATPBridge",
    "GenesisManager",
    "IntegrityCheckResult",
    "IntegrityViolation",
    "TrustChainIntegrity",
    "TrustRecordHash",
    "MessageChannel",
    "MessageRouter",
    "MessageType",
    "NEVER_DELEGATED_ACTIONS",
    "PostureChange",
    "PostureEvidence",
    "ReasoningTrace",
    "ReasoningTraceStore",
    "RevocationManager",
    "RevocationRecord",
    "SDJWTBuilder",
    "SelectiveDisclosureJWT",
    "ShadowEnforcer",
    "ShadowMetrics",
    "ShadowReport",
    "ShadowResult",
    "TrustFactors",
    "TrustGrade",
    "TrustPosture",
    "TrustScore",
    "UncertaintyClassifier",
    "UncertaintyLevel",
    "VerificationToken",
    "bridge_verification_level",
    "calculate_trust_score",
    "canonical_hash",
    "canonical_serialize",
    "care_audited",
    "care_shadow",
    "care_verified",
    "effective_posture",
]
