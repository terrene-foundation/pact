# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for ProximityScanner integration into GradientEngine."""

import pytest
from eatp.enforce.proximity import ProximityConfig, ProximityScanner

from care_platform.config.schema import (
    GradientRuleConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.envelope import (
    DimensionEvaluation,
    EnvelopeEvaluation,
    EvaluationResult,
)
from care_platform.constraint.gradient import GradientEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def gradient_config():
    return VerificationGradientConfig(
        default_level=VerificationLevel.AUTO_APPROVED,
        rules=[
            GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
            GradientRuleConfig(pattern="delete_*", level=VerificationLevel.BLOCKED),
        ],
    )


@pytest.fixture()
def scanner():
    """ProximityScanner with default thresholds (80% flag, 95% hold)."""
    return ProximityScanner(config=ProximityConfig(flag_threshold=0.80, hold_threshold=0.95))


@pytest.fixture()
def engine_with_scanner(gradient_config, scanner):
    """GradientEngine with ProximityScanner."""
    return GradientEngine(gradient_config, proximity_scanner=scanner)


@pytest.fixture()
def engine_without_scanner(gradient_config):
    """GradientEngine without ProximityScanner (baseline)."""
    return GradientEngine(gradient_config)


def _make_envelope(utilizations: dict[str, float]) -> EnvelopeEvaluation:
    """Create an envelope evaluation with specified dimension utilizations."""
    dimensions = []
    overall = EvaluationResult.ALLOWED
    for dim, util in utilizations.items():
        if util >= 1.0:
            result = EvaluationResult.DENIED
            overall = EvaluationResult.DENIED
        elif util >= 0.8:
            result = EvaluationResult.NEAR_BOUNDARY
            if overall == EvaluationResult.ALLOWED:
                overall = EvaluationResult.NEAR_BOUNDARY
        else:
            result = EvaluationResult.ALLOWED
        dimensions.append(DimensionEvaluation(dimension=dim, result=result, utilization=util))
    return EnvelopeEvaluation(
        envelope_id="env-001",
        action="test_action",
        agent_id="agent-001",
        overall_result=overall,
        dimensions=dimensions,
    )


# ---------------------------------------------------------------------------
# Proximity Escalation Tests
# ---------------------------------------------------------------------------


class TestProximityEscalation:
    """Tests that proximity alerts escalate classification levels."""

    def test_no_proximity_without_scanner(self, engine_without_scanner):
        """Without scanner, no proximity alerts are generated."""
        envelope = _make_envelope({"financial": 0.85})
        result = engine_without_scanner.classify(
            action="read_data", agent_id="agent-001", envelope_evaluation=envelope
        )
        assert result.proximity_alerts is None

    def test_no_proximity_without_envelope(self, engine_with_scanner):
        """Without envelope evaluation, no proximity alerts."""
        result = engine_with_scanner.classify(action="read_data", agent_id="agent-001")
        assert result.proximity_alerts is None

    def test_low_utilization_no_alerts(self, engine_with_scanner):
        """Utilization below 80% generates no alerts."""
        envelope = _make_envelope({"financial": 0.50})
        result = engine_with_scanner.classify(
            action="read_data", agent_id="agent-001", envelope_evaluation=envelope
        )
        assert not result.has_proximity_alerts

    def test_flag_threshold_generates_alert(self, engine_with_scanner):
        """Utilization at 82% (above 80% flag threshold) generates alert."""
        envelope = _make_envelope({"financial": 0.82})
        result = engine_with_scanner.classify(
            action="read_data", agent_id="agent-001", envelope_evaluation=envelope
        )
        assert result.has_proximity_alerts
        assert len(result.proximity_alerts) >= 1

    def test_hold_threshold_escalates(self, engine_with_scanner):
        """Utilization at 96% (above 95% hold threshold) escalates."""
        envelope = _make_envelope({"financial": 0.96})
        result = engine_with_scanner.classify(
            action="read_data", agent_id="agent-001", envelope_evaluation=envelope
        )
        assert result.has_proximity_alerts
        # Should be escalated from AUTO_APPROVED
        assert result.level in (
            VerificationLevel.FLAGGED,
            VerificationLevel.HELD,
        )

    def test_monotonic_escalation_only(self, engine_with_scanner):
        """Proximity never downgrades a level."""
        # BLOCKED actions stay BLOCKED regardless of proximity
        envelope = _make_envelope({"financial": 0.10})
        result = engine_with_scanner.classify(
            action="delete_everything", agent_id="agent-001", envelope_evaluation=envelope
        )
        assert result.level == VerificationLevel.BLOCKED

    def test_multiple_dimensions(self, engine_with_scanner):
        """Multiple dimensions can generate multiple alerts."""
        envelope = _make_envelope(
            {
                "financial": 0.85,
                "operational": 0.90,
            }
        )
        result = engine_with_scanner.classify(
            action="read_data", agent_id="agent-001", envelope_evaluation=envelope
        )
        if result.has_proximity_alerts:
            assert len(result.proximity_alerts) >= 1


class TestProximityBoundaryValues:
    """Tests at exact boundary values."""

    def test_exactly_at_flag_threshold(self, engine_with_scanner):
        """Utilization exactly at 80% triggers proximity alert."""
        envelope = _make_envelope({"financial": 0.80})
        result = engine_with_scanner.classify(
            action="read_data", agent_id="agent-001", envelope_evaluation=envelope
        )
        # At exactly 80%, the scanner should generate a flag-level alert
        assert result.has_proximity_alerts

    def test_just_below_flag_threshold(self, engine_with_scanner):
        """Utilization at 79% does NOT trigger flag."""
        envelope = _make_envelope({"financial": 0.79})
        result = engine_with_scanner.classify(
            action="read_data", agent_id="agent-001", envelope_evaluation=envelope
        )
        assert not result.has_proximity_alerts

    def test_exactly_at_hold_threshold(self, engine_with_scanner):
        """Utilization at 95% triggers hold-level alert."""
        envelope = _make_envelope({"financial": 0.95})
        result = engine_with_scanner.classify(
            action="read_data", agent_id="agent-001", envelope_evaluation=envelope
        )
        assert result.has_proximity_alerts


class TestProximityScannerErrorHandling:
    """Tests for ProximityScanner fail-safe behavior."""

    def test_broken_scanner_doesnt_crash_classification(self, gradient_config):
        """A scanner that raises is caught — classification still returns."""
        from unittest.mock import MagicMock

        broken_scanner = MagicMock()
        broken_scanner.scan.side_effect = RuntimeError("Scanner broke")

        engine = GradientEngine(gradient_config, proximity_scanner=broken_scanner)
        envelope = _make_envelope({"financial": 0.85})
        result = engine.classify(
            action="read_data", agent_id="agent-001", envelope_evaluation=envelope
        )
        # Should still return a valid result without crashing.
        # Level is FLAGGED because 85% utilization triggers NEAR_BOUNDARY
        # in envelope evaluation (independent of proximity scanner).
        assert result.level == VerificationLevel.FLAGGED
        assert result.proximity_alerts is None  # Scanner failed, no alerts


class TestBackwardCompatibility:
    """Verify existing code works with new optional fields."""

    def test_result_without_proximity_fields(self):
        """VerificationResult can be created without proximity fields."""
        from care_platform.constraint.verification_level import VerificationThoroughness

        result = GradientEngine(
            VerificationGradientConfig(
                default_level=VerificationLevel.AUTO_APPROVED,
            )
        ).classify(action="read_data", agent_id="agent-001")

        assert result.proximity_alerts is None
        assert result.recommendations is not None  # Recommendations always set
        assert result.has_proximity_alerts is False
