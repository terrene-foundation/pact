# Todo 2704: Agent Task Lifecycle (Submit → Verify → Execute → Audit)

**Milestone**: M27 — Agent Execution Runtime
**Priority**: High
**Effort**: Large
**Source**: Phase 3 requirement
**Dependencies**: 2701

## What

Implement the complete agent task lifecycle as a traceable state machine. The four stages are:

1. **Submit**: Agent submits an action request. Request is assigned a unique task ID and logged.
2. **Verify**: Constraint middleware evaluates the action against all five constraint dimensions. Result is AUTO_APPROVED, FLAGGED, HELD, or BLOCKED. HELD actions enter the approval queue; BLOCKED actions terminate here.
3. **Hold/Approve** (if HELD): Approval queue entry is created. Human approves or rejects via the API. Approval decision is logged with approver identity and timestamp.
4. **Execute**: Approved action is dispatched to the LLM backend. Response is received and validated.
5. **Audit**: An audit anchor is created containing the full lifecycle record (task ID, stages, decisions, response hash, timestamps). Anchor is persisted to the trust store.

Emit real-time WebSocket events at each stage transition so the dashboard can display live task progress.

## Where

- `src/care_platform/execution/runtime.py`
- `src/care_platform/execution/lifecycle.py`

## Evidence

- [ ] Every task is assigned a unique ID at submission and is traceable through all stages
- [ ] BLOCKED tasks terminate at the Verify stage with no LLM call made
- [ ] HELD tasks enter the approval queue and do not proceed until approved or rejected
- [ ] Approved tasks proceed to Execute and receive an LLM response
- [ ] An audit anchor is persisted at the end of every completed lifecycle (including rejected HELD tasks)
- [ ] WebSocket events are emitted at each stage transition with task ID and new stage
- [ ] Full lifecycle is visible in the audit trail with all timestamps
- [ ] Integration tests trace a task through all stages including a HELD → approved path
