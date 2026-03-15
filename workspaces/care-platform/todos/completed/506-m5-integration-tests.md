# 506: Milestone 5 Integration Tests — Cross-Functional Bridges

**Milestone**: 5 — Cross-Functional Bridges
**Priority**: High (quality gate for Milestone 5)
**Estimated effort**: Small
**Depends on**: 501-505

## Description

Comprehensive integration tests that verify the full cross-functional bridge lifecycle from request through approval, message exchange, expiry, and revocation cascade. These tests confirm that workspace-to-workspace coordination works correctly with EATP trust verification on both sides of each bridge.

## Tasks

- [ ] Test: Full bridge lifecycle — Standing Bridge
  - Create standing bridge from DM team to Standards workspace (read access)
  - Send 5 bridge messages → each produces audit anchors on both sides
  - Verify anchors present on sending side AND receiving side
  - Revoke bridge → subsequent message attempt denied
- [ ] Test: Full bridge lifecycle — Scoped Bridge
  - Create scoped bridge with 24-hour expiry and specific document access
  - Use bridge within time/scope bounds → succeeds
  - Attempt access outside scope (different document) → denied
  - Wait for expiry (fast-forward time in test) → message attempt denied with "bridge expired"
  - Verify expiry event recorded in audit log
- [ ] Test: Full bridge lifecycle — Ad-Hoc Bridge
  - DM agent posts governance content → action HELD → governance team receives review request
  - Governance team reviews via Ad-Hoc bridge → approves
  - Approval propagates back → DM action completes
  - Verify complete chain: DM anchor → bridge anchor → governance anchor → outcome anchor
- [ ] Test: Bridge request and approval workflow
  - Team A requests bridge from Team B → bridge request in PENDING state
  - Team B Team Lead approves → bridge ACTIVE
  - Team B Team Lead rejects → bridge REJECTED; request attempt cannot retry without new request
- [ ] Test: Revocation cascade through bridges
  - Establish scoped bridge for Agent X in Team A
  - Revoke Agent X → bridge immediately invalidated
  - Verify Team B's registry shows bridge as REVOKED
  - Revoke Team A's Team Lead → all Team A bridges invalidated
- [ ] Test: Cross-Team Coordinator routing
  - Incoming bridge message arrives at Team A's Coordinator
  - Coordinator routes to correct specialist based on message type
  - Coordinator escalates bridge request requiring Team Lead approval
  - Verify audit anchor created for each routing decision
- [ ] Test: Concurrent bridges — no cross-contamination
  - 3 active bridges between different team pairs running concurrently
  - Messages on one bridge do not appear in another bridge's audit log
  - Revocation of one bridge does not affect others
- [ ] Test: Bridge audit completeness
  - Walk audit chains for both sides of a completed bridge conversation
  - Verify every message has a corresponding anchor on sender side AND receiver side
  - Verify no orphaned anchors (anchors with no corresponding action)

## Acceptance Criteria

- All three bridge types tested with full lifecycle (create, use, expire/revoke)
- Bridge revocation cascade works correctly (agent revoke → bridge revoke)
- Ad-hoc review pattern round-trip verified end-to-end
- Audit anchors present on both sides for every bridge interaction
- Concurrent bridge tests verify no cross-contamination
- All tests run in CI with MemoryStore (no external dependencies)

## Dependencies

- 501: Cross-functional bridge data model
- 502: Bridge request and approval workflow
- 503: Bridge messaging — signed inter-team communication
- 504: Knowledge bridge integration
- 505: Cross-team coordinator agent definition

## References

- Bridge types: `01-analysis/01-research/06-architecture-gap-analysis.md` — Gap 5
- EATP cross-team delegation: EATP SDK `src/eatp/delegation/` — cross-team patterns
