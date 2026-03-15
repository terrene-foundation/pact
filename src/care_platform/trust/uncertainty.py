# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Uncertainty Classifier — maps action uncertainty to verification levels.

Classifies actions by their uncertainty level based on metadata about the
action's context (data completeness, precedent availability, reversibility,
and impact scope). Each uncertainty level maps to a CARE verification level:

    NONE           -> AUTO_APPROVED
    INFORMATIONAL  -> AUTO_APPROVED
    INTERPRETIVE   -> FLAGGED
    JUDGMENTAL     -> HELD
    FUNDAMENTAL    -> BLOCKED
"""

from __future__ import annotations

import logging
from enum import Enum

from pydantic import BaseModel, Field

from care_platform.config.schema import VerificationLevel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Uncertainty Level Enum
# ---------------------------------------------------------------------------


class UncertaintyLevel(str, Enum):
    """Levels of uncertainty about an agent action.

    Ordered from least uncertain (NONE) to most uncertain (FUNDAMENTAL).
    """

    NONE = "none"
    INFORMATIONAL = "informational"
    INTERPRETIVE = "interpretive"
    JUDGMENTAL = "judgmental"
    FUNDAMENTAL = "fundamental"


# ---------------------------------------------------------------------------
# Uncertainty -> Verification Level Mapping
# ---------------------------------------------------------------------------

_UNCERTAINTY_TO_VERIFICATION: dict[UncertaintyLevel, VerificationLevel] = {
    UncertaintyLevel.NONE: VerificationLevel.AUTO_APPROVED,
    UncertaintyLevel.INFORMATIONAL: VerificationLevel.AUTO_APPROVED,
    UncertaintyLevel.INTERPRETIVE: VerificationLevel.FLAGGED,
    UncertaintyLevel.JUDGMENTAL: VerificationLevel.HELD,
    UncertaintyLevel.FUNDAMENTAL: VerificationLevel.BLOCKED,
}


# ---------------------------------------------------------------------------
# Action Metadata
# ---------------------------------------------------------------------------


class ActionMetadata(BaseModel):
    """Metadata about an action used to classify its uncertainty.

    Args:
        data_completeness: How complete the available data is (0.0 to 1.0).
            1.0 means all required information is available.
        precedent_available: Whether there is prior precedent for this action.
        reversible: Whether the action can be undone.
        impact_scope: The scope of the action's impact.
            One of: "local", "team", "organization".
    """

    data_completeness: float = Field(ge=0.0, le=1.0)
    precedent_available: bool
    reversible: bool
    impact_scope: str  # "local", "team", "organization"


# ---------------------------------------------------------------------------
# Classification Result
# ---------------------------------------------------------------------------


class ClassificationResult(BaseModel):
    """Result of classifying an action's uncertainty."""

    level: UncertaintyLevel
    verification_level: VerificationLevel
    score: float = Field(
        ge=0.0, le=1.0,
        description="Uncertainty score: 0.0 = fully certain, 1.0 = fundamentally uncertain",
    )
    reason: str


# ---------------------------------------------------------------------------
# Uncertainty Classifier
# ---------------------------------------------------------------------------


class UncertaintyClassifier:
    """Classifies actions by their uncertainty level.

    Uses action metadata (data completeness, precedent availability,
    reversibility, and impact scope) to compute an uncertainty score,
    map it to an UncertaintyLevel, and then to a VerificationLevel.
    """

    def map_to_verification(self, level: UncertaintyLevel) -> VerificationLevel:
        """Map an uncertainty level to its corresponding verification level.

        Args:
            level: The uncertainty level to map.

        Returns:
            The corresponding VerificationLevel.
        """
        return _UNCERTAINTY_TO_VERIFICATION[level]

    def classify(self, metadata: ActionMetadata) -> ClassificationResult:
        """Classify an action's uncertainty based on its metadata.

        The classification uses a scoring algorithm that considers:
        - Data completeness (lower completeness = higher uncertainty)
        - Precedent availability (no precedent = higher uncertainty)
        - Reversibility (irreversible = higher uncertainty)
        - Impact scope (wider scope = higher uncertainty)

        Args:
            metadata: The action's metadata.

        Returns:
            A ClassificationResult with the uncertainty level, verification
            level, score, and reasoning.
        """
        score = self._compute_score(metadata)
        level = self._score_to_level(score)
        verification_level = self.map_to_verification(level)
        reason = self._build_reason(metadata, score, level)

        return ClassificationResult(
            level=level,
            verification_level=verification_level,
            score=score,
            reason=reason,
        )

    def _compute_score(self, metadata: ActionMetadata) -> float:
        """Compute an uncertainty score from action metadata.

        Score ranges from 0.0 (fully certain) to 1.0 (fundamentally uncertain).

        Factors and their weights:
        - Data completeness: 40% (inverted -- lower completeness = higher score)
        - Precedent: 20% (no precedent = 0.2 added)
        - Reversibility: 20% (irreversible = 0.2 added)
        - Impact scope: 20% (local=0.0, team=0.1, organization=0.2)
        """
        # Data completeness: invert (0.0 completeness -> 0.4, 1.0 -> 0.0)
        data_factor = (1.0 - metadata.data_completeness) * 0.4

        # Precedent: 0.0 if available, 0.2 if not
        precedent_factor = 0.0 if metadata.precedent_available else 0.2

        # Reversibility: 0.0 if reversible, 0.2 if not
        reversibility_factor = 0.0 if metadata.reversible else 0.2

        # Impact scope
        scope_map = {"local": 0.0, "team": 0.1, "organization": 0.2}
        scope_factor = scope_map.get(metadata.impact_scope, 0.1)

        score = data_factor + precedent_factor + reversibility_factor + scope_factor
        return min(score, 1.0)

    def _score_to_level(self, score: float) -> UncertaintyLevel:
        """Convert an uncertainty score to an UncertaintyLevel.

        Thresholds:
        - 0.00 - 0.10: NONE
        - 0.10 - 0.25: INFORMATIONAL
        - 0.25 - 0.50: INTERPRETIVE
        - 0.50 - 0.75: JUDGMENTAL
        - 0.75 - 1.00: FUNDAMENTAL
        """
        if score <= 0.10:
            return UncertaintyLevel.NONE
        if score <= 0.25:
            return UncertaintyLevel.INFORMATIONAL
        if score <= 0.50:
            return UncertaintyLevel.INTERPRETIVE
        if score <= 0.75:
            return UncertaintyLevel.JUDGMENTAL
        return UncertaintyLevel.FUNDAMENTAL

    def _build_reason(
        self,
        metadata: ActionMetadata,
        score: float,
        level: UncertaintyLevel,
    ) -> str:
        """Build a human-readable explanation for the classification."""
        factors = []

        if metadata.data_completeness < 0.5:
            factors.append(
                f"low data completeness ({metadata.data_completeness:.0%})"
            )
        elif metadata.data_completeness < 0.8:
            factors.append(
                f"moderate data completeness ({metadata.data_completeness:.0%})"
            )

        if not metadata.precedent_available:
            factors.append("no prior precedent available")

        if not metadata.reversible:
            factors.append("action is irreversible")

        if metadata.impact_scope == "organization":
            factors.append("organization-wide impact scope")
        elif metadata.impact_scope == "team":
            factors.append("team-wide impact scope")

        if not factors:
            factors.append("all indicators within normal range")

        return (
            f"Uncertainty level {level.value} (score: {score:.2f}): "
            f"{'; '.join(factors)}"
        )
