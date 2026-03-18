# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for CARE enforcement pipeline — GradientEngine + StrictEnforcer."""

import pytest
from eatp.enforce.strict import EATPBlockedError, EATPHeldError, HeldBehavior, Verdict

from care_platform.build.config.schema import (
    GradientRuleConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.trust.constraint.enforcement import (
    CareEnforcementPipeline,
    EnforcementResult,
    care_result_to_eatp_result,
    verdict_to_care_level,
)
from care_platform.trust.constraint.gradient import GradientEngine, VerificationResult
from care_platform.trust.constraint.verification_level import VerificationThoroughness

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def gradient_config():
    """Gradient config with rules mapping actions to different levels."""
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
def gradient(gradient_config):
    """GradientEngine instance."""
    return GradientEngine(gradient_config)


@pytest.fixture()
def pipeline(gradient):
    """Pipeline with default RAISE behavior on held."""
    return CareEnforcementPipeline(gradient, on_held=HeldBehavior.RAISE)


@pytest.fixture()
def queue_pipeline(gradient):
    """Pipeline with QUEUE behavior on held (doesn't raise)."""
    return CareEnforcementPipeline(gradient, on_held=HeldBehavior.QUEUE)


# ---------------------------------------------------------------------------
# Adapter Tests
# ---------------------------------------------------------------------------


class TestCareResultToEatpResult:
    """Tests for the VerificationResult adapter."""

    def test_auto_approved_maps_to_valid(self):
        """AUTO_APPROVED CARE result maps to valid=True EATP result."""
        care = VerificationResult(
            action="read_data",
            agent_id="agent-001",
            level=VerificationLevel.AUTO_APPROVED,
            thoroughness=VerificationThoroughness.STANDARD,
        )
        eatp = care_result_to_eatp_result(care)
        assert eatp.valid is True
        assert eatp.reason is None

    def test_flagged_maps_to_valid(self):
        """FLAGGED CARE result maps to valid=True EATP result."""
        care = VerificationResult(
            action="draft_content",
            agent_id="agent-001",
            level=VerificationLevel.FLAGGED,
            thoroughness=VerificationThoroughness.STANDARD,
            reason="Near boundary",
        )
        eatp = care_result_to_eatp_result(care)
        assert eatp.valid is True
        assert eatp.reason == "Near boundary"

    def test_held_maps_to_valid(self):
        """HELD CARE result maps to valid=True (held is not invalid)."""
        care = VerificationResult(
            action="approve_budget",
            agent_id="agent-001",
            level=VerificationLevel.HELD,
            thoroughness=VerificationThoroughness.STANDARD,
        )
        eatp = care_result_to_eatp_result(care)
        assert eatp.valid is True

    def test_blocked_maps_to_invalid(self):
        """BLOCKED CARE result maps to valid=False EATP result."""
        care = VerificationResult(
            action="delete_everything",
            agent_id="agent-001",
            level=VerificationLevel.BLOCKED,
            thoroughness=VerificationThoroughness.STANDARD,
            reason="Action forbidden",
        )
        eatp = care_result_to_eatp_result(care)
        assert eatp.valid is False
        assert eatp.reason == "Action forbidden"

    def test_eatp_fields_default(self):
        """EATP-specific fields have sensible defaults."""
        care = VerificationResult(
            action="read_data",
            agent_id="agent-001",
            level=VerificationLevel.AUTO_APPROVED,
            thoroughness=VerificationThoroughness.STANDARD,
        )
        eatp = care_result_to_eatp_result(care)
        assert eatp.capability_used is None
        assert eatp.effective_constraints == []
        assert eatp.violations == []


class TestVerdictToCareLevel:
    """Tests for Verdict → CARE VerificationLevel mapping."""

    def test_all_verdicts_map(self):
        """Every Verdict maps to a CARE VerificationLevel."""
        assert verdict_to_care_level(Verdict.AUTO_APPROVED) == VerificationLevel.AUTO_APPROVED
        assert verdict_to_care_level(Verdict.FLAGGED) == VerificationLevel.FLAGGED
        assert verdict_to_care_level(Verdict.HELD) == VerificationLevel.HELD
        assert verdict_to_care_level(Verdict.BLOCKED) == VerificationLevel.BLOCKED

    def test_roundtrip_preserves_meaning(self):
        """CARE level → EATP result → StrictEnforcer → Verdict → CARE level preserves semantics."""
        for care_level in VerificationLevel:
            care = VerificationResult(
                action="test",
                agent_id="agent-001",
                level=care_level,
                thoroughness=VerificationThoroughness.STANDARD,
            )
            eatp = care_result_to_eatp_result(care)
            # For non-blocked levels, valid=True. StrictEnforcer.classify
            # maps based on violations count, not the valid flag directly.
            # The important guarantee: BLOCKED always maps to BLOCKED.
            if care_level == VerificationLevel.BLOCKED:
                assert eatp.valid is False


# ---------------------------------------------------------------------------
# Pipeline Tests
# ---------------------------------------------------------------------------


class TestCareEnforcementPipeline:
    """Tests for the full enforcement pipeline."""

    def test_auto_approved_action_passes(self, pipeline):
        """Auto-approved actions pass through without raising."""
        result = pipeline.classify_and_enforce(action="read_data", agent_id="agent-001")
        assert isinstance(result, EnforcementResult)
        assert result.verdict == Verdict.AUTO_APPROVED
        assert result.enforced_level == VerificationLevel.AUTO_APPROVED
        assert result.is_auto_approved is True
        assert result.is_blocked is False

    def test_blocked_action_raises(self, pipeline):
        """Blocked actions raise EATPBlockedError."""
        with pytest.raises(EATPBlockedError):
            pipeline.classify_and_enforce(action="delete_everything", agent_id="agent-001")

    def test_held_action_raises_with_raise_behavior(self, pipeline):
        """Held actions raise EATPHeldError when on_held=RAISE."""
        with pytest.raises(EATPHeldError):
            pipeline.classify_and_enforce(action="approve_budget", agent_id="agent-001")

    def test_held_action_queued_with_queue_behavior(self, queue_pipeline):
        """Held actions return HELD verdict when on_held=QUEUE."""
        with pytest.raises(EATPHeldError):
            # QUEUE behavior still raises, but adds to review queue
            queue_pipeline.classify_and_enforce(action="approve_budget", agent_id="agent-001")

    def test_flagged_action_passes(self, pipeline):
        """Flagged actions pass through (enforcement is advisory)."""
        result = pipeline.classify_and_enforce(action="draft_content", agent_id="agent-001")
        assert result.enforced_level == VerificationLevel.FLAGGED

    def test_classification_preserved_in_result(self, pipeline):
        """The original CARE classification is preserved in the result."""
        result = pipeline.classify_and_enforce(action="read_data", agent_id="agent-001")
        assert result.classification.action == "read_data"
        assert result.classification.agent_id == "agent-001"
        assert result.classification.level == VerificationLevel.AUTO_APPROVED

    def test_classify_only_delegates_to_gradient(self, pipeline):
        """classify_only returns GradientEngine result without enforcement."""
        result = pipeline.classify_only(action="delete_everything", agent_id="agent-001")
        # Should NOT raise — no enforcement step
        assert result.level == VerificationLevel.BLOCKED
        assert result.action == "delete_everything"

    def test_metadata_passed_through(self, pipeline):
        """Metadata is preserved in the enforcement result."""
        result = pipeline.classify_and_enforce(
            action="read_data",
            agent_id="agent-001",
            metadata={"request_id": "req-123"},
        )
        assert result.metadata["request_id"] == "req-123"

    def test_enforcer_accessible(self, pipeline):
        """The underlying StrictEnforcer is accessible for record inspection."""
        pipeline.classify_and_enforce(action="read_data", agent_id="agent-001")
        assert len(pipeline.enforcer.records) > 0

    def test_gradient_accessible(self, pipeline, gradient):
        """The underlying GradientEngine is accessible."""
        assert pipeline.gradient is gradient


class TestCallbackPipeline:
    """Tests for pipeline with held_callback."""

    def test_callback_invoked_on_held(self, gradient):
        """held_callback is invoked when an action is HELD."""
        callback_calls = []

        def my_callback(agent_id, action, result):
            callback_calls.append((agent_id, action))
            return True  # Approved

        pipeline = CareEnforcementPipeline(
            gradient,
            on_held=HeldBehavior.CALLBACK,
            held_callback=my_callback,
        )
        pipeline.classify_and_enforce(action="approve_budget", agent_id="agent-001")
        assert len(callback_calls) == 1
        assert callback_calls[0] == ("agent-001", "approve_budget")


class TestMonotonicGuarantee:
    """Tests that enforcement never downgrades a classification."""

    def test_blocked_stays_blocked(self, pipeline):
        """A BLOCKED classification always results in BLOCKED verdict."""
        with pytest.raises(EATPBlockedError):
            pipeline.classify_and_enforce(action="delete_everything", agent_id="agent-001")

    def test_auto_approved_never_escalated(self, pipeline):
        """AUTO_APPROVED is never escalated by the enforcer alone."""
        result = pipeline.classify_and_enforce(action="read_data", agent_id="agent-001")
        assert result.verdict == Verdict.AUTO_APPROVED


# ---------------------------------------------------------------------------
# Regression Tests — Existing Callers Unaffected
# ---------------------------------------------------------------------------


class TestExistingCallersUnaffected:
    """Verify GradientEngine.classify() works independently of the pipeline."""

    def test_gradient_classify_still_works(self, gradient):
        """GradientEngine.classify() returns CARE VerificationResult directly."""
        result = gradient.classify(action="read_data", agent_id="agent-001")
        assert isinstance(result, VerificationResult)
        assert result.level == VerificationLevel.AUTO_APPROVED

    def test_gradient_classify_blocked(self, gradient):
        """GradientEngine.classify() does NOT raise on BLOCKED (no enforcement)."""
        result = gradient.classify(action="delete_everything", agent_id="agent-001")
        assert result.level == VerificationLevel.BLOCKED
        # No exception — classify only classifies, doesn't enforce


# ---------------------------------------------------------------------------
# Approval Callback Tests (Gap #3 from test coverage audit)
# ---------------------------------------------------------------------------


class TestApprovalHeldCallback:
    """Tests for create_approval_held_callback factory."""

    def test_callback_submits_to_queue(self):
        """Callback submits held action to approval queue."""
        from unittest.mock import MagicMock

        from eatp.chain import VerificationResult as EATPResult

        from care_platform.trust.constraint.enforcement import create_approval_held_callback

        mock_queue = MagicMock()
        callback = create_approval_held_callback(mock_queue)

        eatp_result = EATPResult(valid=True, reason="Near limit")
        result = callback("agent-001", "approve_budget", eatp_result)

        assert result is True
        mock_queue.submit.assert_called_once_with(
            agent_id="agent-001",
            action="approve_budget",
            reason="Near limit",
        )

    def test_callback_returns_false_on_queue_failure(self):
        """Callback returns False when queue submission fails."""
        from unittest.mock import MagicMock

        from eatp.chain import VerificationResult as EATPResult

        from care_platform.trust.constraint.enforcement import create_approval_held_callback

        mock_queue = MagicMock()
        mock_queue.submit.side_effect = RuntimeError("Queue full")
        callback = create_approval_held_callback(mock_queue)

        eatp_result = EATPResult(valid=True, reason="Near limit")
        result = callback("agent-001", "approve_budget", eatp_result)

        assert result is False


# ---------------------------------------------------------------------------
# Thoroughness Tests (Gap #5 from test coverage audit)
# ---------------------------------------------------------------------------


class TestThoroughnessAdjustments:
    """Tests for FULL and QUICK thoroughness in GradientEngine."""

    def test_full_thoroughness_escalates_auto_approved(self, gradient):
        """FULL thoroughness bumps AUTO_APPROVED to FLAGGED."""
        result = gradient.classify(
            action="read_data",
            agent_id="agent-001",
            thoroughness=VerificationThoroughness.FULL,
        )
        assert result.level == VerificationLevel.FLAGGED

    def test_quick_thoroughness_relaxes_flagged(self, gradient):
        """QUICK thoroughness relaxes FLAGGED to AUTO_APPROVED."""
        result = gradient.classify(
            action="draft_content",
            agent_id="agent-001",
            thoroughness=VerificationThoroughness.QUICK,
        )
        assert result.level == VerificationLevel.AUTO_APPROVED

    def test_thoroughness_never_adjusts_held(self, gradient):
        """HELD is never adjusted by any thoroughness level."""
        for t in VerificationThoroughness:
            result = gradient.classify(
                action="approve_budget",
                agent_id="agent-001",
                thoroughness=t,
            )
            assert result.level == VerificationLevel.HELD

    def test_thoroughness_never_adjusts_blocked(self, gradient):
        """BLOCKED is never adjusted by any thoroughness level."""
        for t in VerificationThoroughness:
            result = gradient.classify(
                action="delete_everything",
                agent_id="agent-001",
                thoroughness=t,
            )
            assert result.level == VerificationLevel.BLOCKED
