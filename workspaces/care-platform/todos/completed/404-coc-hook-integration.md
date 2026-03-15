# 404: COC Hook System Integration

**Milestone**: 4 — Agent Execution Runtime
**Priority**: High (closes Gap 3 — cryptographic enforcement at execution)
**Estimated effort**: Medium
**Completed**: 2026-03-12
**Verified by**: HookEnforcer + HookVerdict + HookResult + fail-safe BLOCK default in `care_platform/execution/hook_enforcer.py`; 16 unit tests pass in `tests/unit/execution/test_hook_enforcer.py`

## Description

Integrate the CARE Platform trust enforcement into the existing COC hook system. Currently, hooks (`validate-bash-command.js`, `pre-tool-call`, etc.) provide lightweight behavioral enforcement. This todo upgrades them to EATP VERIFY operations — every hooked action is verified against the agent's signed constraint envelope, closing Architecture Gap 3.

## Tasks

- [ ] Audit existing COC hooks in `.claude/hooks/`:
  - List each hook, what it checks, what it allows/blocks
  - Map each hook action to CARE constraint dimensions
  - Identify which hooks should become VERIFY operations vs remain simple checks
- [ ] Implement EATP VERIFY in hook layer:
  - Hook calls `GradientEngine.classify(action, envelope)` before allowing
  - AUTO_APPROVED: proceed
  - FLAGGED: proceed but log to audit
  - HELD: block tool call, enqueue in held-action queue, return "action queued"
  - BLOCKED: reject with clear reason
- [ ] Implement `care_platform/execution/hook_enforcer.py`:
  - `HookEnforcer` — wraps hook validation with EATP verification
  - Stateless (reads agent context from platform state)
  - Resilient: if platform state unavailable, default to BLOCKED (fail-safe)
- [ ] Implement hook telemetry:
  - Every hook invocation → audit anchor (even for AUTO_APPROVED)
  - Hook performance logging (verify latency at QUICK/STANDARD/FULL levels)
- [ ] Generate updated hook scripts that call the Python enforcement layer:
  - Hooks call `python -m care_platform.execution.hook_enforcer --action "..." --agent "..."`
  - Return exit code: 0 = allow, 1 = block, 2 = held
- [ ] Write integration tests:
  - Hook call → VERIFY → AUTO_APPROVED → anchor created
  - Hook call → VERIFY → HELD → queued in held-action queue
  - Hook call → VERIFY → BLOCKED → rejected with reason
  - Hook unavailable (platform down) → BLOCKED (fail-safe)

## Acceptance Criteria

- Every hooked action verified against signed constraint envelope
- HELD actions route to human-in-the-loop queue
- BLOCKED actions rejected with clear EATP reason
- Fail-safe: platform unavailable defaults to BLOCKED
- Integration tests cover all gradient outcomes

## Dependencies

- 104: Verification gradient engine
- 204: Constraint envelope signing
- 403: Human-in-the-loop approval system (for HELD routing)

## Risk Assessment

- HIGH: Fail-safe behavior — if the platform enforcement layer is down, hooks must fail closed (block all), not open (allow all).
- MEDIUM: Performance — adding Python subprocess invocation to every hook adds latency.

## References

- Existing hooks: `.claude/hooks/`
- Architecture Gap 3: Cryptographic enforcement
