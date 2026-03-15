# 502: Implement Scoped Bridge (Time-Bounded, Purpose-Bounded)

**Milestone**: 5 — Cross-Functional Bridges
**Priority**: Medium
**Estimated effort**: Medium
**Depends on**: 501
**Completed**: 2026-03-12
**Verified by**: ScopedBridge with valid_until + one_time_use + auto-expiry in `care_platform/workspace/bridge.py`; tests for scoped bridge lifecycle, expiry, and one-time-use in `tests/unit/workspace/test_bridge.py`

## Description

Implement Scoped Bridges — time-bounded, purpose-bounded delegations between teams. Example: DM team requests EATP summary from Standards team for a specific LinkedIn post, valid 7 days, read-only, attribution required.

## Tasks

- [ ] Implement `ScopedBridge` model:
  - All Standing Bridge fields plus:
  - Time bound (valid from / valid until — e.g., 7 days)
  - Purpose bound (specific use case described)
  - Auto-expire after time bound
  - One-time use option (bridge closes after first use)
- [ ] Implement purpose verification:
  - Data access must align with stated purpose
  - Misuse detection (data used beyond stated purpose)
- [ ] Implement automatic expiry:
  - Bridge auto-closes after time bound
  - Warning before expiry
  - Extension requires new approval
- [ ] Implement the Standards → DM content pattern:
  - Standards Team Lead creates delegation: "Content Creator may use this EATP summary for LinkedIn content, valid 7 days, read-only, attribution required"
  - DM Content Creator can access within bounds
  - Access logged, attribution tracked
- [ ] Write integration tests:
  - Bridge creation with time/purpose bounds
  - Access within bounds (allowed)
  - Access after expiry (denied)
  - Purpose mismatch (flagged)

## Acceptance Criteria

- Time-bounded bridges auto-expire
- Purpose-bounded bridges track usage
- Expiry and misuse detection work
- Integration tests passing
