# 403: Implement Human Approval Queue

**Milestone**: 4 — Agent Execution Runtime
**Priority**: High (core Human-on-the-Loop mechanism)
**Estimated effort**: Medium
**Depends on**: 212
**Completed**: 2026-03-12
**Verified by**: ApprovalQueue + PendingAction + UrgencyLevel + capacity tracking in `care_platform/execution/approval.py`; 25 unit tests pass in `tests/unit/execution/test_approval.py`

## Description

Implement the human approval queue — the mechanism for HELD actions. When the verification gradient classifies an action as HELD, it's queued for human review. The human can approve, reject, or modify constraints.

## Tasks

- [ ] Implement `care_platform/execution/approval.py`:
  - `ApprovalQueue` — Stores pending HELD actions
  - `PendingAction` model: action, agent, reason, constraint that triggered HELD, timestamp, urgency
  - Queue is persistent (survives platform restart)
- [ ] Implement approval workflow:
  - Human reviews pending action with full context
  - Options: APPROVE (execute as-is), REJECT (cancel with explanation), MODIFY (adjust constraints then re-evaluate)
  - Approval/rejection creates audit anchor with human's decision
- [ ] Implement notification system:
  - Alert human when items enter queue
  - Configurable urgency levels (immediate, daily digest, weekly review)
  - Console output for CLI users (initial implementation)
  - Webhook support for external notification (future)
- [ ] Implement queue management:
  - Age tracking (items older than X hours escalated)
  - Priority sorting (external-facing > internal changes)
  - Batch approval (approve all similar items)
- [ ] Implement founder capacity guard (addresses H-4):
  - Track items/day, items/week
  - Alert when queue depth exceeds sustainable rate
  - Suggest constraint adjustments if pattern is consistent
- [ ] Write integration tests:
  - HELD action → queue → approve → execute → audit
  - HELD action → queue → reject → logged, not executed
  - Queue persistence across restart
  - Capacity alerts

## Acceptance Criteria

- HELD actions properly queued with full context
- Human approval/rejection creates audit trail
- Notifications functional (console at minimum)
- Capacity tracking addresses H-4 finding
- Integration tests passing
