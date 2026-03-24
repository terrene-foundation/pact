# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Compatibility shims for types formerly in deleted trust submodules.

These types were defined in modules superseded by kailash.trust and kailash-pact.
They are retained here (minimally) because runtime code in pact_platform still
references them. They will be phased out as pact_platform migrates fully to the
kailash.trust API.

Originated from:
- pact_platform.trust.posture (TrustPosture, NEVER_DELEGATED_ACTIONS, POSTURE_ORDER, UPGRADE_REQUIREMENTS)
- pact_platform.trust.jcs (canonical_serialize, canonical_hash)
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

import jcs as _jcs
from pydantic import BaseModel, Field

from pact_platform.build.config.schema import TrustPostureLevel, VerificationLevel

logger = logging.getLogger(__name__)

__all__ = [
    "TrustPosture",
    "PostureEvidence",
    "NEVER_DELEGATED_ACTIONS",
    "POSTURE_ORDER",
    "UPGRADE_REQUIREMENTS",
    "canonical_serialize",
    "canonical_hash",
    "effective_posture",
    "bridge_verification_level",
]

# ---------------------------------------------------------------------------
# Constants from old posture.py
# ---------------------------------------------------------------------------

# Ordered posture levels (lower = more restrictive)
POSTURE_ORDER: dict[TrustPostureLevel, int] = {
    TrustPostureLevel.PSEUDO_AGENT: 0,
    TrustPostureLevel.SUPERVISED: 1,
    TrustPostureLevel.SHARED_PLANNING: 2,
    TrustPostureLevel.CONTINUOUS_INSIGHT: 3,
    TrustPostureLevel.DELEGATED: 4,
}

# Actions that must never be fully delegated regardless of posture.
NEVER_DELEGATED_ACTIONS: set[str] = {
    "content_strategy",
    "novel_outreach",
    "crisis_response",
    "financial_decisions",
    "modify_constraints",
    "modify_governance",
    "external_publication",
}

# Evidence-based upgrade requirements per target posture level.
UPGRADE_REQUIREMENTS: dict[TrustPostureLevel, dict] = {
    TrustPostureLevel.SUPERVISED: {
        "min_days": 7,
        "min_operations": 10,
        "min_success_rate": 0.90,
        "max_incidents": 0,
    },
    TrustPostureLevel.SHARED_PLANNING: {
        "min_days": 90,
        "min_success_rate": 0.95,
        "min_operations": 100,
        "shadow_enforcer_required": True,
        "shadow_pass_rate": 0.90,
    },
    TrustPostureLevel.CONTINUOUS_INSIGHT: {
        "min_days": 180,
        "min_success_rate": 0.98,
        "min_operations": 500,
        "shadow_enforcer_required": True,
        "shadow_pass_rate": 0.95,
    },
    TrustPostureLevel.DELEGATED: {
        "min_days": 365,
        "min_success_rate": 0.99,
        "min_operations": 1000,
        "shadow_enforcer_required": True,
        "shadow_pass_rate": 0.98,
    },
}


# ---------------------------------------------------------------------------
# TrustPosture model (lightweight version of old posture.py class)
# ---------------------------------------------------------------------------


class TrustPosture(BaseModel):
    """Runtime trust posture for an agent.

    Lightweight compatibility shim retaining the fields and methods used
    by pact_platform runtime code. The full posture lifecycle (EATP state
    machine, evidence-based upgrades) now lives in kailash.trust.posture.
    """

    agent_id: str
    current_level: TrustPostureLevel = TrustPostureLevel.SUPERVISED
    posture_since: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_action_always_held(self, action: str) -> bool:
        """Check if an action is in the never-delegated list."""
        return action in NEVER_DELEGATED_ACTIONS


class PostureEvidence(BaseModel):
    """Evidence supporting a posture upgrade.

    Lightweight compatibility shim. The full model with EATP state machine
    integration now lives in kailash.trust.posture.
    """

    successful_operations: int = Field(default=0, ge=0)
    total_operations: int = Field(default=0, ge=0)
    days_at_current_posture: int = Field(default=0, ge=0)
    shadow_enforcer_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    incidents: int = Field(default=0, ge=0)
    shadow_blocked_count: int = Field(default=0, ge=0)

    @property
    def success_rate(self) -> float:
        if self.total_operations == 0:
            return 0.0
        return self.successful_operations / self.total_operations


# ---------------------------------------------------------------------------
# JCS canonical serialization (from old jcs.py)
# ---------------------------------------------------------------------------


def canonical_serialize(data: dict) -> bytes:
    """Serialize a dict to RFC 8785 canonical JSON bytes.

    Args:
        data: The dictionary to serialize.

    Returns:
        Canonical JSON bytes per RFC 8785.

    Raises:
        TypeError: If the data cannot be serialized.
    """
    return _jcs.canonicalize(data)


def canonical_hash(data: dict) -> str:
    """Compute SHA-256 hash of RFC 8785 canonical JSON.

    Args:
        data: The dictionary to hash.

    Returns:
        64-character hex SHA-256 digest of the canonical JSON bytes.
    """
    return hashlib.sha256(_jcs.canonicalize(data)).hexdigest()


# ---------------------------------------------------------------------------
# Bridge posture functions (from old bridge_posture.py)
# ---------------------------------------------------------------------------


def effective_posture(
    source_posture: TrustPostureLevel,
    target_posture: TrustPostureLevel,
) -> TrustPostureLevel:
    """Return the more restrictive of two postures (minimum by POSTURE_ORDER).

    Bridge actions operate at the trust level of the least-trusted side.
    """
    source_order = POSTURE_ORDER[source_posture]
    target_order = POSTURE_ORDER[target_posture]
    if source_order <= target_order:
        return source_posture
    return target_posture


def bridge_verification_level(effective: TrustPostureLevel) -> VerificationLevel:
    """Map an effective bridge posture to a verification gradient level.

    Lower trust postures require more scrutiny:
    - PSEUDO_AGENT, SUPERVISED -> HELD (requires human approval)
    - SHARED_PLANNING -> FLAGGED (flagged for review but proceeds)
    - CONTINUOUS_INSIGHT, DELEGATED -> AUTO_APPROVED (proceeds automatically)
    """
    if effective in (TrustPostureLevel.PSEUDO_AGENT, TrustPostureLevel.SUPERVISED):
        return VerificationLevel.HELD
    elif effective == TrustPostureLevel.SHARED_PLANNING:
        return VerificationLevel.FLAGGED
    else:
        return VerificationLevel.AUTO_APPROVED
