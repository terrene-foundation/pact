# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Schema migration framework for TrustStore backends.

Tracks applied migrations in a ``_migrations`` table. Each migration has a
version number, description, and list of SQL statements. Supports both SQLite
and PostgreSQL.

Usage::

    from pact_platform.trust.store.migrations import migrate, current_version
    from pact_platform.trust.store.sqlite_store import SQLiteTrustStore

    store = SQLiteTrustStore("care.db")
    applied = migrate(store)
    print(f"Schema at version {current_version(store)}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MigrationError(Exception):
    """Raised when a migration fails to apply."""

    pass


# ---------------------------------------------------------------------------
# Migration dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Migration:
    """A single schema migration.

    Attributes:
        version: Positive integer identifying this migration (must be > 0).
        description: Human-readable description (must not be empty).
        sql_statements: One or more SQL statements to execute (must not be empty).
    """

    version: int
    description: str
    sql_statements: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError(f"Migration version must be > 0, got {self.version}")
        if not self.description or not self.description.strip():
            raise ValueError("Migration description must not be empty")
        if not self.sql_statements:
            raise ValueError("Migration sql_statements must not be empty")


# ---------------------------------------------------------------------------
# Defined migrations
# ---------------------------------------------------------------------------

# Migration v1: Initial schema — creates all trust store tables.
# These match the schema defined in SQLiteTrustStore._create_tables but
# expressed as standard SQL that works for both SQLite and PostgreSQL.
# The actual SQLiteTrustStore already creates tables on construction, so
# this migration is a no-op for existing stores but ensures the migration
# table tracks the baseline.

_MIGRATIONS: list[Migration] = [
    Migration(
        version=1,
        description="Initial schema — trust store tables",
        sql_statements=[
            # Constraint envelopes
            """CREATE TABLE IF NOT EXISTS envelopes (
                envelope_id TEXT PRIMARY KEY,
                agent_id TEXT,
                data TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
            "CREATE INDEX IF NOT EXISTS idx_envelopes_agent ON envelopes(agent_id)",
            # Audit anchors (append-only)
            """CREATE TABLE IF NOT EXISTS audit_anchors (
                anchor_id TEXT PRIMARY KEY,
                agent_id TEXT,
                action TEXT,
                verification_level TEXT,
                timestamp TEXT,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
            "CREATE INDEX IF NOT EXISTS idx_anchors_agent ON audit_anchors(agent_id)",
            "CREATE INDEX IF NOT EXISTS idx_anchors_timestamp ON audit_anchors(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_anchors_level ON audit_anchors(verification_level)",
            # Posture changes (append-only)
            """CREATE TABLE IF NOT EXISTS posture_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
            "CREATE INDEX IF NOT EXISTS idx_posture_agent ON posture_changes(agent_id)",
            # Revocations
            """CREATE TABLE IF NOT EXISTS revocations (
                revocation_id TEXT PRIMARY KEY,
                agent_id TEXT,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
            "CREATE INDEX IF NOT EXISTS idx_revocations_agent ON revocations(agent_id)",
            # Genesis records
            """CREATE TABLE IF NOT EXISTS genesis_records (
                authority_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
            # Delegation records
            """CREATE TABLE IF NOT EXISTS delegations (
                delegation_id TEXT PRIMARY KEY,
                delegator_id TEXT NOT NULL,
                delegatee_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
            "CREATE INDEX IF NOT EXISTS idx_delegations_delegator ON delegations(delegator_id)",
            "CREATE INDEX IF NOT EXISTS idx_delegations_delegatee ON delegations(delegatee_id)",
            # Capability attestations
            """CREATE TABLE IF NOT EXISTS attestations (
                attestation_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
            "CREATE INDEX IF NOT EXISTS idx_attestations_agent ON attestations(agent_id)",
            # Organization definitions
            """CREATE TABLE IF NOT EXISTS org_definitions (
                org_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_migrations_table(store: object) -> None:
    """Create the ``_migrations`` table if it does not exist.

    Works with any store that exposes ``_get_connection()``.
    """
    conn = store._get_connection()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS _migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.commit()


def _get_applied_versions(store: object) -> set[int]:
    """Return the set of already-applied migration versions."""
    conn = store._get_connection()
    try:
        rows = conn.execute("SELECT version FROM _migrations ORDER BY version").fetchall()
        return {row[0] for row in rows}
    except Exception:
        # Table may not exist yet
        return set()


def _apply_migration(store: object, migration: Migration) -> None:
    """Apply a single migration within a transaction.

    Raises MigrationError on failure with version context.
    """
    conn = store._get_connection()
    try:
        with conn:
            for sql in migration.sql_statements:
                conn.execute(sql)
            conn.execute(
                "INSERT INTO _migrations (version, description) VALUES (?, ?)",
                (migration.version, migration.description),
            )
        logger.info("Applied migration v%d: %s", migration.version, migration.description)
    except Exception as exc:
        raise MigrationError(
            f"Failed to apply migration v{migration.version} ({migration.description}): {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def current_version(store: object) -> int:
    """Return the current schema version (highest applied migration).

    Returns 0 if no migrations have been applied.
    """
    _ensure_migrations_table(store)
    conn = store._get_connection()
    row = conn.execute("SELECT MAX(version) FROM _migrations").fetchone()
    if row is None or row[0] is None:
        return 0
    return row[0]


def get_pending_migrations(store: object) -> list[Migration]:
    """Return migrations that have not yet been applied, in version order."""
    _ensure_migrations_table(store)
    applied = _get_applied_versions(store)
    return [m for m in sorted(_MIGRATIONS, key=lambda m: m.version) if m.version not in applied]


def migrate(store: object) -> list[Migration]:
    """Apply all pending migrations in ascending version order.

    Returns the list of migrations that were applied (empty if all
    migrations were already applied).

    Raises MigrationError if any migration fails.
    """
    _ensure_migrations_table(store)
    pending = get_pending_migrations(store)
    applied: list[Migration] = []
    for migration in pending:
        _apply_migration(store, migration)
        applied.append(migration)
    return applied
