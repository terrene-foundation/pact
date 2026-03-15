# M16-T01: Runtime constraint enforcement — ConstraintEnforcer

**Status**: ACTIVE
**Priority**: Critical
**Milestone**: M16 — Gap Closure: Runtime Enforcement
**Dependencies**: 1301-1304

## What

Create `ConstraintEnforcer` that wraps `VerificationMiddleware` and is injected into `ExecutionRuntime`. Currently middleware exists but runtime can bypass it. The enforcer makes constraint checking mandatory: every `runtime.submit()` / `runtime.process_next()` must pass through the enforcer. If enforcer is None, runtime refuses to process tasks.

## Where

- New: `src/care_platform/constraint/enforcer.py`
- Modify: `src/care_platform/execution/runtime.py`

## Evidence

- Test: agent action violating constraint is blocked even without explicit middleware call
- Test: removing enforcer causes clear error, not silent bypass
