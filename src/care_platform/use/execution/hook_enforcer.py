# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""COC hook enforcer — bridges COC hook validation with EATP verification.

The hook enforcer wraps the verification gradient engine and constraint envelope
to produce hook verdicts (ALLOW/BLOCK/HOLD) from EATP verification levels
(AUTO_APPROVED/FLAGGED/HELD/BLOCKED).

Fail-safe principle: if the verification system is unavailable (no gradient engine
or no envelope configured), the enforcer defaults to BLOCK. This ensures that
misconfiguration never silently permits actions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from care_platform.build.config.schema import TrustPostureLevel, VerificationLevel
from care_platform.trust.constraint.envelope import ConstraintEnvelope
from care_platform.trust.constraint.gradient import GradientEngine, VerificationThoroughness
from care_platform.trust.posture import TrustPosture

logger = logging.getLogger(__name__)


class HookVerdict(str, Enum):
    """Hook enforcement verdict — maps to COC hook exit codes."""

    ALLOW = "allow"  # exit code 0
    BLOCK = "block"  # exit code 1
    HOLD = "hold"  # exit code 2


class HookResult(BaseModel):
    """Result of hook enforcement."""

    verdict: HookVerdict
    reason: str = ""
    verification_level: str = ""  # which gradient level triggered
    agent_id: str = ""
    action: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Mapping from EATP verification levels to hook verdicts
_LEVEL_TO_VERDICT: dict[VerificationLevel, HookVerdict] = {
    VerificationLevel.AUTO_APPROVED: HookVerdict.ALLOW,
    VerificationLevel.FLAGGED: HookVerdict.ALLOW,  # allowed but logged
    VerificationLevel.HELD: HookVerdict.HOLD,
    VerificationLevel.BLOCKED: HookVerdict.BLOCK,
}


