# Todo 2705: Agent Execution Integration Tests

**Milestone**: M27 — Agent Execution Runtime
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2701, 2702, 2703, 2704

## What

Integration tests covering the complete agent execution flow from agent definition through to audit recording. Tests must exercise: agent definition loaded from workspace config, task submission, constraint verification decision, approval gate for HELD actions, LLM execution via both Anthropic and OpenAI backends (gated by key availability), audit anchor persisted to the trust store, and ShadowEnforcer metrics collected when live mode is enabled. No model strings hardcoded in test files; all read from environment variables.

## Where

- `tests/integration/test_agent_execution.py`

## Evidence

- [ ] Full lifecycle test passes: submit → verify (AUTO_APPROVED) → execute → audit recorded
- [ ] HELD lifecycle test passes: submit → verify (HELD) → approve → execute → audit recorded
- [ ] BLOCKED lifecycle test passes: submit → verify (BLOCKED) → no LLM call made → audit recorded
- [ ] Test with Anthropic backend passes when `ANTHROPIC_API_KEY` is present; skips otherwise
- [ ] Test with OpenAI backend passes when `OPENAI_API_KEY` is present; skips otherwise
- [ ] All five posture modes produce the expected behaviour in integration tests
- [ ] ShadowEnforcer metrics are non-zero after test run with live mode enabled
- [ ] Audit trail contains complete records for all tested lifecycle paths
