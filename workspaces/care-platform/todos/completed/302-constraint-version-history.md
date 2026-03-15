# 302: Implement Constraint Envelope Version History

**Milestone**: 3 — Persistence Layer
**Priority**: Medium (auditability of constraint changes)
**Estimated effort**: Small
**Depends on**: 301
**Completed**: 2026-03-12
**Verified by**: VersionTracker + EnvelopeVersion + EnvelopeDiff in `care_platform/persistence/versioning.py`; 24 unit tests pass in `tests/unit/persistence/test_versioning.py`

## Description

Track all changes to constraint envelopes over time — who changed what, when, and why. Essential for regulatory compliance and organizational learning.

## Tasks

- [ ] Implement version tracking:
  - Every constraint change creates a new version
  - Previous versions immutable (append-only history)
  - Each version includes: diff from previous, author, timestamp, reasoning
- [ ] Implement diff computation:
  - `envelope_diff(v1, v2)` → list of changes per dimension
  - Human-readable format ("Financial limit increased from $0 to $50")
- [ ] Implement constraint review history:
  - Track 90-day renewal cycle
  - Track ShadowEnforcer-driven adjustments
  - Track incident-driven tightenings
- [ ] Write unit tests for versioning and diff

## Acceptance Criteria

- Full history of every constraint envelope change
- Diffs human-readable
- Renewal cycle tracked
- Unit tests passing
