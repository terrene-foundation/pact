# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""SQLite-backed TrustStore — durable trust state persistence.

Provides a TrustStore implementation backed by SQLite. Trust state survives
process restarts. Audit anchors and posture changes are append-only
(immutability enforced by database triggers). Genesis records are write-once
(a second store_genesis() call for the same authority_id raises
GenesisAlreadyExistsError).

Thread safety: Uses ``threading.local()`` so each thread gets its own SQLite
connection. For ``:memory:`` databases the shared-cache URI mode
(``file::memory:?cache=shared``) ensures all threads see the same data.

Usage:
    store = SQLiteTrustStore("care_platform.db")
    store.store_envelope("env-1", {"id": "env-1", ...})
    envelope = store.get_envelope("env-1")
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class GenesisAlreadyExistsError(ValueError):
    """Raised when attempting to overwrite an existing genesis record.

    Genesis records are write-once (immutable after creation). Attempting
    to store a second genesis record for the same authority_id is an error
    that must be handled explicitly by the caller.
    """

    def __init__(self, authority_id: str) -> None:
        self.authority_id = authority_id
        super().__init__(
            f"Genesis record already exists for authority '{authority_id}'. "
            "Genesis records are write-once and cannot be overwritten."
        )


class SQLiteTrustStore:
    """SQLite-backed implementation of the TrustStore protocol.

    All trust objects are stored as JSON blobs in typed tables. Audit anchors
    and posture changes are append-only — database triggers prevent UPDATE and
    DELETE on those tables.  Genesis records are write-once — a second insert
    for the same authority_id raises ``GenesisAlreadyExistsError``.

    Thread safety: Per-thread connections via ``threading.local()``.
    """

    # Counter for unique in-memory database names so that each instance gets
    # its own isolated shared-cache database.
    _instance_counter_lock = threading.Lock()
    _instance_counter = 0

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        """Initialize SQLite store.

        Args:
            db_path: Path to SQLite database file. Use ":memory:" for
                in-memory storage (useful for testing).
        """
        self._db_path = str(db_path)
        if self._db_path == ":memory:":
            with SQLiteTrustStore._instance_counter_lock:
                SQLiteTrustStore._instance_counter += 1
                self._memory_id = SQLiteTrustStore._instance_counter
        else:
            self._memory_id = 0
        self._local = threading.local()
        self._init_lock = threading.Lock()
        # Write lock serialises mutations when using shared-cache mode
        # (shared-cache table-level locks are not handled by busy_timeout).
        self._write_lock = threading.Lock()
        self._tables_created = False
        # Initialise tables on the calling thread's connection.
        self._ensure_tables(self._get_connection())

    # --- Connection management ---

    def _get_connection(self) -> sqlite3.Connection:
        """Return a per-thread SQLite connection, creating one if needed."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            if self._db_path == ":memory:":
                conn = sqlite3.connect(
                    f"file:memdb_{self._memory_id}?mode=memory&cache=shared",
                    uri=True,
                )
            else:
                conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            # Limit WAL journal size to 64 MB to prevent unbounded growth
            conn.execute("PRAGMA journal_size_limit=67108864")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            self._ensure_tables(conn)
        return self._local.conn

    def _ensure_tables(self, conn: sqlite3.Connection) -> None:
        """Create tables exactly once (double-checked locking)."""
        if not self._tables_created:
            with self._init_lock:
                if not self._tables_created:
                    self._create_tables(conn)
                    self._tables_created = True

    # --- Schema ---

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """Create tables if they don't exist."""
        with conn:
            # Constraint envelopes — RT4-L6: version column
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS envelopes (
                    envelope_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    data TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_envelopes_agent
                ON envelopes(agent_id)
            """
            )

            # Audit anchors (append-only: triggers below)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_anchors (
                    anchor_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    action TEXT,
                    verification_level TEXT,
                    timestamp TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_anchors_agent
                ON audit_anchors(agent_id)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_anchors_timestamp
                ON audit_anchors(timestamp)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_anchors_level
                ON audit_anchors(verification_level)
            """
            )

            # Posture changes (append-only: triggers below)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posture_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posture_agent
                ON posture_changes(agent_id)
            """
            )

            # Revocations
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS revocations (
                    revocation_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_revocations_agent
                ON revocations(agent_id)
            """
            )

            # Genesis records
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS genesis_records (
                    authority_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """
            )

            # Delegation records
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS delegations (
                    delegation_id TEXT PRIMARY KEY,
                    delegator_id TEXT NOT NULL,
                    delegatee_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_delegations_delegator
                ON delegations(delegator_id)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_delegations_delegatee
                ON delegations(delegatee_id)
            """
            )

            # Capability attestations
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attestations (
                    attestation_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_attestations_agent
                ON attestations(agent_id)
            """
            )

            # Organization definitions
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS org_definitions (
                    org_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """
            )

            # ---------------------------------------------------------
            # RT4-C1: Append-only triggers for audit_anchors
            # ---------------------------------------------------------
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_audit_anchor_update
                BEFORE UPDATE ON audit_anchors BEGIN
                    SELECT RAISE(ABORT, 'Audit anchors are immutable: UPDATE not permitted');
                END
            """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_audit_anchor_delete
                BEFORE DELETE ON audit_anchors BEGIN
                    SELECT RAISE(ABORT, 'Audit anchors are immutable: DELETE not permitted');
                END
            """
            )

            # ---------------------------------------------------------
            # RT4-C1: Append-only triggers for posture_changes
            # ---------------------------------------------------------
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_posture_change_update
                BEFORE UPDATE ON posture_changes BEGIN
                    SELECT RAISE(ABORT, 'Posture changes are immutable: UPDATE not permitted');
                END
            """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_posture_change_delete
                BEFORE DELETE ON posture_changes BEGIN
                    SELECT RAISE(ABORT, 'Posture changes are immutable: DELETE not permitted');
                END
            """
            )

            # ---------------------------------------------------------
            # RT4-C3: Referential integrity trigger — prevent deletion
            # of genesis records that are referenced by delegations.
            # ---------------------------------------------------------
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_genesis_delete_with_delegations
                BEFORE DELETE ON genesis_records BEGIN
                    SELECT RAISE(ABORT, 'Cannot delete genesis: delegations reference this authority')
                    WHERE EXISTS (
                        SELECT 1 FROM delegations
                        WHERE json_extract(data, '$.delegator_id') = OLD.authority_id
                    );
                END
            """
            )

    # --- TrustStore Protocol: Envelopes ---

    def store_envelope(self, envelope_id: str, data: dict) -> None:
        """Store a constraint envelope.

        RT4-L6: If an envelope with the same ID already exists, the version
        number is incremented on replacement.
        """
        conn = self._get_connection()
        agent_id = data.get("agent_id", "")

        with self._write_lock:
            # Check for existing version to increment
            row = conn.execute(
                "SELECT version FROM envelopes WHERE envelope_id = ?",
                (envelope_id,),
            ).fetchone()
            new_version = (row[0] + 1) if row is not None else 1

            with conn:
                conn.execute(
                    """INSERT OR REPLACE INTO envelopes
                       (envelope_id, agent_id, data, version)
                       VALUES (?, ?, ?, ?)""",
                    (envelope_id, agent_id, json.dumps(data, default=str), new_version),
                )

    def get_envelope(self, envelope_id: str) -> dict | None:
        """Get a constraint envelope by ID."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT data FROM envelopes WHERE envelope_id = ?",
            (envelope_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def get_envelope_version(self, envelope_id: str) -> int | None:
        """Get the current version number of an envelope.

        Returns None if the envelope does not exist.
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT version FROM envelopes WHERE envelope_id = ?",
            (envelope_id,),
        ).fetchone()
        if row is None:
            return None
        return row[0]

    def list_envelopes(self, agent_id: str | None = None) -> list[dict]:
        """List envelopes, optionally filtered by agent_id."""
        conn = self._get_connection()
        if agent_id is not None:
            rows = conn.execute(
                "SELECT data FROM envelopes WHERE agent_id = ? ORDER BY created_at",
                (agent_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT data FROM envelopes ORDER BY created_at",
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    # --- TrustStore Protocol: Audit Anchors ---

    def store_audit_anchor(self, anchor_id: str, data: dict) -> None:
        """Store an audit anchor (append-only)."""
        conn = self._get_connection()
        agent_id = data.get("agent_id", "")
        action = data.get("action", "")
        verification_level = data.get("verification_level", "")
        timestamp = data.get("timestamp", datetime.now(UTC).isoformat())
        with self._write_lock, conn:
            conn.execute(
                """INSERT OR IGNORE INTO audit_anchors
                       (anchor_id, agent_id, action, verification_level, timestamp, data)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    anchor_id,
                    agent_id,
                    action,
                    verification_level,
                    timestamp,
                    json.dumps(data, default=str),
                ),
            )

    def get_audit_anchor(self, anchor_id: str) -> dict | None:
        """Get an audit anchor by ID."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT data FROM audit_anchors WHERE anchor_id = ?",
            (anchor_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def query_anchors(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        verification_level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit anchors with filtering."""
        conn = self._get_connection()
        conditions: list[str] = []
        params: list[str | int] = []

        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if action is not None:
            conditions.append("action = ?")
            params.append(action)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())
        if until is not None:
            conditions.append("timestamp <= ?")
            params.append(until.isoformat())
        if verification_level is not None:
            conditions.append("verification_level = ?")
            params.append(verification_level)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT data FROM audit_anchors WHERE {where_clause} ORDER BY timestamp LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [json.loads(row[0]) for row in rows]

    # --- TrustStore Protocol: Posture Changes ---

    def store_posture_change(self, agent_id: str, data: dict) -> None:
        """Store a posture change record (append-only)."""
        conn = self._get_connection()
        with self._write_lock, conn:
            conn.execute(
                "INSERT INTO posture_changes (agent_id, data) VALUES (?, ?)",
                (agent_id, json.dumps(data, default=str)),
            )

    def get_posture_history(self, agent_id: str) -> list[dict]:
        """Get posture change history for an agent."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT data FROM posture_changes WHERE agent_id = ? ORDER BY created_at",
            (agent_id,),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    # --- TrustStore Protocol: Revocations ---

    def store_revocation(self, revocation_id: str, data: dict) -> None:
        """Store a revocation record."""
        conn = self._get_connection()
        agent_id = data.get("agent_id", "")
        with self._write_lock:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO revocations (revocation_id, agent_id, data) VALUES (?, ?, ?)",
                    (revocation_id, agent_id, json.dumps(data, default=str)),
                )

    def get_revocations(self, agent_id: str | None = None) -> list[dict]:
        """Get revocations, optionally filtered by agent_id."""
        conn = self._get_connection()
        if agent_id is not None:
            rows = conn.execute(
                "SELECT data FROM revocations WHERE agent_id = ? ORDER BY created_at",
                (agent_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT data FROM revocations ORDER BY created_at",
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    # --- Extended: Genesis Records ---

    def store_genesis(self, authority_id: str, data: dict) -> None:
        """Store a genesis record (write-once).

        RT5-14: If a genesis record already exists for the given
        *authority_id*, raises ``GenesisAlreadyExistsError`` so that the
        caller must handle the duplicate explicitly. The original trust
        root is never overwritten.

        Raises:
            GenesisAlreadyExistsError: If a genesis record already exists
                for the given authority_id.
        """
        conn = self._get_connection()
        with self._write_lock:
            existing = self.get_genesis(authority_id)
            if existing is not None:
                logger.warning(
                    "Genesis record already exists for '%s' (write-once enforcement)",
                    authority_id,
                )
                raise GenesisAlreadyExistsError(authority_id)
            with conn:
                conn.execute(
                    "INSERT INTO genesis_records (authority_id, data) VALUES (?, ?)",
                    (authority_id, json.dumps(data, default=str)),
                )

    def get_genesis(self, authority_id: str) -> dict | None:
        """Get a genesis record by authority ID."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT data FROM genesis_records WHERE authority_id = ?",
            (authority_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    # --- Extended: Delegation Records ---

    def store_delegation(self, delegation_id: str, data: dict) -> None:
        """Store a delegation record."""
        conn = self._get_connection()
        delegator_id = data.get("delegator_id", "")
        delegatee_id = data.get("delegatee_id", "")
        with self._write_lock, conn:
            conn.execute(
                """INSERT OR REPLACE INTO delegations
                       (delegation_id, delegator_id, delegatee_id, data)
                       VALUES (?, ?, ?, ?)""",
                (delegation_id, delegator_id, delegatee_id, json.dumps(data, default=str)),
            )

    def get_delegation(self, delegation_id: str) -> dict | None:
        """Get a delegation record by ID."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT data FROM delegations WHERE delegation_id = ?",
            (delegation_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def get_delegations_for(self, agent_id: str) -> list[dict]:
        """Get all delegations where agent is delegator or delegatee."""
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT data FROM delegations
               WHERE delegator_id = ? OR delegatee_id = ?
               ORDER BY created_at""",
            (agent_id, agent_id),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    # --- Extended: Attestations ---

    def store_attestation(self, attestation_id: str, data: dict) -> None:
        """Store a capability attestation."""
        conn = self._get_connection()
        agent_id = data.get("agent_id", "")
        with self._write_lock:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO attestations (attestation_id, agent_id, data) VALUES (?, ?, ?)",
                    (attestation_id, agent_id, json.dumps(data, default=str)),
                )

    def get_attestation(self, attestation_id: str) -> dict | None:
        """Get an attestation by ID."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT data FROM attestations WHERE attestation_id = ?",
            (attestation_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def get_attestations_for(self, agent_id: str) -> list[dict]:
        """Get all attestations for an agent."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT data FROM attestations WHERE agent_id = ? ORDER BY created_at",
            (agent_id,),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    # --- Org Definitions ---

    def store_org_definition(self, org_id: str, data: dict) -> None:
        """Store an organization definition (upsert)."""
        conn = self._get_connection()
        with self._write_lock, conn:
            conn.execute(
                "INSERT OR REPLACE INTO org_definitions (org_id, data) VALUES (?, ?)",
                (org_id, json.dumps(data, default=str)),
            )

    def get_org_definition(self, org_id: str) -> dict | None:
        """Get an organization definition by ID."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT data FROM org_definitions WHERE org_id = ?",
            (org_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    # --- Health ---

    def health_check(self) -> bool:
        """Check if the SQLite database is accessible.

        Executes a simple query to verify connectivity.
        """
        try:
            conn = self._get_connection()
            conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    # --- Lifecycle ---

    def close(self) -> None:
        """Close the current thread's database connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def __enter__(self) -> SQLiteTrustStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
