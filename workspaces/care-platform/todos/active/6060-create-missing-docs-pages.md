# Task 6060: Create 3 Missing Docs Pages

**Milestone**: M43
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

Three core conceptual documentation pages are missing from the docs site. These are the pages users need to understand before they can use the platform meaningfully. They should be written for a technical audience (developers building on CARE Platform) but not assume familiarity with EATP internals.

Pages to create:

1. `docs/trust-model.md` — Explains the Trust Plane: genesis records, delegation records, constraint envelopes, capability attestations, audit anchors, and how they form a trust chain. Include a diagram of the trust lineage chain.
2. `docs/constraint-envelopes.md` — Explains the 5 constraint dimensions (Financial, Operational, Temporal, Data Access, Communication), how monotonic tightening works, and how envelopes are inherited through org → department → team → agent hierarchy.
3. `docs/verification-gradient.md` — Explains the 4 verification levels (AUTO_APPROVED, FLAGGED, HELD, BLOCKED), when each is triggered, how the ShadowEnforcer uses them, and how to configure thresholds.

## Acceptance Criteria

- [ ] All 3 pages created in `docs/`
- [ ] Each page has: overview, key concepts, code example or YAML example, and a "next steps" section
- [ ] The 5 constraint dimension names are exactly: Financial, Operational, Temporal, Data Access, Communication (per terrene-naming rules)
- [ ] The 4 verification levels are exactly: AUTO_APPROVED, FLAGGED, HELD, BLOCKED (uppercase, per naming rules)
- [ ] The 5 trust postures are exactly: PSEUDO_AGENT, SUPERVISED, SHARED_PLANNING, CONTINUOUS_INSIGHT, DELEGATED (per naming rules)
- [ ] Pages linked from the docs index / navigation
- [ ] Docs site builds without warnings after adding the pages

## Dependencies

- Task 6016 (docs updated for M38 restructure, so paths referenced in docs are current)
