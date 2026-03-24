# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""ShadowEnforcer — parallel trust evaluation that observes without enforcing.

Runs governance verification alongside normal agent operations, collecting
metrics that provide empirical evidence for trust posture upgrades. The
ShadowEnforcer NEVER blocks, holds, or modifies actions — it only records
what WOULD have happened under the current governance configuration.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pact_platform.trust._compat import (
    UPGRADE_REQUIREMENTS,
    PostureEvidence,
    TrustPostureLevel,
    VerificationLevel,
)

if TYPE_CHECKING:
    from pact.governance.engine import GovernanceEngine

logger = logging.getLogger(__name__)


class ShadowResult(BaseModel):
    """Result of a shadow evaluation."""

    action: str
    agent_id: str
    would_be_blocked: bool
    would_be_held: bool
    would_be_flagged: bool
    would_be_auto_approved: bool
    verification_level: VerificationLevel
    dimension_results: dict[str, str]  # dimension -> evaluation result string
    timestamp: datetime


class ShadowMetrics(BaseModel):
    """Rolling metrics from shadow enforcement."""

    agent_id: str
    total_evaluations: int = 0
    auto_approved_count: int = 0
    flagged_count: int = 0
    held_count: int = 0
    blocked_count: int = 0

    # Per-dimension breakdowns: dimension -> count of non-ALLOWED evaluations
    dimension_trigger_counts: dict[str, int] = Field(default_factory=dict)

    # Rolling windows
    window_start: datetime
    window_end: datetime

    # Previous pass rate for change_rate computation
    previous_pass_rate: float = 0.0

    @property
    def pass_rate(self) -> float:
        """Percentage of actions that would pass cleanly (auto-approved)."""
        if self.total_evaluations == 0:
            return 0.0
        return self.auto_approved_count / self.total_evaluations

    @property
    def block_rate(self) -> float:
        """Percentage of actions that would be blocked."""
        if self.total_evaluations == 0:
            return 0.0
        return self.blocked_count / self.total_evaluations

    @property
    def change_rate(self) -> float:
        """Absolute delta between current pass_rate and previous_pass_rate."""
        return abs(self.pass_rate - self.previous_pass_rate)


class ShadowReport(BaseModel):
    """Report for posture upgrade decisions."""

    agent_id: str
    evaluation_period_days: int
    total_evaluations: int
    pass_rate: float
    block_rate: float
    hold_rate: float
    flag_rate: float
    dimension_breakdown: dict[str, float]  # dimension -> trigger rate
    upgrade_eligible: bool
    upgrade_blockers: list[str]  # reasons why upgrade is blocked
    recommendation: str  # human-readable recommendation


# Map governance verdict level strings to VerificationLevel enum
_LEVEL_MAP: dict[str, VerificationLevel] = {
    "auto_approved": VerificationLevel.AUTO_APPROVED,
    "flagged": VerificationLevel.FLAGGED,
    "held": VerificationLevel.HELD,
    "blocked": VerificationLevel.BLOCKED,
}


