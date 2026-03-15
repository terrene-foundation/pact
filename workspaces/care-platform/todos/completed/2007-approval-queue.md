# M20-T07: Approval queue (HELD items)

**Status**: ACTIVE
**Priority**: High
**Milestone**: M20 — Frontend Dashboard Views
**Dependencies**: 1803, 1804, 1805

## What

Interactive approval queue for HELD actions. Each item: agent, action, reason held, urgency, constraint details. Approve/Reject buttons calling the API.

## Where

- `apps/web/app/approvals/page.tsx`
- `apps/web/components/approvals/ApprovalCard.tsx`
- `apps/web/components/approvals/ApprovalActions.tsx`

## Evidence

- HELD items display; Approve/Reject buttons call API; item moves to decided state
