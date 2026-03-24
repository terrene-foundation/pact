# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Platform configuration schema — re-exports from kailash-pact.

All config types are canonical in ``kailash.trust.pact.config`` (kailash-pact v0.4.0).
This module re-exports them so that ``from pact_platform.build.config.schema import X``
continues to work across the platform codebase.
"""

from kailash.trust.pact.config import (  # noqa: F401
    CONFIDENTIALITY_ORDER,
    AgentConfig,
    CommunicationConstraintConfig,
    ConfidentialityLevel,
    ConstraintDimension,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    DepartmentConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    OrgDefinition,
    PactConfig,
    PlatformConfig,
    TeamConfig,
    TemporalConstraintConfig,
    TrustPosture,
    TrustPostureLevel,
    ValidationResult,
    ValidationSeverity,
    VerificationGradientConfig,
    VerificationLevel,
    WorkspaceConfig,
)

__all__ = [
    "AgentConfig",
    "CONFIDENTIALITY_ORDER",
    "CommunicationConstraintConfig",
    "ConfidentialityLevel",
    "ConstraintDimension",
    "ConstraintEnvelopeConfig",
    "DataAccessConstraintConfig",
    "DepartmentConfig",
    "FinancialConstraintConfig",
    "GenesisConfig",
    "GradientRuleConfig",
    "OperationalConstraintConfig",
    "OrgDefinition",
    "PactConfig",
    "PlatformConfig",
    "TeamConfig",
    "TemporalConstraintConfig",
    "TrustPosture",
    "TrustPostureLevel",
    "ValidationResult",
    "ValidationSeverity",
    "VerificationGradientConfig",
    "VerificationLevel",
    "WorkspaceConfig",
]
