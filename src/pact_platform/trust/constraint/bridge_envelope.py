# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Bridge constraint envelope intersection — computes effective constraint
envelopes for cross-team actions through Cross-Functional Bridges.

When two teams collaborate through a bridge, the effective constraint envelope
is the most restrictive combination of:
1. The source team's constraint envelope
2. The bridge's own permissions
3. The target team's constraint envelope

This module also provides:
- Information sharing modes (AUTO_SHARE, REQUEST_SHARE, NEVER_SHARE) for
  field-level control over what data flows through a bridge.
- Bridge tightening validation to ensure a bridge envelope never exceeds
  either team's individual constraints.
"""

from __future__ import annotations

import fnmatch
import logging
from enum import Enum

from pydantic import BaseModel, Field

from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)
from pact_platform.build.workspace.bridge import BridgePermission

logger = logging.getLogger(__name__)


def _is_time_window_tighter(
    child_start: str, child_end: str, parent_start: str, parent_end: str
) -> bool:
    """Check if child time window is a subset of parent time window."""

    def _to_min(t: str) -> int:
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    cs, ce, ps, pe = (
        _to_min(child_start),
        _to_min(child_end),
        _to_min(parent_start),
        _to_min(parent_end),
    )
    parent_overnight = pe <= ps
    child_overnight = ce <= cs

    if not parent_overnight and child_overnight:
        return False
    if not parent_overnight and not child_overnight:
        return cs >= ps and ce <= pe
    if parent_overnight and child_overnight:
        return cs >= ps and ce <= pe
    if parent_overnight and not child_overnight:
        return (cs >= ps) or (ce <= pe)
    return False


def _path_covered(child: str, parent: str) -> bool:
    """Check if a single child path is covered by a parent path."""
    if child == parent:
        return True
    parent_prefix = parent.rstrip("*")
    child_prefix = child.rstrip("*")
    return child_prefix.startswith(parent_prefix)


def _paths_covered_by(child_paths: list[str], parent_paths: list[str]) -> bool:
    """Check that every child path is covered by at least one parent path."""
    for cp in child_paths:
        if not any(_path_covered(cp, pp) for pp in parent_paths):
            return False
    return True


# ---------------------------------------------------------------------------
# Information Sharing Modes (Task 3202)
# ---------------------------------------------------------------------------


class SharingMode(str, Enum):
    """Controls how a field flows through a Cross-Functional Bridge.

    - AUTO_SHARE: field passes through the bridge automatically
    - REQUEST_SHARE: field is queued for human approval (HELD)
    - NEVER_SHARE: field is blocked from crossing the bridge boundary
    """

    AUTO_SHARE = "auto_share"
    REQUEST_SHARE = "request_share"
    NEVER_SHARE = "never_share"


class FieldSharingRule(BaseModel):
    """A single field-level sharing rule for a bridge.

    Rules are matched in order — the first rule whose field_pattern matches
    the field path (via fnmatch) determines the sharing mode.
    """

    field_pattern: str = Field(description="Glob pattern for field/path matching")
    mode: SharingMode = Field(description="Sharing mode for matching fields")
    justification: str = Field(
        default="",
        description="Human-readable reason for this rule",
    )


class BridgeSharingPolicy(BaseModel):
    """Field-level sharing policy for a Cross-Functional Bridge.

    Controls which fields can flow through the bridge and under what conditions.
    Rules are tried in order — the first matching rule wins.
    """

    rules: list[FieldSharingRule] = Field(default_factory=list)
    default_mode: SharingMode = Field(
        default=SharingMode.REQUEST_SHARE,
        description="Sharing mode applied when no rule matches",
    )

    def check_field(self, field_path: str) -> SharingMode:
        """Get the sharing mode for a specific field path.

        Matches field_path against rules in order using fnmatch.fnmatch().
        Returns the first matching rule's mode, or default_mode if no rule matches.

        RT13-L3 design note: NEVER_SHARE is a **path-level** access control,
        not an information-flow control.  It blocks direct access to paths
        matching the glob pattern (e.g. ``salary.*``) but cannot prevent
        indirect leakage through derived or aggregated fields accessed via
        a different path.  For true information-flow protection, combine
        NEVER_SHARE with ``blocked_data_types`` in the Data Access dimension
        or upstream data classification.

        Args:
            field_path: The field path to check (e.g., "budget.annual").

        Returns:
            The applicable SharingMode for this field.
        """
        for rule in self.rules:
            if fnmatch.fnmatch(field_path, rule.field_pattern):
                return rule.mode
        return self.default_mode


# ---------------------------------------------------------------------------
# Envelope Intersection (Task 3201)
# ---------------------------------------------------------------------------


def _to_minutes(time_str: str) -> int:
    """Convert HH:MM string to minutes since midnight.

    Validates that hours are 0-23 and minutes are 0-59.
    Raises ValueError for malformed input.
    """
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format (expected HH:MM): {time_str!r}")
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"Invalid time format (non-numeric): {time_str!r}")
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Invalid time values (h={h}, m={m}): {time_str!r}")
    return h * 60 + m


def _from_minutes(minutes: int) -> str:
    """Convert minutes since midnight to HH:MM string."""
    minutes = minutes % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _intersect_time_windows(
    start_a: str | None,
    end_a: str | None,
    start_b: str | None,
    end_b: str | None,
) -> tuple[str | None, str | None]:
    """Compute the overlapping active hours window of two time windows.

    Each window is defined by start and end times in HH:MM format.
    None means "no restriction" (fully permissive).

    Returns:
        (start, end) of the overlap, or a sentinel (same start and end)
        if there is no overlap.
    """
    # If either window is unrestricted, use the other
    if start_a is None or end_a is None:
        return start_b, end_b
    if start_b is None or end_b is None:
        return start_a, end_a

    sa, ea = _to_minutes(start_a), _to_minutes(end_a)
    sb, eb = _to_minutes(start_b), _to_minutes(end_b)

    overnight_a = ea <= sa
    overnight_b = eb <= sb

    if not overnight_a and not overnight_b:
        # Both are normal daytime windows
        overlap_start = max(sa, sb)
        overlap_end = min(ea, eb)
        if overlap_start >= overlap_end:
            # No overlap — return sentinel
            return "00:00", "00:00"
        return _from_minutes(overlap_start), _from_minutes(overlap_end)

    if overnight_a and overnight_b:
        # Both are overnight windows (e.g., 22:00-06:00 and 20:00-04:00)
        # Overnight covers [start, 24:00) U [00:00, end)
        # Intersection: latest start, earliest end
        overlap_start = max(sa, sb)
        overlap_end = min(ea, eb)
        if overlap_end <= 0:
            # No morning segment overlap — just evening segment
            return _from_minutes(overlap_start), _from_minutes(overlap_end)
        return _from_minutes(overlap_start), _from_minutes(overlap_end)

    # One overnight, one normal — normalize so A is overnight
    if not overnight_a:
        sa, ea, sb, eb = sb, eb, sa, ea

    # A is overnight: covers [sa, 24:00) U [00:00, ea)
    # B is normal: covers [sb, eb)
    # Check overlap with evening segment [sa, 24:00)
    evening_overlap_start = max(sa, sb)
    evening_overlap_end = min(24 * 60, eb)
    evening_overlap = evening_overlap_start < evening_overlap_end

    # Check overlap with morning segment [00:00, ea)
    morning_overlap_start = max(0, sb)
    morning_overlap_end = min(ea, eb)
    morning_overlap = morning_overlap_start < morning_overlap_end

    if evening_overlap and morning_overlap:
        # Both segments overlap with B — return overnight window
        return _from_minutes(evening_overlap_start), _from_minutes(morning_overlap_end)
    if evening_overlap:
        return _from_minutes(evening_overlap_start), _from_minutes(evening_overlap_end)
    if morning_overlap:
        return _from_minutes(morning_overlap_start), _from_minutes(morning_overlap_end)

    # No overlap
    return "00:00", "00:00"


def compute_bridge_envelope(
    source_envelope: ConstraintEnvelopeConfig,
    bridge_permissions: BridgePermission,
    target_envelope: ConstraintEnvelopeConfig,
    sharing_policy: BridgeSharingPolicy | None = None,
) -> ConstraintEnvelopeConfig:
    """Compute the effective constraint envelope for a bridge action.

    Returns the most restrictive combination across all five CARE dimensions
    by intersecting the source team's envelope, the bridge permissions, and
    the target team's envelope.

    Args:
        source_envelope: Constraint envelope of the source team.
        bridge_permissions: Bridge-level permissions (read_paths, write_paths,
            message_types).
        target_envelope: Constraint envelope of the target team.
        sharing_policy: Optional field-level sharing policy. When provided,
            NEVER_SHARE fields are excluded from the resulting data access paths.

    Returns:
        A new ConstraintEnvelopeConfig representing the most restrictive
        combination across all dimensions.

    RT13-M2 staleness note: The bridge envelope is computed once at
    bridge activation and stored as a frozen snapshot (via
    ``effective_permissions``).  If either team's parent envelope is
    subsequently tightened, the bridge envelope may be wider than the
    new parent.  This is acceptable because (1) the bridge envelope can
    never exceed EITHER team's envelope *at activation time*, and (2)
    bridge re-activation or re-approval after a parent envelope change
    triggers a fresh computation.  Continuous staleness checks would
    require per-access recomputation, which conflicts with the frozen-
    snapshot design for performance and determinism.
    """
    financial = _intersect_financial(source_envelope.financial, target_envelope.financial)
    operational = _intersect_operational(source_envelope.operational, target_envelope.operational)
    temporal = _intersect_temporal(source_envelope.temporal, target_envelope.temporal)
    data_access = _intersect_data_access(
        source_envelope.data_access,
        target_envelope.data_access,
        bridge_permissions,
        sharing_policy,
    )
    communication = _intersect_communication(
        source_envelope.communication, target_envelope.communication
    )

    return ConstraintEnvelopeConfig(
        id=f"bridge-{source_envelope.id}-{target_envelope.id}",
        description=(
            f"Bridge envelope: intersection of '{source_envelope.id}' and '{target_envelope.id}'"
        ),
        financial=financial,
        operational=operational,
        temporal=temporal,
        data_access=data_access,
        communication=communication,
    )


def _intersect_financial(
    source: FinancialConstraintConfig | None,
    target: FinancialConstraintConfig | None,
) -> FinancialConstraintConfig | None:
    """Financial dimension: min of both budgets.

    If either config is None (no financial capability), the result is None
    because no financial capability is the tightest constraint.
    """
    if source is None or target is None:
        return None

    max_spend = min(source.max_spend_usd, target.max_spend_usd)

    # Approval threshold: min of both if both set, otherwise the one that is set
    approval = None
    if (
        source.requires_approval_above_usd is not None
        and target.requires_approval_above_usd is not None
    ):
        approval = min(source.requires_approval_above_usd, target.requires_approval_above_usd)
    elif source.requires_approval_above_usd is not None:
        approval = source.requires_approval_above_usd
    elif target.requires_approval_above_usd is not None:
        approval = target.requires_approval_above_usd

    # API cost budget: min of both if both set
    api_budget = None
    if source.api_cost_budget_usd is not None and target.api_cost_budget_usd is not None:
        api_budget = min(source.api_cost_budget_usd, target.api_cost_budget_usd)
    elif source.api_cost_budget_usd is not None:
        api_budget = source.api_cost_budget_usd
    elif target.api_cost_budget_usd is not None:
        api_budget = target.api_cost_budget_usd

    # Reasoning required: union (if either requires it, the bridge requires it)
    reasoning = source.reasoning_required or target.reasoning_required

    return FinancialConstraintConfig(
        max_spend_usd=max_spend,
        requires_approval_above_usd=approval,
        api_cost_budget_usd=api_budget,
        reasoning_required=reasoning,
    )


def _intersect_operational(
    source: OperationalConstraintConfig,
    target: OperationalConstraintConfig,
) -> OperationalConstraintConfig:
    """Operational dimension: allowed = intersection, blocked = union, rate = min.

    RT12-003: Empty allowed_actions means "no actions allowed" (most restrictive).
    If either side has an empty list, the intersection result is empty.
    """
    # Allowed actions: intersection (empty = no access, not "unrestricted")
    if not source.allowed_actions or not target.allowed_actions:
        allowed: list[str] = []
    else:
        allowed = sorted(set(source.allowed_actions) & set(target.allowed_actions))

    # Blocked actions: union
    blocked = sorted(set(source.blocked_actions) | set(target.blocked_actions))

    # Rate limits: min of both if both set, otherwise use the one that is set
    max_per_day = _min_optional(source.max_actions_per_day, target.max_actions_per_day)
    max_per_hour = _min_optional(source.max_actions_per_hour, target.max_actions_per_hour)

    # Reasoning required: union
    reasoning = source.reasoning_required or target.reasoning_required

    return OperationalConstraintConfig(
        allowed_actions=allowed,
        blocked_actions=blocked,
        max_actions_per_day=max_per_day,
        max_actions_per_hour=max_per_hour,
        reasoning_required=reasoning,
    )


def _intersect_temporal(
    source: TemporalConstraintConfig,
    target: TemporalConstraintConfig,
) -> TemporalConstraintConfig:
    """Temporal dimension: overlapping active hours window.

    Computes the overlap of two time windows. If there is no overlap,
    returns a sentinel window (start == end) that will deny all actions.
    Blackout periods are unioned.
    """
    start, end = _intersect_time_windows(
        source.active_hours_start,
        source.active_hours_end,
        target.active_hours_start,
        target.active_hours_end,
    )

    # Blackout periods: union
    blackouts = sorted(set(source.blackout_periods) | set(target.blackout_periods))

    # Reasoning required: union
    reasoning = source.reasoning_required or target.reasoning_required

    return TemporalConstraintConfig(
        active_hours_start=start,
        active_hours_end=end,
        blackout_periods=blackouts,
        reasoning_required=reasoning,
    )


def _intersect_data_access(
    source: DataAccessConstraintConfig,
    target: DataAccessConstraintConfig,
    bridge_permissions: BridgePermission,
    sharing_policy: BridgeSharingPolicy | None = None,
) -> DataAccessConstraintConfig:
    """Data Access dimension: paths intersected with bridge permissions.

    Read/write paths are intersected across all three sources using exact string
    matching on pattern strings. blocked_data_types are unioned.

    When a sharing_policy is provided, paths matching NEVER_SHARE rules are
    excluded from the result.
    """
    # Read paths: intersection of source, target, and bridge permissions
    read_paths = _intersect_path_lists(
        source.read_paths,
        target.read_paths,
        bridge_permissions.read_paths,
    )

    # Write paths: intersection of source, target, and bridge permissions
    write_paths = _intersect_path_lists(
        source.write_paths,
        target.write_paths,
        bridge_permissions.write_paths,
    )

    # Apply sharing policy: exclude NEVER_SHARE paths
    if sharing_policy is not None:
        read_paths = [
            p for p in read_paths if sharing_policy.check_field(p) != SharingMode.NEVER_SHARE
        ]
        write_paths = [
            p for p in write_paths if sharing_policy.check_field(p) != SharingMode.NEVER_SHARE
        ]

    # Blocked data types: union
    blocked = sorted(set(source.blocked_data_types) | set(target.blocked_data_types))

    # Reasoning required: union
    reasoning = source.reasoning_required or target.reasoning_required

    return DataAccessConstraintConfig(
        read_paths=read_paths,
        write_paths=write_paths,
        blocked_data_types=blocked,
        reasoning_required=reasoning,
    )


def _intersect_communication(
    source: CommunicationConstraintConfig,
    target: CommunicationConstraintConfig,
) -> CommunicationConstraintConfig:
    """Communication dimension: most restrictive wins on every field.

    internal_only and external_requires_approval are True if either is True.
    allowed_channels is the intersection.
    """
    internal_only = source.internal_only or target.internal_only
    external_requires_approval = (
        source.external_requires_approval or target.external_requires_approval
    )

    # RT12-003: Allowed channels: intersection (empty = no channels, not "unrestricted")
    if not source.allowed_channels or not target.allowed_channels:
        channels: list[str] = []
    else:
        channels = sorted(set(source.allowed_channels) & set(target.allowed_channels))

    # Reasoning required: union
    reasoning = source.reasoning_required or target.reasoning_required

    return CommunicationConstraintConfig(
        internal_only=internal_only,
        external_requires_approval=external_requires_approval,
        allowed_channels=channels,
        reasoning_required=reasoning,
    )


# ---------------------------------------------------------------------------
# Bridge Tightening Validation (Task 3203)
# ---------------------------------------------------------------------------


def validate_bridge_tightening(
    bridge_envelope: ConstraintEnvelopeConfig,
    source_envelope: ConstraintEnvelopeConfig,
    target_envelope: ConstraintEnvelopeConfig,
) -> tuple[bool, list[str]]:
    """Verify that the bridge constraint envelope is no wider than either team's envelope.

    The bridge envelope must be a valid tightening of BOTH the source and target
    envelopes. This is the safety check that prevents a bridge from accidentally
    granting broader access than either party actually holds.

    RT13-H5 transitive monotonicity note: Each bridge is independently
    computed as the intersection of the two participant envelopes, so
    multi-bridge chains (A->B->C) enforce progressive narrowing — the
    A->C path through B is at most as permissive as min(A,B) intersected
    with min(B,C).  A direct A->C bridge is independently computed as
    min(A,C), which may differ from the transitive path.  This is correct
    behaviour: each bridge is scoped to its two participants' envelopes
    and cannot widen either side.  Transitive constraint analysis across
    bridge chains is a monitoring concern, not a per-bridge invariant.

    Args:
        bridge_envelope: The computed bridge envelope to validate.
        source_envelope: The source team's constraint envelope.
        target_envelope: The target team's constraint envelope.

    Returns:
        Tuple of (is_valid, violations) where violations is a list of
        human-readable violation descriptions. Empty list means valid.
    """
    violations: list[str] = []

    # Check against both source and target
    for label, parent in [("source", source_envelope), ("target", target_envelope)]:
        violations.extend(_check_tightening_against(bridge_envelope, parent, label))

    is_valid = len(violations) == 0
    return is_valid, violations


def _check_tightening_against(
    bridge: ConstraintEnvelopeConfig,
    parent: ConstraintEnvelopeConfig,
    label: str,
) -> list[str]:
    """Check that bridge envelope is no wider than a single parent envelope.

    Args:
        bridge: The bridge envelope being validated.
        parent: The parent envelope (source or target) to check against.
        label: "source" or "target" for human-readable messages.

    Returns:
        List of violation descriptions.
    """
    violations: list[str] = []

    # --- Financial ---
    if parent.financial is None and bridge.financial is not None:
        violations.append(f"Financial: bridge has financial capability but {label} has none")
    elif parent.financial is not None and bridge.financial is not None:
        if bridge.financial.max_spend_usd > parent.financial.max_spend_usd:
            violations.append(
                f"Financial: bridge allows ${bridge.financial.max_spend_usd} "
                f"but {label} only allows ${parent.financial.max_spend_usd}"
            )

    # --- Operational: allowed actions ---
    if parent.operational.allowed_actions:
        parent_actions = set(parent.operational.allowed_actions)
        bridge_actions = set(bridge.operational.allowed_actions)
        extra = bridge_actions - parent_actions
        if extra:
            violations.append(f"Operational: bridge allows actions not in {label}: {sorted(extra)}")

    # --- Operational: blocked actions must include parent's ---
    parent_blocked = set(parent.operational.blocked_actions)
    bridge_blocked = set(bridge.operational.blocked_actions)
    missing = parent_blocked - bridge_blocked
    if missing:
        violations.append(
            f"Operational: bridge is missing {label} blocked actions: {sorted(missing)}"
        )

    # --- Operational: rate limit ---
    if (
        parent.operational.max_actions_per_day is not None
        and bridge.operational.max_actions_per_day is None
    ):
        violations.append(
            f"Operational: bridge removes {label} daily rate limit "
            f"({parent.operational.max_actions_per_day})"
        )
    elif (
        parent.operational.max_actions_per_day is not None
        and bridge.operational.max_actions_per_day is not None
        and bridge.operational.max_actions_per_day > parent.operational.max_actions_per_day
    ):
        violations.append(
            f"Operational: bridge daily rate limit {bridge.operational.max_actions_per_day} "
            f"exceeds {label} limit {parent.operational.max_actions_per_day}"
        )

    # --- Temporal ---
    pt = parent.temporal
    bt = bridge.temporal
    if pt.active_hours_start is not None and pt.active_hours_end is not None:
        if bt.active_hours_start is None or bt.active_hours_end is None:
            violations.append(
                f"Temporal: bridge removes {label} active hours window "
                f"({pt.active_hours_start}-{pt.active_hours_end})"
            )
        else:
            if not _is_time_window_tighter(
                bt.active_hours_start,
                bt.active_hours_end,
                pt.active_hours_start,
                pt.active_hours_end,
            ):
                violations.append(
                    f"Temporal: bridge window ({bt.active_hours_start}-{bt.active_hours_end}) "
                    f"is not within {label} window ({pt.active_hours_start}-{pt.active_hours_end})"
                )

    # --- Data Access: read paths ---
    if parent.data_access.read_paths:
        if not bridge.data_access.read_paths:
            violations.append(f"Data Access: bridge removes {label} read_paths restriction")
        elif not _paths_covered_by(
            list(bridge.data_access.read_paths),
            list(parent.data_access.read_paths),
        ):
            violations.append(
                f"Data Access: bridge read paths {sorted(bridge.data_access.read_paths)} "
                f"not covered by {label} {sorted(parent.data_access.read_paths)}"
            )

    # --- Data Access: write paths ---
    if parent.data_access.write_paths:
        if not bridge.data_access.write_paths:
            violations.append(f"Data Access: bridge removes {label} write_paths restriction")
        elif not _paths_covered_by(
            list(bridge.data_access.write_paths),
            list(parent.data_access.write_paths),
        ):
            violations.append(
                f"Data Access: bridge write paths {sorted(bridge.data_access.write_paths)} "
                f"not covered by {label} {sorted(parent.data_access.write_paths)}"
            )

    # --- Data Access: blocked data types ---
    parent_blocked_types = set(parent.data_access.blocked_data_types)
    bridge_blocked_types = set(bridge.data_access.blocked_data_types)
    missing_types = parent_blocked_types - bridge_blocked_types
    if missing_types:
        violations.append(
            f"Data Access: bridge is missing {label} blocked data types: {sorted(missing_types)}"
        )

    # --- Communication ---
    if parent.communication.internal_only and not bridge.communication.internal_only:
        violations.append(f"Communication: {label} is internal_only but bridge is not")
    if (
        parent.communication.external_requires_approval
        and not bridge.communication.external_requires_approval
    ):
        violations.append(f"Communication: {label} requires external approval but bridge does not")

    return violations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _min_optional(a: int | None, b: int | None) -> int | None:
    """Return min of two optional ints, treating None as infinity."""
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _intersect_path_lists(
    paths_a: list[str],
    paths_b: list[str],
    paths_c: list[str],
) -> list[str]:
    """Intersect three path lists using exact string matching on pattern strings.

    A path is included in the result only if it appears in all three lists.

    RT12-002: An empty list means "no access" (most restrictive), not "unrestricted".
    If any list is empty, the result is empty.
    """
    # If any list is empty, the intersection is empty (fail-closed)
    if not paths_a or not paths_b or not paths_c:
        return []

    result = set(paths_a) & set(paths_b) & set(paths_c)
    return sorted(result)
