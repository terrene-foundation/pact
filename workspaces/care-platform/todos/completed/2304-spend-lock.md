# Todo 2304: Cumulative Spend Thread Lock

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: Medium
**Effort**: Small
**Source**: RT10-A2
**Dependencies**: 2302 (spend accumulator must exist before it can be made thread-safe)

## What

Add a `threading.Lock` to the cumulative spend accumulator in `VerificationMiddleware`. The current accumulator is read and written without synchronisation, creating a race condition when multiple agents submit actions concurrently. The lock must guard the read-modify-write cycle for all spend fields: per-action totals, daily totals, monthly totals, and vendor-specific totals. Follow the pattern already established for other shared state in the RT7-RT9 hardening work.

## Where

- `src/care_platform/constraint/middleware.py` — add `threading.Lock` instance on the middleware class and wrap all spend accumulator mutations

## Evidence

- [ ] `VerificationMiddleware` initialises a `threading.Lock` alongside the spend accumulator
- [ ] All read-modify-write operations on the spend accumulator are performed inside a `with self._spend_lock:` block
- [ ] Concurrent verification calls from multiple threads do not produce double-spend or under-count
- [ ] Unit test confirms thread-safe behaviour under concurrent access (e.g. `ThreadPoolExecutor` with shared middleware instance)
- [ ] No functional change to single-threaded behaviour; existing spend tests continue to pass
