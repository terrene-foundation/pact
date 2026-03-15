# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Verification gradient engine — classifies agent actions into verification levels.

The gradient determines how each action is handled:
- AUTO_APPROVED: execute and log
- FLAGGED: execute but highlight for review
- HELD: queue for human approval
- BLOCKED: reject outright
"""

from __future__ import annotations

import fnmatch
import logging
import time
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from care_platform.config.schema import (
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.envelope import EnvelopeEvaluation, EvaluationResult
from care_platform.constraint.verification_level import VerificationThoroughness

logger = logging.getLogger(__name__)


class VerificationResult(BaseModel):
    """Result of classifying an action through the verification gradient."""

    action: str
    agent_id: str
    level: VerificationLevel
    thoroughness: VerificationThoroughness
    matched_rule: str | None = None
    reason: str = ""
    envelope_evaluation: EnvelopeEvaluation | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = 0.0

    # Optional proximity and recommendation fields (backward compatible).
    # These are populated when a ProximityScanner is configured on the
    # GradientEngine. Existing callers that construct VerificationResult
    # without these fields are unaffected.
    proximity_alerts: list[dict[str, Any]] | None = None
    recommendations: list[str] | None = None

    @property
    def requires_human_approval(self) -> bool:
        return self.level == VerificationLevel.HELD

    @property
    def is_blocked(self) -> bool:
        return self.level == VerificationLevel.BLOCKED

    @property
    def is_auto_approved(self) -> bool:
        return self.level == VerificationLevel.AUTO_APPROVED

    @property
    def has_proximity_alerts(self) -> bool:
        """Whether any proximity alerts were generated."""
        return bool(self.proximity_alerts)


class GradientEngine:
    """Classifies agent actions into verification levels.

    Uses a combination of pattern-matching rules and envelope evaluation
    to determine the appropriate verification level for each action.

    Optionally integrates EATP's ``ProximityScanner`` to detect when
    constraint utilization is approaching limits and escalate accordingly.
    """

    def __init__(
        self,
        config: VerificationGradientConfig,
        *,
        near_boundary_threshold: float = 0.8,
        proximity_scanner: Any | None = None,
    ) -> None:
        """Initialize the gradient engine.

        Args:
            config: Gradient rules and default level.
            near_boundary_threshold: Utilization ratio for near-boundary detection.
            proximity_scanner: Optional EATP ProximityScanner for constraint
                utilization scanning. If provided, envelope dimension evaluations
                are fed through the scanner for proximity alert generation.
        """
        self._config = config
        self._near_boundary_threshold = near_boundary_threshold
        self._proximity_scanner = proximity_scanner

    def classify(
        self,
        action: str,
        agent_id: str,
        *,
        thoroughness: VerificationThoroughness = VerificationThoroughness.STANDARD,
        envelope_evaluation: EnvelopeEvaluation | None = None,
    ) -> VerificationResult:
        """Classify an action into a verification level.

        The thoroughness parameter adjusts the determined level (RT4-L3):
        - FULL: stricter — AUTO_APPROVED is bumped to FLAGGED.
        - QUICK: more permissive — FLAGGED is relaxed to AUTO_APPROVED.
        - STANDARD: no adjustment.

        BLOCKED and HELD levels are never adjusted by thoroughness to
        preserve hard safety boundaries.

        When a ProximityScanner is configured, the classification is further
        adjusted by proximity alerts (monotonic escalation only — proximity
        never downgrades a level).

        Args:
            action: The action to classify.
            agent_id: The agent attempting the action.
            thoroughness: How thoroughly to verify.
            envelope_evaluation: Optional pre-computed envelope evaluation.

        Returns:
            VerificationResult with the determined level, optional proximity
            alerts, and optional recommendations.
        """
        start = time.monotonic()

        # Step 1: Check envelope evaluation (if provided)
        if envelope_evaluation is not None:
            if envelope_evaluation.overall_result == EvaluationResult.DENIED:
                result = VerificationResult(
                    action=action,
                    agent_id=agent_id,
                    level=VerificationLevel.BLOCKED,
                    thoroughness=thoroughness,
                    reason="Blocked by constraint envelope",
                    envelope_evaluation=envelope_evaluation,
                    duration_ms=_elapsed_ms(start),
                )
                result.recommendations = _build_recommendations(result)
                return result
            if envelope_evaluation.overall_result == EvaluationResult.NEAR_BOUNDARY:
                level = _apply_thoroughness(VerificationLevel.FLAGGED, thoroughness)
                result = VerificationResult(
                    action=action,
                    agent_id=agent_id,
                    level=level,
                    thoroughness=thoroughness,
                    reason="Near constraint boundary",
                    envelope_evaluation=envelope_evaluation,
                    duration_ms=_elapsed_ms(start),
                )
                result = self._apply_proximity(result)
                result.recommendations = _build_recommendations(result)
                return result

        # Step 2: Match against gradient rules (first match wins)
        for rule in self._config.rules:
            if fnmatch.fnmatch(action, rule.pattern):
                level = _apply_thoroughness(rule.level, thoroughness)
                result = VerificationResult(
                    action=action,
                    agent_id=agent_id,
                    level=level,
                    thoroughness=thoroughness,
                    matched_rule=rule.pattern,
                    reason=rule.reason,
                    envelope_evaluation=envelope_evaluation,
                    duration_ms=_elapsed_ms(start),
                )
                result = self._apply_proximity(result)
                result.recommendations = _build_recommendations(result)
                return result

        # Step 3: Use default level
        level = _apply_thoroughness(self._config.default_level, thoroughness)
        result = VerificationResult(
            action=action,
            agent_id=agent_id,
            level=level,
            thoroughness=thoroughness,
            reason="No matching rule; using default level",
            envelope_evaluation=envelope_evaluation,
            duration_ms=_elapsed_ms(start),
        )
        result = self._apply_proximity(result)
        result.recommendations = _build_recommendations(result)
        return result

    def _apply_proximity(self, result: VerificationResult) -> VerificationResult:
        """Apply ProximityScanner to the classification result.

        Feeds envelope dimension evaluations into the scanner to detect
        constraint utilization near thresholds. Proximity alerts can only
        escalate the level (monotonic — never downgrade).

        Returns the result with proximity_alerts populated and level
        potentially escalated.
        """
        if self._proximity_scanner is None:
            return result
        if result.envelope_evaluation is None:
            return result
        if not result.envelope_evaluation.dimensions:
            return result

        try:
            from eatp.constraints.dimension import ConstraintCheckResult
            from eatp.enforce.strict import Verdict

            # Convert CARE DimensionEvaluations to EATP ConstraintCheckResults
            check_results = []
            for dim_eval in result.envelope_evaluation.dimensions:
                if dim_eval.utilization > 0:
                    check_results.append(
                        ConstraintCheckResult(
                            satisfied=dim_eval.result != EvaluationResult.DENIED,
                            reason=dim_eval.reason,
                            used=dim_eval.utilization,
                            limit=1.0,  # utilization is already a ratio
                        )
                    )

            if not check_results:
                return result

            # Scan for proximity alerts
            alerts = self._proximity_scanner.scan(check_results)

            if alerts:
                # Attach alerts to result (serialized as dicts for Pydantic)
                result.proximity_alerts = [a.to_dict() for a in alerts]

                # Map CARE level to Verdict for escalation (inline to avoid
                # circular import with enforcement.py)
                _CARE_TO_VERDICT = {
                    VerificationLevel.AUTO_APPROVED: Verdict.AUTO_APPROVED,
                    VerificationLevel.FLAGGED: Verdict.FLAGGED,
                    VerificationLevel.HELD: Verdict.HELD,
                    VerificationLevel.BLOCKED: Verdict.BLOCKED,
                }
                _VERDICT_TO_CARE = {v: k for k, v in _CARE_TO_VERDICT.items()}

                base_verdict = _CARE_TO_VERDICT.get(result.level, Verdict.AUTO_APPROVED)

                # Escalate verdict based on proximity (monotonic)
                escalated = self._proximity_scanner.escalate_verdict(base_verdict, alerts)

                if escalated != base_verdict:
                    escalated_level = _VERDICT_TO_CARE.get(escalated, result.level)
                    result = result.model_copy(
                        update={
                            "level": escalated_level,
                            "reason": f"{result.reason}; escalated by proximity alert",
                            "proximity_alerts": result.proximity_alerts,
                        }
                    )

        except Exception:
            # Proximity scanning is advisory — never block classification
            logger.warning(
                "ProximityScanner error for action=%s agent=%s. " "Proximity scanning skipped.",
                result.action,
                result.agent_id,
            )

        return result


def _build_recommendations(result: VerificationResult) -> list[str]:
    """Generate actionable recommendations based on the classification.

    Produces human-readable suggestions that explain what the verification
    level means and what actions are available. When proximity alerts are
    present, includes specific dimension names and utilization percentages.

    Args:
        result: The classification result to generate recommendations for.

    Returns:
        List of recommendation strings (may be empty for AUTO_APPROVED
        with no proximity alerts).
    """
    recommendations: list[str] = []
    level = result.level

    # Add proximity-specific recommendations
    if result.proximity_alerts:
        for alert in result.proximity_alerts:
            dimension = alert.get("dimension", "unknown")
            usage_pct = alert.get("usage_ratio", 0.0) * 100
            recommendations.append(
                f"{dimension} usage at {usage_pct:.0f}%. "
                f"Consider reviewing resource consumption."
            )

    # Add level-specific recommendations
    if level == VerificationLevel.BLOCKED:
        dimensions = _blocked_dimensions(result)
        if dimensions:
            recommendations.append(
                f"Action violates hard constraint on {', '.join(dimensions)}. " f"Cannot proceed."
            )
        else:
            recommendations.append("Action violates a hard constraint. Cannot proceed.")
    elif level == VerificationLevel.HELD:
        dimensions = _near_limit_dimensions(result)
        if dimensions:
            recommendations.append(
                f"Action exceeds soft limit on {', '.join(dimensions)}. "
                f"Requires human approval."
            )
        else:
            recommendations.append("Action requires human approval before proceeding.")
    elif level == VerificationLevel.FLAGGED:
        recommendations.append("Action near operational boundary. Review before proceeding.")

    return recommendations


def _blocked_dimensions(result: VerificationResult) -> list[str]:
    """Extract dimension names that caused a BLOCKED result."""
    if result.envelope_evaluation is None:
        return []
    return [
        d.dimension
        for d in result.envelope_evaluation.dimensions
        if d.result == EvaluationResult.DENIED
    ]


def _near_limit_dimensions(result: VerificationResult) -> list[str]:
    """Extract dimension names that are near their limits."""
    if result.envelope_evaluation is None:
        return []
    return [
        d.dimension
        for d in result.envelope_evaluation.dimensions
        if d.result == EvaluationResult.NEAR_BOUNDARY
    ]


def _apply_thoroughness(
    level: VerificationLevel,
    thoroughness: VerificationThoroughness,
) -> VerificationLevel:
    """Adjust a verification level based on thoroughness (RT4-L3).

    - FULL thoroughness is stricter: AUTO_APPROVED -> FLAGGED.
    - QUICK thoroughness is more permissive: FLAGGED -> AUTO_APPROVED.
    - STANDARD thoroughness makes no change.
    - HELD and BLOCKED are never adjusted (hard safety boundaries).

    RT13-L2 accepted trade-off: QUICK thoroughness relaxes FLAGGED to
    AUTO_APPROVED.  This is only selected for cache hits on non-cross-team,
    non-first actions (see ``select_verification_level``), so the risk is
    limited to routine actions that are near but not exceeding a boundary.
    The trade-off is deliberate: high-frequency routine actions would
    otherwise overwhelm operators with FLAGGED notifications.

    Args:
        level: The base verification level determined by rules/envelope.
        thoroughness: The verification thoroughness to apply.

    Returns:
        The adjusted verification level.
    """
    if thoroughness == VerificationThoroughness.FULL:
        if level == VerificationLevel.AUTO_APPROVED:
            return VerificationLevel.FLAGGED
    elif thoroughness == VerificationThoroughness.QUICK:
        if level == VerificationLevel.FLAGGED:
            return VerificationLevel.AUTO_APPROVED
    return level


def _elapsed_ms(start: float) -> float:
    return (time.monotonic() - start) * 1000
