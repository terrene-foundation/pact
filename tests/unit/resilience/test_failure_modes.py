# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Five Failure Modes (M14 Task 1406)."""

import pytest

from pact_platform.trust.resilience.failure_modes import (
    FailureDetector,
    FailureMode,
    FailureSeverity,
    SystemHealth,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def detector():
    return FailureDetector()


# ---------------------------------------------------------------------------
# Test: FailureMode Enum
# ---------------------------------------------------------------------------


class TestFailureModeEnum:
    def test_trust_chain_break_exists(self):
        assert FailureMode.TRUST_CHAIN_BREAK.value == "trust_chain_break"

    def test_constraint_violation_exists(self):
        assert FailureMode.CONSTRAINT_VIOLATION.value == "constraint_violation"

    def test_communication_isolation_exists(self):
        assert FailureMode.COMMUNICATION_ISOLATION.value == "communication_isolation"

    def test_audit_gap_exists(self):
        assert FailureMode.AUDIT_GAP.value == "audit_gap"

    def test_posture_regression_exists(self):
        assert FailureMode.POSTURE_REGRESSION.value == "posture_regression"

    def test_exactly_five_modes(self):
        assert len(FailureMode) == 5


# ---------------------------------------------------------------------------
# Test: FailureSeverity Enum
# ---------------------------------------------------------------------------


class TestFailureSeverity:
    def test_severity_levels_exist(self):
        assert FailureSeverity.LOW is not None
        assert FailureSeverity.MEDIUM is not None
        assert FailureSeverity.HIGH is not None
        assert FailureSeverity.CRITICAL is not None


# ---------------------------------------------------------------------------
# Test: Trust Chain Break Detection
# ---------------------------------------------------------------------------


class TestTrustChainBreakDetection:
    def test_detects_missing_genesis(self, detector):
        health = SystemHealth(
            genesis_valid=False,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        failure_modes = [r.failure_mode for r in results]
        assert FailureMode.TRUST_CHAIN_BREAK in failure_modes

    def test_detects_broken_delegation_chain(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=False,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        failure_modes = [r.failure_mode for r in results]
        assert FailureMode.TRUST_CHAIN_BREAK in failure_modes

    def test_trust_chain_break_has_critical_severity(self, detector):
        health = SystemHealth(
            genesis_valid=False,
            delegation_chain_valid=False,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        trust_results = [r for r in results if r.failure_mode == FailureMode.TRUST_CHAIN_BREAK]
        assert len(trust_results) > 0
        assert trust_results[0].severity == FailureSeverity.CRITICAL


# ---------------------------------------------------------------------------
# Test: Constraint Violation Detection
# ---------------------------------------------------------------------------


class TestConstraintViolationDetection:
    def test_detects_unenforced_constraints(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=True,
            constraints_enforced=False,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        failure_modes = [r.failure_mode for r in results]
        assert FailureMode.CONSTRAINT_VIOLATION in failure_modes

    def test_constraint_violation_severity(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=True,
            constraints_enforced=False,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        constraint_results = [
            r for r in results if r.failure_mode == FailureMode.CONSTRAINT_VIOLATION
        ]
        assert len(constraint_results) > 0
        assert constraint_results[0].severity == FailureSeverity.HIGH


# ---------------------------------------------------------------------------
# Test: Communication Isolation Detection
# ---------------------------------------------------------------------------


class TestCommunicationIsolationDetection:
    def test_detects_isolated_bridges(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=False,
        )
        results = detector.detect(health)
        failure_modes = [r.failure_mode for r in results]
        assert FailureMode.COMMUNICATION_ISOLATION in failure_modes

    def test_communication_isolation_severity(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=False,
        )
        results = detector.detect(health)
        comm_results = [r for r in results if r.failure_mode == FailureMode.COMMUNICATION_ISOLATION]
        assert len(comm_results) > 0
        assert comm_results[0].severity == FailureSeverity.MEDIUM


# ---------------------------------------------------------------------------
# Test: Audit Gap Detection
# ---------------------------------------------------------------------------


class TestAuditGapDetection:
    def test_detects_audit_discontinuity(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=False,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        failure_modes = [r.failure_mode for r in results]
        assert FailureMode.AUDIT_GAP in failure_modes

    def test_audit_gap_severity(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=False,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        audit_results = [r for r in results if r.failure_mode == FailureMode.AUDIT_GAP]
        assert len(audit_results) > 0
        assert audit_results[0].severity == FailureSeverity.HIGH


# ---------------------------------------------------------------------------
# Test: Posture Regression Detection
# ---------------------------------------------------------------------------


class TestPostureRegressionDetection:
    def test_detects_posture_instability(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=False,
            bridges_active=True,
        )
        results = detector.detect(health)
        failure_modes = [r.failure_mode for r in results]
        assert FailureMode.POSTURE_REGRESSION in failure_modes

    def test_posture_regression_severity(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=False,
            bridges_active=True,
        )
        results = detector.detect(health)
        posture_results = [r for r in results if r.failure_mode == FailureMode.POSTURE_REGRESSION]
        assert len(posture_results) > 0
        assert posture_results[0].severity == FailureSeverity.MEDIUM


# ---------------------------------------------------------------------------
# Test: Healthy System
# ---------------------------------------------------------------------------


class TestHealthySystem:
    def test_no_failures_detected_when_healthy(self, detector):
        health = SystemHealth(
            genesis_valid=True,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Test: Multiple Failures
# ---------------------------------------------------------------------------


class TestMultipleFailures:
    def test_detects_multiple_simultaneous_failures(self, detector):
        health = SystemHealth(
            genesis_valid=False,
            delegation_chain_valid=False,
            constraints_enforced=False,
            audit_continuous=False,
            posture_stable=False,
            bridges_active=False,
        )
        results = detector.detect(health)
        failure_modes = {r.failure_mode for r in results}
        assert FailureMode.TRUST_CHAIN_BREAK in failure_modes
        assert FailureMode.CONSTRAINT_VIOLATION in failure_modes
        assert FailureMode.COMMUNICATION_ISOLATION in failure_modes
        assert FailureMode.AUDIT_GAP in failure_modes
        assert FailureMode.POSTURE_REGRESSION in failure_modes

    def test_each_failure_has_mitigation(self, detector):
        health = SystemHealth(
            genesis_valid=False,
            delegation_chain_valid=False,
            constraints_enforced=False,
            audit_continuous=False,
            posture_stable=False,
            bridges_active=False,
        )
        results = detector.detect(health)
        for result in results:
            assert result.mitigation is not None
            assert len(result.mitigation.description) > 0
            assert len(result.mitigation.immediate_actions) > 0

    def test_each_failure_has_recovery_plan(self, detector):
        health = SystemHealth(
            genesis_valid=False,
            delegation_chain_valid=False,
            constraints_enforced=False,
            audit_continuous=False,
            posture_stable=False,
            bridges_active=False,
        )
        results = detector.detect(health)
        for result in results:
            assert result.recovery is not None
            assert len(result.recovery.steps) > 0

    def test_each_failure_has_impact_assessment(self, detector):
        health = SystemHealth(
            genesis_valid=False,
            delegation_chain_valid=False,
            constraints_enforced=False,
            audit_continuous=False,
            posture_stable=False,
            bridges_active=False,
        )
        results = detector.detect(health)
        for result in results:
            assert result.impact_description is not None
            assert len(result.impact_description) > 0


# ---------------------------------------------------------------------------
# Test: Detection Result Structure
# ---------------------------------------------------------------------------


class TestDetectionResultStructure:
    def test_detection_result_has_failure_mode(self, detector):
        health = SystemHealth(
            genesis_valid=False,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        assert len(results) > 0
        result = results[0]
        assert isinstance(result.failure_mode, FailureMode)

    def test_detection_result_has_severity(self, detector):
        health = SystemHealth(
            genesis_valid=False,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        result = results[0]
        assert isinstance(result.severity, FailureSeverity)

    def test_detection_result_has_timestamp(self, detector):
        health = SystemHealth(
            genesis_valid=False,
            delegation_chain_valid=True,
            constraints_enforced=True,
            audit_continuous=True,
            posture_stable=True,
            bridges_active=True,
        )
        results = detector.detect(health)
        result = results[0]
        assert result.detected_at is not None
