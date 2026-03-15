# M19-T07: Behavioral test 1 — Constraints enforced, not advisory

**Status**: ACTIVE
**Priority**: High
**Milestone**: M19 — Constrained Organization Validation
**Dependencies**: 1601, 1901

## What

Test that constraints are enforced at runtime. Submit action violating constraint, verify BLOCKED (not just FLAGGED). Verify audit shows rejection.

## Where

- New: `tests/integration/test_behavioral_tests.py`

## Evidence

- Violating action is BLOCKED; audit records rejection
