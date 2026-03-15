# Todo 2301: Financial Constraint Optional Pattern

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: High
**Effort**: Small
**Source**: RT5-19
**Dependencies**: 2201, 2202 (M22 must be complete)

## What

Change financial constraint defaults from `0.0` to `Optional[float] = None`. A value of `None` means "not configured — skip this check entirely." A value of `0.0` means "explicitly zero budget — block all spending." Update all financial constraint evaluation paths in the verification gradient engine and constraint envelope to handle `Optional` correctly. Where `None` is present, the financial dimension check must be bypassed without emitting a BLOCKED or FLAGGED decision.

## Where

- `src/care_platform/config/schema.py` — financial constraint field declarations
- `src/care_platform/constraint/envelope.py` — financial dimension evaluation logic

## Evidence

- [ ] `budget_limit`, `per_action_limit`, and all other financial fields accept `None` without type error
- [ ] A constraint envelope with all financial fields set to `None` passes financial checks (check skipped)
- [ ] A constraint envelope with `budget_limit = 0.0` returns BLOCKED for any action with non-zero cost
- [ ] A constraint envelope with `budget_limit = 100.0` returns AUTO_APPROVED for actions within budget
- [ ] Existing unit tests for financial evaluation continue to pass
- [ ] New unit tests cover the `None` skip path and the explicit-zero block path
