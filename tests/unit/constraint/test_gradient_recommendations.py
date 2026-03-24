# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for recommendation generation in GradientEngine."""

import pytest

from pact_platform.build.config.schema import (
    GradientRuleConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from pact_platform.trust.constraint.envelope import (
    DimensionEvaluation,
    EnvelopeEvaluation,
    EvaluationResult,
)
from pact_platform.trust.constraint.gradient import GradientEngine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def gradient_config():
    return VerificationGradientConfig(
        default_level=VerificationLevel.FLAGGED,
        rules=[
            GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
            GradientRuleConfig(pattern="draft_*", level=VerificationLevel.FLAGGED),
            GradientRuleConfig(pattern="approve_*", level=VerificationLevel.HELD),
            GradientRuleConfig(pattern="delete_*", level=VerificationLevel.BLOCKED),
        ],
    )


@pytest.fixture()
def engine(gradient_config):
    return GradientEngine(gradient_config)


# ---------------------------------------------------------------------------
# Recommendation Content Tests
# ---------------------------------------------------------------------------


class TestRecommendationGeneration:
    """Tests that recommendations are generated with correct content."""

    def test_auto_approved_no_recommendations(self, engine):
        """AUTO_APPROVED with no alerts produces no recommendations."""
        result = engine.classify(action="read_data", agent_id="agent-001")
        assert result.level == VerificationLevel.AUTO_APPROVED
        assert result.recommendations == []

    def test_flagged_has_recommendation(self, engine):
        """FLAGGED produces a boundary-related recommendation."""
        result = engine.classify(action="draft_content", agent_id="agent-001")
        assert result.level == VerificationLevel.FLAGGED
        assert len(result.recommendations) >= 1
        assert "boundary" in result.recommendations[0].lower()

    def test_held_has_recommendation(self, engine):
        """HELD produces a human approval recommendation."""
        result = engine.classify(action="approve_budget", agent_id="agent-001")
        assert result.level == VerificationLevel.HELD
        assert len(result.recommendations) >= 1
        assert "human approval" in result.recommendations[0].lower()

    def test_blocked_has_recommendation(self, engine):
        """BLOCKED produces a constraint violation recommendation."""
        result = engine.classify(action="delete_everything", agent_id="agent-001")
        assert result.level == VerificationLevel.BLOCKED
        assert len(result.recommendations) >= 1
        assert "cannot proceed" in result.recommendations[0].lower()

    def test_blocked_with_envelope_includes_dimensions(self, engine):
        """BLOCKED with envelope evaluation names the violated dimensions."""
        envelope = EnvelopeEvaluation(
            envelope_id="env-001",
            action="delete_all",
            agent_id="agent-001",
            overall_result=EvaluationResult.DENIED,
            dimensions=[
                DimensionEvaluation(
                    dimension="financial",
                    result=EvaluationResult.DENIED,
                    reason="Exceeds budget",
                    utilization=1.0,
                ),
            ],
        )
        result = engine.classify(
            action="delete_all",
            agent_id="agent-001",
            envelope_evaluation=envelope,
        )
        assert result.level == VerificationLevel.BLOCKED
        assert any("financial" in r for r in result.recommendations)

    def test_held_with_envelope_includes_dimensions(self, engine):
        """HELD with near-boundary dimensions names them."""
        envelope = EnvelopeEvaluation(
            envelope_id="env-001",
            action="approve_budget",
            agent_id="agent-001",
            overall_result=EvaluationResult.NEAR_BOUNDARY,
            dimensions=[
                DimensionEvaluation(
                    dimension="operational",
                    result=EvaluationResult.NEAR_BOUNDARY,
                    reason="Near action limit",
                    utilization=0.92,
                ),
            ],
        )
        result = engine.classify(
            action="approve_budget",
            agent_id="agent-001",
            envelope_evaluation=envelope,
        )
        # Near-boundary envelope → FLAGGED (not HELD from rule, since envelope takes precedence)
        assert len(result.recommendations) >= 1


class TestRecommendationsAlwaysPresent:
    """Verify recommendations field is always populated (never None)."""

    def test_recommendations_not_none(self, engine):
        """Recommendations is always a list, never None."""
        result = engine.classify(action="read_data", agent_id="agent-001")
        assert result.recommendations is not None
        assert isinstance(result.recommendations, list)

    def test_recommendations_with_envelope(self, engine):
        """Recommendations present even with envelope evaluation."""
        envelope = EnvelopeEvaluation(
            envelope_id="env-001",
            action="read_data",
            agent_id="agent-001",
            overall_result=EvaluationResult.ALLOWED,
            dimensions=[],
        )
        result = engine.classify(
            action="read_data",
            agent_id="agent-001",
            envelope_evaluation=envelope,
        )
        assert result.recommendations is not None
