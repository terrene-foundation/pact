# Todo 2404: EATP Gap Adapter Documentation and Markers

**Milestone**: M24 — EATP SDK Alignment
**Priority**: Medium
**Effort**: Small
**Source**: EATP SDK alignment — gap tracking
**Dependencies**: 2401, 2402, 2403 (all three migration todos must be complete so all gaps are in place)

## What

Ensure all 14 EATP SDK gaps identified during Phase 2 are consistently documented in both code and the gap tracking document. No custom EATP reimplementations should exist outside designated gap adapter blocks.

**In code**: Each gap adapter block must have a comment in the exact format `# EATP-GAP: <gap-id>` on the line immediately above the adapter code, where `<gap-id>` matches the IDs in the tracking document (M1-M4 for messaging, R1-R6 for revocation, P1-P4 for postures).

**In the tracking document**: Update `04-eatp-sdk-gaps.md` to reflect the current state of each gap: whether an adapter is in place, which file and line range contains the adapter, and what the EATP SDK would need to add for each gap to be closed.

**Summary section**: Add a "Gap Closure Requirements" section to the tracking document that summarises, for each gap, the minimum EATP SDK change needed. This section is intended to be shared with EATP SDK maintainers as a contribution to the SDK roadmap.

## Where

- All files containing gap adapters: `src/care_platform/trust/messaging.py`, `src/care_platform/trust/revocation.py`, `src/care_platform/trust/posture.py` — verify `# EATP-GAP` markers are present and correctly formatted
- `workspaces/care-platform/01-analysis/01-research/04-eatp-sdk-gaps.md` — update gap status, add file/line references, add "Gap Closure Requirements" section

## Evidence

- [ ] Exactly 14 `# EATP-GAP:` comments exist across the three trust module files (4 + 6 + 4)
- [ ] Each marker uses the exact format `# EATP-GAP: <gap-id>` with the correct gap ID
- [ ] No custom EATP cryptographic or protocol logic exists outside a marked gap adapter block
- [ ] `04-eatp-sdk-gaps.md` lists all 14 gaps with current status (adapter in place)
- [ ] Each gap entry in the tracking document references the file and approximate line range of its adapter
- [ ] "Gap Closure Requirements" section present with a one-paragraph description per gap of what the EATP SDK must add
- [ ] A grep for `# EATP-GAP:` across `src/` returns exactly 14 matches
