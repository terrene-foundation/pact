# 606: DM Team — Initial ShadowEnforcer Run and Calibration

**Milestone**: 6 — DM Team Vertical
**Priority**: Medium (prerequisite for any posture upgrade)
**Estimated effort**: Medium

## Description

Run the ShadowEnforcer alongside the DM team for an initial calibration period. This is the empirical baseline — before any agent acts with real authority, run simulated scenarios to calibrate constraint thresholds, verify gradient classification accuracy, and produce the initial ShadowEnforcer report. The report is evidence that the team is ready to operate at Supervised posture.

## Tasks

- [ ] Generate simulated DM team action dataset:
  - 200 realistic action scenarios for the DM team
  - Distribution: ~60% auto-approved, ~25% flagged, ~12% held, ~3% blocked
  - Cover all 6 agent roles
  - Include edge cases from the analysis document flagged actions table
- [ ] Run ShadowEnforcer against simulated dataset:
  - ShadowEnforcer.process_batch(simulated_actions)
  - Collect metrics: per-agent, per-dimension, per-gradient-level
  - Identify any misclassifications (actions expected to be HELD but auto-approved)
- [ ] Review and calibrate:
  - If any simulated "always HELD" action is classified as AUTO_APPROVED → this is a critical finding; fix gradient rules before proceeding
  - Tune near-boundary thresholds (flagging) until false positive rate < 10%
  - Document calibration decisions
- [ ] Generate initial ShadowEnforcer report:
  - Baseline metrics for DM team
  - Confirm: team is ready to operate at SUPERVISED posture
  - Document expected false positive rate and calibration choices
- [ ] Store report as `workspaces/media/.care/shadow-report-initial.json`
- [ ] Write integration test: verify ShadowEnforcer catches all analysis-defined BLOCKED actions

## Acceptance Criteria

- No "always HELD" action classifies as AUTO_APPROVED
- ShadowEnforcer report generated and stored
- Calibration documented
- Integration test verifies critical BLOCKED actions are caught
- Report confirms team ready for SUPERVISED operation

## Dependencies

- 208: ShadowEnforcer implementation
- 603: DM gradient rules configured (rules must exist before ShadowEnforcer can validate them)
- 605: DM workspace set up (report stored there)

## References

- DM team verification gradient table: `01-analysis/01-research/03-eatp-trust-model-dm-team.md` Section 3
- ShadowEnforcer three-phase pattern (from 208)
