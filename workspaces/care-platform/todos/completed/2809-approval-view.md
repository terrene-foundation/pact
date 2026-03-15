# Todo 2809: Approval Queue (HELD Items) View

**Milestone**: M28 — Dashboard Frontend
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2801, 2802

## What

Implement the Approval Queue view that lists all actions currently in the HELD state awaiting human approval. Each row shows: task ID, agent name, action summary, reason the action was held (which constraint dimension triggered the hold), time waiting (duration since submission), and constraint envelope detail. Each row has an Approve button and a Reject button. Clicking Approve opens a confirmation dialog before submitting the approval. Clicking Reject opens a dialog prompting for a rejection reason before submitting. The view must update in real time via WebSocket so new HELD items appear immediately and approved/rejected items disappear without requiring a page refresh.

## Where

- `apps/web/src/app/approvals/`

## Evidence

- [ ] HELD items are listed with task ID, agent, action summary, hold reason, wait time, and constraint detail
- [ ] Approve button opens a confirmation dialog and submits the approval on confirmation
- [ ] Reject button opens a dialog, requires a rejection reason, and submits the rejection
- [ ] Approved item disappears from the list in real time (without page refresh)
- [ ] Rejected item disappears from the list in real time (without page refresh)
- [ ] New HELD items appear in real time via WebSocket without page refresh
- [ ] Data is fetched from the API via the typed client; real-time updates via WebSocket client (2801)
- [ ] Component tests confirm approve flow, reject flow, and real-time update behaviour
