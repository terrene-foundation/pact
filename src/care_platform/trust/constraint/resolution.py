# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Constraint Resolution Algorithm — resolves a hierarchy of constraint envelopes
into a single effective envelope.

Given a list of ConstraintEnvelopeConfig objects ordered from broadest (org-level)
to narrowest (agent-level), produces a single resolved envelope that represents
the intersection/most-restrictive combination of all levels.

Resolution rules per dimension:
- **Financial**: minimum of max_spend_usd across all envelopes
- **Operational**: intersection of allowed_actions, union of blocked_actions,
  minimum of max_actions_per_day
- **Temporal**: intersection of active windows (latest start, earliest end)
- **Data Access**: intersection of read_paths and write_paths,
  union of blocked_data_types
- **Communication**: most restrictive wins (any True overrides False)
"""

from __future__ import annotations

import logging

from care_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConstraintResolutionError(Exception):
    """Raised when constraint resolution fails."""


# ---------------------------------------------------------------------------
# Resolution Functions
# ---------------------------------------------------------------------------


def resolve_constraints(
    envelopes: list[ConstraintEnvelopeConfig],
) -> ConstraintEnvelopeConfig:
    """Resolve a hierarchy of constraint envelopes into a single effective envelope.

    Args:
        envelopes: Ordered list of ConstraintEnvelopeConfig, from broadest
            (org-level) to narrowest (agent-level). Must contain at least one
            envelope.

    Returns:
        A single ConstraintEnvelopeConfig representing the resolved intersection
        of all envelopes.

    Raises:
        ConstraintResolutionError: If the envelopes list is empty.
    """
    if not envelopes:
        raise ConstraintResolutionError(
            "Cannot resolve constraints from an empty list of envelopes. "
            "At least one envelope is required."
        )

    if len(envelopes) == 1:
        # Single envelope: generate a resolved copy with a descriptive ID
        env = envelopes[0]
        return ConstraintEnvelopeConfig(
            id=f"resolved:{env.id}",
            description=f"Resolved from: {env.id}",
            financial=env.financial,
            operational=env.operational,
            temporal=env.temporal,
            data_access=env.data_access,
            communication=env.communication,
        )

    # Start with the first envelope and progressively resolve
    resolved = envelopes[0]
    source_ids = [resolved.id]

    for env in envelopes[1:]:
        source_ids.append(env.id)
        resolved = _resolve_pair(resolved, env)

    # Build final resolved envelope with descriptive ID
    return ConstraintEnvelopeConfig(
        id=f"resolved:{'+'.join(source_ids)}",
        description=f"Resolved from: {', '.join(source_ids)}",
        financial=resolved.financial,
        operational=resolved.operational,
        temporal=resolved.temporal,
        data_access=resolved.data_access,
        communication=resolved.communication,
    )


def _resolve_pair(
    a: ConstraintEnvelopeConfig,
    b: ConstraintEnvelopeConfig,
) -> ConstraintEnvelopeConfig:
    """Resolve two constraint envelopes into one (most restrictive combination).

    Args:
        a: First envelope (typically broader).
        b: Second envelope (typically narrower).

    Returns:
        A resolved ConstraintEnvelopeConfig.
    """
    return ConstraintEnvelopeConfig(
        id="intermediate",
        financial=_resolve_financial(a.financial, b.financial),
        operational=_resolve_operational(a.operational, b.operational),
        temporal=_resolve_temporal(a.temporal, b.temporal),
        data_access=_resolve_data_access(a.data_access, b.data_access),
        communication=_resolve_communication(a.communication, b.communication),
    )


# ---------------------------------------------------------------------------
# Per-Dimension Resolution
# ---------------------------------------------------------------------------


def _resolve_financial(
    a: FinancialConstraintConfig,
    b: FinancialConstraintConfig,
) -> FinancialConstraintConfig:
    """Financial: minimum of max_spend_usd."""
    return FinancialConstraintConfig(
        max_spend_usd=min(a.max_spend_usd, b.max_spend_usd),
        api_cost_budget_usd=_min_optional(a.api_cost_budget_usd, b.api_cost_budget_usd),
        requires_approval_above_usd=_min_optional(
            a.requires_approval_above_usd, b.requires_approval_above_usd
        ),
    )


def _resolve_operational(
    a: OperationalConstraintConfig,
    b: OperationalConstraintConfig,
) -> OperationalConstraintConfig:
    """Operational: intersection of allowed_actions, union of blocked_actions,
    minimum of max_actions_per_day."""
    # Intersection of allowed_actions:
    # Empty list means "unrestricted" — so if one is empty, use the other.
    if a.allowed_actions and b.allowed_actions:
        allowed = sorted(set(a.allowed_actions) & set(b.allowed_actions))
        if not allowed:
            raise ConstraintResolutionError(
                f"Operational constraint resolution failed: allowed_actions "
                f"have no overlap ({a.allowed_actions} ∩ {b.allowed_actions} = ∅). "
                f"No actions would be permitted."
            )
    elif a.allowed_actions:
        allowed = list(a.allowed_actions)
    elif b.allowed_actions:
        allowed = list(b.allowed_actions)
    else:
        allowed = []

    # Union of blocked_actions
    blocked = sorted(set(a.blocked_actions) | set(b.blocked_actions))

    # Minimum of max_actions_per_day
    rate_limit = _min_optional(a.max_actions_per_day, b.max_actions_per_day)

    return OperationalConstraintConfig(
        allowed_actions=allowed,
        blocked_actions=blocked,
        max_actions_per_day=rate_limit,
    )


def _resolve_temporal(
    a: TemporalConstraintConfig,
    b: TemporalConstraintConfig,
) -> TemporalConstraintConfig:
    """Temporal: intersection of active windows (latest start, earliest end)."""
    start = _latest_time(a.active_hours_start, b.active_hours_start)
    end = _earliest_time(a.active_hours_end, b.active_hours_end)

    # Union of blackout periods
    blackouts = sorted(set(a.blackout_periods) | set(b.blackout_periods))

    # Use the most specific timezone (prefer non-UTC if one is set)
    timezone = a.timezone if a.timezone != "UTC" else b.timezone

    return TemporalConstraintConfig(
        active_hours_start=start,
        active_hours_end=end,
        timezone=timezone,
        blackout_periods=blackouts,
    )


def _resolve_data_access(
    a: DataAccessConstraintConfig,
    b: DataAccessConstraintConfig,
) -> DataAccessConstraintConfig:
    """Data Access: intersection of read/write paths, union of blocked_data_types."""
    # Intersection of read_paths (empty = unrestricted)
    if a.read_paths and b.read_paths:
        read_paths = sorted(set(a.read_paths) & set(b.read_paths))
        if not read_paths:
            raise ConstraintResolutionError(
                f"Data access constraint resolution failed: read_paths "
                f"have no overlap ({a.read_paths} ∩ {b.read_paths} = ∅). "
                f"No read access would be permitted."
            )
    elif a.read_paths:
        read_paths = list(a.read_paths)
    elif b.read_paths:
        read_paths = list(b.read_paths)
    else:
        read_paths = []

    # Intersection of write_paths (empty = unrestricted)
    if a.write_paths and b.write_paths:
        write_paths = sorted(set(a.write_paths) & set(b.write_paths))
        if not write_paths:
            raise ConstraintResolutionError(
                f"Data access constraint resolution failed: write_paths "
                f"have no overlap ({a.write_paths} ∩ {b.write_paths} = ∅). "
                f"No write access would be permitted."
            )
    elif a.write_paths:
        write_paths = list(a.write_paths)
    elif b.write_paths:
        write_paths = list(b.write_paths)
    else:
        write_paths = []

    # Union of blocked_data_types
    blocked = sorted(set(a.blocked_data_types) | set(b.blocked_data_types))

    return DataAccessConstraintConfig(
        read_paths=read_paths,
        write_paths=write_paths,
        blocked_data_types=blocked,
    )


def _resolve_communication(
    a: CommunicationConstraintConfig,
    b: CommunicationConstraintConfig,
) -> CommunicationConstraintConfig:
    """Communication: most restrictive wins (any True overrides False)."""
    # Intersection of allowed_channels
    if a.allowed_channels and b.allowed_channels:
        channels = sorted(set(a.allowed_channels) & set(b.allowed_channels))
    elif a.allowed_channels:
        channels = list(a.allowed_channels)
    elif b.allowed_channels:
        channels = list(b.allowed_channels)
    else:
        channels = []

    return CommunicationConstraintConfig(
        internal_only=a.internal_only or b.internal_only,
        external_requires_approval=a.external_requires_approval or b.external_requires_approval,
        allowed_channels=channels,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _min_optional(a: int | float | None, b: int | float | None) -> int | float | None:
    """Return the minimum of two optional values. None means unrestricted."""
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _latest_time(a: str | None, b: str | None) -> str | None:
    """Return the later of two HH:MM time strings. None means no restriction."""
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def _earliest_time(a: str | None, b: str | None) -> str | None:
    """Return the earlier of two HH:MM time strings. None means no restriction."""
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)
