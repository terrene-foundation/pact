# 608: DM Team — Approval Load Analysis (H-4 Mitigation)

**Milestone**: 6 — DM Team Vertical
**Priority**: High (addresses critical red team finding H-4)
**Estimated effort**: Small

## Description

Analyze and document the expected approval workload for a solo human operator managing the DM team at Supervised posture. Red team finding H-4 identified that the approval bottleneck could be unsustainable. This todo quantifies the load, designs for rapid triage, and documents the scaling plan.

## Tasks

- [ ] Calculate expected daily HELD actions at Supervised posture:
  - Based on DM team verification gradient rules (603)
  - Estimate: Content Creator might produce 10 drafts/day, all requiring review
  - Estimate: Outreach Agent might draft 2-3 outreach emails/day, all HELD
  - Estimate: Scheduling Agent might schedule 2-3 posts/day (calendar approved weekly)
  - Total: estimate HELD actions per day across all DM agents
- [ ] Design rapid-triage approval interface:
  - `care-platform list-held --team dm` must show in < 5 lines per action:
    1. Agent + action type
    2. Content preview (truncated to 200 chars)
    3. Why it is HELD
    4. Action ID for approve/reject
  - Batch approval: `care-platform approve-batch action-id-1 action-id-2 ...`
  - Approve-all (for routine items with low risk): `care-platform approve-routine --team dm`
- [ ] Define "routine" vs "non-routine" HELD actions:
  - Routine: templated content within approved categories (human reviews batch at start of week)
  - Non-routine: crisis content, regulatory topics, novel outreach (requires individual review)
  - Configurable per constraint envelope
- [ ] Project workload at each posture level:
  - Supervised: estimate minutes per day for approval queue
  - Shared Planning: reduced load (batch at week level)
  - Continuous Insight: dashboard review only (minimal HELD)
  - Document in `workspaces/media/.care/approval-load-projection.md`
- [ ] Write unit tests for rapid-triage interface
- [ ] Document bottleneck mitigation strategy:
  - H-4 resolution: posture evolution reduces load; routine batch approval reduces per-item time
  - Escalation path if Founder unavailable (backup approver — future governance)

## Acceptance Criteria

- Expected daily HELD count estimated and documented
- Rapid-triage interface implemented (5 lines per item)
- Batch approval command works
- Workload projection documented per posture level
- H-4 finding explicitly addressed in documentation

## Dependencies

- 403: Human-in-the-loop approval system (interface to improve)
- 603: DM gradient rules (source of HELD count estimate)
- 604: Posture evolution plan (load reduction trajectory)

## References

- Red team finding H-4: Solo founder approval bottleneck
- Synthesis: `01-analysis/02-synthesis.md`
