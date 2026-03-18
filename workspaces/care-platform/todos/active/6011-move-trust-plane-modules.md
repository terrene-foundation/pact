# Task 6011: Move Trust-Plane Modules into trust/

**Milestone**: M38
**Priority**: Critical
**Effort**: Large
**Status**: Active

## Description

Move all Trust Plane source modules into the new `src/care_platform/trust/` package. Trust Plane modules are those implementing governance primitives: constraint enforcement, audit, authentication, persistence, store isolation, and resilience.

Modules to move (exact paths may vary — audit before moving):

- `constraint/` — constraint envelope logic
- `audit/` — audit anchor and audit chain
- `auth/` — authentication and credential lifecycle
- `persistence/` — trust store persistence
- `store_isolation/` — workspace store isolation
- `resilience/` — circuit breakers, retry logic
- Any existing `trust/` submodules — reorganize within the new structure

This task covers only the file moves and within-module relative imports. Cross-module imports are updated in task 6014.

## Acceptance Criteria

- [ ] All trust-plane source files are under `src/care_platform/trust/`
- [ ] Subdirectory structure is logical and flat where possible (avoid deep nesting)
- [ ] Each moved module has its own `__init__.py` with `__all__`
- [ ] Relative imports within the `trust/` subtree are correct
- [ ] `src/care_platform/trust/__init__.py` re-exports the primary public API of the trust plane
- [ ] Git history preserved (use `git mv` rather than copy-delete)

## Dependencies

- Task 6010 (directory structure must exist)

## Risk

Large refactor. Do this in a single atomic commit. If partial moves leave imports broken, the test suite will fail loudly — this is intentional and expected until 6014 is complete.
