# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""CARE enforcement pipeline — composes GradientEngine + EATP StrictEnforcer.

The pipeline processes actions through two sequential stages:

1. **GradientEngine.classify()** (pre-verification): Classifies action strings
   into verification levels (AUTO_APPROVED, FLAGGED, HELD, BLOCKED) based on
   pattern matching, envelope evaluation, and thoroughness configuration.

2. **StrictEnforcer.enforce()** (post-verification): Decides what to do with
   the classification result — raise on BLOCKED, queue on HELD, warn on FLAGGED.
   Produces a ``Verdict`` with enforcement actions.

The pipeline also handles the ``VerificationResult`` adapter between CARE's
Pydantic model and EATP's dataclass, since they have different field sets.

Existing callers of ``GradientEngine.classify()`` are unaffected — the pipeline
is an opt-in composition that adds enforcement on top of classification.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from eatp.chain import VerificationLevel as EATPVerificationLevel
from eatp.chain import VerificationResult as EATPVerificationResult
from eatp.enforce.strict import HeldBehavior, StrictEnforcer, Verdict

from care_platform.config.schema import VerificationLevel as CareVerificationLevel
from care_platform.constraint.envelope import EnvelopeEvaluation
from care_platform.constraint.gradient import (
    GradientEngine,
    VerificationResult as CareVerificationResult,
)
from care_platform.constraint.verification_level import VerificationThoroughness

if TYPE_CHECKING:
    from care_platform.execution.approval import ApprovalQueue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Verification Result Adapter
# ---------------------------------------------------------------------------

# Field mapping: CARE VerificationResult → EATP VerificationResult
#
# | CARE Field           | EATP Field             | Mapping                          |
# |----------------------|------------------------|----------------------------------|
# | level (enum)         | valid (bool)           | BLOCKED → False, others → True   |
# | level (enum)         | level (enum)           | See _CARE_TO_EATP_LEVEL          |
# | reason (str)         | reason (str)           | Direct copy                      |
# | action (str)         | —                      | Not in EATP (preserved in ctx)   |
# | agent_id (str)       | —                      | Not in EATP (preserved in ctx)   |
# | thoroughness         | —                      | Not in EATP (preserved in ctx)   |
# | matched_rule         | —                      | Not in EATP (preserved in ctx)   |
# | envelope_evaluation  | —                      | Not in EATP (preserved in ctx)   |
# | timestamp            | —                      | Not in EATP (preserved in ctx)   |
# | duration_ms          | —                      | Not in EATP (preserved in ctx)   |
# | —                    | capability_used        | Not in CARE (left as None)       |
# | —                    | effective_constraints  | Not in CARE (left as [])         |
# | —                    | violations             | Not in CARE (left as [])         |

_CARE_TO_EATP_LEVEL: dict[CareVerificationLevel, EATPVerificationLevel] = {
    CareVerificationLevel.AUTO_APPROVED: EATPVerificationLevel.QUICK,
    CareVerificationLevel.FLAGGED: EATPVerificationLevel.STANDARD,
    CareVerificationLevel.HELD: EATPVerificationLevel.STANDARD,
    CareVerificationLevel.BLOCKED: EATPVerificationLevel.FULL,
}

_VERDICT_TO_CARE_LEVEL: dict[Verdict, CareVerificationLevel] = {
    Verdict.AUTO_APPROVED: CareVerificationLevel.AUTO_APPROVED,
    Verdict.FLAGGED: CareVerificationLevel.FLAGGED,
    Verdict.HELD: CareVerificationLevel.HELD,
    Verdict.BLOCKED: CareVerificationLevel.BLOCKED,
}


# The pipeline uses flag_threshold=2 so the violation-count mapping is clean:
#   0 violations → AUTO_APPROVED
#   1 violation  → FLAGGED
#   2 violations → HELD
#   valid=False  → BLOCKED
_CARE_LEVEL_VIOLATION_COUNT: dict[CareVerificationLevel, int] = {
    CareVerificationLevel.AUTO_APPROVED: 0,
    CareVerificationLevel.FLAGGED: 1,
    CareVerificationLevel.HELD: 2,
    CareVerificationLevel.BLOCKED: 1,  # Doesn't matter — valid=False triggers BLOCKED
}

