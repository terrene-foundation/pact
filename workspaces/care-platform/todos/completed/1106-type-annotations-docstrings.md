# 1106: Type Annotations and Docstring Accuracy

**Priority**: Medium
**Effort**: Small
**Source**: RT3 R3-02, R3-03, R3-06, R3-07
**Dependencies**: None

## Problem

Several type annotation and docstring accuracy issues:

1. **R3-02**: `verification` parameter in `_handle_auto_approved`, `_handle_flagged`, `_handle_held`, `_handle_blocked` (middleware.py:567,603,646,716) has no type annotation. Should be `VerificationResult`.

2. **R3-06**: `halted_check` typed as `object | None` in ShadowEnforcer and HookEnforcer. Should be `Callable[[], bool] | None`.

3. **R3-07**: Middleware `process_action` docstring omits the RT2-06 attestation check step between step 3 (posture) and step 4 (never-delegated).

4. **R3-03**: ShadowEnforcer docstring pipeline steps don't match code order after R3-01 fix.

5. **R3-15**: Missing `-> None` return annotation on `RevocationManager.__init__`.

## Implementation

1. Add `from care_platform.constraint.gradient import VerificationResult` to middleware.py and annotate all four handler methods
2. Change `halted_check: object | None` to `Callable[[], bool] | None` in both shadow_enforcer.py and hook_enforcer.py (add `from collections.abc import Callable`)
3. Insert "3b. Check agent attestation validity via EATP bridge (RT2-06)" into middleware docstring
4. Update ShadowEnforcer docstring to include expiry check step
5. Add `-> None` to `RevocationManager.__init__`

## Acceptance Criteria

- [ ] All type annotations are accurate
- [ ] Docstrings match actual code execution order
- [ ] Pyright reports no new errors
- [ ] All tests pass
