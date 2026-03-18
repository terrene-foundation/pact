# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the verification gradient engine."""

from care_platform.build.config.schema import (
    GradientRuleConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.trust.constraint.envelope import EnvelopeEvaluation, EvaluationResult
from care_platform.trust.constraint.gradient import (
    GradientEngine,
    VerificationThoroughness,
)


def _make_engine(*rules, default=VerificationLevel.HELD) -> GradientEngine:
    config = VerificationGradientConfig(rules=list(rules), default_level=default)
    return GradientEngine(config)


class TestGradientClassification:
    def test_default_level_when_no_rules(self):
        engine = _make_engine(default=VerificationLevel.HELD)
        result = engine.classify("unknown_action", "agent-1")
        assert result.level == VerificationLevel.HELD

    def test_first_matching_rule_wins(self):
        engine = _make_engine(
            GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
            GradientRuleConfig(pattern="read_sensitive", level=VerificationLevel.HELD),
        )
        result = engine.classify("read_sensitive", "agent-1")
        assert result.level == VerificationLevel.AUTO_APPROVED  # first match wins

    def test_blocked_pattern(self):
        engine = _make_engine(
            GradientRuleConfig(pattern="publish_*", level=VerificationLevel.BLOCKED),
        )
        result = engine.classify("publish_post", "agent-1")
        assert result.is_blocked

    def test_auto_approved_pattern(self):
        engine = _make_engine(
            GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
        )
        result = engine.classify("read_metrics", "agent-1")
        assert result.is_auto_approved

    def test_flagged_pattern(self):
        engine = _make_engine(
            GradientRuleConfig(
                pattern="draft_*",
                level=VerificationLevel.FLAGGED,
                reason="Near content boundary",
            ),
        )
        result = engine.classify("draft_post", "agent-1")
        assert result.level == VerificationLevel.FLAGGED
        assert result.matched_rule == "draft_*"

    def test_held_requires_human_approval(self):
        engine = _make_engine(
            GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
        )
        result = engine.classify("send_email", "agent-1")
        assert result.requires_human_approval

    def test_envelope_denied_overrides_rules(self):
        engine = _make_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope_eval = EnvelopeEvaluation(
            envelope_id="env-1",
            action="spend_money",
            agent_id="agent-1",
            overall_result=EvaluationResult.DENIED,
        )
        result = engine.classify("spend_money", "agent-1", envelope_evaluation=envelope_eval)
        assert result.is_blocked

    def test_envelope_near_boundary_flags(self):
        engine = _make_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope_eval = EnvelopeEvaluation(
            envelope_id="env-1",
            action="action",
            agent_id="agent-1",
            overall_result=EvaluationResult.NEAR_BOUNDARY,
        )
        result = engine.classify("action", "agent-1", envelope_evaluation=envelope_eval)
        assert result.level == VerificationLevel.FLAGGED

    def test_duration_recorded(self):
        engine = _make_engine()
        result = engine.classify("action", "agent-1")
        assert result.duration_ms >= 0

    def test_thoroughness_preserved(self):
        engine = _make_engine()
        result = engine.classify("action", "agent-1", thoroughness=VerificationThoroughness.FULL)
        assert result.thoroughness == VerificationThoroughness.FULL


class TestThoroughnessAdjustment:
    """RT4-L3: GradientEngine must actually vary behavior based on thoroughness."""

    def test_full_thoroughness_bumps_auto_approved_to_flagged(self):
        """When thoroughness is FULL, AUTO_APPROVED results should be bumped to FLAGGED."""
        engine = _make_engine(
            GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
        )
        result = engine.classify(
            "read_metrics", "agent-1", thoroughness=VerificationThoroughness.FULL
        )
        assert result.level == VerificationLevel.FLAGGED
        assert result.thoroughness == VerificationThoroughness.FULL

    def test_full_thoroughness_does_not_bump_flagged(self):
        """FULL thoroughness only bumps AUTO_APPROVED; FLAGGED stays FLAGGED."""
        engine = _make_engine(
            GradientRuleConfig(pattern="draft_*", level=VerificationLevel.FLAGGED),
        )
        result = engine.classify(
            "draft_post", "agent-1", thoroughness=VerificationThoroughness.FULL
        )
        assert result.level == VerificationLevel.FLAGGED

    def test_full_thoroughness_does_not_bump_held(self):
        """FULL thoroughness does not change HELD level."""
        engine = _make_engine(
            GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
        )
        result = engine.classify(
            "send_email", "agent-1", thoroughness=VerificationThoroughness.FULL
        )
        assert result.level == VerificationLevel.HELD

    def test_full_thoroughness_does_not_bump_blocked(self):
        """FULL thoroughness does not change BLOCKED level."""
        engine = _make_engine(
            GradientRuleConfig(pattern="publish_*", level=VerificationLevel.BLOCKED),
        )
        result = engine.classify(
            "publish_post", "agent-1", thoroughness=VerificationThoroughness.FULL
        )
        assert result.level == VerificationLevel.BLOCKED

    def test_quick_thoroughness_relaxes_flagged_to_auto_approved(self):
        """When thoroughness is QUICK, FLAGGED results should be relaxed to AUTO_APPROVED."""
        engine = _make_engine(
            GradientRuleConfig(pattern="draft_*", level=VerificationLevel.FLAGGED),
        )
        result = engine.classify(
            "draft_post", "agent-1", thoroughness=VerificationThoroughness.QUICK
        )
        assert result.level == VerificationLevel.AUTO_APPROVED
        assert result.thoroughness == VerificationThoroughness.QUICK

    def test_quick_thoroughness_does_not_relax_held(self):
        """QUICK thoroughness only relaxes FLAGGED; HELD stays HELD."""
        engine = _make_engine(
            GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
        )
        result = engine.classify(
            "send_email", "agent-1", thoroughness=VerificationThoroughness.QUICK
        )
        assert result.level == VerificationLevel.HELD

    def test_quick_thoroughness_does_not_relax_blocked(self):
        """QUICK thoroughness does not change BLOCKED level."""
        engine = _make_engine(
            GradientRuleConfig(pattern="publish_*", level=VerificationLevel.BLOCKED),
        )
        result = engine.classify(
            "publish_post", "agent-1", thoroughness=VerificationThoroughness.QUICK
        )
        assert result.level == VerificationLevel.BLOCKED

    def test_standard_thoroughness_no_adjustment(self):
        """STANDARD thoroughness makes no adjustment to the determined level."""
        engine = _make_engine(
            GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
        )
        result = engine.classify(
            "read_metrics", "agent-1", thoroughness=VerificationThoroughness.STANDARD
        )
        assert result.level == VerificationLevel.AUTO_APPROVED

    def test_full_thoroughness_on_default_level_auto_approved(self):
        """FULL thoroughness bumps AUTO_APPROVED default level to FLAGGED."""
        engine = _make_engine(default=VerificationLevel.AUTO_APPROVED)
        result = engine.classify(
            "any_action", "agent-1", thoroughness=VerificationThoroughness.FULL
        )
        assert result.level == VerificationLevel.FLAGGED

    def test_quick_thoroughness_on_default_level_flagged(self):
        """QUICK thoroughness relaxes FLAGGED default level to AUTO_APPROVED."""
        engine = _make_engine(default=VerificationLevel.FLAGGED)
        result = engine.classify(
            "any_action", "agent-1", thoroughness=VerificationThoroughness.QUICK
        )
        assert result.level == VerificationLevel.AUTO_APPROVED

    def test_envelope_blocked_not_affected_by_quick(self):
        """Envelope DENIED -> BLOCKED is never relaxed, even with QUICK thoroughness."""
        engine = _make_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope_eval = EnvelopeEvaluation(
            envelope_id="env-1",
            action="spend",
            agent_id="agent-1",
            overall_result=EvaluationResult.DENIED,
        )
        result = engine.classify(
            "spend",
            "agent-1",
            thoroughness=VerificationThoroughness.QUICK,
            envelope_evaluation=envelope_eval,
        )
        assert result.level == VerificationLevel.BLOCKED

    def test_envelope_near_boundary_flagged_relaxed_by_quick(self):
        """Envelope NEAR_BOUNDARY -> FLAGGED is relaxed to AUTO_APPROVED by QUICK."""
        engine = _make_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope_eval = EnvelopeEvaluation(
            envelope_id="env-1",
            action="action",
            agent_id="agent-1",
            overall_result=EvaluationResult.NEAR_BOUNDARY,
        )
        result = engine.classify(
            "action",
            "agent-1",
            thoroughness=VerificationThoroughness.QUICK,
            envelope_evaluation=envelope_eval,
        )
        assert result.level == VerificationLevel.AUTO_APPROVED
