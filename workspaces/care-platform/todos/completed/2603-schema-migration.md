# Todo 2603: Schema Migration Framework

**Milestone**: M26 — Production Persistence
**Priority**: High
**Effort**: Large
**Source**: Phase 3 requirement
**Dependencies**: 2601

## What

Implement a schema versioning and migration system under `src/care_platform/persistence/migrations/`. Store the current schema version in a `schema_version` table. Provide individual migration scripts (Python modules) that upgrade from version N to N+1, each containing an `up()` and a `down()` function. Implement rollback capability: `down()` on the latest migration returns the schema to the previous version. On every application startup, auto-detect the current schema version and run pending migrations in order. Support both SQLite and PostgreSQL backends with the same migration scripts (use standard SQL where possible; mark dialect-specific SQL clearly).

## Where

- `src/care_platform/persistence/migrations/`
- `src/care_platform/persistence/migrations/0001_initial.py`
- `src/care_platform/persistence/migrations/runner.py`

## Evidence

- [ ] `schema_version` table is created on first startup
- [ ] Migration from v1 to v2 (add a test column) runs successfully on SQLite
- [ ] Migration from v1 to v2 runs successfully on PostgreSQL
- [ ] Rollback from v2 to v1 runs successfully on both backends
- [ ] Auto-migration on startup applies only pending migrations (idempotent)
- [ ] Running migrations twice does not error or duplicate work
- [ ] Unit tests cover the migration runner logic
- [ ] Integration tests confirm end-to-end migration and rollback on both database backends
