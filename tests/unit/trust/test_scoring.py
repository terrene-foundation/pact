# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for trust scoring model."""

from care_platform.build.config.schema import TrustPostureLevel
from care_platform.trust.scoring import (
    TrustFactors,
    TrustGrade,
    calculate_trust_score,
)


class TestTrustScoring:
    def test_perfect_score(self):
        factors = TrustFactors(
            has_genesis=True,
            has_delegation=True,
            has_envelope=True,
            has_attestation=True,
            has_audit_anchor=True,
            delegation_depth=0,
            dimensions_configured=5,
            posture_level=TrustPostureLevel.DELEGATED,
            newest_attestation_age_days=0,
        )
        score = calculate_trust_score("agent-1", factors)
        assert score.overall_score >= 0.95
        assert score.grade == TrustGrade.A_PLUS

    def test_zero_score(self):
        factors = TrustFactors()
        score = calculate_trust_score("agent-1", factors)
        assert score.overall_score < 0.35
        assert score.grade == TrustGrade.F

    def test_partial_chain(self):
        factors = TrustFactors(
            has_genesis=True,
            has_delegation=True,
            has_envelope=True,
            dimensions_configured=3,
            posture_level=TrustPostureLevel.SUPERVISED,
        )
        score = calculate_trust_score("agent-1", factors)
        assert 0.2 < score.overall_score < 0.7

    def test_factors_breakdown(self):
        factors = TrustFactors(
            has_genesis=True,
            has_delegation=True,
            has_envelope=True,
            has_attestation=True,
            has_audit_anchor=True,
        )
        score = calculate_trust_score("agent-1", factors)
        assert "chain_completeness" in score.factors
        assert score.factors["chain_completeness"] == 1.0

    def test_deep_delegation_lowers_score(self):
        shallow = TrustFactors(delegation_depth=1, max_delegation_depth=5)
        deep = TrustFactors(delegation_depth=4, max_delegation_depth=5)
        s1 = calculate_trust_score("a", shallow)
        s2 = calculate_trust_score("a", deep)
        assert s1.factors["delegation_depth"] > s2.factors["delegation_depth"]

    def test_grade_boundaries(self):
        for score_val, expected_grade in [
            (0.96, TrustGrade.A_PLUS),
            (0.86, TrustGrade.A),
            (0.76, TrustGrade.B_PLUS),
            (0.66, TrustGrade.B),
            (0.51, TrustGrade.C),
            (0.36, TrustGrade.D),
            (0.10, TrustGrade.F),
        ]:
            from care_platform.trust.scoring import _score_to_grade

            assert _score_to_grade(score_val) == expected_grade
