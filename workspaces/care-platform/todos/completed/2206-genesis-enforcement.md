# Todo 2206: Non-SQLite Genesis Write-Once Enforcement

**Milestone**: M22 — API Hardening
**Priority**: High
**Effort**: Small
**Source**: RT5-14
**Dependencies**: None

## What

`SQLiteTrustStore` enforces genesis record immutability at the database level using triggers. `MemoryStore` and `FilesystemStore` have no equivalent guard: a caller can overwrite an existing genesis record by writing a new one. This violates the EATP Genesis Record write-once requirement (a trust root must be immutable once established).

Add an existence check to the genesis write path in both alternative store implementations. Before writing a genesis record, check whether one already exists. If it does, raise an exception (e.g., `GenesisAlreadyExistsError` or similar) that clearly communicates the constraint. The check must be atomic enough to prevent a race between read and write in normal single-threaded and async usage.

## Where

- `src/care_platform/persistence/store.py` — `MemoryStore` genesis write method, `FilesystemStore` genesis write method

## Evidence

- [ ] `MemoryStore` raises an appropriate error when a second genesis record write is attempted
- [ ] `FilesystemStore` raises an appropriate error when a second genesis record write is attempted
- [ ] `SQLiteTrustStore` behavior is unchanged (trigger still enforces the constraint at the DB layer)
- [ ] The error type is consistent across all three store implementations (same exception class or a shared base)
- [ ] Unit tests cover: first write succeeds, second write raises error, for both `MemoryStore` and `FilesystemStore`
- [ ] Existing tests continue to pass
