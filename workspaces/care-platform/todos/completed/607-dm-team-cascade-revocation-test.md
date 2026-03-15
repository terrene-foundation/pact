# 607: DM Team — Cascade Revocation Test and Crisis Protocol

**Milestone**: 6 — DM Team Vertical
**Priority**: High (safety mechanism must be tested before live operation)
**Estimated effort**: Small

## Description

Test cascade revocation for the DM team and document the crisis protocol. Before the DM team operates with any real authority, the safety mechanism (cascade revocation) must be proven to work. This test is a prerequisite for live DM operation.

## Tasks

- [ ] Test surgical revocation on DM team:
  - Establish DM team with full trust chain
  - Revoke Content Creator (surgical)
  - Verify: Content Creator REVOKED
  - Verify: All other DM agents UNAFFECTED (Team Lead, Analytics, Scheduling, Clip Extractor, Outreach all still active)
  - Verify: Re-establishing Content Creator creates new trust chain (clean slate)
- [ ] Test team-wide cascade revocation:
  - Establish DM team with full trust chain
  - Revoke DM Team Lead
  - Verify: ALL 7 downstream agents REVOKED
  - Verify: No orphaned agents attempting to act
  - Verify: Cross-team bridges also invalidated (if any active)
  - Verify: Audit anchor records the revocation event
- [ ] Test revocation with in-flight held action:
  - Establish DM team
  - Enqueue a HELD action for Content Creator
  - Revoke Content Creator before action is approved
  - Verify: HELD action auto-rejected (agent revoked)
  - Verify: Human operator notified
- [ ] Document DM team crisis protocol:
  - `workspaces/media/.care/crisis-protocol.md`
  - Trigger conditions (what causes a revocation)
  - Who can initiate revocation (only Founder or Board)
  - How to revoke (CLI command, API endpoint)
  - Recovery steps (re-establish agent with new trust chain)
  - Audit trail preservation during crisis
- [ ] Write integration tests covering all three revocation scenarios

## Acceptance Criteria

- Surgical revocation: 1 agent revoked, 7 unaffected
- Team-wide cascade: all 8 agents revoked, no orphans
- In-flight HELD action cancelled on revocation
- Crisis protocol documented and accessible
- Integration tests passing

## Dependencies

- 602: DM team trust established
- 207: Cascade revocation implementation
- 403: Human-in-the-loop (held action cancellation)

## References

- Cascade revocation patterns: `01-analysis/01-research/03-eatp-trust-model-dm-team.md` Section 6
