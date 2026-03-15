# Todo 2601: PostgreSQL TrustStore Implementation

**Milestone**: M26 — Production Persistence
**Priority**: High
**Effort**: Large
**Source**: Phase 3 requirement
**Dependencies**: 2101

## What

Implement `PostgreSQLTrustStore` following the `TrustStore` protocol already defined for `SQLiteTrustStore`. Use `asyncpg` or `psycopg` (async variant) for non-blocking database access. The implementation must provide the same correctness guarantees as the SQLite store: append-only audit log (no updates or deletes permitted), write-once genesis record (second write raises a typed error), and hash chain continuity enforcement. Add connection pooling (configurable pool size from `.env`). Schema must be auto-created on first connection if tables do not exist. Read connection parameters from `CARE_DB_URL` in `.env`.

## Where

- `src/care_platform/persistence/postgresql_store.py`

## Evidence

- [ ] `PostgreSQLTrustStore` connects to a live PostgreSQL instance using `CARE_DB_URL`
- [ ] All `TrustStore` protocol tests pass when run against PostgreSQL
- [ ] Append-only constraint is enforced: any attempt to update or delete a record raises a typed error
- [ ] Write-once genesis constraint is enforced: a second genesis write for the same workspace raises a typed error
- [ ] Hash chain continuity is validated on every append
- [ ] Connection pooling is active and pool size is configurable from `.env`
- [ ] Schema (tables, indexes) is auto-created on first connection when absent
- [ ] Integration tests run against a real PostgreSQL instance (Docker-based in CI)
