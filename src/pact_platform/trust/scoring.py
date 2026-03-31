# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Trust scoring — 5-factor weighted trust score for agents.

Computes a composite trust score (0.0-1.0) for an agent based on five
factors derived from the EATP verification gradient spec:

1. Chain completeness (30%): Does the agent have a complete delegation
   chain from genesis? Score 1.0 if chain is valid and complete, 0.0 if broken.
2. Delegation depth (15%): Shorter chains = higher trust.
   Score = 1.0 - (depth / MAX_DEPTH). Depth 0 (genesis direct) = 1.0.
3. Constraint coverage (25%): How many of the 5 constraint dimensions
   are configured? Score = configured_dimensions / 5.
4. Posture level (20%): Higher posture = higher trust.
   PSEUDO_AGENT=0.0, SUPERVISED=0.25, SHARED_PLANNING=0.5,
   CONTINUOUS_INSIGHT=0.75, DELEGATED=1.0.
5. Chain recency (10%): How recently was the delegation created?
   Score = 1.0 if < 30 days, linear decay to 0.0 at 365 days.

Grade mapping: A (>=0.9), B (>=0.75), C (>=0.6), D (>=0.4), F (<0.4).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pact.governance.engine import GovernanceEngine
    from pact_platform.trust.store.store import TrustStore

__all__ = [
    "TrustScore",
    "compute_trust_score",
    "FACTOR_WEIGHTS",
    "MAX_DELEGATION_DEPTH",
    "POSTURE_SCORES",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_DELEGATION_DEPTH: int = 50
"""Maximum delegation depth for normalization. Matches _MAX_CHAIN_DEPTH in runtime."""

FACTOR_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {
        "chain_completeness": 0.30,
        "delegation_depth": 0.15,
        "constraint_coverage": 0.25,
        "posture_level": 0.20,
        "chain_recency": 0.10,
    }
)
"""Weight for each trust factor. Must sum to 1.0. Immutable (M2 fix)."""

POSTURE_SCORES: Mapping[str, float] = MappingProxyType(
    {
        "pseudo_agent": 0.0,
        "supervised": 0.25,
        "shared_planning": 0.5,
        "continuous_insight": 0.75,
        "delegated": 1.0,
    }
)
"""Trust score mapped to each posture level (by .value string). Immutable (M2 fix)."""

# Recency thresholds (in days)
_RECENCY_FULL_SCORE_DAYS: int = 30
_RECENCY_ZERO_SCORE_DAYS: int = 365

# Grade boundaries (lower bound, inclusive)
_GRADE_BOUNDARIES: list[tuple[float, str]] = [
    (0.9, "A"),
    (0.75, "B"),
    (0.6, "C"),
    (0.4, "D"),
]


