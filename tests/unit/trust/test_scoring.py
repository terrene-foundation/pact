# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the 5-factor trust scoring system.

Covers:
- Perfect agent (complete chain, shallow depth, all dimensions, DELEGATED, recent) -> A
- Minimal agent (no chain, PSEUDO_AGENT, no dimensions) -> F
- Mixed agent -> B or C
- Grade boundary tests (A/B, B/C, C/D, D/F thresholds)
- Individual factor scoring
- Edge cases: NaN/Inf rejection, cycle detection, missing data
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from pact_platform.trust.scoring import (
    FACTOR_WEIGHTS,
    MAX_DELEGATION_DEPTH,
    POSTURE_SCORES,
    TrustScore,
    _recency_score_from_timestamp,
    _score_chain_completeness,
    _score_chain_recency,
    _score_constraint_coverage,
    _score_delegation_depth,
    _score_posture_level,
    _score_to_grade,
    compute_trust_score,
)
from pact_platform.trust.store.store import MemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_genesis(authority_id: str) -> dict[str, Any]:
    """Build a genesis record dict."""
    return {
        "authority_id": authority_id,
        "public_key": f"pk-{authority_id}",
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _make_delegation(
    delegator_id: str,
    delegatee_id: str,
    *,
    delegation_id: str = "",
    revoked: bool = False,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Build a delegation record dict."""
    d_id = delegation_id or f"del-{delegator_id}-{delegatee_id}"
    ts = timestamp or datetime.now(UTC)
    return {
        "delegation_id": d_id,
        "delegator_id": delegator_id,
        "delegatee_id": delegatee_id,
        "revoked": revoked,
        "timestamp": ts.isoformat(),
    }


def _make_posture_change(
    agent_id: str,
    to_posture: str,
    from_posture: str = "pseudo_agent",
) -> dict[str, Any]:
    """Build a posture change record dict."""
    return {
        "agent_id": agent_id,
        "from_posture": from_posture,
        "to_posture": to_posture,
        "direction": "upgrade",
        "trigger": "manual",
        "changed_by": "admin",
        "changed_at": datetime.now(UTC).isoformat(),
    }


def _make_envelope(
    agent_id: str,
    *,
    financial: dict | None = None,
    operational: dict | None = None,
    temporal: dict | None = None,
    data_access: dict | None = None,
    communication: dict | None = None,
) -> dict[str, Any]:
    """Build an envelope dict with specific constraint dimensions."""
    envelope: dict[str, Any] = {
        "envelope_id": f"env-{agent_id}",
        "agent_id": agent_id,
    }
    if financial is not None:
        envelope["financial"] = financial
    if operational is not None:
        envelope["operational"] = operational
    if temporal is not None:
        envelope["temporal"] = temporal
    if data_access is not None:
        envelope["data_access"] = data_access
    if communication is not None:
        envelope["communication"] = communication
    return envelope


def _build_perfect_agent_store() -> MemoryStore:
    """Build a store with a perfect-score agent."""
    store = MemoryStore()

    # Genesis authority
    store.store_genesis("root-authority", _make_genesis("root-authority"))

    # Direct delegation from genesis to agent (depth=1, recent)
    store.store_delegation(
        "del-root-agent-perfect",
        _make_delegation(
            "root-authority",
            "agent-perfect",
            delegation_id="del-root-agent-perfect",
            timestamp=datetime.now(UTC) - timedelta(days=5),
        ),
    )

    # All 5 constraint dimensions configured
    store.store_envelope(
        "env-agent-perfect",
        _make_envelope(
            "agent-perfect",
            financial={"max_spend_per_action": 100.0},
            operational={"max_daily_actions": 1000},
            temporal={"operating_hours": "24/7"},
            data_access={"allowed_resources": ["*"]},
            communication={"allowed_channels": ["internal"]},
        ),
    )

    # DELEGATED posture (highest)
    store.store_posture_change(
        "agent-perfect",
        _make_posture_change("agent-perfect", "delegated"),
    )

    return store


def _build_minimal_agent_store() -> MemoryStore:
    """Build a store with a minimal-score agent (no chain, no dimensions, no posture)."""
    store = MemoryStore()
    # No genesis, no delegations, no envelopes, no posture history
    # The agent just... exists with nothing.
    return store


# ---------------------------------------------------------------------------
# Test: TrustScore dataclass validation
# ---------------------------------------------------------------------------


class TestTrustScoreValidation:
    def test_valid_construction(self):
        score = TrustScore(total=0.85, grade="B", factors={"chain_completeness": 1.0})
        assert score.total == 0.85
        assert score.grade == "B"
        assert score.factors["chain_completeness"] == 1.0

    def test_frozen(self):
        score = TrustScore(total=0.5, grade="C", factors={})
        with pytest.raises(AttributeError):
            score.total = 0.9  # type: ignore[misc]

    def test_rejects_nan_total(self):
        with pytest.raises(ValueError, match="finite"):
            TrustScore(total=float("nan"), grade="F", factors={})

    def test_rejects_inf_total(self):
        with pytest.raises(ValueError, match="finite"):
            TrustScore(total=float("inf"), grade="A", factors={})

    def test_rejects_out_of_range_total(self):
        with pytest.raises(ValueError, match="\\[0.0, 1.0\\]"):
            TrustScore(total=1.5, grade="A", factors={})

    def test_rejects_negative_total(self):
        with pytest.raises(ValueError, match="\\[0.0, 1.0\\]"):
            TrustScore(total=-0.1, grade="F", factors={})

    def test_rejects_invalid_grade(self):
        with pytest.raises(ValueError, match="A/B/C/D/F"):
            TrustScore(total=0.5, grade="X", factors={})


# ---------------------------------------------------------------------------
# Test: Grade boundaries
# ---------------------------------------------------------------------------


class TestGradeBoundaries:
    def test_grade_a(self):
        assert _score_to_grade(0.9) == "A"
        assert _score_to_grade(1.0) == "A"
        assert _score_to_grade(0.95) == "A"

    def test_grade_b(self):
        assert _score_to_grade(0.75) == "B"
        assert _score_to_grade(0.89) == "B"

    def test_grade_c(self):
        assert _score_to_grade(0.6) == "C"
        assert _score_to_grade(0.74) == "C"

    def test_grade_d(self):
        assert _score_to_grade(0.4) == "D"
        assert _score_to_grade(0.59) == "D"

    def test_grade_f(self):
        assert _score_to_grade(0.39) == "F"
        assert _score_to_grade(0.0) == "F"

    def test_exact_boundary_a_b(self):
        """0.9 is A, 0.8999 is B."""
        assert _score_to_grade(0.9) == "A"
        assert _score_to_grade(0.8999) == "B"

    def test_exact_boundary_b_c(self):
        """0.75 is B, 0.7499 is C."""
        assert _score_to_grade(0.75) == "B"
        assert _score_to_grade(0.7499) == "C"

    def test_exact_boundary_c_d(self):
        """0.6 is C, 0.5999 is D."""
        assert _score_to_grade(0.6) == "C"
        assert _score_to_grade(0.5999) == "D"

    def test_exact_boundary_d_f(self):
        """0.4 is D, 0.3999 is F."""
        assert _score_to_grade(0.4) == "D"
        assert _score_to_grade(0.3999) == "F"


# ---------------------------------------------------------------------------
# Test: Factor weights
# ---------------------------------------------------------------------------


class TestFactorWeights:
    def test_weights_sum_to_one(self):
        assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 1e-9

    def test_all_weights_positive(self):
        for name, weight in FACTOR_WEIGHTS.items():
            assert weight > 0, f"Weight for {name} must be positive"


# ---------------------------------------------------------------------------
# Test: Factor 1 — Chain completeness
# ---------------------------------------------------------------------------


class TestChainCompleteness:
    def test_complete_chain_genesis_direct(self):
        """Agent IS the genesis authority -> 1.0."""
        store = MemoryStore()
        store.store_genesis("agent-1", _make_genesis("agent-1"))
        assert _score_chain_completeness("agent-1", store) == 1.0

    def test_complete_chain_one_hop(self):
        """Genesis -> delegator -> agent -> 1.0."""
        store = MemoryStore()
        store.store_genesis("root", _make_genesis("root"))
        store.store_delegation("d1", _make_delegation("root", "agent-1", delegation_id="d1"))
        assert _score_chain_completeness("agent-1", store) == 1.0

    def test_broken_chain_no_delegation(self):
        """Agent has no inbound delegation and is not genesis -> 0.0."""
        store = MemoryStore()
        assert _score_chain_completeness("orphan-agent", store) == 0.0

    def test_broken_chain_revoked_delegation(self):
        """All inbound delegations are revoked -> 0.0."""
        store = MemoryStore()
        store.store_genesis("root", _make_genesis("root"))
        store.store_delegation(
            "d1",
            _make_delegation("root", "agent-1", delegation_id="d1", revoked=True),
        )
        assert _score_chain_completeness("agent-1", store) == 0.0

    def test_cycle_detection(self):
        """Cyclic delegation graph -> 0.0."""
        store = MemoryStore()
        store.store_delegation("d1", _make_delegation("agent-a", "agent-b", delegation_id="d1"))
        store.store_delegation("d2", _make_delegation("agent-b", "agent-a", delegation_id="d2"))
        assert _score_chain_completeness("agent-a", store) == 0.0


# ---------------------------------------------------------------------------
# Test: Factor 2 — Delegation depth
# ---------------------------------------------------------------------------


class TestDelegationDepth:
    def test_genesis_direct_depth_zero(self):
        """Agent IS genesis -> depth=0, score=1.0."""
        store = MemoryStore()
        store.store_genesis("agent-1", _make_genesis("agent-1"))
        score, depth = _score_delegation_depth("agent-1", store)
        assert depth == 0
        assert score == 1.0

    def test_one_hop_depth(self):
        """One delegation hop -> depth=1."""
        store = MemoryStore()
        store.store_genesis("root", _make_genesis("root"))
        store.store_delegation("d1", _make_delegation("root", "agent-1", delegation_id="d1"))
        score, depth = _score_delegation_depth("agent-1", store)
        assert depth == 1
        assert score == pytest.approx(1.0 - (1 / MAX_DELEGATION_DEPTH))

    def test_no_chain_zero_score(self):
        """No delegation chain -> score=0.0."""
        store = MemoryStore()
        score, _depth = _score_delegation_depth("orphan", store)
        assert score == 0.0


# ---------------------------------------------------------------------------
# Test: Factor 3 — Constraint coverage
# ---------------------------------------------------------------------------


class TestConstraintCoverage:
    def test_all_five_dimensions(self):
        """All 5 constraint dimensions configured -> 1.0."""
        store = MemoryStore()
        store.store_envelope(
            "env-1",
            _make_envelope(
                "agent-1",
                financial={"max": 100},
                operational={"max": 10},
                temporal={"hours": "9-17"},
                data_access={"allowed": ["*"]},
                communication={"channels": ["slack"]},
            ),
        )
        assert _score_constraint_coverage("agent-1", store, None) == 1.0

    def test_three_dimensions(self):
        """3 of 5 dimensions -> 0.6."""
        store = MemoryStore()
        store.store_envelope(
            "env-1",
            _make_envelope(
                "agent-1",
                financial={"max": 100},
                operational={"max": 10},
                temporal={"hours": "9-17"},
            ),
        )
        assert _score_constraint_coverage("agent-1", store, None) == pytest.approx(0.6)

    def test_no_envelope(self):
        """No envelope at all -> 0.0."""
        store = MemoryStore()
        assert _score_constraint_coverage("agent-1", store, None) == 0.0

    def test_zero_dimensions(self):
        """Envelope with no recognized dimensions -> 0.0."""
        store = MemoryStore()
        store.store_envelope(
            "env-1",
            {"envelope_id": "env-1", "agent_id": "agent-1", "description": "empty"},
        )
        assert _score_constraint_coverage("agent-1", store, None) == 0.0


# ---------------------------------------------------------------------------
# Test: Factor 4 — Posture level
# ---------------------------------------------------------------------------


class TestPostureLevel:
    def test_delegated_posture(self):
        store = MemoryStore()
        store.store_posture_change("agent-1", _make_posture_change("agent-1", "delegated"))
        assert _score_posture_level("agent-1", store) == 1.0

    def test_pseudo_agent_posture(self):
        store = MemoryStore()
        store.store_posture_change("agent-1", _make_posture_change("agent-1", "pseudo_agent"))
        assert _score_posture_level("agent-1", store) == 0.0

    def test_supervised_posture(self):
        store = MemoryStore()
        store.store_posture_change("agent-1", _make_posture_change("agent-1", "supervised"))
        assert _score_posture_level("agent-1", store) == 0.25

    def test_no_posture_history(self):
        store = MemoryStore()
        assert _score_posture_level("agent-1", store) == 0.0

    def test_all_posture_values(self):
        """Verify all posture values have expected scores."""
        for posture_value, expected_score in POSTURE_SCORES.items():
            store = MemoryStore()
            store.store_posture_change("agent-x", _make_posture_change("agent-x", posture_value))
            assert (
                _score_posture_level("agent-x", store) == expected_score
            ), f"Posture {posture_value} should score {expected_score}"


# ---------------------------------------------------------------------------
# Test: Factor 5 — Chain recency
# ---------------------------------------------------------------------------


class TestChainRecency:
    def test_recent_delegation_full_score(self):
        """Delegation < 30 days ago -> 1.0."""
        store = MemoryStore()
        store.store_genesis("root", _make_genesis("root"))
        store.store_delegation(
            "d1",
            _make_delegation(
                "root",
                "agent-1",
                delegation_id="d1",
                timestamp=datetime.now(UTC) - timedelta(days=5),
            ),
        )
        score = _score_chain_recency("agent-1", store)
        assert score == 1.0

    def test_old_delegation_zero_score(self):
        """Delegation >= 365 days ago -> 0.0."""
        store = MemoryStore()
        store.store_genesis("root", _make_genesis("root"))
        store.store_delegation(
            "d1",
            _make_delegation(
                "root",
                "agent-1",
                delegation_id="d1",
                timestamp=datetime.now(UTC) - timedelta(days=400),
            ),
        )
        score = _score_chain_recency("agent-1", store)
        assert score == 0.0

    def test_mid_decay_delegation(self):
        """Delegation ~197 days ago -> roughly 0.5 (midpoint of 30-365 range)."""
        store = MemoryStore()
        store.store_genesis("root", _make_genesis("root"))
        midpoint_days = 30 + (365 - 30) / 2  # ~197.5 days
        store.store_delegation(
            "d1",
            _make_delegation(
                "root",
                "agent-1",
                delegation_id="d1",
                timestamp=datetime.now(UTC) - timedelta(days=midpoint_days),
            ),
        )
        score = _score_chain_recency("agent-1", store)
        assert score == pytest.approx(0.5, abs=0.02)

    def test_genesis_authority_recency(self):
        """Genesis authority uses genesis timestamp for recency."""
        store = MemoryStore()
        genesis = _make_genesis("agent-1")
        genesis["timestamp"] = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        store.store_genesis("agent-1", genesis)
        score = _score_chain_recency("agent-1", store)
        assert score == 1.0

    def test_no_delegation_no_genesis(self):
        """Agent with no delegation and no genesis -> 0.0."""
        store = MemoryStore()
        assert _score_chain_recency("orphan", store) == 0.0


class TestRecencyScoreFromTimestamp:
    def test_recent_timestamp(self):
        ts = datetime.now(UTC) - timedelta(days=10)
        assert _recency_score_from_timestamp(ts.isoformat()) == 1.0

    def test_old_timestamp(self):
        ts = datetime.now(UTC) - timedelta(days=500)
        assert _recency_score_from_timestamp(ts.isoformat()) == 0.0

    def test_future_timestamp(self):
        ts = datetime.now(UTC) + timedelta(days=10)
        assert _recency_score_from_timestamp(ts.isoformat()) == 1.0

    def test_invalid_timestamp(self):
        assert _recency_score_from_timestamp("not-a-date") == 0.0

    def test_datetime_object_directly(self):
        ts = datetime.now(UTC) - timedelta(days=5)
        assert _recency_score_from_timestamp(ts) == 1.0


# ---------------------------------------------------------------------------
# Test: compute_trust_score — integration
# ---------------------------------------------------------------------------


class TestComputeTrustScore:
    def test_perfect_agent_scores_a(self):
        """Agent with complete chain, shallow depth, all dimensions, DELEGATED, recent -> A."""
        store = _build_perfect_agent_store()
        score = compute_trust_score("agent-perfect", store)

        assert score.grade == "A"
        assert score.total >= 0.9
        assert score.factors["chain_completeness"] == 1.0
        assert score.factors["delegation_depth"] > 0.95
        assert score.factors["constraint_coverage"] == 1.0
        assert score.factors["posture_level"] == 1.0
        assert score.factors["chain_recency"] == 1.0

    def test_minimal_agent_scores_f(self):
        """Agent with no chain, no dimensions, no posture -> F."""
        store = _build_minimal_agent_store()
        score = compute_trust_score("ghost-agent", store)

        assert score.grade == "F"
        assert score.total < 0.4
        assert score.factors["chain_completeness"] == 0.0
        assert score.factors["delegation_depth"] == 0.0
        assert score.factors["constraint_coverage"] == 0.0
        assert score.factors["posture_level"] == 0.0
        assert score.factors["chain_recency"] == 0.0

    def test_mixed_agent_intermediate_grade(self):
        """Agent with some factors high and others low -> B or C."""
        store = MemoryStore()

        # Complete chain (good) but deep (mediocre)
        store.store_genesis("root", _make_genesis("root"))
        store.store_delegation(
            "d1",
            _make_delegation(
                "root",
                "mid-1",
                delegation_id="d1",
                timestamp=datetime.now(UTC) - timedelta(days=100),
            ),
        )
        store.store_delegation(
            "d2",
            _make_delegation(
                "mid-1",
                "agent-mixed",
                delegation_id="d2",
                timestamp=datetime.now(UTC) - timedelta(days=100),
            ),
        )

        # 3 of 5 dimensions (good but not perfect)
        store.store_envelope(
            "env-mixed",
            _make_envelope(
                "agent-mixed",
                financial={"max": 100},
                operational={"max": 10},
                temporal={"hours": "9-17"},
            ),
        )

        # SHARED_PLANNING posture (middle)
        store.store_posture_change(
            "agent-mixed",
            _make_posture_change("agent-mixed", "shared_planning"),
        )

        score = compute_trust_score("agent-mixed", store)

        assert score.grade in ("B", "C")
        assert 0.5 <= score.total < 0.9
        assert score.factors["chain_completeness"] == 1.0
        assert score.factors["constraint_coverage"] == pytest.approx(0.6)
        assert score.factors["posture_level"] == 0.5

    def test_returns_all_five_factors(self):
        """Result always includes all 5 factor names."""
        store = MemoryStore()
        score = compute_trust_score("any-agent", store)
        expected_factors = {
            "chain_completeness",
            "delegation_depth",
            "constraint_coverage",
            "posture_level",
            "chain_recency",
        }
        assert set(score.factors.keys()) == expected_factors

    def test_total_is_weighted_sum_of_factors(self):
        """Total should equal the weighted sum of individual factors."""
        store = _build_perfect_agent_store()
        score = compute_trust_score("agent-perfect", store)

        expected_total = sum(
            score.factors[name] * weight for name, weight in FACTOR_WEIGHTS.items()
        )
        assert score.total == pytest.approx(round(expected_total, 4), abs=1e-4)

    def test_no_exception_on_empty_store(self):
        """Scoring never raises even with completely empty data."""
        store = MemoryStore()
        score = compute_trust_score("nonexistent-agent", store)
        assert isinstance(score, TrustScore)
        assert score.grade == "F"

    def test_governance_engine_none_is_safe(self):
        """Passing None for governance_engine should work fine."""
        store = _build_perfect_agent_store()
        score = compute_trust_score("agent-perfect", store, governance_engine=None)
        assert score.grade == "A"


# ---------------------------------------------------------------------------
# M1: Chain recency uses most recent inbound delegation
# ---------------------------------------------------------------------------


class TestChainRecencySorting:
    """Verify _score_chain_recency picks the most recent delegation, not first in list."""

    def test_picks_most_recent_delegation(self):
        """With multiple inbound delegations, the newest timestamp should be used."""
        store = MemoryStore()
        now = datetime.now(UTC)
        old_time = now - timedelta(days=200)
        recent_time = now - timedelta(days=5)

        store.store_genesis("root", _make_genesis("root"))
        # Two delegations to the same agent with different timestamps
        store.store_delegation(
            "del-old",
            _make_delegation("root", "agent-1", delegation_id="del-old", timestamp=old_time),
        )
        store.store_delegation(
            "del-new",
            _make_delegation("root", "agent-1", delegation_id="del-new", timestamp=recent_time),
        )

        score = _score_chain_recency("agent-1", store)
        # The recent delegation (5 days old) should give a score near 1.0
        assert score > 0.9, f"Expected high recency score for 5-day-old delegation, got {score}"

    def test_old_delegation_alone_gives_low_score(self):
        """A single old delegation should give a low recency score."""
        store = MemoryStore()
        old_time = datetime.now(UTC) - timedelta(days=300)

        store.store_genesis("root", _make_genesis("root"))
        store.store_delegation(
            "del-old",
            _make_delegation("root", "agent-1", timestamp=old_time),
        )

        score = _score_chain_recency("agent-1", store)
        assert score < 0.3, f"Expected low recency score for 300-day-old delegation, got {score}"


# ---------------------------------------------------------------------------
# M2: Immutable weights and posture scores
# ---------------------------------------------------------------------------


class TestImmutableConstants:
    """Verify FACTOR_WEIGHTS and POSTURE_SCORES cannot be mutated at runtime."""

    def test_factor_weights_immutable(self):
        with pytest.raises(TypeError):
            FACTOR_WEIGHTS["chain_completeness"] = 0.99  # type: ignore[index]

    def test_posture_scores_immutable(self):
        with pytest.raises(TypeError):
            POSTURE_SCORES["delegated"] = 0.0  # type: ignore[index]

    def test_factor_weights_sum_to_one(self):
        total = sum(FACTOR_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_trust_score_factors_immutable(self):
        """C1 fix: TrustScore.factors must not be mutable after construction."""
        score = TrustScore(total=0.5, grade="C", factors={"chain_completeness": 1.0})
        with pytest.raises(TypeError):
            score.factors["chain_completeness"] = 0.0  # type: ignore[index]

    def test_trust_score_factors_isolated_from_source(self):
        """C1 fix: mutating the source dict must not affect the TrustScore."""
        source = {"chain_completeness": 1.0}
        score = TrustScore(total=0.5, grade="C", factors=source)
        source["chain_completeness"] = 0.0
        assert score.factors["chain_completeness"] == 1.0
