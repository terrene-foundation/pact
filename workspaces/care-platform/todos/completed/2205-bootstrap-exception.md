# Todo 2205: Bootstrap Exception Handling Fix

**Milestone**: M22 — API Hardening
**Priority**: Medium
**Effort**: Small
**Source**: RT5-15
**Dependencies**: None

## What

The bootstrap SQLite operations temporarily change the connection's `isolation_level`. If a `KeyboardInterrupt` or `SystemExit` is raised mid-operation, the `isolation_level` is never restored, leaving the connection in an inconsistent state for any subsequent database work in the same process. The fix is to wrap all code that modifies `isolation_level` in a `try/finally` block so the level is always restored, regardless of whether the exit is a normal return, an exception, a `KeyboardInterrupt`, or a `SystemExit` (all of which are `BaseException` subclasses).

The `try/finally` pattern must cover `BaseException`, not just `Exception`, since `KeyboardInterrupt` and `SystemExit` do not inherit from `Exception`.

## Where

- `src/care_platform/bootstrap.py` — SQLite `isolation_level` modification block(s)

## Evidence

- [ ] `isolation_level` is restored to its original value when the guarded block exits normally
- [ ] `isolation_level` is restored when a standard `Exception` is raised inside the block
- [ ] `isolation_level` is restored when a `KeyboardInterrupt` is raised inside the block
- [ ] `isolation_level` is restored when a `SystemExit` is raised inside the block
- [ ] Unit tests cover all four exit paths above
- [ ] Existing tests continue to pass
