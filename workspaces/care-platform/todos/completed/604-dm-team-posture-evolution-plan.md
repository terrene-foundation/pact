# 604: DM Team — Trust Posture Evolution Plan

**Milestone**: 6 — DM Team Vertical
**Priority**: Medium (long-term governance plan for DM operations)
**Estimated effort**: Small

## Description

Encode the DM team's trust posture evolution plan as platform configuration. The analysis defines a four-phase posture trajectory from Supervised (Month 1-3) through Delegated (Month 12+). This plan becomes a configurable roadmap that the platform tracks and uses to suggest posture reviews.

## Tasks

- [ ] Define posture plan YAML (`examples/dm-team/posture-plan.yaml`):
  - Phase 1 (Month 1-3): SUPERVISED
    - Agent autonomy: internal operations auto-execute; all external actions HELD
    - Human role: approves every external action
    - Upgrade criteria: 3 months clean record, ShadowEnforcer pass rate > 95%, no incidents
  - Phase 2 (Month 3-6): SHARED_PLANNING
    - Agent autonomy: internal operations auto; routine external held for 1-hour window
    - Human role: approves calendar weekly, not per-post
    - Upgrade criteria: 3 more months, pass rate > 97%, analytics reports auto-distribute internally
  - Phase 3 (Month 6-12): CONTINUOUS_INSIGHT
    - Agent autonomy: routine content auto-publishes within verified templates
    - Human role: reviews dashboard daily; flagged items escalated
    - Upgrade criteria: 6 months at Shared Planning, pass rate > 99%
  - Phase 4 (Month 12+): DELEGATED (select tasks only)
    - Agent autonomy: analytics and templated posts fully autonomous
    - Human role: periodic audit review
    - Content strategy, novel outreach, crisis response: permanently HELD
- [ ] Implement "never delegated" permanent hold list:
  - Content strategy changes
  - Novel outreach (to new individuals/organizations)
  - Crisis response
  - Financial decisions
  - Any content about Foundation governance or membership
- [ ] Implement posture plan scheduling:
  - Platform tracks each DM agent's current posture phase
  - Monthly reminder: "DM Team Lead is eligible for posture review — run ShadowEnforcer assessment"
  - Alert: "DM Content Creator has been at Supervised for 95 days; consider review"
- [ ] Write unit tests for posture plan configuration loading and scheduling

## Acceptance Criteria

- Posture evolution plan encoded in YAML and loads correctly
- Never-delegated list applied regardless of posture level
- Monthly review reminders triggered
- Upgrade criteria defined and machine-readable (feeds ShadowEnforcer assessment in 305)

## Dependencies

- 305: Posture history and upgrade workflow
- 208: ShadowEnforcer (evidence source for upgrades)
- 601: DM team agents (agents to track)

## References

- Posture evolution table: `01-analysis/01-research/03-eatp-trust-model-dm-team.md` Section 4
