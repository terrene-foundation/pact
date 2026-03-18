# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Constraint envelope evaluation — runtime evaluation of agent actions against
the five CARE constraint dimensions.
"""

from __future__ import annotations

import fnmatch
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

from pydantic import BaseModel, ConfigDict, Field

from care_platform.build.config.schema import ConfidentialityLevel, ConstraintEnvelopeConfig

# Numeric ordering for confidentiality comparisons (mirrors trust.reasoning._CONFIDENTIALITY_ORDER).
# Defined here locally to avoid circular import with trust.reasoning.
_CONFIDENTIALITY_ORDER: dict[ConfidentialityLevel, int] = {
    ConfidentialityLevel.PUBLIC: 0,
    ConfidentialityLevel.RESTRICTED: 1,
    ConfidentialityLevel.CONFIDENTIAL: 2,
    ConfidentialityLevel.SECRET: 3,
    ConfidentialityLevel.TOP_SECRET: 4,
}


def select_active_envelope(
    envelope_dicts: list[dict],
) -> dict | None:
    """RT7-06: Select the most recent non-expired envelope from a list.

    Filters out expired envelopes (by checking ``expires_at`` in the envelope
    dict or its nested ``config``), then returns the most recently created one.

    Args:
        envelope_dicts: List of envelope dictionaries, each potentially
            containing ``expires_at`` and ``created_at`` keys (either at
            top-level or inside a ``config`` sub-dict).

    Returns:
        The most recent non-expired envelope dict, or ``None`` if no valid
        envelopes remain.
    """
    valid: list[dict] = []
    for env_data in envelope_dicts:
        expires_at = env_data.get("expires_at") or env_data.get("config", {}).get("expires_at")
        if expires_at:
            try:
                if isinstance(expires_at, str):
                    exp_dt = datetime.fromisoformat(expires_at)
                else:
                    exp_dt = expires_at
                if hasattr(exp_dt, "tzinfo") and exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=UTC)
                if exp_dt < datetime.now(UTC):
                    continue
            except (ValueError, TypeError):
                # Fail-closed: unparseable expires_at is treated as expired.
                # An envelope with corrupt metadata should not be trusted.
                env_id = env_data.get("config", {}).get("id", env_data.get("id", "unknown"))
                logger.warning(
                    "Envelope '%s' has unparseable expires_at: %r — "
                    "treating as expired (fail-closed)",
                    env_id,
                    expires_at,
                )
                continue
        valid.append(env_data)

    if not valid:
        return None

    # RT8-06: Sort by created_at descending, pick most recent.
    # Normalize sort key to always produce a string to avoid TypeError
    # when mixing datetime and str types across envelope dicts.
    def _envelope_sort_key(e: dict) -> str:
        raw = e.get("created_at", e.get("config", {}).get("created_at"))
        if raw is None:
            return ""
        if isinstance(raw, datetime):
            return raw.isoformat()
        return str(raw)

    return sorted(valid, key=_envelope_sort_key, reverse=True)[0]


class EvaluationResult(str, Enum):
    """Result of evaluating an action against a constraint envelope."""

    ALLOWED = "allowed"
    DENIED = "denied"
    NEAR_BOUNDARY = "near_boundary"


class DimensionEvaluation(BaseModel):
    """Result of evaluating one constraint dimension."""

    dimension: str
    result: EvaluationResult
    reason: str = ""
    utilization: float = Field(default=0.0, ge=0.0, le=1.0)


class EnvelopeEvaluation(BaseModel):
    """Complete evaluation result across all five dimensions."""

    envelope_id: str
    action: str
    agent_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    overall_result: EvaluationResult
    dimensions: list[DimensionEvaluation] = Field(default_factory=list)

    @property
    def is_allowed(self) -> bool:
        return self.overall_result == EvaluationResult.ALLOWED

    @property
    def is_near_boundary(self) -> bool:
        return self.overall_result == EvaluationResult.NEAR_BOUNDARY


def _is_time_window_tighter(
    child_start: str, child_end: str, parent_start: str, parent_end: str
) -> bool:
    """RT8-04: Check if child time window is a subset of parent time window.

    Handles overnight windows (where end < start means wrapping midnight).
    Converts HH:MM strings to minutes for correct numeric comparison.
    """

    def _to_min(t: str) -> int:
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    cs, ce, ps, pe = (
        _to_min(child_start),
        _to_min(child_end),
        _to_min(parent_start),
        _to_min(parent_end),
    )

    # Detect overnight windows (end <= start means wrapping midnight)
    parent_overnight = pe <= ps
    child_overnight = ce <= cs

    if not parent_overnight and child_overnight:
        # Child wraps midnight but parent doesn't — child is NOT tighter
        return False

    if not parent_overnight and not child_overnight:
        # Both normal daytime windows: child must be within parent
        return cs >= ps and ce <= pe

    if parent_overnight and child_overnight:
        # Both overnight: child start must be >= parent start, child end must be <= parent end
        return cs >= ps and ce <= pe

    if parent_overnight and not child_overnight:
        # Parent wraps midnight, child doesn't — child is tighter if
        # entirely within one of the two parent segments:
        # Parent covers [ps, 24:00) U [00:00, pe)
        # Child [cs, ce) must be entirely within one of these segments
        return (cs >= ps) or (ce <= pe)

    return False


def _paths_covered_by(child_paths: list[str], parent_paths: list[str]) -> bool:
    """Check that every child path is covered by at least one parent path.

    A child path is covered if:
    - It exactly matches a parent path, OR
    - A parent path is a glob prefix of the child path (e.g., parent "a/*"
      covers child "a/b/*" because everything under "a/b/*" is under "a/*").
    """
    for cp in child_paths:
        if not any(_path_covered(cp, pp) for pp in parent_paths):
            return False
    return True


def _path_covered(child: str, parent: str) -> bool:
    """Check if a single child path is covered by a parent path."""
    if child == parent:
        return True
    # Strip trailing glob for prefix comparison: "a/b/*" -> "a/b/"
    parent_prefix = parent.rstrip("*")
    child_prefix = child.rstrip("*")
    # Child is covered if its prefix starts with the parent prefix
    # e.g., "workspaces/dm/content/" starts with "workspaces/dm/"
    return child_prefix.startswith(parent_prefix)


class ConstraintEnvelope(BaseModel):
    """Runtime constraint envelope with evaluation logic.

    Wraps a ConstraintEnvelopeConfig and adds:
    - Action evaluation against all five dimensions
    - Monotonic tightening validation (child can only narrow parent)
    - Versioning and expiry (90-day default)
    - Content hashing for integrity verification

    Frozen after construction to prevent post-creation constraint widening.
    Code that needs to update an envelope must create a new instance.
    """

    model_config = ConfigDict(frozen=True)

    config: ConstraintEnvelopeConfig
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = Field(default=None)
    parent_envelope_id: str | None = Field(default=None)

    def model_post_init(self, __context: Any) -> None:
        if self.expires_at is None:
            object.__setattr__(self, "expires_at", self.created_at + timedelta(days=90))

    @property
    def id(self) -> str:
        return self.config.id

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def content_hash(self) -> str:
        """SHA-256 hash of envelope content for integrity verification."""
        content = self.config.model_dump_json(exclude={"id"})
        return hashlib.sha256(content.encode()).hexdigest()

    def evaluate_action(
        self,
        action: str,
        agent_id: str,
        *,
        spend_amount: float = 0.0,
        cumulative_spend: float = 0.0,
        current_action_count: int = 0,
        current_time: datetime | None = None,
        data_paths: list[str] | None = None,
        access_type: str = "read",
        is_external: bool = False,
        data_classification: ConfidentialityLevel | None = None,
        reasoning_trace: str | None = None,
    ) -> EnvelopeEvaluation:
        """Evaluate an action against all constraint dimensions.

        Args:
            action: The action being attempted.
            agent_id: The agent attempting the action.
            spend_amount: Per-action spend amount (USD).
            cumulative_spend: Total cumulative API spend so far (USD).
            current_action_count: Number of actions taken today.
            current_time: Time of the action (defaults to now).
            data_paths: List of data paths being accessed.
            access_type: "read" or "write" for data access path checks.
            is_external: Whether this is an external communication.
            data_classification: Confidentiality classification of data being accessed.
                When provided, checked against the envelope's confidentiality_clearance.
            reasoning_trace: Reasoning trace text for actions on dimensions with
                reasoning_required=True. When None and reasoning is required,
                the action is HELD (NEAR_BOUNDARY).

        Returns an EnvelopeEvaluation with per-dimension results and an overall verdict.
        The overall result is the most restrictive dimension result.
        """
        now = current_time or datetime.now(UTC)

        # RT2-09: Check expiry inside evaluate_action so direct callers are protected
        if self.is_expired:
            return EnvelopeEvaluation(
                envelope_id=self.id,
                action=action,
                agent_id=agent_id,
                timestamp=now,
                overall_result=EvaluationResult.DENIED,
                dimensions=[
                    DimensionEvaluation(
                        dimension="expiry",
                        result=EvaluationResult.DENIED,
                        reason="Constraint envelope has expired",
                    )
                ],
            )

        dimensions: list[DimensionEvaluation] = []

        # The five CARE constraint dimensions
        # M23/2301: Skip financial evaluation when financial config is None
        if self.config.financial is not None:
            dimensions.append(self._evaluate_financial(action, spend_amount, cumulative_spend))
        dimensions.append(self._evaluate_operational(action, current_action_count))
        dimensions.append(self._evaluate_temporal(action, now))
        dimensions.append(self._evaluate_data_access(action, data_paths or [], access_type))
        dimensions.append(self._evaluate_communication(action, is_external))

        # M15/1501: Confidentiality clearance — evaluated when data_classification is provided
        # or when the envelope has non-PUBLIC clearance (i.e., it's configured for confidentiality).
        if (
            data_classification is not None
            or self.config.confidentiality_clearance != ConfidentialityLevel.PUBLIC
        ):
            dimensions.append(self._evaluate_confidentiality(data_classification))

        # M15/1503: REASONING_REQUIRED — evaluated when any dimension has the flag set
        # M23/2301: Guard against None financial config
        any_requires_reasoning = any(
            [
                (
                    self.config.financial.reasoning_required
                    if self.config.financial is not None
                    else False
                ),
                self.config.operational.reasoning_required,
                self.config.temporal.reasoning_required,
                self.config.data_access.reasoning_required,
                self.config.communication.reasoning_required,
            ]
        )
        if any_requires_reasoning:
            dimensions.append(self._evaluate_reasoning_required(reasoning_trace))

        # Overall = most restrictive
        if any(d.result == EvaluationResult.DENIED for d in dimensions):
            overall = EvaluationResult.DENIED
        elif any(d.result == EvaluationResult.NEAR_BOUNDARY for d in dimensions):
            overall = EvaluationResult.NEAR_BOUNDARY
        else:
            overall = EvaluationResult.ALLOWED

        return EnvelopeEvaluation(
            envelope_id=self.id,
            action=action,
            agent_id=agent_id,
            timestamp=now,
            overall_result=overall,
            dimensions=dimensions,
        )

    def is_tighter_than(self, parent: ConstraintEnvelope) -> bool:
        """Verify this envelope is a monotonic tightening of the parent.

        A child envelope must not expand any constraint beyond the parent.
        """
        pc = parent.config
        cc = self.config

        # M23/2301: Financial — handle optional financial configs
        # None financial means "no spending capability" — the tightest possible.
        # Child with financial when parent has None is looser (parent allows nothing).
        if pc.financial is None and cc.financial is not None:
            return False  # parent disallows financial, child allows it — looser
        if cc.financial is not None and pc.financial is not None:
            # Both have financial: child max_spend must be <= parent
            if cc.financial.max_spend_usd > pc.financial.max_spend_usd:
                return False
        # If cc.financial is None, child has no spend capability — always tighter

        # M23/2302: max_delegation_depth — child cannot have deeper delegation than parent
        if pc.max_delegation_depth is not None:
            if cc.max_delegation_depth is None:
                return False  # parent restricts depth, child removes it — looser
            if cc.max_delegation_depth > pc.max_delegation_depth:
                return False

        # Operational: child allowed_actions must be subset of parent
        if pc.operational.allowed_actions:
            parent_set = set(pc.operational.allowed_actions)
            child_set = set(cc.operational.allowed_actions)
            if not child_set.issubset(parent_set):
                return False

        # Operational: child must include all parent blocked_actions
        parent_blocked = set(pc.operational.blocked_actions)
        child_blocked = set(cc.operational.blocked_actions)
        if not parent_blocked.issubset(child_blocked):
            return False

        # RT5-18: child must not remove a rate limit the parent imposes
        if (
            pc.operational.max_actions_per_day is not None
            and cc.operational.max_actions_per_day is None
        ):
            return False  # child has no rate limit when parent does — less restrictive

        # Operational: child max_actions_per_day must be <= parent (if both are set)
        if (
            pc.operational.max_actions_per_day is not None
            and cc.operational.max_actions_per_day is not None
            and cc.operational.max_actions_per_day > pc.operational.max_actions_per_day
        ):
            return False

        # RT7-09/RT8-04: Temporal — child active hours must be within parent active hours.
        # Use minute-based comparison to handle overnight windows correctly.
        if pc.temporal.active_hours_start is not None and pc.temporal.active_hours_end is not None:
            if cc.temporal.active_hours_start is None or cc.temporal.active_hours_end is None:
                # Parent restricts active hours but child removes the restriction — looser
                return False
            if not _is_time_window_tighter(
                cc.temporal.active_hours_start,
                cc.temporal.active_hours_end,
                pc.temporal.active_hours_start,
                pc.temporal.active_hours_end,
            ):
                return False

        # RT7-09: Temporal — child blackout periods must include all parent blackout periods
        if pc.temporal.blackout_periods:
            parent_blackouts = set(pc.temporal.blackout_periods)
            child_blackouts = set(cc.temporal.blackout_periods)
            if not parent_blackouts.issubset(child_blackouts):
                return False

        # RT7-09: Data Access — child read_paths must be covered by parent read_paths
        if pc.data_access.read_paths:
            if not cc.data_access.read_paths:
                # Parent restricts read paths but child removes restriction — looser
                return False
            if not _paths_covered_by(cc.data_access.read_paths, pc.data_access.read_paths):
                return False

        # RT7-09: Data Access — child write_paths must be covered by parent write_paths
        if pc.data_access.write_paths:
            if not cc.data_access.write_paths:
                # Parent restricts write paths but child removes restriction — looser
                return False
            if not _paths_covered_by(cc.data_access.write_paths, pc.data_access.write_paths):
                return False

        # RT7-09: Data Access — child blocked_data_types must include all parent blocked_data_types
        if pc.data_access.blocked_data_types:
            parent_blocked_types = set(pc.data_access.blocked_data_types)
            child_blocked_types = set(cc.data_access.blocked_data_types)
            if not parent_blocked_types.issubset(child_blocked_types):
                return False

        # Communication: child cannot be less restrictive
        if pc.communication.internal_only and not cc.communication.internal_only:
            return False
        if (
            pc.communication.external_requires_approval
            and not cc.communication.external_requires_approval
        ):
            return False

        # M15/1501: Confidentiality clearance — child cannot have higher clearance than parent
        parent_clearance = _CONFIDENTIALITY_ORDER[pc.confidentiality_clearance]
        child_clearance = _CONFIDENTIALITY_ORDER[cc.confidentiality_clearance]
        if child_clearance > parent_clearance:
            return False

        # M15/1503: REASONING_REQUIRED — child cannot remove reasoning_required set by parent.
        # Check all five dimension configs for reasoning_required propagation.
        # M23/2301: Guard against None financial config.
        dimension_pairs: list[tuple] = []
        if pc.financial is not None and cc.financial is not None:
            dimension_pairs.append((pc.financial, cc.financial))
        elif pc.financial is not None and cc.financial is None:
            # If parent has financial with reasoning_required and child removes
            # financial entirely, that is acceptable (child is tighter — no financial at all).
            pass
        dimension_pairs.extend(
            [
                (pc.operational, cc.operational),
                (pc.temporal, cc.temporal),
                (pc.data_access, cc.data_access),
                (pc.communication, cc.communication),
            ]
        )
        for parent_dim, child_dim in dimension_pairs:
            if parent_dim.reasoning_required and not child_dim.reasoning_required:
                return False

        return True

    def _evaluate_financial(
        self, action: str, spend_amount: float, cumulative_spend: float = 0.0
    ) -> DimensionEvaluation:
        fc = self.config.financial

        # RT-27: Cumulative API budget check (before per-action max)
        if fc.api_cost_budget_usd is not None and fc.api_cost_budget_usd > 0:
            if cumulative_spend + spend_amount > fc.api_cost_budget_usd:
                return DimensionEvaluation(
                    dimension="financial",
                    result=EvaluationResult.DENIED,
                    reason=(
                        f"Cumulative API budget exceeded: "
                        f"${cumulative_spend} + ${spend_amount} > ${fc.api_cost_budget_usd}"
                    ),
                    utilization=1.0,
                )

        # Per-action max spend check
        if spend_amount > fc.max_spend_usd:
            return DimensionEvaluation(
                dimension="financial",
                result=EvaluationResult.DENIED,
                reason=f"Spend ${spend_amount} exceeds limit ${fc.max_spend_usd}",
                utilization=1.0,
            )

        # RT-24: Soft-limit approval threshold
        if (
            fc.requires_approval_above_usd is not None
            and spend_amount > fc.requires_approval_above_usd
        ):
            return DimensionEvaluation(
                dimension="financial",
                result=EvaluationResult.NEAR_BOUNDARY,
                reason=f"Spend ${spend_amount} exceeds approval threshold ${fc.requires_approval_above_usd}",
                utilization=spend_amount / fc.max_spend_usd if fc.max_spend_usd > 0 else 0.0,
            )

        if fc.max_spend_usd > 0:
            util = spend_amount / fc.max_spend_usd
            if util > 0.8:
                return DimensionEvaluation(
                    dimension="financial",
                    result=EvaluationResult.NEAR_BOUNDARY,
                    reason=f"Spend at {util:.0%} of limit",
                    utilization=util,
                )
        return DimensionEvaluation(
            dimension="financial",
            result=EvaluationResult.ALLOWED,
            utilization=spend_amount / fc.max_spend_usd if fc.max_spend_usd > 0 else 0.0,
        )

    def _evaluate_operational(self, action: str, current_action_count: int) -> DimensionEvaluation:
        oc = self.config.operational
        # Check blocked actions
        if action in oc.blocked_actions:
            return DimensionEvaluation(
                dimension="operational",
                result=EvaluationResult.DENIED,
                reason=f"Action '{action}' is explicitly blocked",
            )
        # Check allowed actions (if specified, action must be in list)
        if oc.allowed_actions and action not in oc.allowed_actions:
            return DimensionEvaluation(
                dimension="operational",
                result=EvaluationResult.DENIED,
                reason=f"Action '{action}' not in allowed actions list",
            )
        # Check rate limit
        if oc.max_actions_per_day is not None:
            if current_action_count >= oc.max_actions_per_day:
                return DimensionEvaluation(
                    dimension="operational",
                    result=EvaluationResult.DENIED,
                    reason=f"Daily limit of {oc.max_actions_per_day} actions reached",
                    utilization=1.0,
                )
            util = current_action_count / oc.max_actions_per_day
            if util > 0.8:
                return DimensionEvaluation(
                    dimension="operational",
                    result=EvaluationResult.NEAR_BOUNDARY,
                    reason=f"At {current_action_count}/{oc.max_actions_per_day} actions today",
                    utilization=util,
                )
            return DimensionEvaluation(
                dimension="operational",
                result=EvaluationResult.ALLOWED,
                utilization=util,
            )
        return DimensionEvaluation(
            dimension="operational",
            result=EvaluationResult.ALLOWED,
        )

    def _evaluate_temporal(self, action: str, current_time: datetime) -> DimensionEvaluation:
        tc = self.config.temporal

        # RT-15/RT-35: Convert to configured timezone before evaluation
        local_time = current_time
        if tc.timezone and tc.timezone != "UTC":
            try:
                tz = ZoneInfo(tc.timezone)
                local_time = current_time.astimezone(tz)
            except (KeyError, ValueError):
                # Fail-closed: invalid timezone config is logged.
                # Falls back to UTC (the provided time) which is acceptable
                # because temporal evaluation still runs — it just uses UTC
                # instead of the configured timezone.
                import logging

                logging.getLogger(__name__).warning(
                    "Invalid timezone '%s' in temporal constraint. "
                    "Falling back to UTC for temporal evaluation.",
                    tc.timezone,
                )

        # RT-15: Check blackout periods first (they take precedence)
        if tc.blackout_periods:
            date_full = local_time.strftime("%Y-%m-%d")
            date_md = local_time.strftime("%m-%d")
            for period in tc.blackout_periods:
                if period == date_full or period == date_md:
                    return DimensionEvaluation(
                        dimension="temporal",
                        result=EvaluationResult.DENIED,
                        reason=f"Action during blackout period ({period})",
                    )

        # RT-28: Handle overnight windows (start > end means overnight)
        if tc.active_hours_start and tc.active_hours_end:
            time_str = local_time.strftime("%H:%M")
            is_overnight = tc.active_hours_start > tc.active_hours_end

            if is_overnight:
                # Overnight window (e.g., 22:00-06:00): allowed if >= start OR <= end
                if not (time_str >= tc.active_hours_start or time_str <= tc.active_hours_end):
                    return DimensionEvaluation(
                        dimension="temporal",
                        result=EvaluationResult.DENIED,
                        reason=f"Outside active hours ({tc.active_hours_start}-{tc.active_hours_end})",
                    )
            else:
                # Normal window (e.g., 09:00-17:00): allowed if start <= time <= end
                if not (tc.active_hours_start <= time_str <= tc.active_hours_end):
                    return DimensionEvaluation(
                        dimension="temporal",
                        result=EvaluationResult.DENIED,
                        reason=f"Outside active hours ({tc.active_hours_start}-{tc.active_hours_end})",
                    )

        return DimensionEvaluation(
            dimension="temporal",
            result=EvaluationResult.ALLOWED,
        )

    def _evaluate_data_access(
        self, action: str, data_paths: list[str], access_type: str = "read"
    ) -> DimensionEvaluation:
        dc = self.config.data_access

        # Check blocked data types first (always enforced)
        for path in data_paths:
            for blocked in dc.blocked_data_types:
                if blocked.lower() in path.lower():
                    return DimensionEvaluation(
                        dimension="data_access",
                        result=EvaluationResult.DENIED,
                        reason=f"Access to '{path}' blocked (matches '{blocked}')",
                    )

        # RT-16: Enforce read_paths for read access
        if access_type == "read" and dc.read_paths:
            for path in data_paths:
                if not any(
                    path.startswith(rp) or fnmatch.fnmatch(path, rp) for rp in dc.read_paths
                ):
                    return DimensionEvaluation(
                        dimension="data_access",
                        result=EvaluationResult.DENIED,
                        reason=f"Read access to '{path}' not under allowed read paths",
                    )

        # RT-16: Enforce write_paths for write access
        if access_type == "write" and dc.write_paths:
            for path in data_paths:
                if not any(
                    path.startswith(wp) or fnmatch.fnmatch(path, wp) for wp in dc.write_paths
                ):
                    return DimensionEvaluation(
                        dimension="data_access",
                        result=EvaluationResult.DENIED,
                        reason=f"Write access to '{path}' not under allowed write paths",
                    )

        return DimensionEvaluation(
            dimension="data_access",
            result=EvaluationResult.ALLOWED,
        )

    def _evaluate_communication(self, action: str, is_external: bool) -> DimensionEvaluation:
        cc = self.config.communication
        if is_external and cc.internal_only:
            return DimensionEvaluation(
                dimension="communication",
                result=EvaluationResult.DENIED,
                reason="External communication blocked (internal_only=true)",
            )
        # RT-17: external_requires_approval enforcement
        if is_external and cc.external_requires_approval:
            return DimensionEvaluation(
                dimension="communication",
                result=EvaluationResult.NEAR_BOUNDARY,
                reason="External communication requires approval",
            )
        return DimensionEvaluation(
            dimension="communication",
            result=EvaluationResult.ALLOWED,
        )

    def _evaluate_confidentiality(
        self, data_classification: ConfidentialityLevel | None
    ) -> DimensionEvaluation:
        """M15/1501: Evaluate data access against the envelope's confidentiality clearance.

        When data_classification is provided, the data's classification level must
        not exceed the envelope's confidentiality_clearance. If it does, the action
        is denied.

        Args:
            data_classification: The confidentiality level of the data being accessed.
                When None, the check is a no-op (ALLOWED).

        Returns:
            DimensionEvaluation for the confidentiality dimension.
        """
        if data_classification is None:
            return DimensionEvaluation(
                dimension="confidentiality",
                result=EvaluationResult.ALLOWED,
            )

        envelope_clearance = _CONFIDENTIALITY_ORDER[self.config.confidentiality_clearance]
        data_level = _CONFIDENTIALITY_ORDER[data_classification]

        if data_level > envelope_clearance:
            return DimensionEvaluation(
                dimension="confidentiality",
                result=EvaluationResult.DENIED,
                reason=(
                    f"Data classified as {data_classification.value} exceeds "
                    f"envelope clearance {self.config.confidentiality_clearance.value}"
                ),
            )

        return DimensionEvaluation(
            dimension="confidentiality",
            result=EvaluationResult.ALLOWED,
        )

    def _evaluate_reasoning_required(self, reasoning_trace: str | None) -> DimensionEvaluation:
        """M15/1503: Evaluate REASONING_REQUIRED meta-constraint.

        Called only when at least one dimension has reasoning_required=True.
        When no reasoning_trace is provided, the action is flagged as
        NEAR_BOUNDARY (HELD for human review).

        Args:
            reasoning_trace: The reasoning trace text. When None or empty,
                the action is HELD.

        Returns:
            DimensionEvaluation for the reasoning dimension.
        """
        if not reasoning_trace:
            return DimensionEvaluation(
                dimension="reasoning",
                result=EvaluationResult.NEAR_BOUNDARY,
                reason="Reasoning trace required but not provided",
            )

        return DimensionEvaluation(
            dimension="reasoning",
            result=EvaluationResult.ALLOWED,
        )
