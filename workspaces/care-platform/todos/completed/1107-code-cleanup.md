# 1107: Minor Code Cleanup

**Priority**: Low
**Effort**: Tiny
**Source**: RT3 R3-08, R3-09, R3-13, R3-14, R3-16
**Dependencies**: None

## Problem

Minor cleanup items from the code quality review:

1. **R3-13**: Unused `MagicMock` import in `test_redteam_round2.py:14`
2. **R3-14**: Unused `CommunicationConstraintConfig` and `OperationalConstraintConfig` imports in `test_remaining_redteam.py:13,17`
3. **R3-08**: Redundant halt checks in `_approve_via_shared_queue` and `_reject_via_shared_queue` — add defense-in-depth comments
4. **R3-09**: `_URGENCY_PRIORITY` dict lookup with no fallback — use `.get(pa.urgency, 99)`
5. **R3-16**: Deprecated `asyncio.get_event_loop().run_until_complete()` in tests — replace with `asyncio.run()`

## Implementation

1. Remove unused import `MagicMock` from test_redteam_round2.py
2. Remove unused config imports from test_remaining_redteam.py
3. Add `# Defense-in-depth: caller checks halt, re-check for safety` comments
4. Change `_URGENCY_PRIORITY[pa.urgency]` to `_URGENCY_PRIORITY.get(pa.urgency, 99)`
5. Replace `asyncio.get_event_loop().run_until_complete()` with `asyncio.run()` in test files

## Acceptance Criteria

- [ ] No unused imports in test files
- [ ] Defense-in-depth halt checks documented
- [ ] No deprecated asyncio patterns
- [ ] All tests pass
