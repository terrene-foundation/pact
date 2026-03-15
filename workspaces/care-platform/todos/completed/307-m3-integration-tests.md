# 307: Milestone 3 Integration Tests — Full Persistence Stack

**Milestone**: 3 — Persistence Layer
**Priority**: High (quality gate for Milestone 3)
**Estimated effort**: Small
**Depends on**: 301-306

## Description

Comprehensive integration tests that verify the full persistence stack works end-to-end. Tests must confirm that trust objects survive a platform restart, that audit chains remain intact, that posture history is append-only, and that API cost tracking records correctly. These tests are the quality gate before Milestone 4 begins.

## Tasks

- [ ] Test: Trust object round-trip through DataFlow
  - Create genesis record → persist → restart platform → reload → verify identical
  - Create delegation chain (3 hops) → persist → reload → verify chain integrity
  - Create constraint envelope → persist → reload → verify signatures intact
- [ ] Test: Audit chain integrity after restart
  - Create 10 audit anchors with chain linking → persist → restart → reload
  - Walk chain from genesis to latest anchor → verify all hash links valid
  - Deliberately corrupt one anchor hash → run integrity check → expect failure detected
- [ ] Test: Posture history accuracy
  - Record 3 posture changes for an agent (Supervised → Shared Planning → back to Supervised)
  - Verify history returns all 3 records in order
  - Verify append-only: attempt to modify a record → expect failure
  - Verify current_posture reflects latest record
- [ ] Test: Audit query interface correctness
  - Insert 50 audit anchors with varied agents, times, action types, gradient levels
  - Query by agent → verify correct subset
  - Query by time range → verify correct subset
  - Query by gradient level HELD → verify only held actions returned
  - Compound query (agent + time range) → verify intersection correct
- [ ] Test: API cost tracking with budget enforcement
  - Record LLM calls totaling 90% of daily budget → alert triggered
  - Record LLM call that would exceed budget → call blocked
  - Spend report returns correct totals
- [ ] Test: DataFlow migration
  - Start with MemoryStore, migrate to DataFlowStore → all records preserved
  - Verify no data lost in migration

## Acceptance Criteria

- All trust objects round-trip through DataFlow with no data loss
- Audit chain integrity check correctly detects tampering
- Posture history is append-only (modifications rejected)
- Audit queries return accurate results across all filter types
- API cost enforcement blocks overspend correctly
- Migration path tested and verified
- All tests run in CI (no external database required — use DataFlow with in-memory SQLite)

## Dependencies

- 301: DataFlow schema
- 302: Trust object persistence
- 303: Workspace and agent registry persistence
- 304: Audit history query interface
- 305: Posture history and upgrade workflow
- 306: API cost tracking and budget controls

## References

- Testing patterns: `rules/testing.md` — 3-tier testing strategy
- DataFlow test setup: check DataFlow SDK for in-memory SQLite configuration
