# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Platform configuration — schema, loading, and defaults."""

from pact_platform.build.config.defaults import (
    DEFAULT_TRUST_POSTURE,
    DEFAULT_VERIFICATION_LEVEL,
    default_constraint_envelope,
    default_verification_gradient,
)
from pact_platform.build.config.loader import ConfigError, load_config, load_config_from_dict
from pact_platform.build.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintDimension,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    PactConfig,
    PlatformConfig,
    TeamConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
    WorkspaceConfig,
)

__all__ = [
    "AgentConfig",
    "CommunicationConstraintConfig",
    "ConfigError",
    "ConstraintDimension",
    "ConstraintEnvelopeConfig",
    "DEFAULT_TRUST_POSTURE",
    "DEFAULT_VERIFICATION_LEVEL",
    "DataAccessConstraintConfig",
    "FinancialConstraintConfig",
    "GenesisConfig",
    "GradientRuleConfig",
    "OperationalConstraintConfig",
    "PactConfig",
    "PlatformConfig",
    "TeamConfig",
    "TemporalConstraintConfig",
    "TrustPostureLevel",
    "VerificationGradientConfig",
    "VerificationLevel",
    "WorkspaceConfig",
    "default_constraint_envelope",
    "default_verification_gradient",
    "load_config",
    "load_config_from_dict",
]
