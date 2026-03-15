# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""PostgreSQL-backed TrustStore — production trust state persistence.

Provides a TrustStore implementation backed by PostgreSQL with connection
pooling. Trust state survives process restarts. Audit anchors and posture
changes are append-only (immutability enforced by database triggers/rules).
Genesis records are write-once (a second store_genesis() call for the same
authority_id is silently ignored).

Thread safety: Uses ``psycopg2`` connection pool — each thread gets its
own connection from the pool.

Usage::

    store = PostgreSQLTrustStore(database_url="postgresql://user:pass@host/db")
    store.store_envelope("env-1", {"id": "env-1", ...})
    envelope = store.get_envelope("env-1")
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)


class PostgreSQLTrustStore:
    """PostgreSQL-backed implementation of the TrustStore protocol.

    All trust objects are stored as JSONB in typed tables. Audit anchors
    and posture changes are append-only — database triggers prevent UPDATE
    and DELETE on those tables. Genesis records are write-once — a second
    insert for the same authority_id is silently ignored.

    Thread safety: Uses ``psycopg2.pool.ThreadedConnectionPool``.
    """

    def __init__(
        self,
        database_url: str | None = None,
        pool_min: int = 2,
        pool_max: int = 10,
    ) -> None:
        """Initialize PostgreSQL store.

        Args:
            database_url: PostgreSQL connection URL. Must not be empty.
            pool_min: Minimum number of connections in the pool.
            pool_max: Maximum number of connections in the pool.

        Raises:
            ValueError: If database_url is empty or None.
        """
        if not database_url or not database_url.strip():
            raise ValueError(
                "database_url must not be empty — set DATABASE_URL environment variable"
            )

        self._database_url = database_url
        self._pool_min = pool_min
        self._pool_max = pool_max
        self._pool: psycopg2.pool.ThreadedConnectionPool | None = None
        self._init_lock = threading.Lock()
        self._pool_closed = False

        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=pool_min,
            maxconn=pool_max,
            dsn=database_url,
        )

        self._create_tables()

    @property
    def pool_min(self) -> int:
        return self._pool_min

    @property
    def pool_max(self) -> int:
        return self._pool_max

    # --- Connection management ---

    def _get_connection(self) -> psycopg2.extensions.connection:
        """Get a connection from the pool."""
        if self._pool is None or self._pool_closed:
            raise RuntimeError("Connection pool is closed")
        conn = self._pool.getconn()
        conn.autocommit = False
        return conn

    def _put_connection(self, conn: psycopg2.extensions.connection) -> None:
        """Return a connection to the pool."""
        if self._pool is not None and not self._pool_closed:
            self._pool.putconn(conn)

    def _execute_with_connection(self, func):
        """Execute a function with a pooled connection, handling cleanup."""
        conn = self._get_connection()
        try:
            result = func(conn)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_connection(conn)

    def _execute_raw(self, sql: str, params: tuple = ()) -> None:
        """Execute raw SQL — used for testing trigger enforcement.

        This does NOT catch exceptions so tests can verify that triggers
        raise errors on forbidden operations.
        """
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_connection(conn)

    # --- Schema ---

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()

            # Constraint envelopes
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS envelopes (
                    envelope_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    data JSONB NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_envelopes_agent
                ON envelopes(agent_id)
            """
            )

            # Audit anchors (append-only: triggers below)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_anchors (
                    anchor_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    action TEXT,
                    verification_level TEXT,
                    timestamp TIMESTAMPTZ,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_anchors_agent
                ON audit_anchors(agent_id)
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_anchors_timestamp
                ON audit_anchors(timestamp)
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_anchors_level
                ON audit_anchors(verification_level)
            """
            )

            # Posture changes (append-only: triggers below)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS posture_changes (
                    id SERIAL PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posture_agent
                ON posture_changes(agent_id)
            """
            )

            # Revocations
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS revocations (
                    revocation_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_revocations_agent
                ON revocations(agent_id)
            """
            )

            # Genesis records
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS genesis_records (
                    authority_id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """
            )

            # Delegation records
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS delegations (
                    delegation_id TEXT PRIMARY KEY,
                    delegator_id TEXT NOT NULL,
                    delegatee_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_delegations_delegator
                ON delegations(delegator_id)
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_delegations_delegatee
                ON delegations(delegatee_id)
            """
            )

            # Capability attestations
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS attestations (
                    attestation_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_attestations_agent
                ON attestations(agent_id)
            """
            )

            # Organization definitions
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS org_definitions (
                    org_id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """
            )

            # ---------------------------------------------------------
            # Append-only triggers for audit_anchors
            # ---------------------------------------------------------
            cur.execute(
                """
                CREATE OR REPLACE FUNCTION prevent_audit_anchor_mutation()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'Audit anchors are immutable: % not permitted', TG_OP;
                END;
                $$ LANGUAGE plpgsql
            """
            )
            cur.execute(
                """
                DROP TRIGGER IF EXISTS prevent_audit_anchor_update ON audit_anchors
            """
            )
            cur.execute(
                """
                CREATE TRIGGER prevent_audit_anchor_update
                BEFORE UPDATE ON audit_anchors
                FOR EACH ROW EXECUTE FUNCTION prevent_audit_anchor_mutation()
            """
            )
            cur.execute(
                """
                DROP TRIGGER IF EXISTS prevent_audit_anchor_delete ON audit_anchors
            """
            )
            cur.execute(
                """
                CREATE TRIGGER prevent_audit_anchor_delete
                BEFORE DELETE ON audit_anchors
                FOR EACH ROW EXECUTE FUNCTION prevent_audit_anchor_mutation()
            """
            )

            # ---------------------------------------------------------
            # Append-only triggers for posture_changes
            # ---------------------------------------------------------
            cur.execute(
                """
                CREATE OR REPLACE FUNCTION prevent_posture_change_mutation()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'Posture changes are immutable: % not permitted', TG_OP;
                END;
                $$ LANGUAGE plpgsql
            """
            )
            cur.execute(
                """
                DROP TRIGGER IF EXISTS prevent_posture_change_update ON posture_changes
            """
            )
            cur.execute(
                """
                CREATE TRIGGER prevent_posture_change_update
                BEFORE UPDATE ON posture_changes
                FOR EACH ROW EXECUTE FUNCTION prevent_posture_change_mutation()
            """
            )
            cur.execute(
                """
                DROP TRIGGER IF EXISTS prevent_posture_change_delete ON posture_changes
            """
            )
            cur.execute(
                """
                CREATE TRIGGER prevent_posture_change_delete
                BEFORE DELETE ON posture_changes
                FOR EACH ROW EXECUTE FUNCTION prevent_posture_change_mutation()
            """
            )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_connection(conn)

    # --- TrustStore Protocol: Envelopes ---

    def store_envelope(self, envelope_id: str, data: dict) -> None:
        """Store a constraint envelope (upsert with version increment)."""
        agent_id = data.get("agent_id", "")
        data_json = json.dumps(data, default=str)

        def _do(conn):
            cur = conn.cursor()
            # Upsert: insert or update with version increment
            cur.execute(
                """INSERT INTO envelopes (envelope_id, agent_id, data, version)
                   VALUES (%s, %s, %s::jsonb, 1)
                   ON CONFLICT (envelope_id) DO UPDATE SET
                       agent_id = EXCLUDED.agent_id,
                       data = EXCLUDED.data,
                       version = envelopes.version + 1""",
                (envelope_id, agent_id, data_json),
            )

        self._execute_with_connection(_do)

    def get_envelope(self, envelope_id: str) -> dict | None:
        """Get a constraint envelope by ID."""

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM envelopes WHERE envelope_id = %s",
                (envelope_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])

        return self._execute_with_connection(_do)

    def list_envelopes(self, agent_id: str | None = None) -> list[dict]:
        """List envelopes, optionally filtered by agent_id."""

        def _do(conn):
            cur = conn.cursor()
            if agent_id is not None:
                cur.execute(
                    "SELECT data FROM envelopes WHERE agent_id = %s ORDER BY created_at",
                    (agent_id,),
                )
            else:
                cur.execute("SELECT data FROM envelopes ORDER BY created_at")
            rows = cur.fetchall()
            return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]

        return self._execute_with_connection(_do)

    # --- TrustStore Protocol: Audit Anchors ---

    def store_audit_anchor(self, anchor_id: str, data: dict) -> None:
        """Store an audit anchor (append-only, INSERT ON CONFLICT DO NOTHING)."""
        agent_id = data.get("agent_id", "")
        action = data.get("action", "")
        verification_level = data.get("verification_level", "")
        timestamp = data.get("timestamp", datetime.now(UTC).isoformat())
        data_json = json.dumps(data, default=str)

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO audit_anchors
                   (anchor_id, agent_id, action, verification_level, timestamp, data)
                   VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (anchor_id) DO NOTHING""",
                (anchor_id, agent_id, action, verification_level, timestamp, data_json),
            )

        self._execute_with_connection(_do)

    def get_audit_anchor(self, anchor_id: str) -> dict | None:
        """Get an audit anchor by ID."""

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM audit_anchors WHERE anchor_id = %s",
                (anchor_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])

        return self._execute_with_connection(_do)

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

        def _do(conn):
            cur = conn.cursor()
            conditions: list[str] = []
            params: list = []

            if agent_id is not None:
                conditions.append("agent_id = %s")
                params.append(agent_id)
            if action is not None:
                conditions.append("action = %s")
                params.append(action)
            if since is not None:
                conditions.append("timestamp >= %s")
                params.append(since.isoformat())
            if until is not None:
                conditions.append("timestamp <= %s")
                params.append(until.isoformat())
            if verification_level is not None:
                conditions.append("verification_level = %s")
                params.append(verification_level)

            where_clause = " AND ".join(conditions) if conditions else "TRUE"
            query = (
                f"SELECT data FROM audit_anchors WHERE {where_clause} ORDER BY timestamp LIMIT %s"
            )
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()
            return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]

        return self._execute_with_connection(_do)

    # --- TrustStore Protocol: Posture Changes ---

    def store_posture_change(self, agent_id: str, data: dict) -> None:
        """Store a posture change record (append-only)."""
        data_json = json.dumps(data, default=str)

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO posture_changes (agent_id, data) VALUES (%s, %s::jsonb)",
                (agent_id, data_json),
            )

        self._execute_with_connection(_do)

    def get_posture_history(self, agent_id: str) -> list[dict]:
        """Get posture change history for an agent."""

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM posture_changes WHERE agent_id = %s ORDER BY created_at",
                (agent_id,),
            )
            rows = cur.fetchall()
            return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]

        return self._execute_with_connection(_do)

    # --- TrustStore Protocol: Revocations ---

    def store_revocation(self, revocation_id: str, data: dict) -> None:
        """Store a revocation record."""
        agent_id = data.get("agent_id", "")
        data_json = json.dumps(data, default=str)

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO revocations (revocation_id, agent_id, data)
                   VALUES (%s, %s, %s::jsonb)
                   ON CONFLICT (revocation_id) DO UPDATE SET
                       agent_id = EXCLUDED.agent_id,
                       data = EXCLUDED.data""",
                (revocation_id, agent_id, data_json),
            )

        self._execute_with_connection(_do)

    def get_revocations(self, agent_id: str | None = None) -> list[dict]:
        """Get revocations, optionally filtered by agent_id."""

        def _do(conn):
            cur = conn.cursor()
            if agent_id is not None:
                cur.execute(
                    "SELECT data FROM revocations WHERE agent_id = %s ORDER BY created_at",
                    (agent_id,),
                )
            else:
                cur.execute("SELECT data FROM revocations ORDER BY created_at")
            rows = cur.fetchall()
            return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]

        return self._execute_with_connection(_do)

    # --- Genesis Records (write-once) ---

    def store_genesis(self, authority_id: str, data: dict) -> None:
        """Store a genesis record (write-once).

        If a genesis record already exists for the given authority_id,
        the call is silently ignored so the original trust root is
        never overwritten.
        """
        data_json = json.dumps(data, default=str)

        def _do(conn):
            cur = conn.cursor()
            # Write-once: INSERT ON CONFLICT DO NOTHING
            cur.execute(
                """INSERT INTO genesis_records (authority_id, data)
                   VALUES (%s, %s::jsonb)
                   ON CONFLICT (authority_id) DO NOTHING""",
                (authority_id, data_json),
            )

        self._execute_with_connection(_do)

    def get_genesis(self, authority_id: str) -> dict | None:
        """Get a genesis record by authority ID."""

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM genesis_records WHERE authority_id = %s",
                (authority_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])

        return self._execute_with_connection(_do)

    # --- Delegation Records ---

    def store_delegation(self, delegation_id: str, data: dict) -> None:
        """Store a delegation record."""
        delegator_id = data.get("delegator_id", "")
        delegatee_id = data.get("delegatee_id", "")
        data_json = json.dumps(data, default=str)

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO delegations
                   (delegation_id, delegator_id, delegatee_id, data)
                   VALUES (%s, %s, %s, %s::jsonb)
                   ON CONFLICT (delegation_id) DO UPDATE SET
                       delegator_id = EXCLUDED.delegator_id,
                       delegatee_id = EXCLUDED.delegatee_id,
                       data = EXCLUDED.data""",
                (delegation_id, delegator_id, delegatee_id, data_json),
            )

        self._execute_with_connection(_do)

    def get_delegation(self, delegation_id: str) -> dict | None:
        """Get a delegation record by ID."""

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM delegations WHERE delegation_id = %s",
                (delegation_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])

        return self._execute_with_connection(_do)

    def get_delegations_for(self, agent_id: str) -> list[dict]:
        """Get all delegations where agent is delegator or delegatee."""

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                """SELECT data FROM delegations
                   WHERE delegator_id = %s OR delegatee_id = %s
                   ORDER BY created_at""",
                (agent_id, agent_id),
            )
            rows = cur.fetchall()
            return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]

        return self._execute_with_connection(_do)

    # --- Attestations ---

    def store_attestation(self, attestation_id: str, data: dict) -> None:
        """Store a capability attestation."""
        agent_id = data.get("agent_id", "")
        data_json = json.dumps(data, default=str)

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO attestations (attestation_id, agent_id, data)
                   VALUES (%s, %s, %s::jsonb)
                   ON CONFLICT (attestation_id) DO UPDATE SET
                       agent_id = EXCLUDED.agent_id,
                       data = EXCLUDED.data""",
                (attestation_id, agent_id, data_json),
            )

        self._execute_with_connection(_do)

    def get_attestation(self, attestation_id: str) -> dict | None:
        """Get an attestation by ID."""

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM attestations WHERE attestation_id = %s",
                (attestation_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])

        return self._execute_with_connection(_do)

    def get_attestations_for(self, agent_id: str) -> list[dict]:
        """Get all attestations for an agent."""

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM attestations WHERE agent_id = %s ORDER BY created_at",
                (agent_id,),
            )
            rows = cur.fetchall()
            return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]

        return self._execute_with_connection(_do)

    # --- Org Definitions ---

    def store_org_definition(self, org_id: str, data: dict) -> None:
        """Store an organization definition (upsert)."""
        data_json = json.dumps(data, default=str)

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO org_definitions (org_id, data)
                   VALUES (%s, %s::jsonb)
                   ON CONFLICT (org_id) DO UPDATE SET data = EXCLUDED.data""",
                (org_id, data_json),
            )

        self._execute_with_connection(_do)

    def get_org_definition(self, org_id: str) -> dict | None:
        """Get an organization definition by ID."""

        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM org_definitions WHERE org_id = %s",
                (org_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])

        return self._execute_with_connection(_do)

    # --- Health ---

    def health_check(self) -> bool:
        """Check if the PostgreSQL database is accessible."""
        try:

            def _do(conn):
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                return True

            return self._execute_with_connection(_do)
        except Exception:
            return False

    # --- Cleanup (for tests) ---

    def _drop_all_tables(self) -> None:
        """Drop all trust store tables. Used in test cleanup."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            # Drop triggers first
            cur.execute("DROP TRIGGER IF EXISTS prevent_audit_anchor_update ON audit_anchors")
            cur.execute("DROP TRIGGER IF EXISTS prevent_audit_anchor_delete ON audit_anchors")
            cur.execute("DROP TRIGGER IF EXISTS prevent_posture_change_update ON posture_changes")
            cur.execute("DROP TRIGGER IF EXISTS prevent_posture_change_delete ON posture_changes")
            # Drop functions
            cur.execute("DROP FUNCTION IF EXISTS prevent_audit_anchor_mutation() CASCADE")
            cur.execute("DROP FUNCTION IF EXISTS prevent_posture_change_mutation() CASCADE")
            # Drop tables
            for table in (
                "envelopes",
                "audit_anchors",
                "posture_changes",
                "revocations",
                "genesis_records",
                "delegations",
                "attestations",
                "org_definitions",
                "_migrations",
            ):
                cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_connection(conn)

    # --- Lifecycle ---

    def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None and not self._pool_closed:
            self._pool_closed = True
            self._pool.closeall()

    def __enter__(self) -> PostgreSQLTrustStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
