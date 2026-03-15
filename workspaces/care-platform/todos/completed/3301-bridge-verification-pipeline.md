# Todo 3301: Bridge Verification Pipeline

**Milestone**: M33 — Cross-Team Execution
**Priority**: High
**Effort**: Large
**Source**: Phase 4 plan
**Dependencies**: 3101, 3201, 3103

## What

Integrate bridge checks into `ExecutionRuntime`'s verification pipeline so that cross-team tasks are subject to bridge-aware trust enforcement before execution.

When a task targets an agent on a different team, the runtime must:

1. Find an ACTIVE bridge between the source and target teams
2. Verify the action type is allowed by the bridge permissions
3. Compute the effective constraint envelope (via `compute_bridge_envelope` from 3201)
4. Compute the effective posture (via `effective_posture` from 3103)
5. Run the action through the verification gradient using the effective envelope and posture
6. Route based on result: AUTO_APPROVED or FLAGGED — execute; HELD — queue for human approval; BLOCKED — reject

Add an `is_cross_team_task(task)` helper that checks whether `task.agent_id` belongs to a different team than the submitting agent. Extend `process_next()` to detect cross-team tasks and apply bridge verification before standard verification proceeds.

If no ACTIVE bridge exists between the source and target teams, the task must be BLOCKED immediately — there is no fallback path for bridgeless cross-team execution.

## Where

- `src/care_platform/execution/runtime.py` (extend)

## Evidence

- [ ] `is_cross_team_task(task)` helper implemented and returns correct boolean
- [ ] `process_next()` detects cross-team tasks and routes them through bridge verification
- [ ] Cross-team task with an ACTIVE bridge: verification gradient applied using effective envelope and posture
- [ ] Cross-team task without any bridge: result is BLOCKED
- [ ] Cross-team task with a SUSPENDED bridge: result is BLOCKED
- [ ] Effective envelope from 3201 is passed to the verification gradient (not the raw agent envelope)
- [ ] Effective posture from 3103 is used when calling the gradient (not the raw agent posture)
- [ ] AUTO_APPROVED and FLAGGED results proceed to execution
- [ ] HELD results are queued for human approval
- [ ] BLOCKED results are rejected with a descriptive reason referencing the missing or invalid bridge
- [ ] All unit tests pass
