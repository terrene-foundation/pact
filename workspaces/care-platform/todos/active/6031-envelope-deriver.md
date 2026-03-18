# Task 6031: Create EnvelopeDeriver

**Milestone**: M40
**Priority**: Critical
**Effort**: Medium
**Status**: Active

## Description

Create `EnvelopeDeriver` — a utility that generates valid child constraint envelopes from a parent envelope by applying a tightening factor. Used by `OrgGenerator` to automatically derive department envelopes from the org envelope, and team envelopes from department envelopes, while guaranteeing monotonic tightening.

The deriver takes a parent `ConstraintEnvelope` and a set of tightening parameters (or uses sensible defaults) and returns a child `ConstraintEnvelope` where each dimension's limit is less than or equal to the parent's.

## Acceptance Criteria

- [ ] `EnvelopeDeriver` class created in `src/care_platform/build/org/envelope_deriver.py`
- [ ] `EnvelopeDeriver.derive(parent: ConstraintEnvelope, tightening: float = 0.8) -> ConstraintEnvelope` where `tightening` is a factor (0 < tightening <= 1.0) applied to each numeric dimension
- [ ] `EnvelopeDeriver.derive_for_role(parent: ConstraintEnvelope, role: RoleDefinition) -> ConstraintEnvelope` uses role-specific tightening based on role default posture
- [ ] Derived envelopes always satisfy: `child.X <= parent.X` for all constraint dimensions
- [ ] Derived envelopes are never negative (clamp to 0 minimum)
- [ ] `EnvelopeDeriver` is exported from `care_platform.build.org`
- [ ] Unit tests: derive() with various tightening factors, derive_for_role() for each standard role, verify monotonic property holds

## Dependencies

- Task 6030 (RoleCatalog and RoleDefinition must exist for derive_for_role)
