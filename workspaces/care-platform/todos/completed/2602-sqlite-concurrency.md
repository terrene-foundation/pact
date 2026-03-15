# Todo 2602: SQLite WAL Mode Concurrency

**Milestone**: M26 — Production Persistence
**Priority**: Medium
**Effort**: Small
**Source**: Phase 3 requirement
**Dependencies**: None

## What

Enable WAL (Write-Ahead Logging) mode on `SQLiteTrustStore` to allow concurrent read access from multiple processes or threads while a writer holds the exclusive write lock. Execute `PRAGMA journal_mode=WAL` immediately after each new connection is opened. Verify compatibility with the current installed version of the Kailash SDK (SQLite usage patterns). Document the single-writer limitation clearly in a module-level docstring: SQLite WAL mode permits concurrent readers but only one writer at a time; use `PostgreSQLTrustStore` for multi-writer deployments.

## Where

- `src/care_platform/persistence/sqlite_store.py`

## Evidence

- [ ] `PRAGMA journal_mode=WAL` is executed on every new SQLite connection
- [ ] Concurrent read access from two threads does not block or deadlock
- [ ] Writer exclusion is maintained: a second concurrent writer is serialised (not errored)
- [ ] Module-level docstring documents the single-writer limitation with a reference to `PostgreSQLTrustStore`
- [ ] Existing `SQLiteTrustStore` tests continue to pass
- [ ] A concurrency test confirms two simultaneous readers can query without blocking