# The pipeline's StrictEnforcer must use this threshold for the mapping to work.
CARE_FLAG_THRESHOLD = 2


def care_result_to_eatp_result(
    care_result: CareVerificationResult,
) -> EATPVerificationResult:
    """Convert a CARE VerificationResult to an EATP VerificationResult.

    This adapter bridges the two type systems. The StrictEnforcer classifies
    using ``valid`` and ``len(violations)`` with ``flag_threshold=2``:

    +-----------------+-------+------------+---------+
    | CARE Level      | valid | violations | Verdict |
    +-----------------+-------+------------+---------+
    | AUTO_APPROVED   | True  | 0          | AUTO    |
    | FLAGGED         | True  | 1          | FLAGGED |
    | HELD            | True  | 2          | HELD    |
    | BLOCKED         | False | (any)      | BLOCKED |
    +-----------------+-------+------------+---------+

    This requires ``flag_threshold=2`` on the StrictEnforcer (see
    ``CARE_FLAG_THRESHOLD``). The ``CareEnforcementPipeline`` sets this
    automatically.

    CARE fields without EATP counterparts are NOT lost — they remain
    on the original CARE result, which the pipeline preserves alongside
    the EATP conversion.
    """
    level = care_result.level
    reason = care_result.reason or None
    is_blocked = level == CareVerificationLevel.BLOCKED
    violation_count = _CARE_LEVEL_VIOLATION_COUNT[level]

    violations = [
        {"dimension": "gradient", "detail": reason or level.value} for _ in range(violation_count)
    ]

    return EATPVerificationResult(
        valid=not is_blocked,
        level=_CARE_TO_EATP_LEVEL[level],
        reason=reason,
        violations=violations,
    )


def verdict_to_care_level(verdict: Verdict) -> CareVerificationLevel:
    """Convert an EATP Verdict back to a CARE VerificationLevel.

    This ensures the pipeline's output uses CARE's type system,
    maintaining a consistent API for all CARE components.
    """
    return _VERDICT_TO_CARE_LEVEL[verdict]


# ---------------------------------------------------------------------------
# Pipeline Result
# ---------------------------------------------------------------------------


@dataclass
class EnforcementResult:
    """Result of the full enforcement pipeline.

    Contains both the CARE classification and the EATP enforcement verdict,
    providing the complete picture for callers that need either level of detail.
    """

    classification: CareVerificationResult
    """The original CARE GradientEngine classification."""

    verdict: Verdict
    """The EATP StrictEnforcer verdict after enforcement."""

    enforced_level: CareVerificationLevel
    """The verdict mapped back to CARE's verification level system."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional context from the enforcement pass."""

    @property
    def requires_human_approval(self) -> bool:
        """Whether this action needs human approval."""
        return self.verdict == Verdict.HELD

    @property
    def is_blocked(self) -> bool:
        """Whether this action was blocked."""
        return self.verdict == Verdict.BLOCKED

    @property
    def is_auto_approved(self) -> bool:
        """Whether this action was auto-approved."""
        return self.verdict == Verdict.AUTO_APPROVED


# ---------------------------------------------------------------------------
# Enforcement Pipeline
# ---------------------------------------------------------------------------