# ---------------------------------------------------------------------------
# TrustScore dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrustScore:
    """Composite trust score for an agent.

    Attributes:
        total: Weighted sum of all factors, clamped to [0.0, 1.0].
        grade: Letter grade derived from total (A, B, C, D, F).
        factors: Individual factor scores keyed by factor name.
    """

    total: float
    grade: str
    factors: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate that total is finite and in range.  Freeze mutable factors dict."""
        if not math.isfinite(self.total):
            raise ValueError(f"total must be finite, got {self.total}")
        if self.total < 0.0 or self.total > 1.0:
            raise ValueError(f"total must be in [0.0, 1.0], got {self.total}")
        if self.grade not in ("A", "B", "C", "D", "F"):
            raise ValueError(f"grade must be A/B/C/D/F, got {self.grade!r}")
        # C1 fix: freeze mutable factors dict to prevent post-construction mutation
        object.__setattr__(self, "factors", MappingProxyType(dict(self.factors)))


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------


def _score_to_grade(total: float) -> str:
    """Map a total score to a letter grade."""
    for threshold, grade in _GRADE_BOUNDARIES:
        if total >= threshold:
            return grade
    return "F"


def _score_chain_completeness(
    agent_id: str,
    trust_store: TrustStore,
) -> float:
    """Factor 1: Chain completeness (1.0 if complete chain to genesis, 0.0 if broken).

    Walks the delegation chain from agent_id back toward genesis. A chain is
    complete when we reach a delegator_id that has a genesis record.
    """
    try:
        visited: set[str] = set()
        current_id = agent_id
        depth = 0

        while depth < MAX_DELEGATION_DEPTH:
            if current_id in visited:
                # Cycle detected -- broken chain
                return 0.0
            visited.add(current_id)

            # Check if current_id is a genesis authority
            genesis = trust_store.get_genesis(current_id)
            if genesis is not None:
                return 1.0

            # Look for an inbound delegation (where current_id is delegatee)
            delegations = trust_store.get_delegations_for(current_id)
            inbound = [
                d
                for d in delegations
                if d.get("delegatee_id") == current_id and not d.get("revoked", False)
            ]

            if not inbound:
                # No inbound delegation and no genesis -- broken chain
                return 0.0

            # Follow the first non-revoked inbound delegation
            current_id = inbound[0].get("delegator_id", "")
            if not current_id:
                return 0.0
            depth += 1

        # Exceeded max depth -- treat as broken
        return 0.0
    except Exception:
        logger.exception("Chain completeness check failed for agent '%s'", agent_id)
        return 0.0


def _score_delegation_depth(
    agent_id: str,
    trust_store: TrustStore,
) -> tuple[float, int]:
    """Factor 2: Delegation depth. Shorter = higher trust.

    Returns (score, depth) where score = 1.0 - (depth / MAX_DEPTH).
    Depth 0 means the agent IS the genesis authority.
    """
    try:
        visited: set[str] = set()
        current_id = agent_id
        depth = 0

        while depth < MAX_DELEGATION_DEPTH:
            if current_id in visited:
                return 0.0, depth
            visited.add(current_id)

            genesis = trust_store.get_genesis(current_id)
            if genesis is not None:
                score = 1.0 - (depth / MAX_DELEGATION_DEPTH)
                return max(0.0, score), depth

            delegations = trust_store.get_delegations_for(current_id)
            inbound = [
                d
                for d in delegations
                if d.get("delegatee_id") == current_id and not d.get("revoked", False)
            ]

            if not inbound:
                return 0.0, depth

            current_id = inbound[0].get("delegator_id", "")
            if not current_id:
                return 0.0, depth
            depth += 1

        return 0.0, depth
    except Exception:
        logger.exception("Delegation depth check failed for agent '%s'", agent_id)
        return 0.0, 0


def _score_constraint_coverage(
    agent_id: str,
    trust_store: TrustStore,
    governance_engine: GovernanceEngine | None,
) -> float:
    """Factor 3: Constraint coverage (configured_dimensions / 5).

    The 5 constraint dimensions are: financial, operational, temporal,
    data_access, communication. A dimension is "configured" if it appears
    in the effective envelope and is not None.
    """
    dimension_names = ("financial", "operational", "temporal", "data_access", "communication")

    try:
        # Try governance engine first (preferred -- knows about role envelopes)
        envelope_data: dict[str, Any] | None = None

        if governance_engine is not None:
            # We don't have the role_address for the agent here directly,
            # so try to use the store's envelope data.
            pass

        # Fall back to trust store envelope lookup
        envelopes = trust_store.list_envelopes(agent_id=agent_id)
        if envelopes:
            # Use the most recent envelope
            envelope_data = envelopes[-1]

        if envelope_data is None:
            return 0.0

        configured = 0
        for dim_name in dimension_names:
            dim_value = envelope_data.get(dim_name)
            if dim_value is not None:
                configured += 1

        return configured / len(dimension_names)
    except Exception:
        logger.exception("Constraint coverage check failed for agent '%s'", agent_id)
        return 0.0


def _score_posture_level(
    agent_id: str,
    trust_store: TrustStore,
) -> float:
    """Factor 4: Posture level. Higher posture = higher trust."""
    try:
        history = trust_store.get_posture_history(agent_id)
        if not history:
            return 0.0

        # Get the latest posture from the history (last record's to_posture)
        latest = history[-1]
        posture_value = latest.get("to_posture", "")

        return POSTURE_SCORES.get(posture_value, 0.0)
    except Exception:
        logger.exception("Posture level check failed for agent '%s'", agent_id)
        return 0.0


def _score_chain_recency(
    agent_id: str,
    trust_store: TrustStore,
) -> float:
    """Factor 5: Chain recency. 1.0 if < 30 days, linear decay to 0.0 at 365 days.

    Uses the timestamp of the delegation record that delegates TO this agent.
    If no timestamp is available, returns 0.0.
    """
    try:
        delegations = trust_store.get_delegations_for(agent_id)
        inbound = [
            d
            for d in delegations
            if d.get("delegatee_id") == agent_id and not d.get("revoked", False)
        ]

        if not inbound:
            # If agent is genesis authority, check genesis timestamp
            genesis = trust_store.get_genesis(agent_id)
            if genesis is not None:
                timestamp_str = genesis.get("timestamp")
                if timestamp_str:
                    return _recency_score_from_timestamp(timestamp_str)
            return 0.0

        # Sort inbound by timestamp descending to pick the most recent delegation.
        # Without sorting, list order is store-dependent — the wrong delegation
        # could be used for the recency score (M1 fix).
        def _ts_key(d: dict[str, Any]) -> str:
            return d.get("timestamp") or d.get("created_at") or ""

        inbound.sort(key=_ts_key, reverse=True)

        timestamp_str = _ts_key(inbound[0])
        if not timestamp_str:
            return 0.0

        return _recency_score_from_timestamp(timestamp_str)
    except Exception:
        logger.exception("Chain recency check failed for agent '%s'", agent_id)
        return 0.0


def _recency_score_from_timestamp(timestamp_str: str | datetime) -> float:
    """Compute recency score from a timestamp.

    Returns 1.0 if the timestamp is within the last 30 days, then linear
    decay to 0.0 at 365 days. Future timestamps get 1.0.
    """
    if isinstance(timestamp_str, datetime):
        ts = timestamp_str
    else:
        try:
            ts = datetime.fromisoformat(str(timestamp_str))
        except (ValueError, TypeError):
            return 0.0

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    age_days = (now - ts).total_seconds() / 86_400.0

    if age_days <= _RECENCY_FULL_SCORE_DAYS:
        return 1.0
    if age_days >= _RECENCY_ZERO_SCORE_DAYS:
        return 0.0

    # Linear decay between 30 and 365 days
    decay_range = _RECENCY_ZERO_SCORE_DAYS - _RECENCY_FULL_SCORE_DAYS
    return 1.0 - ((age_days - _RECENCY_FULL_SCORE_DAYS) / decay_range)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def compute_trust_score(
    agent_id: str,
    trust_store: TrustStore,
    governance_engine: GovernanceEngine | None = None,
) -> TrustScore:
    """Compute a weighted trust score for an agent.

    Args:
        agent_id: The agent to score.
        trust_store: Trust store for delegation chains, posture history, envelopes.
        governance_engine: Optional governance engine for envelope resolution.

    Returns:
        TrustScore with total (0.0-1.0), grade (A-F), and per-factor breakdown.

    The function never raises -- all factor computation failures are fail-safe
    to 0.0 for the failed factor (logged at ERROR level). This is intentionally
    fail-OPEN because scoring is observational, not enforcement.
    """
    chain_completeness = _score_chain_completeness(agent_id, trust_store)
    depth_score, _depth = _score_delegation_depth(agent_id, trust_store)
    constraint_coverage = _score_constraint_coverage(agent_id, trust_store, governance_engine)
    posture_level = _score_posture_level(agent_id, trust_store)
    chain_recency = _score_chain_recency(agent_id, trust_store)

    factors = {
        "chain_completeness": chain_completeness,
        "delegation_depth": depth_score,
        "constraint_coverage": constraint_coverage,
        "posture_level": posture_level,
        "chain_recency": chain_recency,
    }

    # Weighted sum
    total = sum(factors[factor_name] * weight for factor_name, weight in FACTOR_WEIGHTS.items())

    # Clamp to [0.0, 1.0] for safety (should already be in range)
    total = max(0.0, min(1.0, total))

    grade = _score_to_grade(total)

    return TrustScore(total=round(total, 4), grade=grade, factors=factors)
