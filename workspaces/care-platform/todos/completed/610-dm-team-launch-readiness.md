# 610: DM Team — Launch Readiness Review

**Milestone**: 6 — DM Team Vertical
**Priority**: High (final gate before DM team goes live)
**Estimated effort**: Small

## Description

Conduct the launch readiness review for the DM team. Before any DM agent acts with real authority (posting to actual social accounts, sending real outreach), every safety check must pass. This is the final gate — a structured checklist covering trust, safety, cost, and operator readiness.

## Tasks

- [ ] Trust readiness checklist:
  - Genesis record signed and verified
  - All 8 agent delegation chains valid and verifiable
  - Capability attestations in place
  - All constraint envelopes signed (not just models — cryptographically signed)
  - ShadowEnforcer calibration report complete (606)
  - Cascade revocation tested (607)
- [ ] Safety readiness checklist:
  - All external actions confirmed as HELD in gradient rules
  - No agent has unreviewed AUTO_APPROVED actions for external channels
  - Crisis protocol documented and accessible
  - Approval interface tested with real scenarios
  - Approval load projected to be manageable (608)
- [ ] Cost readiness checklist:
  - Daily API cost budget set in constraint envelope
  - Cost tracking active
  - Cost alerts configured
  - First-month cost projection documented
- [ ] Operator readiness checklist:
  - Founder has tested CLI approval workflow
  - Founder understands which actions require approval
  - Notification channel configured (how Founder learns about HELD actions)
  - Session briefing shows DM team status correctly
- [ ] Platform readiness checklist:
  - CI pipeline passing
  - All M1-M6 tests green
  - No CRITICAL or HIGH security findings open
  - Backup/recovery procedure documented
- [ ] Sign-off: Create `workspaces/media/.care/launch-approval.md` documenting:
  - Date of launch readiness review
  - All checklists passed
  - Founder signature (as text — for record)
  - Initial operating constraints (posture: SUPERVISED)

## Acceptance Criteria

- All five readiness checklists complete with no open items
- Launch approval document created and signed
- Platform is actually ready — this is not a box-ticking exercise

## Dependencies

- 601-609: All M6 todos complete
- All M1-M5 tests passing

## References

- Red team findings: Address H-1 through H-5 and M-6 before launch
