# 1205: Agent Execution Runtime

**Priority**: Critical
**Effort**: Large
**Source**: RT3 Theme B
**Dependencies**: 1201 (persistence), 1203 (bootstrap)

## Problem

The platform has constraint enforcement and trust governance but no way to actually run agents. There's no execution loop that takes a task, selects an agent, runs it through the verification pipeline, and records the result.

## Implementation

Create `care_platform/execution/runtime.py`:

- Task queue: submit tasks for agent execution
- Agent selection: match tasks to capable agents
- Execution loop: verify -> execute -> audit for each task
- Integration with VerificationMiddleware for constraint enforcement
- Agent lifecycle: start, monitor, restart on failure
- Result recording and task completion tracking

## Acceptance Criteria

- [ ] Tasks can be submitted and processed by agents
- [ ] Every execution goes through the verification pipeline
- [ ] Results are recorded in the audit chain
- [ ] Agent failures are detected and handled
- [ ] Tests verify the full task -> verify -> execute -> audit flow
