# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for care_platform top-level package exports (Task 113).

Validates that all key public types are importable directly from care_platform.
"""


class TestConfigExports:
    """All config types must be importable from care_platform."""

    def test_platform_config(self):
        from care_platform import PlatformConfig

        assert PlatformConfig is not None

    def test_agent_config(self):
        from care_platform import AgentConfig

        assert AgentConfig is not None

    def test_team_config(self):
        from care_platform import TeamConfig

        assert TeamConfig is not None

    def test_workspace_config(self):
        from care_platform import WorkspaceConfig

        assert WorkspaceConfig is not None

    def test_constraint_envelope_config(self):
        from care_platform import ConstraintEnvelopeConfig

        assert ConstraintEnvelopeConfig is not None


class TestConstraintExports:
    """Constraint types must be importable from care_platform."""

    def test_constraint_envelope(self):
        from care_platform import ConstraintEnvelope

        assert ConstraintEnvelope is not None

    def test_gradient_engine(self):
        from care_platform import GradientEngine

        assert GradientEngine is not None

    def test_evaluation_result(self):
        from care_platform import EvaluationResult

        assert EvaluationResult is not None


class TestTrustExports:
    """Trust types must be importable from care_platform."""

    def test_trust_posture(self):
        from care_platform import TrustPosture

        assert TrustPosture is not None

    def test_capability_attestation(self):
        from care_platform import CapabilityAttestation

        assert CapabilityAttestation is not None

    def test_trust_score(self):
        from care_platform import TrustScore

        assert TrustScore is not None

    def test_calculate_trust_score(self):
        from care_platform import calculate_trust_score

        assert callable(calculate_trust_score)


class TestAuditExports:
    """Audit types must be importable from care_platform."""

    def test_audit_anchor(self):
        from care_platform import AuditAnchor

        assert AuditAnchor is not None

    def test_audit_chain(self):
        from care_platform import AuditChain

        assert AuditChain is not None


class TestWorkspaceExports:
    """Workspace types must be importable from care_platform."""

    def test_workspace(self):
        from care_platform import Workspace

        assert Workspace is not None

    def test_workspace_phase(self):
        from care_platform import WorkspacePhase

        assert WorkspacePhase is not None

    def test_workspace_registry(self):
        from care_platform import WorkspaceRegistry

        assert WorkspaceRegistry is not None


class TestExecutionExports:
    """Execution types must be importable from care_platform."""

    def test_agent_definition(self):
        from care_platform import AgentDefinition

        assert AgentDefinition is not None

    def test_team_definition(self):
        from care_platform import TeamDefinition

        assert TeamDefinition is not None


class TestAllExportsConsistent:
    """Verify __all__ is defined and consistent."""

    def test_all_defined(self):
        import care_platform

        assert hasattr(care_platform, "__all__")

    def test_all_contains_key_types(self):
        import care_platform

        expected = [
            "PlatformConfig",
            "AgentConfig",
            "TeamConfig",
            "WorkspaceConfig",
            "ConstraintEnvelopeConfig",
            "ConstraintEnvelope",
            "GradientEngine",
            "EvaluationResult",
            "TrustPosture",
            "CapabilityAttestation",
            "TrustScore",
            "calculate_trust_score",
            "AuditAnchor",
            "AuditChain",
            "Workspace",
            "WorkspacePhase",
            "WorkspaceRegistry",
            "AgentDefinition",
            "TeamDefinition",
        ]
        for name in expected:
            assert name in care_platform.__all__, f"{name} not in __all__"

    def test_all_entries_are_importable(self):
        import care_platform

        for name in care_platform.__all__:
            assert hasattr(care_platform, name), f"{name} in __all__ but not importable"
