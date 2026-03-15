# 409: Milestone 4 Integration Tests — Full Runtime Stack

**Milestone**: 4 — Agent Execution Runtime
**Priority**: High (quality gate for Milestone 4)
**Estimated effort**: Medium
**Depends on**: 401-408

## Description

Comprehensive integration tests for the agent execution runtime. Tests the full loop: agent definition → trust establishment → execution → verification → audit.

## Tasks

- [ ] Test: Single agent execution with trust enforcement
  - Define agent → establish trust → agent acts → verified → audit anchor created
- [ ] Test: Multi-agent team execution
  - Team Lead + 2 specialists → concurrent execution → each action independently verified
- [ ] Test: Verification gradient during execution
  - Agent action auto-approved → executes
  - Agent action held → queued → human approves → executes
  - Agent action blocked → rejected, logged
- [ ] Test: Multi-LLM backend
  - Same agent definition, different backends → same verification behavior
- [ ] Test: Agent lifecycle during execution
  - Active agent revoked mid-task → current action completes, future actions blocked
  - Paused agent → queued actions preserved → resume → actions execute
- [ ] Test: ShadowEnforcer during execution
  - Shadow mode: evaluation runs but does not block → metrics collected
- [ ] Test: Stress test
  - Multiple teams, multiple agents, concurrent actions → all verified, all audited, no race conditions

## Acceptance Criteria

- All integration tests pass
- Tests run in CI with MemoryStore (no external dependencies)
- Race condition tests verify thread safety
- Full execution loop tested end-to-end
