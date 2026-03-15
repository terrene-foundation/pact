# M14-T06: Five failure modes with detection, impact, mitigation, recovery

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M14 — CARE Formal Specifications
**Dependencies**: 1301-1304

## What

Implement `FailureMode` enum and `FailureDetector` class for the five CARE-specified failure modes:

1. Trust Chain Break — genesis or delegation invalid
2. Constraint Violation — envelope breached
3. Communication Isolation — bridge failure
4. Audit Gap — missing anchors in chain
5. Posture Regression — agent operating above allowed posture

Each has detection criteria, impact assessment, mitigation procedure, recovery procedure.

## Where

- New: `src/care_platform/resilience/failure_modes.py`

## Evidence

- Unit tests for each failure mode detection, impact calculation, mitigation invocation
