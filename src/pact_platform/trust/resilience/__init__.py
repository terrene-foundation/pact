# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Resilience module — failure mode detection, mitigation, and recovery for the PACT.

Implements the five formal failure modes from the CARE specification:
1. Trust Chain Break
2. Constraint Violation
3. Communication Isolation
4. Audit Gap
5. Posture Regression
"""

from pact_platform.trust.resilience.failure_modes import (
    DetectionResult,
    FailureDetector,
    FailureMode,
    FailureSeverity,
    MitigationAction,
    RecoveryPlan,
    SystemHealth,
)

__all__ = [
    "DetectionResult",
    "FailureDetector",
    "FailureMode",
    "FailureSeverity",
    "MitigationAction",
    "RecoveryPlan",
    "SystemHealth",
]