class CareEnforcementPipeline:
    """Composes GradientEngine classification + EATP StrictEnforcer enforcement.

    This pipeline adds enforcement actions on top of the GradientEngine's
    classification. The GradientEngine determines the verification level;
    the StrictEnforcer decides what to do about it (raise, queue, warn).

    Usage::

        pipeline = CareEnforcementPipeline(
            gradient=gradient_engine,
            on_held=HeldBehavior.CALLBACK,
            held_callback=my_approval_handler,
        )

        result = pipeline.enforce(
            action="draft_content",
            agent_id="agent-001",
        )

        if result.is_blocked:
            # Action was rejected
            ...
        elif result.requires_human_approval:
            # Action queued for human review
            ...

    Existing callers of ``GradientEngine.classify()`` are NOT affected.
    The pipeline is an additive opt-in layer.
    """

    def __init__(
        self,
        gradient: GradientEngine,
        *,
        on_held: HeldBehavior = HeldBehavior.RAISE,
        held_callback: Callable[[str, str, EATPVerificationResult], bool] | None = None,
        maxlen: int = 10_000,
    ) -> None:
        """Initialize the enforcement pipeline.

        Args:
            gradient: The GradientEngine for action classification.
            on_held: Behavior when an action is HELD.
            held_callback: Callback for HELD actions (when on_held=CALLBACK).
            maxlen: Maximum enforcement records to retain.
        """
        self._gradient = gradient
        self._enforcer = StrictEnforcer(
            on_held=on_held,
            held_callback=held_callback,
            flag_threshold=CARE_FLAG_THRESHOLD,
            maxlen=maxlen,
        )

    @property
    def enforcer(self) -> StrictEnforcer:
        """Access the underlying StrictEnforcer for record inspection."""
        return self._enforcer

    @property
    def gradient(self) -> GradientEngine:
        """Access the underlying GradientEngine."""
        return self._gradient

    def classify_and_enforce(
        self,
        action: str,
        agent_id: str,
        *,
        thoroughness: VerificationThoroughness = VerificationThoroughness.STANDARD,
        envelope_evaluation: EnvelopeEvaluation | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EnforcementResult:
        """Run the full pipeline: classify → adapt → enforce.

        Args:
            action: The action string to evaluate.
            agent_id: The agent performing the action.
            thoroughness: Classification thoroughness level.
            envelope_evaluation: Optional envelope evaluation for context.
            metadata: Optional metadata for the enforcement record.

        Returns:
            EnforcementResult with classification, verdict, and enforced level.

        Raises:
            EATPBlockedError: If the action is BLOCKED.
            EATPHeldError: If the action is HELD and on_held=RAISE.
        """
        # Stage 1: Classify (CARE GradientEngine)
        care_result = self._gradient.classify(
            action=action,
            agent_id=agent_id,
            thoroughness=thoroughness,
            envelope_evaluation=envelope_evaluation,
        )

        # Stage 2: Adapt (CARE → EATP type system)
        eatp_result = care_result_to_eatp_result(care_result)

        # Stage 3: Enforce (EATP StrictEnforcer)
        verdict = self._enforcer.enforce(
            agent_id=agent_id,
            action=action,
            result=eatp_result,
            metadata=metadata,
        )

        # Stage 4: Map verdict back to CARE level
        enforced_level = verdict_to_care_level(verdict)

        return EnforcementResult(
            classification=care_result,
            verdict=verdict,
            enforced_level=enforced_level,
            metadata=metadata or {},
        )

    def classify_only(
        self,
        action: str,
        agent_id: str,
        *,
        thoroughness: VerificationThoroughness = VerificationThoroughness.STANDARD,
        envelope_evaluation: EnvelopeEvaluation | None = None,
    ) -> CareVerificationResult:
        """Run classification only (no enforcement). Delegates to GradientEngine.

        Provided for convenience so callers can use the pipeline for both
        classification-only and full enforcement workflows.
        """
        return self._gradient.classify(
            action=action,
            agent_id=agent_id,
            thoroughness=thoroughness,
            envelope_evaluation=envelope_evaluation,
        )


def create_approval_held_callback(
    approval_queue: ApprovalQueue,
) -> Callable[[str, str, EATPVerificationResult], bool]:
    """Create a held_callback that wires to CARE's ApprovalQueue.

    When the StrictEnforcer encounters a HELD verdict and on_held=CALLBACK,
    it calls this function. The callback submits the action to the CARE
    approval queue for human review.

    Args:
        approval_queue: The CARE Platform approval queue.

    Returns:
        A callback compatible with StrictEnforcer's held_callback signature.
    """

    def callback(
        agent_id: str,
        action: str,
        result: EATPVerificationResult,
    ) -> bool:
        """Submit held action to CARE approval queue."""
        try:
            approval_queue.submit(
                agent_id=agent_id,
                action=action,
                reason=result.reason or "Action held by enforcement pipeline",
            )
            return True  # Queued successfully
        except Exception:
            logger.warning(
                "Failed to submit held action to approval queue: " "agent=%s action=%s",
                agent_id,
                action,
            )
            return False  # Queue submission failed

    return callback
