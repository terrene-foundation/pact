# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""COC hook enforcer — bridges COC hook validation with PACT governance.

The hook enforcer wraps the GovernanceEngine to produce hook verdicts
(ALLOW/BLOCK/HOLD) from governance verdict levels
(auto_approved/flagged/held/blocked).

Fail-safe principle: if the governance engine is unavailable (no engine
or no role_address configured), the enforcer defaults to BLOCK. This
ensures that misconfiguration never silently permits actions.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pact_platform.build.config.schema import TrustPostureLevel

if TYPE_CHECKING:
    from pact.governance.engine import GovernanceEngine

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
    verification_level: str = ""  # which governance level triggered
    agent_id: str = ""
    action: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Mapping from governance verdict levels (strings) to hook verdicts
_LEVEL_TO_VERDICT: dict[str, HookVerdict] = {
    "auto_approved": HookVerdict.ALLOW,
    "flagged": HookVerdict.ALLOW,  # allowed but logged
    "held": HookVerdict.HOLD,
    "blocked": HookVerdict.BLOCK,
}


class HookEnforcer:
    """Wraps hook validation with PACT governance verification.

    Maps governance verdict levels to hook verdicts:
    - auto_approved -> ALLOW
    - flagged -> ALLOW (but logged for review)
    - held -> HOLD (queued for human approval)
    - blocked -> BLOCK (rejected outright)

    Fail-safe: if the governance engine or role_address is not configured,
    all actions are BLOCKED. This is a deliberate safety measure --
    misconfiguration must never silently permit actions.
    """

    def __init__(
        self,
        governance_engine: GovernanceEngine | None = None,
        role_address: str | None = None,
        *,
        halted_check: Callable[[], bool] | None = None,
        maxlen: int = 10_000,
    ) -> None:
        self._engine = governance_engine
        self._role_address = role_address
        self._results: list[HookResult] = []
        self._maxlen = maxlen
        self._lock = threading.Lock()
        self._halted_check = halted_check

    def enforce(
        self,
        agent_id: str,
        action: str,
        resource: str = "",
        *,
        agent_posture: TrustPostureLevel | None = None,
        **kwargs: Any,
    ) -> HookResult:
        """Enforce hook through PACT governance verification.

        Args:
            agent_id: The agent attempting the action.
            action: The action being attempted.
            resource: Optional resource identifier for context.
            agent_posture: Agent's trust posture level for escalation.
            **kwargs: Additional context forwarded to verify_action.

        Returns:
            HookResult with the enforcement verdict.
        """
        # Emergency halt check
        if self._halted_check is not None and callable(self._halted_check):
            if self._halted_check():
                result = HookResult(
                    verdict=HookVerdict.BLOCK,
                    reason="Fail-safe BLOCK: emergency halt is active",
                    verification_level="blocked",
                    agent_id=agent_id,
                    action=action,
                )
                self._record_result(result)
                return result

        # PSEUDO_AGENT posture blocks everything
        if agent_posture == TrustPostureLevel.PSEUDO_AGENT:
            result = HookResult(
                verdict=HookVerdict.BLOCK,
                reason="Agent at PSEUDO_AGENT posture has no action authority",
                verification_level="blocked",
                agent_id=agent_id,
                action=action,
            )
            self._record_result(result)
            return result

        # Fail-safe: if governance system is not configured, BLOCK
        if self._engine is None or self._role_address is None:
            missing = []
            if self._engine is None:
                missing.append("governance_engine")
            if self._role_address is None:
                missing.append("role_address")
            reason = f"Fail-safe BLOCK: governance not configured (missing: {', '.join(missing)})"
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
            self._record_result(result)
            return result

        # Use GovernanceEngine for the decision — fail-closed on any error
        try:
            context: dict[str, Any] = {"agent_id": agent_id}
            if resource:
                context["resource"] = resource
            if agent_posture is not None:
                context["agent_posture"] = agent_posture.value
            context.update(kwargs)

            verdict = self._engine.verify_action(
                self._role_address,
                action,
                context=context,
            )

            # Map governance verdict level to hook verdict
            hook_verdict = _LEVEL_TO_VERDICT.get(verdict.level, HookVerdict.BLOCK)

            if verdict.level == "flagged":
                logger.info(
                    "Hook enforcer FLAGGED (allowed but logged): agent_id=%s, action=%s, reason=%s",
                    agent_id,
                    action,
                    verdict.reason,
                )

            result = HookResult(
                verdict=hook_verdict,
                reason=verdict.reason,
                verification_level=verdict.level,
                agent_id=agent_id,
                action=action,
            )
        except Exception:
            logger.exception(
                "Governance engine error for agent_id=%s action=%s — fail-closed BLOCK",
                agent_id,
                action,
            )
            result = HookResult(
                verdict=HookVerdict.BLOCK,
                reason="Fail-safe BLOCK: governance engine error",
                verification_level="blocked",
                agent_id=agent_id,
                action=action,
            )

        self._record_result(result)
        return result

    def _record_result(self, result: HookResult) -> None:
        """Thread-safe recording of a result with bounded memory."""
        with self._lock:
            self._results.append(result)
            if len(self._results) > self._maxlen:
                trim_count = max(1, len(self._results) // 10)
                self._results = self._results[trim_count:]

    @property
    def enforcement_log(self) -> list[HookResult]:
        """Get all enforcement results (thread-safe snapshot)."""
        with self._lock:
            return list(self._results)

    def get_stats(self) -> dict[str, int]:
        """Get enforcement statistics.

        Returns:
            Dictionary with counts: total, allow, hold, block.
        """
        with self._lock:
            results = list(self._results)
        stats = {
            "total": len(results),
            "allow": 0,
            "hold": 0,
            "block": 0,
        }
        for result in results:
            if result.verdict == HookVerdict.ALLOW:
                stats["allow"] += 1
            elif result.verdict == HookVerdict.HOLD:
                stats["hold"] += 1
            elif result.verdict == HookVerdict.BLOCK:
                stats["block"] += 1
        return stats
