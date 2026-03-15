# Todo 2604: Trust Store Backup and Restore

**Milestone**: M26 — Production Persistence
**Priority**: Medium
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2601

## What

Implement automated backup and restore for the trust store. For SQLite: use the `.backup` command (via the `sqlite3` API) or `VACUUM INTO` to create a consistent copy without locking writers for extended periods. For PostgreSQL: invoke `pg_dump` via subprocess to create a portable dump file. Support point-in-time restore by replaying a backup file against a fresh database. After any restore, run hash chain integrity verification across all records to confirm the restored data is uncorrupted. Expose backup and restore as CLI commands (`care backup` and `care restore <path>`).

## Where

- `src/care_platform/persistence/backup.py`
- `src/care_platform/cli/` (backup/restore commands)

## Evidence

- [ ] `care backup` creates a valid SQLite backup file when the active store is SQLite
- [ ] `care backup` creates a valid pg_dump file when the active store is PostgreSQL
- [ ] `care restore <path>` restores from a SQLite backup file and the platform starts correctly
- [ ] `care restore <path>` restores from a PostgreSQL dump file and the platform starts correctly
- [ ] Hash chain integrity check runs automatically after every restore
- [ ] A tampered backup file fails the integrity check with a clear error message
- [ ] Unit tests cover the backup and restore logic for both backends
- [ ] CLI commands are documented in the operator guide (2903)