class ShadowEnforcer:
    """Parallel trust evaluation that observes without enforcing.

    Collects metrics to provide empirical evidence for trust posture upgrades.
    Evaluates every action through the GovernanceEngine, recording what WOULD
    happen, but never actually blocking or modifying any action.
    """

    def __init__(
        self,
        governance_engine: GovernanceEngine,
        role_address: str,
        *,
        halted_check: Callable[[], bool] | None = None,
        maxlen: int = 10_000,
    ) -> None:
        self._engine = governance_engine
        self._role_address = role_address
        self._results: list[ShadowResult] = []
        self._metrics: dict[str, ShadowMetrics] = {}  # agent_id -> metrics
        self._maxlen: int = maxlen
        self._lock = threading.Lock()
        self._halted_check = halted_check

    def evaluate(
        self,
        action: str,
        agent_id: str,
        *,
        agent_posture: TrustPostureLevel | None = None,
        **kwargs: Any,
    ) -> ShadowResult:
        """Run shadow evaluation -- does NOT block or modify the action.

        Fail-safe: On ANY internal exception, returns a safe ShadowResult with
        would_be_blocked=False, would_be_auto_approved=True. The ShadowEnforcer
        must NEVER crash the caller.

        Args:
            action: The action string to evaluate.
            agent_id: The agent performing the action.
            agent_posture: Agent's trust posture level for escalation.
            **kwargs: Additional context forwarded to verify_action.

        Returns:
            ShadowResult describing what WOULD have happened.
        """
        try:
            return self._evaluate_inner(action, agent_id, agent_posture=agent_posture, **kwargs)
        except Exception:
            logger.error(
                "Shadow evaluation failed for action=%r agent=%r; "
                "returning safe (auto-approved) result. Shadow must never block.",
                action,
                agent_id,
                exc_info=True,
            )
            return ShadowResult(
                action=action,
                agent_id=agent_id,
                would_be_blocked=False,
                would_be_held=False,
                would_be_flagged=False,
                would_be_auto_approved=True,
                verification_level=VerificationLevel.AUTO_APPROVED,
                dimension_results={},
                timestamp=datetime.now(UTC),
            )

    def _evaluate_inner(
        self,
        action: str,
        agent_id: str,
        *,
        agent_posture: TrustPostureLevel | None = None,
        **kwargs: Any,
    ) -> ShadowResult:
        """Core evaluation logic, separated for fail-safe wrapping."""
        now = datetime.now(UTC)

        # Check halt state — if halted, everything would be blocked
        if self._halted_check is not None and callable(self._halted_check):
            if self._halted_check():
                result = ShadowResult(
                    action=action,
                    agent_id=agent_id,
                    would_be_blocked=True,
                    would_be_held=False,
                    would_be_flagged=False,
                    would_be_auto_approved=False,
                    verification_level=VerificationLevel.BLOCKED,
                    dimension_results={"halt": "blocked"},
                    timestamp=now,
                )
                self._record_result(agent_id, result)
                return result

        # PSEUDO_AGENT posture blocks everything
        if agent_posture == TrustPostureLevel.PSEUDO_AGENT:
            result = ShadowResult(
                action=action,
                agent_id=agent_id,
                would_be_blocked=True,
                would_be_held=False,
                would_be_flagged=False,
                would_be_auto_approved=False,
                verification_level=VerificationLevel.BLOCKED,
                dimension_results={"posture": "pseudo_agent_blocked"},
                timestamp=now,
            )
            self._record_result(agent_id, result)
            return result

        # Use GovernanceEngine for the decision
        context: dict[str, Any] = {"agent_id": agent_id}
        if agent_posture is not None:
            context["agent_posture"] = agent_posture.value
        context.update(kwargs)

        verdict = self._engine.verify_action(
            self._role_address,
            action,
            context=context,
        )

        level = _LEVEL_MAP.get(verdict.level, VerificationLevel.BLOCKED)

        # Extract dimension details from verdict audit_details if available
        dimension_results: dict[str, str] = {}
        if hasattr(verdict, "audit_details") and isinstance(verdict.audit_details, dict):
            dims = verdict.audit_details.get("dimensions", {})
            for dim_name, dim_val in dims.items():
                if isinstance(dim_val, str) and dim_val != "allowed":
                    dimension_results[dim_name] = dim_val

        result = ShadowResult(
            action=action,
            agent_id=agent_id,
            would_be_blocked=level == VerificationLevel.BLOCKED,
            would_be_held=level == VerificationLevel.HELD,
            would_be_flagged=level == VerificationLevel.FLAGGED,
            would_be_auto_approved=level == VerificationLevel.AUTO_APPROVED,
            verification_level=level,
            dimension_results=dimension_results,
            timestamp=now,
        )

        self._record_result(agent_id, result)
        return result

    def _record_result(self, agent_id: str, result: ShadowResult) -> None:
        """Thread-safe recording of a result with bounded memory enforcement."""
        with self._lock:
            self._results.append(result)
            self._update_metrics(agent_id, result)
            self._trim_if_needed()

    def get_metrics(self, agent_id: str) -> ShadowMetrics:
        """Get rolling metrics for an agent.

        Args:
            agent_id: The agent to get metrics for.

        Returns:
            ShadowMetrics for the agent.

        Raises:
            KeyError: If no evaluations have been recorded for this agent.
        """
        if agent_id not in self._metrics:
            raise KeyError(
                f"No shadow metrics found for agent '{agent_id}'. "
                f"No evaluations have been recorded for this agent."
            )
        return self._metrics[agent_id]

    def get_metrics_window(self, agent_id: str, days: int = 30) -> ShadowMetrics:
        """Get metrics for a specific time window.

        Filters results to only include evaluations within the last N days
        and computes fresh metrics from that subset.

        Args:
            agent_id: The agent to get metrics for.
            days: Number of days to look back.

        Returns:
            ShadowMetrics for the specified window.

        Raises:
            KeyError: If no evaluations have been recorded for this agent.
        """
        if agent_id not in self._metrics:
            raise KeyError(
                f"No shadow metrics found for agent '{agent_id}'. "
                f"No evaluations have been recorded for this agent."
            )

        now = datetime.now(UTC)
        window_start = now - timedelta(days=days)

        with self._lock:
            windowed_results = [
                r for r in self._results if r.agent_id == agent_id and r.timestamp >= window_start
            ]

        return self._compute_metrics_from_results(agent_id, windowed_results, window_start, now)

    def generate_report(self, agent_id: str) -> ShadowReport:
        """Generate a posture upgrade recommendation report.

        Args:
            agent_id: The agent to generate the report for.

        Returns:
            ShadowReport with statistics and upgrade recommendation.

        Raises:
            KeyError: If no evaluations have been recorded for this agent.
        """
        metrics = self.get_metrics(agent_id)

        evaluation_period_days = max(
            1,
            (metrics.window_end - metrics.window_start).days,
        )

        total = metrics.total_evaluations
        pass_rate = metrics.pass_rate
        block_rate = metrics.block_rate
        hold_rate = metrics.held_count / total if total > 0 else 0.0
        flag_rate = metrics.flagged_count / total if total > 0 else 0.0

        dimension_breakdown: dict[str, float] = {}
        if total > 0:
            for dim, count in metrics.dimension_trigger_counts.items():
                dimension_breakdown[dim] = count / total

        upgrade_blockers = self._check_upgrade_blockers(metrics)
        upgrade_eligible = len(upgrade_blockers) == 0

        recommendation = self._build_recommendation(
            agent_id, metrics, upgrade_eligible, upgrade_blockers
        )

        return ShadowReport(
            agent_id=agent_id,
            evaluation_period_days=evaluation_period_days,
            total_evaluations=total,
            pass_rate=pass_rate,
            block_rate=block_rate,
            hold_rate=hold_rate,
            flag_rate=flag_rate,
            dimension_breakdown=dimension_breakdown,
            upgrade_eligible=upgrade_eligible,
            upgrade_blockers=upgrade_blockers,
            recommendation=recommendation,
        )

    def to_posture_evidence(self, agent_id: str) -> PostureEvidence:
        """Convert shadow metrics into PostureEvidence for upgrade evaluation.

        Args:
            agent_id: The agent to convert metrics for.

        Returns:
            PostureEvidence populated from shadow metrics.

        Raises:
            KeyError: If no evaluations have been recorded for this agent.
        """
        metrics = self.get_metrics(agent_id)

        days_at_posture = max(
            0,
            (metrics.window_end - metrics.window_start).days,
        )

        return PostureEvidence(
            successful_operations=metrics.auto_approved_count,
            total_operations=metrics.total_evaluations,
            days_at_current_posture=days_at_posture,
            shadow_enforcer_pass_rate=metrics.pass_rate,
            incidents=0,
            shadow_blocked_count=metrics.blocked_count,
        )

    def _update_metrics(self, agent_id: str, result: ShadowResult) -> None:
        """Update rolling metrics for an agent after a new evaluation."""
        is_first = agent_id not in self._metrics
        if is_first:
            self._metrics[agent_id] = ShadowMetrics(
                agent_id=agent_id,
                window_start=result.timestamp,
                window_end=result.timestamp,
            )

        metrics = self._metrics[agent_id]

        if not is_first:
            metrics.previous_pass_rate = metrics.pass_rate

        metrics.total_evaluations += 1

        if result.would_be_auto_approved:
            metrics.auto_approved_count += 1
        elif result.would_be_flagged:
            metrics.flagged_count += 1
        elif result.would_be_held:
            metrics.held_count += 1
        elif result.would_be_blocked:
            metrics.blocked_count += 1

        for dimension in result.dimension_results:
            metrics.dimension_trigger_counts[dimension] = (
                metrics.dimension_trigger_counts.get(dimension, 0) + 1
            )

        if result.timestamp < metrics.window_start:
            metrics.window_start = result.timestamp
        if result.timestamp > metrics.window_end:
            metrics.window_end = result.timestamp

        if is_first:
            metrics.previous_pass_rate = metrics.pass_rate

    def _trim_if_needed(self) -> None:
        """Trim oldest 10% of results when _results exceeds maxlen."""
        if len(self._results) > self._maxlen:
            trim_count = max(1, len(self._results) // 10)
            self._results = self._results[trim_count:]

    def _compute_metrics_from_results(
        self,
        agent_id: str,
        results: list[ShadowResult],
        window_start: datetime,
        window_end: datetime,
    ) -> ShadowMetrics:
        """Compute metrics from a filtered list of results."""
        metrics = ShadowMetrics(
            agent_id=agent_id,
            window_start=window_start,
            window_end=window_end,
        )

        for result in results:
            metrics.total_evaluations += 1

            if result.would_be_auto_approved:
                metrics.auto_approved_count += 1
            elif result.would_be_flagged:
                metrics.flagged_count += 1
            elif result.would_be_held:
                metrics.held_count += 1
            elif result.would_be_blocked:
                metrics.blocked_count += 1

            for dimension in result.dimension_results:
                metrics.dimension_trigger_counts[dimension] = (
                    metrics.dimension_trigger_counts.get(dimension, 0) + 1
                )

        return metrics

    def _check_upgrade_blockers(self, metrics: ShadowMetrics) -> list[str]:
        """Check metrics against the lowest upgrade requirements and return blockers."""
        blockers: list[str] = []

        reqs = UPGRADE_REQUIREMENTS.get(TrustPostureLevel.SHARED_PLANNING)
        if reqs is None:
            blockers.append("No upgrade requirements defined for SHARED_PLANNING")
            return blockers

        required_pass_rate = reqs.get("shadow_pass_rate", 0.90)
        if metrics.pass_rate < required_pass_rate:
            blockers.append(
                f"Shadow pass rate {metrics.pass_rate:.0%} is below required "
                f"{required_pass_rate:.0%}"
            )

        min_operations = reqs.get("min_operations", 100)
        if metrics.total_evaluations < min_operations:
            blockers.append(
                f"Total evaluations {metrics.total_evaluations} is below required {min_operations}"
            )

        if metrics.blocked_count > 0:
            blockers.append(
                f"{metrics.blocked_count} blocked action(s) recorded during shadow evaluation"
            )

        return blockers

    def _build_recommendation(
        self,
        agent_id: str,
        metrics: ShadowMetrics,
        upgrade_eligible: bool,
        blockers: list[str],
    ) -> str:
        """Build a human-readable recommendation string."""
        if upgrade_eligible:
            return (
                f"Agent '{agent_id}' shows strong shadow enforcement results "
                f"({metrics.pass_rate:.0%} pass rate across {metrics.total_evaluations} "
                f"evaluations). Eligible for posture upgrade consideration."
            )

        blocker_text = "; ".join(blockers)
        return (
            f"Agent '{agent_id}' is not yet eligible for posture upgrade. Blockers: {blocker_text}"
        )
