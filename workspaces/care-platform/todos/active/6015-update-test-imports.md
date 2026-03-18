# Task 6015: Update All Test Imports and Verify All Tests Pass

**Milestone**: M38
**Priority**: Critical
**Effort**: Large
**Status**: Active

## Description

After source imports are updated (task 6014), the test suite will still reference old module paths. This task updates all imports in `tests/` and then runs the full test suite to confirm zero regressions.

The test suite reportedly has 3000+ tests across unit, integration, and E2E tiers. All must pass after the restructure.

## Acceptance Criteria

- [ ] All import statements in `tests/` updated to new `trust/`, `build/`, `use/` paths
- [ ] No remaining references to old module paths in `tests/` (verified by grep)
- [ ] `pytest tests/unit/` passes with 0 failures
- [ ] `pytest tests/integration/` passes with 0 failures (or pre-existing failures only — document any pre-existing)
- [ ] `pytest tests/e2e/` passes or is documented as requiring live infrastructure (acceptable skip in CI without live infra)
- [ ] Test coverage does not regress (compare before/after if coverage was previously measured)
- [ ] CI pipeline passes on the restructure branch

## Dependencies

- Task 6014 (source imports must be updated first)

## Risk

If any test was directly importing internal implementation details at old paths (rather than through public package API), those tests may need to be updated to use the new paths or refactored to use the public API. Document any such cases.
