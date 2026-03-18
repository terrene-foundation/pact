# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Trust scoring — five-factor weighted scoring for agent trust assessment.

Factors:
  1. Chain completeness (30%) — all 5 EATP elements present
  2. Delegation depth (15%) — shorter chains = higher trust
  3. Constraint coverage (25%) — all 5 dimensions configured
  4. Posture level (20%) — higher posture = higher trust
  5. Chain recency (10%) — fresher attestations = higher trust
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from care_platform.build.config.schema import TrustPostureLevel


class TrustGrade(str, Enum):
    """Letter grade for trust score."""

    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


# Factor weights (must sum to 1.0)
FACTOR_WEIGHTS = {
    "chain_completeness": 0.30,
    "delegation_depth": 0.15,
    "constraint_coverage": 0.25,
    "posture_level": 0.20,
    "chain_recency": 0.10,
}

# Posture level scores (0.0 to 1.0)
POSTURE_SCORES: dict[TrustPostureLevel, float] = {
    TrustPostureLevel.PSEUDO_AGENT: 0.0,
    TrustPostureLevel.SUPERVISED: 0.25,
    TrustPostureLevel.SHARED_PLANNING: 0.50,
    TrustPostureLevel.CONTINUOUS_INSIGHT: 0.75,
    TrustPostureLevel.DELEGATED: 1.0,
}


class TrustFactors(BaseModel):
    """Input factors for trust score calculation."""

    has_genesis: bool = False
    has_delegation: bool = False
    has_envelope: bool = False
    has_attestation: bool = False
    has_audit_anchor: bool = False
    delegation_depth: int = Field(default=0, ge=0)
    max_delegation_depth: int = Field(default=5, ge=1)
    dimensions_configured: int = Field(default=0, ge=0, le=5)
    posture_level: TrustPostureLevel = TrustPostureLevel.PSEUDO_AGENT
    newest_attestation_age_days: int = Field(default=365, ge=0)
    max_acceptable_age_days: int = Field(default=90, ge=1)


class TrustScore(BaseModel):
    """Calculated trust score with factor breakdown."""

    agent_id: str
    overall_score: float = Field(ge=0.0, le=1.0)
    grade: TrustGrade
    factors: dict[str, float] = Field(default_factory=dict)
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def calculate_trust_score(agent_id: str, factors: TrustFactors) -> TrustScore:
    """Calculate a weighted trust score from input factors.

    Each factor produces a score between 0.0 and 1.0, then weighted and summed.
    """
    factor_scores: dict[str, float] = {}

    # 1. Chain completeness (30%) — count of 5 EATP elements present
    elements = [
        factors.has_genesis,
        factors.has_delegation,
        factors.has_envelope,
        factors.has_attestation,
        factors.has_audit_anchor,
    ]
    factor_scores["chain_completeness"] = sum(elements) / 5.0

    # 2. Delegation depth (15%) — shorter = better (inverse)
    if factors.delegation_depth == 0:
        factor_scores["delegation_depth"] = 1.0
    else:
        factor_scores["delegation_depth"] = max(
            0.0, 1.0 - (factors.delegation_depth / factors.max_delegation_depth)
        )

    # 3. Constraint coverage (25%) — how many of 5 dimensions configured
    factor_scores["constraint_coverage"] = factors.dimensions_configured / 5.0

    # 4. Posture level (20%)
    factor_scores["posture_level"] = POSTURE_SCORES.get(factors.posture_level, 0.0)

    # 5. Chain recency (10%) — fresher = better
    if factors.newest_attestation_age_days <= 0:
        factor_scores["chain_recency"] = 1.0
    else:
        factor_scores["chain_recency"] = max(
            0.0,
            1.0 - (factors.newest_attestation_age_days / factors.max_acceptable_age_days),
        )

    # Weighted sum
    overall = sum(factor_scores[k] * FACTOR_WEIGHTS[k] for k in FACTOR_WEIGHTS)
    overall = max(0.0, min(1.0, overall))

    return TrustScore(
        agent_id=agent_id,
        overall_score=overall,
        grade=_score_to_grade(overall),
        factors=factor_scores,
    )


def _score_to_grade(score: float) -> TrustGrade:
    """Convert a numeric score to a letter grade."""
    if score >= 0.95:
        return TrustGrade.A_PLUS
    if score >= 0.85:
        return TrustGrade.A
    if score >= 0.75:
        return TrustGrade.B_PLUS
    if score >= 0.65:
        return TrustGrade.B
    if score >= 0.50:
        return TrustGrade.C
    if score >= 0.35:
        return TrustGrade.D
    return TrustGrade.F
