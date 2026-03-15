# 504: Cross-Functional Bridge Integration Tests

**Milestone**: 5 — Cross-Functional Bridges
**Priority**: High (quality gate for Milestone 5)
**Estimated effort**: Medium
**Depends on**: 501-503

## Description

Comprehensive integration tests for all three bridge types working together.

## Tasks

- [ ] Test: Standing bridge data flow
  - DM reads from Standards workspace via standing bridge → audited on both sides
- [ ] Test: Scoped bridge lifecycle
  - Create scoped bridge → use within bounds → verify expires → attempt after expiry → denied
- [ ] Test: Ad-hoc review pattern
  - DM posts governance content → HELD → governance review → approved → DM can proceed
- [ ] Test: Bridge + revocation interaction
  - Agent revoked → its bridges invalidated
  - Team lead revoked → all team's bridges invalidated
- [ ] Test: Concurrent bridges
  - Multiple active bridges between different teams → all independently verified
- [ ] Test: Bridge audit completeness
  - Every bridge interaction produces anchors on both sides
  - No missing records in either chain

## Acceptance Criteria

- All bridge types tested end-to-end
- Revocation correctly invalidates bridges
- Audit completeness verified
- Integration tests passing
