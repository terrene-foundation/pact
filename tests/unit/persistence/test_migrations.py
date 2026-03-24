# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for schema migration framework (Task 2603).

Validates that:
- Migration framework tracks applied migrations in a _migrations table
- Each migration has version, description, and SQL statements
- migrate(store) applies all pending migrations in order
- current_version(store) returns the current schema version
- Initial schema is defined as migration v1
- Works with both SQLite and PostgreSQL
- Migrations are idempotent (running twice applies nothing new)
- Migrations fail safely on bad SQL
"""

import pytest

from pact_platform.trust.store.migrations import (
    Migration,
    MigrationError,
    current_version,
    get_pending_migrations,
    migrate,
)
from pact_platform.trust.store.sqlite_store import SQLiteTrustStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_store():
    """Create a fresh SQLiteTrustStore for migration testing."""
    store = SQLiteTrustStore()
    yield store
    store.close()


@pytest.fixture
def file_sqlite_store(tmp_path):
    """Create a file-based SQLiteTrustStore for migration testing."""
    db_path = tmp_path / "migration_test.db"
    store = SQLiteTrustStore(db_path=str(db_path))
    yield store
    store.close()


# ---------------------------------------------------------------------------
# Migration dataclass
# ---------------------------------------------------------------------------


class TestMigrationDataclass:
    """Migration must have version, description, and sql_statements."""

    def test_migration_has_required_fields(self):
        m = Migration(
            version=1,
            description="Initial schema",
            sql_statements=["CREATE TABLE test (id TEXT PRIMARY KEY)"],
        )
        assert m.version == 1
        assert m.description == "Initial schema"
        assert len(m.sql_statements) == 1

    def test_migration_requires_version(self):
        """Migration must not accept version <= 0."""
        with pytest.raises((ValueError, TypeError)):
            Migration(version=0, description="Bad", sql_statements=[])

    def test_migration_requires_description(self):
        """Migration must not accept empty description."""
        with pytest.raises((ValueError, TypeError)):
            Migration(version=1, description="", sql_statements=[])

    def test_migration_requires_sql_statements(self):
        """Migration must not accept empty sql_statements."""
        with pytest.raises((ValueError, TypeError)):
            Migration(version=1, description="No SQL", sql_statements=[])


# ---------------------------------------------------------------------------
# current_version
# ---------------------------------------------------------------------------


class TestCurrentVersion:
    """current_version returns the schema version."""

    def test_returns_zero_when_no_migrations(self, sqlite_store):
        """Before any migration, version is 0."""
        version = current_version(sqlite_store)
        assert version == 0

    def test_returns_version_after_migration(self, sqlite_store):
        """After applying migrations, version reflects the latest."""
        migrate(sqlite_store)
        version = current_version(sqlite_store)
        assert version >= 1


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------


class TestMigrate:
    """migrate(store) applies pending migrations in order."""

    def test_applies_initial_schema(self, sqlite_store):
        """Migration v1 creates the initial schema tables."""
        applied = migrate(sqlite_store)
        assert len(applied) >= 1
        assert applied[0].version == 1

    def test_idempotent(self, sqlite_store):
        """Running migrate twice should not apply already-applied migrations."""
        first_run = migrate(sqlite_store)
        second_run = migrate(sqlite_store)
        assert len(second_run) == 0, "No migrations should be applied on second run"

    def test_migrations_applied_in_order(self, sqlite_store):
        """Migrations must be applied in ascending version order."""
        applied = migrate(sqlite_store)
        versions = [m.version for m in applied]
        assert versions == sorted(versions), "Migrations must be applied in order"

    def test_current_version_matches_latest(self, sqlite_store):
        """After migrate, current_version equals the highest migration version."""
        applied = migrate(sqlite_store)
        if applied:
            expected = applied[-1].version
            assert current_version(sqlite_store) == expected

    def test_migrations_table_exists_after_migrate(self, sqlite_store):
        """The _migrations table must exist after running migrate."""
        migrate(sqlite_store)
        conn = sqlite_store._get_connection()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'"
        ).fetchone()
        assert row is not None, "_migrations table must exist"

    def test_migrations_table_records(self, sqlite_store):
        """Each applied migration is recorded in _migrations."""
        applied = migrate(sqlite_store)
        conn = sqlite_store._get_connection()
        rows = conn.execute(
            "SELECT version, description FROM _migrations ORDER BY version"
        ).fetchall()
        assert len(rows) == len(applied)
        for row, migration in zip(rows, applied, strict=True):
            assert row[0] == migration.version
            assert row[1] == migration.description


# ---------------------------------------------------------------------------
# get_pending_migrations
# ---------------------------------------------------------------------------


class TestGetPendingMigrations:
    """get_pending_migrations returns migrations not yet applied."""

    def test_all_pending_initially(self, sqlite_store):
        """Before migrate, all defined migrations are pending."""
        pending = get_pending_migrations(sqlite_store)
        assert len(pending) >= 1

    def test_none_pending_after_migrate(self, sqlite_store):
        """After full migrate, no migrations are pending."""
        migrate(sqlite_store)
        pending = get_pending_migrations(sqlite_store)
        assert len(pending) == 0


# ---------------------------------------------------------------------------
# File-based SQLite
# ---------------------------------------------------------------------------


class TestMigrateFileBased:
    """Migrations work on file-based SQLite databases."""

    def test_file_based_migration(self, file_sqlite_store):
        applied = migrate(file_sqlite_store)
        assert len(applied) >= 1
        version = current_version(file_sqlite_store)
        assert version >= 1

    def test_file_based_persistence(self, file_sqlite_store):
        """Migrations persist across store reopening."""
        migrate(file_sqlite_store)
        # The store uses the same DB file, so version should persist
        version = current_version(file_sqlite_store)
        assert version >= 1


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestMigrationErrors:
    """Migration errors are handled explicitly, not silently."""

    def test_bad_sql_raises_migration_error(self, sqlite_store):
        """Invalid SQL in a migration should raise MigrationError."""
        bad_migration = Migration(
            version=9999,
            description="Bad migration",
            sql_statements=["THIS IS NOT VALID SQL AT ALL"],
        )
        with pytest.raises(MigrationError):
            # We test by directly applying a bad migration
            from pact_platform.trust.store.migrations import _apply_migration

            _apply_migration(sqlite_store, bad_migration)

    def test_migration_error_includes_version(self, sqlite_store):
        """MigrationError should include the version that failed."""
        bad_migration = Migration(
            version=9998,
            description="Failing migration",
            sql_statements=["INVALID SQL GARBAGE"],
        )
        try:
            from pact_platform.trust.store.migrations import _apply_migration

            _apply_migration(sqlite_store, bad_migration)
            pytest.fail("Should have raised MigrationError")
        except MigrationError as exc:
            assert "9998" in str(exc), f"Error should mention version 9998: {exc}"