class HookEnforcer:
    """Wraps hook validation with EATP verification.

    Maps verification gradient levels to hook verdicts:
    - AUTO_APPROVED -> ALLOW
    - FLAGGED -> ALLOW (but logged for review)
    - HELD -> HOLD (queued for human approval)
    - BLOCKED -> BLOCK (rejected outright)

    Fail-safe: if the gradient engine or envelope is not configured,
    all actions are BLOCKED. This is a deliberate safety measure --
    misconfiguration must never silently permit actions.
    """

    def __init__(
        self,
        gradient_engine: GradientEngine | None = None,
        envelope: ConstraintEnvelope | None = None,
        *,
        halted_check: Callable[[], bool] | None = None,
    ) -> None:
        self._gradient = gradient_engine
        self._envelope = envelope
        self._results: list[HookResult] = []
        # RT2-08: Optional callable that returns bool for halt state
        self._halted_check = halted_check
        # RT2-08: Posture helper for never-delegated checks
        self._posture_helper = TrustPosture(agent_id="__hook_helper__")

    def enforce(
        self,
        agent_id: str,
        action: str,
        resource: str = "",
        *,
        agent_posture: TrustPostureLevel | None = None,
        **kwargs: Any,
    ) -> HookResult:
        """Enforce hook through EATP verification.

        RT2-08: Now mirrors the full middleware pipeline including halt state,
        posture-based escalation, and never-delegated action checks.

        Args:
            agent_id: The agent attempting the action.
            action: The action being attempted.
            resource: Optional resource identifier for context.
            agent_posture: RT2-08: Agent's trust posture level for escalation.
            **kwargs: Forwarded to ConstraintEnvelope.evaluate_action
                (e.g. spend_amount, current_action_count, data_paths, is_external).

        Returns:
            HookResult with the enforcement verdict.
        """
        # RT2-08: Emergency halt check
        if self._halted_check is not None and callable(self._halted_check):
            if self._halted_check():
                result = HookResult(
                    verdict=HookVerdict.BLOCK,
                    reason="Fail-safe BLOCK: emergency halt is active",
                    verification_level=VerificationLevel.BLOCKED.value,
                    agent_id=agent_id,
                    action=action,
                )
                self._results.append(result)
                return result

        # RT2-08: PSEUDO_AGENT posture blocks everything
        if agent_posture == TrustPostureLevel.PSEUDO_AGENT:
            result = HookResult(
                verdict=HookVerdict.BLOCK,
                reason="Agent at PSEUDO_AGENT posture has no action authority",
                verification_level=VerificationLevel.BLOCKED.value,
                agent_id=agent_id,
                action=action,
            )
            self._results.append(result)
            return result

        # RT3-01: Check envelope expiry (pipeline parity with middleware RT-08)
        if self._envelope is not None and self._envelope.is_expired:
            result = HookResult(
                verdict=HookVerdict.BLOCK,
                reason="Constraint envelope has expired",
                verification_level=VerificationLevel.BLOCKED.value,
                agent_id=agent_id,
                action=action,
            )
            self._results.append(result)
            return result

        # Fail-safe: if verification system is not configured, BLOCK
        if self._gradient is None or self._envelope is None:
            missing = []
            if self._gradient is None:
                missing.append("gradient_engine")
            if self._envelope is None:
                missing.append("envelope")
            reason = f"Fail-safe BLOCK: verification not configured (missing: {', '.join(missing)})"
            logger.warning(
                "Hook enforcer fail-safe triggered: agent_id=%s, action=%s, missing=%s",
                agent_id,
                action,
                missing,
            )
            result = HookResult(
                verdict=HookVerdict.BLOCK,
                reason=reason,
                verification_level="",
                agent_id=agent_id,
                action=action,
            )
            self._results.append(result)
            return result

        # RT3-10: Forward kwargs to envelope evaluation (spend_amount, etc.)
        envelope_evaluation = self._envelope.evaluate_action(
            action=action,
            agent_id=agent_id,
            **kwargs,
        )

        # Classify through the gradient engine
        verification = self._gradient.classify(
            action=action,
            agent_id=agent_id,
            thoroughness=VerificationThoroughness.STANDARD,
            envelope_evaluation=envelope_evaluation,
        )

        # Apply pipeline overrides before mapping to verdict
        level = verification.level

        # RT2-08: Force HELD for never-delegated actions (mirrors RT-03)
        is_never_delegated = self._posture_helper.is_action_always_held(action)
        if is_never_delegated and level != VerificationLevel.BLOCKED:
            level = VerificationLevel.HELD

        # RT2-08: SUPERVISED posture escalation (mirrors RT-09)
        if agent_posture == TrustPostureLevel.SUPERVISED:
            if level in (VerificationLevel.AUTO_APPROVED, VerificationLevel.FLAGGED):
                level = VerificationLevel.HELD

        # Map verification level to hook verdict
        verdict = _LEVEL_TO_VERDICT[level]
        reason = verification.reason

        if level == VerificationLevel.FLAGGED:
            logger.info(
                "Hook enforcer FLAGGED (allowed but logged): agent_id=%s, action=%s, reason=%s",
                agent_id,
                action,
                reason,
            )

        result = HookResult(
            verdict=verdict,
            reason=reason,
            verification_level=level.value,
            agent_id=agent_id,
            action=action,
        )
        self._results.append(result)
        return result

    @property
    def enforcement_log(self) -> list[HookResult]:
        """Get all enforcement results."""
        return self._results

    def get_stats(self) -> dict[str, int]:
        """Get enforcement statistics.

        Returns:
            Dictionary with counts: total, allow, hold, block.
        """
        stats = {
            "total": len(self._results),
            "allow": 0,
            "hold": 0,
            "block": 0,
        }
        for result in self._results:
            if result.verdict == HookVerdict.ALLOW:
                stats["allow"] += 1
            elif result.verdict == HookVerdict.HOLD:
                stats["hold"] += 1
            elif result.verdict == HookVerdict.BLOCK:
                stats["block"] += 1
        return stats
