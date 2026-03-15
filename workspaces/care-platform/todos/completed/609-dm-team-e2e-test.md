# 609: DM Team End-to-End Test — Content Creation to Publication

**Milestone**: 6 — DM Team Vertical
**Priority**: High (proves the full DM vertical works as a system)
**Estimated effort**: Medium

## Description

The definitive end-to-end test for the DM team vertical: a complete content creation cycle from brief to publication, exercising every DM agent, trust layer, approval workflow, and audit trail. This test validates the CARE Platform as a working governed operational model — not just a collection of components.

## Tasks

- [ ] E2E scenario: "Publish a LinkedIn post about the EATP SDK release"
  1. Founder (human) creates content brief in `workspaces/media/briefs/`
  2. DM Team Lead reads brief, creates editorial plan (auto-approved, internal)
  3. DM Team Lead delegates research task to Content Creator
  4. Content Creator researches (reads public Foundation content — auto-approved)
  5. Content Creator drafts LinkedIn post (draft only — auto-approved)
  6. Content Creator submits for review (internal → Team Lead)
  7. DM Team Lead reviews draft, requests analytics context
  8. Analytics Agent retrieves engagement benchmarks (auto-approved, internal)
  9. DM Team Lead approves draft (internal coordination)
  10. Scheduling Agent queues post for optimal time (auto-approved, internal scheduling)
  11. At scheduled time: publish action raised → HELD (external publication)
  12. Founder (human) reviews HELD action via CLI
  13. Founder approves
  14. Publication proceeds (via platform's output channel)
  15. Analytics Agent monitors post performance (auto-approved, read-only)
- [ ] Verify audit trail:
  - Every step above has an audit anchor
  - Chain integrity verified across all 15+ anchors
  - HELD action approval recorded with approver identity
- [ ] Verify cost tracking:
  - All LLM calls recorded
  - Total cost within expected range for scenario
- [ ] Verify no unauthorized actions occurred:
  - No external communication without HELD approval
  - No content modified after approval
  - No financial transactions

## Acceptance Criteria

- Complete 15-step scenario executes without errors
- Every step produces correct audit anchor
- HELD action pauses execution until human approves
- Audit chain integrity verified after scenario
- Cost tracked for all LLM calls
- No policy violations in audit log

## Dependencies

- 601-608: All M6 todos complete
- 401-409: Agent execution runtime
- 403: Human-in-the-loop approval
- 304: Audit history queries (to verify audit trail)

## References

- DM team agent roles: `01-analysis/01-research/03-eatp-trust-model-dm-team.md`
- Synthesis: `01-analysis/02-synthesis.md`
