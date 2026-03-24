# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Default configuration values for the PACT.

Provides sensible defaults for optional configuration fields. All security-critical
defaults are conservative (e.g., $0 financial authority, internal-only communication,
supervised posture).
"""

from __future__ import annotations

from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)

# Default trust posture: start supervised (most conservative)
DEFAULT_TRUST_POSTURE = TrustPostureLevel.SUPERVISED

# Default verification level: HELD (require human approval when no rule matches)
DEFAULT_VERIFICATION_LEVEL = VerificationLevel.HELD


def default_constraint_envelope(agent_id: str) -> ConstraintEnvelopeConfig:
    """Create a maximally restrictive constraint envelope.

    The default envelope is designed to be safe by default — zero financial
    authority, internal-only communication, no external actions. This follows
    the EATP principle of monotonic constraint tightening: start tight, relax
    only with evidence.
    """
    return ConstraintEnvelopeConfig(
        id=f"{agent_id}-envelope",
        description=f"Default restrictive envelope for {agent_id}",
        financial=FinancialConstraintConfig(
            max_spend_usd=0.0,
        ),
        operational=OperationalConstraintConfig(
            blocked_actions=["publish_external", "send_email", "modify_config"],
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="09:00",
            active_hours_end="18:00",
            timezone="UTC",
        ),
        data_access=DataAccessConstraintConfig(
            blocked_data_types=["pii", "financial_records", "legal_documents"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )


def default_verification_gradient() -> VerificationGradientConfig:
    """Create a conservative verification gradient.

    External actions are always HELD. Internal read operations are auto-approved.
    Everything else defaults to HELD for human review.
    """
    return VerificationGradientConfig(
        default_level=VerificationLevel.HELD,
        rules=[],
    )
