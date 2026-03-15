# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for ShadowEnforcer — parallel trust evaluation that observes without enforcing."""

from datetime import UTC, datetime, timedelta

import pytest

from care_platform.config.schema import (
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.envelope import ConstraintEnvelope
from care_platform.constraint.gradient import GradientEngine
from care_platform.trust.posture import UPGRADE_REQUIREMENTS
from care_platform.trust.shadow_enforcer import (
    ShadowEnforcer,
    ShadowMetrics,
    ShadowReport,
    ShadowResult,
)

# --- Fixtures ---


def _make_envelope(
    max_spend: float = 1000.0,
    allowed_actions: list[str] | None = None,
    blocked_actions: list[str] | None = None,
    max_actions_per_day: int | None = None,
) -> ConstraintEnvelope:
    """Create a ConstraintEnvelope with configurable dimensions."""
    return ConstraintEnvelope(
        config=ConstraintEnvelopeConfig(
            id="test-envelope",
            financial=FinancialConstraintConfig(max_spend_usd=max_spend),
            operational=OperationalConstraintConfig(
                allowed_actions=allowed_actions or [],
                blocked_actions=blocked_actions or [],
                max_actions_per_day=max_actions_per_day,
            ),
        ),
    )


def _make_gradient(
    rules: list[GradientRuleConfig] | None = None,
    default_level: VerificationLevel = VerificationLevel.HELD,
) -> GradientEngine:
    """Create a GradientEngine with configurable rules."""
    return GradientEngine(
        config=VerificationGradientConfig(
            rules=rules or [],
            default_level=default_level,
        ),
    )


def _make_enforcer(
    envelope: ConstraintEnvelope | None = None,
    gradient: GradientEngine | None = None,
) -> ShadowEnforcer:
    """Create a ShadowEnforcer with sensible test defaults."""
    return ShadowEnforcer(
        gradient_engine=gradient or _make_gradient(),
        envelope=envelope or _make_envelope(),
    )


# --- Test: Shadow evaluation does not modify any state ---


class TestShadowEvaluationNoSideEffects:
    """Shadow evaluation must observe without enforcing — no state modification."""

    def test_evaluate_returns_shadow_result(self):
        enforcer = _make_enforcer()
        result = enforcer.evaluate("read_data", "agent-1")
        assert isinstance(result, ShadowResult)

    def test_evaluate_does_not_block_action(self):
        """Even if the action would be blocked, evaluate returns info, not enforcement."""
        envelope = _make_envelope(blocked_actions=["delete_all"])
        enforcer = _make_enforcer(envelope=envelope)
        result = enforcer.evaluate("delete_all", "agent-1")
        assert result.would_be_blocked is True
        # The key point: evaluate returns a result, it does not raise or prevent anything.

    def test_evaluate_populates_all_fields(self):
        enforcer = _make_enforcer()
        result = enforcer.evaluate("read_data", "agent-1")
        assert result.action == "read_data"
        assert result.agent_id == "agent-1"
        assert isinstance(result.would_be_blocked, bool)
        assert isinstance(result.would_be_held, bool)
        assert isinstance(result.would_be_flagged, bool)
        assert isinstance(result.would_be_auto_approved, bool)
        assert isinstance(result.verification_level, VerificationLevel)
        assert isinstance(result.dimension_results, dict)
        assert isinstance(result.timestamp, datetime)

    def test_evaluate_with_envelope_kwargs(self):
        """Envelope kwargs like spend_amount are forwarded correctly."""
        envelope = _make_envelope(max_spend=100.0)
        enforcer = _make_enforcer(envelope=envelope)
        result = enforcer.evaluate("purchase", "agent-1", spend_amount=200.0)
        assert result.would_be_blocked is True
        assert "financial" in result.dimension_results

    def test_evaluate_records_timestamp(self):
        enforcer = _make_enforcer()
        before = datetime.now(UTC)
        result = enforcer.evaluate("read_data", "agent-1")
        after = datetime.now(UTC)
        assert before <= result.timestamp <= after


# --- Test: Metrics collection accuracy ---


class TestMetricsAccuracy:
    """Metrics must accurately track pass/block/hold/flag counts."""

    def test_empty_metrics_for_unknown_agent(self):
        enforcer = _make_enforcer()
        with pytest.raises(KeyError, match="agent-unknown"):
            enforcer.get_metrics("agent-unknown")

    def test_auto_approved_counted(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("read_data", "agent-1")
        enforcer.evaluate("write_data", "agent-1")
        metrics = enforcer.get_metrics("agent-1")
        assert metrics.total_evaluations == 2
        assert metrics.auto_approved_count == 2

    def test_blocked_counted(self):
        envelope = _make_envelope(blocked_actions=["delete_all"])
        enforcer = _make_enforcer(envelope=envelope)
        enforcer.evaluate("delete_all", "agent-1")
        metrics = enforcer.get_metrics("agent-1")
        assert metrics.blocked_count == 1

    def test_held_counted(self):
        gradient = _make_gradient(default_level=VerificationLevel.HELD)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("review_action", "agent-1")
        metrics = enforcer.get_metrics("agent-1")
        assert metrics.held_count == 1

    def test_flagged_counted(self):
        # Near-boundary spend triggers FLAGGED via envelope -> gradient
        envelope = _make_envelope(max_spend=100.0)
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(envelope=envelope, gradient=gradient)
        # 85% spend is near boundary
        enforcer.evaluate("purchase", "agent-1", spend_amount=85.0)
        metrics = enforcer.get_metrics("agent-1")
        assert metrics.flagged_count == 1

    def test_pass_rate_calculation(self):
        gradient = _make_gradient(
            rules=[
                GradientRuleConfig(
                    pattern="safe_*", level=VerificationLevel.AUTO_APPROVED, reason="safe"
                ),
            ],
            default_level=VerificationLevel.BLOCKED,
        )
        enforcer = _make_enforcer(gradient=gradient)
        # 3 auto-approved
        enforcer.evaluate("safe_read", "agent-1")
        enforcer.evaluate("safe_write", "agent-1")
        enforcer.evaluate("safe_list", "agent-1")
        # 1 blocked
        enforcer.evaluate("dangerous_action", "agent-1")
        metrics = enforcer.get_metrics("agent-1")
        assert metrics.total_evaluations == 4
        assert metrics.pass_rate == pytest.approx(0.75)

    def test_block_rate_calculation(self):
        gradient = _make_gradient(default_level=VerificationLevel.BLOCKED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("action1", "agent-1")
        enforcer.evaluate("action2", "agent-1")
        metrics = enforcer.get_metrics("agent-1")
        assert metrics.block_rate == pytest.approx(1.0)

    def test_pass_rate_zero_evaluations(self):
        """ShadowMetrics with zero evaluations should return 0.0 for pass_rate."""
        now = datetime.now(UTC)
        metrics = ShadowMetrics(
            agent_id="agent-1",
            window_start=now,
            window_end=now,
        )
        assert metrics.pass_rate == 0.0

    def test_block_rate_zero_evaluations(self):
        """ShadowMetrics with zero evaluations should return 0.0 for block_rate."""
        now = datetime.now(UTC)
        metrics = ShadowMetrics(
            agent_id="agent-1",
            window_start=now,
            window_end=now,
        )
        assert metrics.block_rate == 0.0


# --- Test: Per-dimension breakdown tracking ---


class TestDimensionBreakdown:
    """ShadowEnforcer must track which dimensions triggered and how often."""

    def test_financial_dimension_tracked(self):
        envelope = _make_envelope(max_spend=100.0)
        enforcer = _make_enforcer(envelope=envelope)
        enforcer.evaluate("purchase", "agent-1", spend_amount=200.0)
        metrics = enforcer.get_metrics("agent-1")
        assert "financial" in metrics.dimension_trigger_counts
        assert metrics.dimension_trigger_counts["financial"] == 1

    def test_operational_dimension_tracked(self):
        envelope = _make_envelope(blocked_actions=["delete_all"])
        enforcer = _make_enforcer(envelope=envelope)
        enforcer.evaluate("delete_all", "agent-1")
        metrics = enforcer.get_metrics("agent-1")
        assert "operational" in metrics.dimension_trigger_counts
        assert metrics.dimension_trigger_counts["operational"] == 1

    def test_multiple_dimensions_tracked_independently(self):
        envelope = _make_envelope(max_spend=100.0, blocked_actions=["delete_all"])
        enforcer = _make_enforcer(envelope=envelope)
        # Trigger financial
        enforcer.evaluate("purchase", "agent-1", spend_amount=200.0)
        # Trigger operational
        enforcer.evaluate("delete_all", "agent-1")
        metrics = enforcer.get_metrics("agent-1")
        assert metrics.dimension_trigger_counts.get("financial", 0) >= 1
        assert metrics.dimension_trigger_counts.get("operational", 0) >= 1

    def test_dimension_results_in_shadow_result(self):
        """Each ShadowResult should contain dimension-level results."""
        envelope = _make_envelope(max_spend=100.0)
        enforcer = _make_enforcer(envelope=envelope)
        result = enforcer.evaluate("purchase", "agent-1", spend_amount=200.0)
        assert "financial" in result.dimension_results
        assert result.dimension_results["financial"] == "denied"

    def test_allowed_dimensions_not_counted_as_triggers(self):
        """Dimensions that evaluate to ALLOWED should not increment trigger counts."""
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("safe_action", "agent-1")
        metrics = enforcer.get_metrics("agent-1")
        # No dimensions should have been triggered
        assert len(metrics.dimension_trigger_counts) == 0


# --- Test: Report generation ---


class TestReportGeneration:
    """Reports must contain correct statistics and recommendations."""

    def test_report_returns_shadow_report(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("read_data", "agent-1")
        report = enforcer.generate_report("agent-1")
        assert isinstance(report, ShadowReport)

    def test_report_has_correct_counts(self):
        gradient = _make_gradient(
            rules=[
                GradientRuleConfig(
                    pattern="safe_*", level=VerificationLevel.AUTO_APPROVED, reason="safe"
                ),
            ],
            default_level=VerificationLevel.BLOCKED,
        )
        enforcer = _make_enforcer(gradient=gradient)
        for _ in range(8):
            enforcer.evaluate("safe_action", "agent-1")
        for _ in range(2):
            enforcer.evaluate("dangerous_action", "agent-1")
        report = enforcer.generate_report("agent-1")
        assert report.total_evaluations == 10
        assert report.pass_rate == pytest.approx(0.8)
        assert report.block_rate == pytest.approx(0.2)

    def test_report_dimension_breakdown(self):
        envelope = _make_envelope(max_spend=100.0)
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(envelope=envelope, gradient=gradient)
        # 2 financial triggers out of 4 total
        enforcer.evaluate("purchase", "agent-1", spend_amount=200.0)
        enforcer.evaluate("purchase", "agent-1", spend_amount=200.0)
        enforcer.evaluate("read_data", "agent-1")
        enforcer.evaluate("read_data", "agent-1")
        report = enforcer.generate_report("agent-1")
        assert "financial" in report.dimension_breakdown
        assert report.dimension_breakdown["financial"] == pytest.approx(0.5)

    def test_report_for_unknown_agent_raises(self):
        enforcer = _make_enforcer()
        with pytest.raises(KeyError, match="agent-unknown"):
            enforcer.generate_report("agent-unknown")

    def test_report_upgrade_eligible_field(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("read_data", "agent-1")
        report = enforcer.generate_report("agent-1")
        assert isinstance(report.upgrade_eligible, bool)

    def test_report_upgrade_blockers_populated_when_ineligible(self):
        gradient = _make_gradient(default_level=VerificationLevel.BLOCKED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("dangerous", "agent-1")
        report = enforcer.generate_report("agent-1")
        assert report.upgrade_eligible is False
        assert len(report.upgrade_blockers) > 0

    def test_report_recommendation_non_empty(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("read_data", "agent-1")
        report = enforcer.generate_report("agent-1")
        assert len(report.recommendation) > 0


# --- Test: PostureEvidence conversion ---


class TestPostureEvidenceConversion:
    """to_posture_evidence() must correctly map shadow metrics to PostureEvidence."""

    def test_conversion_returns_posture_evidence(self):
        from care_platform.trust.posture import PostureEvidence

        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("action1", "agent-1")
        evidence = enforcer.to_posture_evidence("agent-1")
        assert isinstance(evidence, PostureEvidence)

    def test_total_operations_mapped(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        for _ in range(5):
            enforcer.evaluate("action", "agent-1")
        evidence = enforcer.to_posture_evidence("agent-1")
        assert evidence.total_operations == 5

    def test_successful_operations_mapped(self):
        """Auto-approved actions count as successful operations."""
        gradient = _make_gradient(
            rules=[
                GradientRuleConfig(
                    pattern="safe_*", level=VerificationLevel.AUTO_APPROVED, reason="safe"
                ),
            ],
            default_level=VerificationLevel.BLOCKED,
        )
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("safe_action", "agent-1")
        enforcer.evaluate("safe_other", "agent-1")
        enforcer.evaluate("dangerous", "agent-1")
        evidence = enforcer.to_posture_evidence("agent-1")
        assert evidence.successful_operations == 2
        assert evidence.total_operations == 3

    def test_shadow_pass_rate_mapped(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        for _ in range(10):
            enforcer.evaluate("action", "agent-1")
        evidence = enforcer.to_posture_evidence("agent-1")
        assert evidence.shadow_enforcer_pass_rate == pytest.approx(1.0)

    def test_blocked_mapped_to_shadow_blocked_count(self):
        """Blocked actions are mapped to shadow_blocked_count (informational), NOT incidents."""
        gradient = _make_gradient(default_level=VerificationLevel.BLOCKED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("bad_action", "agent-1")
        enforcer.evaluate("bad_action_2", "agent-1")
        evidence = enforcer.to_posture_evidence("agent-1")
        assert evidence.shadow_blocked_count == 2
        assert evidence.incidents == 0  # shadow blocks are not real incidents

    def test_evidence_for_unknown_agent_raises(self):
        enforcer = _make_enforcer()
        with pytest.raises(KeyError, match="agent-unknown"):
            enforcer.to_posture_evidence("agent-unknown")

    def test_evidence_compatible_with_upgrade_requirements(self):
        """PostureEvidence fields match what UPGRADE_REQUIREMENTS expects."""
        from care_platform.config.schema import TrustPostureLevel

        # Verify requirements exist for SHARED_PLANNING (first upgrade target)
        assert TrustPostureLevel.SHARED_PLANNING in UPGRADE_REQUIREMENTS
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("action", "agent-1")
        evidence = enforcer.to_posture_evidence("agent-1")
        # Evidence must have all the fields that upgrade requirements check
        assert hasattr(evidence, "successful_operations")
        assert hasattr(evidence, "total_operations")
        assert hasattr(evidence, "shadow_enforcer_pass_rate")
        assert hasattr(evidence, "incidents")
        assert hasattr(evidence, "days_at_current_posture")
        # shadow_enforcer_pass_rate must be set (not None)
        assert evidence.shadow_enforcer_pass_rate is not None


# --- Test: Window-based metrics filtering ---


class TestWindowBasedMetrics:
    """get_metrics_window() must filter results to the specified time window."""

    def test_window_returns_shadow_metrics(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("action", "agent-1")
        metrics = enforcer.get_metrics_window("agent-1", days=30)
        assert isinstance(metrics, ShadowMetrics)

    def test_window_filters_old_results(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)

        # Inject an old result directly into the internal state
        old_result = ShadowResult(
            action="old_action",
            agent_id="agent-1",
            would_be_blocked=False,
            would_be_held=False,
            would_be_flagged=False,
            would_be_auto_approved=True,
            verification_level=VerificationLevel.AUTO_APPROVED,
            dimension_results={},
            timestamp=datetime.now(UTC) - timedelta(days=60),
        )
        enforcer._results.append(old_result)

        # Add a recent result through the normal API
        enforcer.evaluate("recent_action", "agent-1")

        # 7-day window should only include the recent result
        metrics = enforcer.get_metrics_window("agent-1", days=7)
        assert metrics.total_evaluations == 1

    def test_window_includes_results_within_range(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("action1", "agent-1")
        enforcer.evaluate("action2", "agent-1")
        metrics = enforcer.get_metrics_window("agent-1", days=1)
        assert metrics.total_evaluations == 2

    def test_window_has_correct_start_and_end(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("action", "agent-1")
        metrics = enforcer.get_metrics_window("agent-1", days=30)
        assert metrics.window_end >= metrics.window_start
        assert (metrics.window_end - metrics.window_start).days <= 30

    def test_window_for_unknown_agent_raises(self):
        enforcer = _make_enforcer()
        with pytest.raises(KeyError, match="agent-unknown"):
            enforcer.get_metrics_window("agent-unknown", days=30)


# --- Test: Multiple agents tracked independently ---


class TestMultiAgentTracking:
    """Each agent's metrics must be tracked independently."""

    def test_two_agents_independent_counts(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("action1", "agent-a")
        enforcer.evaluate("action2", "agent-a")
        enforcer.evaluate("action3", "agent-b")
        metrics_a = enforcer.get_metrics("agent-a")
        metrics_b = enforcer.get_metrics("agent-b")
        assert metrics_a.total_evaluations == 2
        assert metrics_b.total_evaluations == 1

    def test_two_agents_different_verification_outcomes(self):
        gradient = _make_gradient(
            rules=[
                GradientRuleConfig(
                    pattern="safe_*", level=VerificationLevel.AUTO_APPROVED, reason="safe"
                ),
            ],
            default_level=VerificationLevel.BLOCKED,
        )
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("safe_action", "agent-a")
        enforcer.evaluate("dangerous", "agent-b")
        metrics_a = enforcer.get_metrics("agent-a")
        metrics_b = enforcer.get_metrics("agent-b")
        assert metrics_a.auto_approved_count == 1
        assert metrics_a.blocked_count == 0
        assert metrics_b.auto_approved_count == 0
        assert metrics_b.blocked_count == 1

    def test_agent_id_stored_in_metrics(self):
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = _make_enforcer(gradient=gradient)
        enforcer.evaluate("action", "agent-x")
        metrics = enforcer.get_metrics("agent-x")
        assert metrics.agent_id == "agent-x"

    def test_reports_for_different_agents_independent(self):
        gradient = _make_gradient(
            rules=[
                GradientRuleConfig(
                    pattern="safe_*", level=VerificationLevel.AUTO_APPROVED, reason="safe"
                ),
            ],
            default_level=VerificationLevel.BLOCKED,
        )
        enforcer = _make_enforcer(gradient=gradient)
        # agent-a: all safe
        for _ in range(5):
            enforcer.evaluate("safe_action", "agent-a")
        # agent-b: all blocked
        for _ in range(3):
            enforcer.evaluate("dangerous", "agent-b")
        report_a = enforcer.generate_report("agent-a")
        report_b = enforcer.generate_report("agent-b")
        assert report_a.pass_rate == pytest.approx(1.0)
        assert report_b.pass_rate == pytest.approx(0.0)
        assert report_a.total_evaluations == 5
        assert report_b.total_evaluations == 3


# --- Test: Bounded memory (maxlen cap with oldest-10% trimming) ---


class TestBoundedMemory:
    """ShadowEnforcer must cap _results to maxlen, trimming oldest 10% on overflow."""

    def test_maxlen_parameter_accepted(self):
        """ShadowEnforcer accepts maxlen parameter."""
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        envelope = _make_envelope()
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=envelope,
            maxlen=500,
        )
        assert enforcer._maxlen == 500

    def test_default_maxlen_is_10000(self):
        """Default maxlen is 10,000."""
        enforcer = _make_enforcer()
        assert enforcer._maxlen == 10_000

    def test_trimming_at_maxlen(self):
        """Results are trimmed when exceeding maxlen (oldest 10% removed)."""
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=_make_envelope(),
            maxlen=20,
        )
        # Add 21 evaluations -- exceeds maxlen of 20
        for i in range(21):
            enforcer.evaluate(f"action_{i}", "agent-1")
        # After exceeding maxlen=20, oldest 10% (= 2) should be trimmed
        # 21 results exceeded 20, so trim 2 oldest -> 19 remain
        assert len(enforcer._results) == 19

    def test_trimming_preserves_newest_results(self):
        """Trimming removes the oldest results, preserving the newest."""
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=_make_envelope(),
            maxlen=10,
        )
        for i in range(11):
            enforcer.evaluate(f"action_{i}", "agent-1")
        # Oldest 10% of 11 = 1 trimmed -> 10 remain
        # The oldest action_0 should be gone
        actions = [r.action for r in enforcer._results]
        assert "action_0" not in actions
        assert "action_10" in actions

    def test_trimming_logs_warning(self, caplog):
        """Trimming logs a warning with context."""
        import logging

        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=_make_envelope(),
            maxlen=10,
        )
        with caplog.at_level(logging.WARNING):
            for i in range(11):
                enforcer.evaluate(f"action_{i}", "agent-1")
        assert any("trimm" in record.message.lower() for record in caplog.records)

    def test_multiple_trims_keep_bounded(self):
        """Repeated overflow triggers keep results bounded."""
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=_make_envelope(),
            maxlen=10,
        )
        for i in range(50):
            enforcer.evaluate(f"action_{i}", "agent-1")
        # Results should never exceed maxlen
        assert len(enforcer._results) <= 10


# --- Test: Thread safety ---


class TestThreadSafety:
    """Multiple threads must be able to evaluate concurrently without data corruption."""

    def test_concurrent_evaluations(self):
        """Multiple threads can evaluate concurrently without errors."""
        import threading

        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=_make_envelope(),
            maxlen=10_000,
        )
        errors: list[Exception] = []

        def worker(thread_id: int):
            try:
                for i in range(50):
                    enforcer.evaluate(f"action_{i}", f"agent-{thread_id}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # 10 threads x 50 evaluations = 500 total results
        assert len(enforcer._results) == 500

    def test_concurrent_evaluate_and_get_metrics_window(self):
        """get_metrics_window is safe to call while evaluate() is running."""
        import threading

        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=_make_envelope(),
            maxlen=10_000,
        )
        # Seed some data first
        for i in range(10):
            enforcer.evaluate(f"seed_{i}", "agent-1")
        errors: list[Exception] = []

        def writer():
            try:
                for i in range(100):
                    enforcer.evaluate(f"write_{i}", "agent-1")
            except Exception as exc:
                errors.append(exc)

        def reader():
            try:
                for _ in range(100):
                    enforcer.get_metrics_window("agent-1", days=30)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# --- Test: Change rate metric ---


class TestChangeRate:
    """ShadowMetrics must track change_rate (delta between pass rates)."""

    def test_change_rate_on_metrics(self):
        """ShadowMetrics has change_rate property."""
        now = datetime.now(UTC)
        metrics = ShadowMetrics(
            agent_id="agent-1",
            window_start=now,
            window_end=now,
        )
        assert hasattr(metrics, "change_rate")
        assert isinstance(metrics.change_rate, float)

    def test_change_rate_initially_zero(self):
        """Change rate is 0.0 when no evaluations have been recorded (default state)."""
        now = datetime.now(UTC)
        metrics = ShadowMetrics(
            agent_id="agent-1",
            window_start=now,
            window_end=now,
        )
        # No evaluations: pass_rate=0.0, previous_pass_rate=0.0 -> change_rate=0.0
        assert metrics.change_rate == pytest.approx(0.0)

    def test_change_rate_tracks_delta(self):
        """Change rate reflects the delta between previous and current pass rates."""
        gradient = _make_gradient(
            rules=[
                GradientRuleConfig(
                    pattern="safe_*", level=VerificationLevel.AUTO_APPROVED, reason="safe"
                ),
            ],
            default_level=VerificationLevel.BLOCKED,
        )
        enforcer = _make_enforcer(gradient=gradient)
        # First batch: 100% pass rate
        for _ in range(5):
            enforcer.evaluate("safe_action", "agent-1")
        metrics_after_first = enforcer.get_metrics("agent-1")
        # pass_rate = 1.0, previous_pass_rate snapshotted from before last eval
        # Before eval 5: pass_rate was 4/4 = 1.0, so previous_pass_rate = 1.0
        # change_rate = |1.0 - 1.0| = 0.0 (no change within same result type)
        assert metrics_after_first.pass_rate == pytest.approx(1.0)

        # Second batch: now add blocked actions, dropping pass rate
        for _ in range(5):
            enforcer.evaluate("dangerous_action", "agent-1")
        metrics_after_second = enforcer.get_metrics("agent-1")
        # Pass rate is now 0.5, previous was snapshotted before last blocked eval
        # Before eval 10: pass_rate was 5/9 ~= 0.556, after = 5/10 = 0.5
        # change_rate = |0.5 - 0.556| ~= 0.056
        assert metrics_after_second.pass_rate == pytest.approx(0.5)
        assert metrics_after_second.change_rate > 0.0  # rate changed

    def test_previous_pass_rate_field_exists(self):
        """ShadowMetrics has previous_pass_rate field."""
        now = datetime.now(UTC)
        metrics = ShadowMetrics(
            agent_id="agent-1",
            window_start=now,
            window_end=now,
        )
        assert hasattr(metrics, "previous_pass_rate")
        assert metrics.previous_pass_rate == 0.0


# --- Test: Fail-safe error handling ---


class TestFailSafe:
    """evaluate() must NEVER raise an exception — the shadow must never crash the caller."""

    def test_evaluate_with_corrupt_envelope(self):
        """Evaluate returns safe result when envelope evaluation raises."""
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        envelope = _make_envelope()
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=envelope,
        )
        # Corrupt the envelope so evaluate_action raises
        enforcer.envelope = None  # type: ignore[assignment]
        result = enforcer.evaluate("action", "agent-1")
        # Must return a safe result, not raise
        assert isinstance(result, ShadowResult)
        assert result.would_be_blocked is False
        assert result.would_be_auto_approved is True

    def test_evaluate_never_raises(self):
        """evaluate() NEVER raises, even with completely broken inputs."""
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=_make_envelope(),
        )
        # Corrupt gradient engine
        enforcer.gradient = None  # type: ignore[assignment]
        result = enforcer.evaluate("action", "agent-1")
        assert isinstance(result, ShadowResult)
        assert result.would_be_blocked is False
        assert result.would_be_auto_approved is True

    def test_failsafe_result_has_correct_action_and_agent(self):
        """Even on failure, the returned result has the correct action and agent_id."""
        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=_make_envelope(),
        )
        enforcer.envelope = None  # type: ignore[assignment]
        result = enforcer.evaluate("my_action", "my_agent")
        assert result.action == "my_action"
        assert result.agent_id == "my_agent"

    def test_failsafe_logs_error(self, caplog):
        """Fail-safe path logs the error for debugging."""
        import logging

        gradient = _make_gradient(default_level=VerificationLevel.AUTO_APPROVED)
        enforcer = ShadowEnforcer(
            gradient_engine=gradient,
            envelope=_make_envelope(),
        )
        enforcer.envelope = None  # type: ignore[assignment]
        with caplog.at_level(logging.ERROR):
            enforcer.evaluate("action", "agent-1")
        assert any("shadow" in record.message.lower() for record in caplog.records)


# --- Test: RT2-07 Pipeline Paths (Gap #4 from test coverage audit) ---


class TestRT207PipelinePaths:
    """Tests for the full middleware-mirroring pipeline in ShadowEnforcer."""

    def test_halted_system_blocks_everything(self):
        """When system is halted, all actions should be BLOCKED."""
        enforcer = ShadowEnforcer(
            gradient_engine=_make_gradient(default_level=VerificationLevel.AUTO_APPROVED),
            envelope=_make_envelope(),
            halted_check=lambda: True,
        )
        result = enforcer.evaluate("read_data", "agent-1")
        assert result.would_be_blocked is True
        assert result.verification_level == VerificationLevel.BLOCKED
        assert "halt" in result.dimension_results

    def test_not_halted_allows_normal_flow(self):
        """When system is not halted, normal classification proceeds."""
        enforcer = ShadowEnforcer(
            gradient_engine=_make_gradient(default_level=VerificationLevel.AUTO_APPROVED),
            envelope=_make_envelope(),
            halted_check=lambda: False,
        )
        result = enforcer.evaluate("read_data", "agent-1")
        assert result.would_be_blocked is False

    def test_pseudo_agent_posture_blocks_everything(self):
        """PSEUDO_AGENT posture blocks all actions regardless of envelope."""
        enforcer = _make_enforcer()
        result = enforcer.evaluate(
            "read_data", "agent-1", agent_posture=TrustPostureLevel.PSEUDO_AGENT
        )
        assert result.would_be_blocked is True
        assert result.verification_level == VerificationLevel.BLOCKED
        assert "posture" in result.dimension_results

    def test_supervised_posture_escalates_to_held(self):
        """SUPERVISED posture escalates AUTO_APPROVED/FLAGGED to HELD."""
        enforcer = ShadowEnforcer(
            gradient_engine=_make_gradient(default_level=VerificationLevel.AUTO_APPROVED),
            envelope=_make_envelope(),
        )
        result = enforcer.evaluate(
            "read_data", "agent-1", agent_posture=TrustPostureLevel.SUPERVISED
        )
        assert result.would_be_held is True
        assert result.verification_level == VerificationLevel.HELD

    def test_never_delegated_action_forced_to_held(self):
        """Actions in NEVER_DELEGATED_ACTIONS are forced to HELD."""
        enforcer = ShadowEnforcer(
            gradient_engine=_make_gradient(default_level=VerificationLevel.AUTO_APPROVED),
            envelope=_make_envelope(),
        )
        # "modify_constraints" is in NEVER_DELEGATED_ACTIONS
        result = enforcer.evaluate("modify_constraints", "agent-1")
        assert result.would_be_held is True
        assert result.verification_level == VerificationLevel.HELD
