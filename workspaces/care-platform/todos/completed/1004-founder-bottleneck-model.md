# 1004: Model Solo Founder Approval Bottleneck (H-4)

**Milestone**: 10 — Red Team Findings
**Priority**: Medium
**Estimated effort**: Small

## Description

Red team finding H-4: Solo founder approval bottleneck should be modeled — how many HELD items can one person review per week across 4+ agent teams?

## Tasks

- [ ] Estimate HELD action volume per team:
  - DM team: ~5-10 external publications/week, ~2-3 outreach emails/week
  - Standards team: ~1-2 publication reviews/week
  - Governance team: ~1-2 compliance reviews/week
  - Partnerships team: ~2-3 engagement reviews/week
  - Total estimated: 10-20 HELD items/week
- [ ] Define sustainable review capacity:
  - Time per review: ~2-5 minutes for routine, ~15-30 minutes for complex
  - Sustainable weekly budget: ~2-3 hours of review time
  - Items/week capacity: ~20-30 items
- [ ] Design capacity monitoring (implemented in todo 403):
  - Track items/day, items/week, review time
  - Alert when approaching capacity
  - Suggest constraint adjustments to reduce HELD volume
- [ ] Define overflow strategy:
  - Priority queue (external-facing first)
  - Batch approval for routine patterns
  - Emergency delegation (Phase 2: trusted Member can review)
- [ ] Document capacity model in operational docs

## Acceptance Criteria

- Capacity model with concrete numbers
- Monitoring approach defined
- Overflow strategy documented
- Integrated with approval queue design (todo 403)
