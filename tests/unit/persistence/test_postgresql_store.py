# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for PostgreSQLTrustStore implementation (Task 2601).

Validates that:
- PostgreSQLTrustStore implements the TrustStore protocol
- All store/get/list/query methods work correctly
- Connection pooling is configured (min 2, max 10)
- Append-only enforcement for audit_anchors and posture_changes
- Write-once enforcement for genesis_records
- Thread safety via connection pool
- Proper error handling and health checks
- Tests skip gracefully when PostgreSQL is unavailable

These tests run against a real PostgreSQL instance when available, and skip
with a clear reason when it is not. NO MOCKING.
"""

import os
import threading
from datetime import UTC, datetime

import pytest

# ---------------------------------------------------------------------------
# Skip if PostgreSQL is not available
# ---------------------------------------------------------------------------

_DATABASE_URL = os.environ.get("DATABASE_URL", "")
_pg_available = False
_skip_reason = "DATABASE_URL not set — PostgreSQL not available"

if _DATABASE_URL and _DATABASE_URL.startswith("postgres"):
    try:
        import psycopg2

        conn = psycopg2.connect(_DATABASE_URL)
        conn.close()
        _pg_available = True
    except Exception as exc:
        _skip_reason = f"PostgreSQL not reachable: {exc}"

pytestmark = pytest.mark.skipif(not _pg_available, reason=_skip_reason)

from pact_platform.trust.store.postgresql_store import PostgreSQLTrustStore
from pact_platform.trust.store.store import TrustStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope_data(envelope_id: str = "env-1", agent_id: str = "agent-1") -> dict:
    return {
        "envelope_id": envelope_id,
        "agent_id": agent_id,
        "financial": {"max_spend_usd": 100.0},
        "created_at": datetime.now(UTC).isoformat(),
    }


def _make_anchor_data(
    anchor_id: str = "anc-1",
    agent_id: str = "agent-1",
    action: str = "read_metrics",
    verification_level: str = "AUTO_APPROVED",
    timestamp: datetime | None = None,
) -> dict:
    return {
        "anchor_id": anchor_id,
        "agent_id": agent_id,
        "action": action,
        "verification_level": verification_level,
        "timestamp": (timestamp or datetime.now(UTC)).isoformat(),
    }


def _make_posture_change_data(
    agent_id: str = "agent-1",
    from_posture: str = "supervised",
    to_posture: str = "shared_planning",
) -> dict:
    return {
        "agent_id": agent_id,
        "from_posture": from_posture,
        "to_posture": to_posture,
        "direction": "upgrade",
        "changed_at": datetime.now(UTC).isoformat(),
    }


def _make_revocation_data(
    revocation_id: str = "rev-1",
    agent_id: str = "agent-1",
) -> dict:
    return {
        "revocation_id": revocation_id,
        "agent_id": agent_id,
        "reason": "Policy violation",
        "revoked_at": datetime.now(UTC).isoformat(),
    }


def _make_genesis_data(authority_id: str = "auth-1") -> dict:
    return {
        "authority_id": authority_id,
        "trust_root": True,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _make_delegation_data(
    delegation_id: str = "del-1",
    delegator_id: str = "agent-1",
    delegatee_id: str = "agent-2",
) -> dict:
    return {
        "delegation_id": delegation_id,
        "delegator_id": delegator_id,
        "delegatee_id": delegatee_id,
        "scope": "read_only",
        "created_at": datetime.now(UTC).isoformat(),
    }


def _make_attestation_data(
    attestation_id: str = "att-1",
    agent_id: str = "agent-1",
) -> dict:
    return {
        "attestation_id": attestation_id,
        "agent_id": agent_id,
        "capabilities": ["read", "write"],
        "created_at": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def pg_store():
    """Create a PostgreSQLTrustStore for testing, clean up after."""
    store = PostgreSQLTrustStore(database_url=_DATABASE_URL)
    yield store
    # Clean up all test data
    store._drop_all_tables()
    store.close()


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestPostgreSQLTrustStoreProtocol:
    """PostgreSQLTrustStore must satisfy the TrustStore protocol."""

    def test_is_trust_store(self, pg_store):
        assert isinstance(pg_store, TrustStore)


# ---------------------------------------------------------------------------
# Construction and connection pooling
# ---------------------------------------------------------------------------


class TestPostgreSQLTrustStoreConstruction:
    """Connection pooling and construction."""

    def test_requires_database_url(self):
        """Must raise ValueError when database_url is empty."""
        with pytest.raises(ValueError, match="database_url"):
            PostgreSQLTrustStore(database_url="")

    def test_requires_non_none_database_url(self):
        """Must raise ValueError when database_url is None."""
        with pytest.raises(ValueError, match="database_url"):
            PostgreSQLTrustStore(database_url=None)

    def test_connection_pool_defaults(self, pg_store):
        """Pool should have min 2, max 10 connections by default."""
        assert pg_store.pool_min == 2
        assert pg_store.pool_max == 10

    def test_custom_pool_size(self):
        """Pool size can be customized."""
        store = PostgreSQLTrustStore(
            database_url=_DATABASE_URL,
            pool_min=1,
            pool_max=5,
        )
        assert store.pool_min == 1
        assert store.pool_max == 5
        store._drop_all_tables()
        store.close()


# ---------------------------------------------------------------------------
# Envelopes
# ---------------------------------------------------------------------------


class TestPostgreSQLEnvelopes:
    def test_store_and_get_envelope(self, pg_store):
        data = _make_envelope_data("env-1")
        pg_store.store_envelope("env-1", data)
        result = pg_store.get_envelope("env-1")
        assert result is not None
        assert result["envelope_id"] == "env-1"

    def test_get_missing_envelope_returns_none(self, pg_store):
        assert pg_store.get_envelope("nonexistent") is None

    def test_list_envelopes_all(self, pg_store):
        pg_store.store_envelope("env-1", _make_envelope_data("env-1", "agent-1"))
        pg_store.store_envelope("env-2", _make_envelope_data("env-2", "agent-2"))
        result = pg_store.list_envelopes()
        assert len(result) == 2

    def test_list_envelopes_by_agent(self, pg_store):
        pg_store.store_envelope("env-1", _make_envelope_data("env-1", "agent-1"))
        pg_store.store_envelope("env-2", _make_envelope_data("env-2", "agent-2"))
        pg_store.store_envelope("env-3", _make_envelope_data("env-3", "agent-1"))
        result = pg_store.list_envelopes(agent_id="agent-1")
        assert len(result) == 2
        assert all(e["agent_id"] == "agent-1" for e in result)

    def test_store_envelope_overwrites_existing(self, pg_store):
        pg_store.store_envelope("env-1", {"envelope_id": "env-1", "version": 1})
        pg_store.store_envelope("env-1", {"envelope_id": "env-1", "version": 2})
        result = pg_store.get_envelope("env-1")
        assert result["version"] == 2


# ---------------------------------------------------------------------------
# Audit Anchors
# ---------------------------------------------------------------------------


class TestPostgreSQLAuditAnchors:
    def test_store_and_get_anchor(self, pg_store):
        data = _make_anchor_data("anc-1")
        pg_store.store_audit_anchor("anc-1", data)
        result = pg_store.get_audit_anchor("anc-1")
        assert result is not None
        assert result["anchor_id"] == "anc-1"

    def test_get_missing_anchor_returns_none(self, pg_store):
        assert pg_store.get_audit_anchor("nonexistent") is None

    def test_query_anchors_by_agent(self, pg_store):
        pg_store.store_audit_anchor("anc-1", _make_anchor_data("anc-1", "agent-1"))
        pg_store.store_audit_anchor("anc-2", _make_anchor_data("anc-2", "agent-2"))
        pg_store.store_audit_anchor("anc-3", _make_anchor_data("anc-3", "agent-1"))
        results = pg_store.query_anchors(agent_id="agent-1")
        assert len(results) == 2

    def test_query_anchors_by_action(self, pg_store):
        pg_store.store_audit_anchor("anc-1", _make_anchor_data("anc-1", action="read"))
        pg_store.store_audit_anchor("anc-2", _make_anchor_data("anc-2", action="write"))
        results = pg_store.query_anchors(action="read")
        assert len(results) == 1
        assert results[0]["action"] == "read"

    def test_query_anchors_by_time_range(self, pg_store):
        t1 = datetime(2026, 1, 1, tzinfo=UTC)
        t2 = datetime(2026, 6, 1, tzinfo=UTC)
        t3 = datetime(2026, 12, 1, tzinfo=UTC)
        pg_store.store_audit_anchor("anc-1", _make_anchor_data("anc-1", timestamp=t1))
        pg_store.store_audit_anchor("anc-2", _make_anchor_data("anc-2", timestamp=t2))
        pg_store.store_audit_anchor("anc-3", _make_anchor_data("anc-3", timestamp=t3))
        results = pg_store.query_anchors(
            since=datetime(2026, 3, 1, tzinfo=UTC),
            until=datetime(2026, 9, 1, tzinfo=UTC),
        )
        assert len(results) == 1
        assert results[0]["anchor_id"] == "anc-2"

    def test_query_anchors_by_verification_level(self, pg_store):
        pg_store.store_audit_anchor("anc-1", _make_anchor_data("anc-1", verification_level="HELD"))
        pg_store.store_audit_anchor(
            "anc-2", _make_anchor_data("anc-2", verification_level="AUTO_APPROVED")
        )
        results = pg_store.query_anchors(verification_level="HELD")
        assert len(results) == 1

    def test_query_anchors_limit(self, pg_store):
        for i in range(10):
            pg_store.store_audit_anchor(f"anc-{i}", _make_anchor_data(f"anc-{i}"))
        results = pg_store.query_anchors(limit=3)
        assert len(results) == 3

    def test_audit_anchor_append_only_no_update(self, pg_store):
        """Audit anchors are immutable: UPDATE must be prevented."""
        data = _make_anchor_data("anc-immutable")
        pg_store.store_audit_anchor("anc-immutable", data)
        # A second insert with same ID should be ignored (INSERT ON CONFLICT DO NOTHING)
        modified_data = _make_anchor_data("anc-immutable", action="MODIFIED")
        pg_store.store_audit_anchor("anc-immutable", modified_data)
        result = pg_store.get_audit_anchor("anc-immutable")
        assert result["action"] == "read_metrics"  # Original value preserved

    def test_audit_anchor_append_only_no_delete(self, pg_store):
        """Audit anchors are immutable: DELETE must be prevented by trigger/rule."""
        data = _make_anchor_data("anc-nodelete")
        pg_store.store_audit_anchor("anc-nodelete", data)
        # Direct delete via raw SQL should be blocked by trigger
        with pytest.raises(Exception):
            pg_store._execute_raw(
                "DELETE FROM audit_anchors WHERE anchor_id = %s", ("anc-nodelete",)
            )


# ---------------------------------------------------------------------------
# Posture Changes
# ---------------------------------------------------------------------------


class TestPostgreSQLPostureChanges:
    def test_store_and_get_posture_change(self, pg_store):
        data = _make_posture_change_data("agent-1")
        pg_store.store_posture_change("agent-1", data)
        results = pg_store.get_posture_history("agent-1")
        assert len(results) == 1
        assert results[0]["agent_id"] == "agent-1"

    def test_multiple_posture_changes_append(self, pg_store):
        pg_store.store_posture_change("agent-1", _make_posture_change_data("agent-1"))
        pg_store.store_posture_change(
            "agent-1",
            _make_posture_change_data("agent-1", "shared_planning", "continuous_insight"),
        )
        results = pg_store.get_posture_history("agent-1")
        assert len(results) == 2

    def test_posture_history_empty_for_unknown_agent(self, pg_store):
        results = pg_store.get_posture_history("unknown-agent")
        assert results == []

    def test_posture_history_isolated_per_agent(self, pg_store):
        pg_store.store_posture_change("agent-1", _make_posture_change_data("agent-1"))
        pg_store.store_posture_change("agent-2", _make_posture_change_data("agent-2"))
        assert len(pg_store.get_posture_history("agent-1")) == 1
        assert len(pg_store.get_posture_history("agent-2")) == 1

    def test_posture_change_append_only_no_delete(self, pg_store):
        """Posture changes are immutable: DELETE must be prevented by trigger/rule."""
        pg_store.store_posture_change("agent-del", _make_posture_change_data("agent-del"))
        with pytest.raises(Exception):
            pg_store._execute_raw("DELETE FROM posture_changes WHERE agent_id = %s", ("agent-del",))


# ---------------------------------------------------------------------------
# Revocations
# ---------------------------------------------------------------------------


class TestPostgreSQLRevocations:
    def test_store_and_get_revocation(self, pg_store):
        data = _make_revocation_data("rev-1", "agent-1")
        pg_store.store_revocation("rev-1", data)
        results = pg_store.get_revocations()
        assert len(results) == 1

    def test_get_revocations_by_agent(self, pg_store):
        pg_store.store_revocation("rev-1", _make_revocation_data("rev-1", "agent-1"))
        pg_store.store_revocation("rev-2", _make_revocation_data("rev-2", "agent-2"))
        results = pg_store.get_revocations(agent_id="agent-1")
        assert len(results) == 1
        assert results[0]["agent_id"] == "agent-1"

    def test_get_revocations_empty(self, pg_store):
        assert pg_store.get_revocations() == []


# ---------------------------------------------------------------------------
# Genesis Records (write-once)
# ---------------------------------------------------------------------------


class TestPostgreSQLGenesisRecords:
    def test_store_and_get_genesis(self, pg_store):
        data = _make_genesis_data("auth-1")
        pg_store.store_genesis("auth-1", data)
        result = pg_store.get_genesis("auth-1")
        assert result is not None
        assert result["authority_id"] == "auth-1"

    def test_get_missing_genesis_returns_none(self, pg_store):
        assert pg_store.get_genesis("nonexistent") is None

    def test_genesis_write_once_ignores_second_write(self, pg_store):
        """Write-once: second store_genesis for same authority_id is silently ignored."""
        data1 = _make_genesis_data("auth-wo")
        data1["trust_root"] = True
        pg_store.store_genesis("auth-wo", data1)

        data2 = _make_genesis_data("auth-wo")
        data2["trust_root"] = False  # Attempt to overwrite
        pg_store.store_genesis("auth-wo", data2)

        result = pg_store.get_genesis("auth-wo")
        assert result["trust_root"] is True  # Original value preserved


# ---------------------------------------------------------------------------
# Delegation Records
# ---------------------------------------------------------------------------


class TestPostgreSQLDelegations:
    def test_store_and_get_delegation(self, pg_store):
        data = _make_delegation_data("del-1")
        pg_store.store_delegation("del-1", data)
        result = pg_store.get_delegation("del-1")
        assert result is not None
        assert result["delegation_id"] == "del-1"

    def test_get_missing_delegation_returns_none(self, pg_store):
        assert pg_store.get_delegation("nonexistent") is None

    def test_get_delegations_for_delegator(self, pg_store):
        pg_store.store_delegation("del-1", _make_delegation_data("del-1", "agent-1", "agent-2"))
        pg_store.store_delegation("del-2", _make_delegation_data("del-2", "agent-3", "agent-4"))
        results = pg_store.get_delegations_for("agent-1")
        assert len(results) == 1

    def test_get_delegations_for_delegatee(self, pg_store):
        pg_store.store_delegation("del-1", _make_delegation_data("del-1", "agent-1", "agent-2"))
        results = pg_store.get_delegations_for("agent-2")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Attestations
# ---------------------------------------------------------------------------


class TestPostgreSQLAttestations:
    def test_store_and_get_attestation(self, pg_store):
        data = _make_attestation_data("att-1")
        pg_store.store_attestation("att-1", data)
        result = pg_store.get_attestation("att-1")
        assert result is not None
        assert result["attestation_id"] == "att-1"

    def test_get_missing_attestation_returns_none(self, pg_store):
        assert pg_store.get_attestation("nonexistent") is None

    def test_get_attestations_for_agent(self, pg_store):
        pg_store.store_attestation("att-1", _make_attestation_data("att-1", "agent-1"))
        pg_store.store_attestation("att-2", _make_attestation_data("att-2", "agent-2"))
        pg_store.store_attestation("att-3", _make_attestation_data("att-3", "agent-1"))
        results = pg_store.get_attestations_for("agent-1")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Org Definitions
# ---------------------------------------------------------------------------


class TestPostgreSQLOrgDefinitions:
    def test_store_and_get_org_definition(self, pg_store):
        data = {"org_id": "org-1", "name": "Test Org"}
        pg_store.store_org_definition("org-1", data)
        result = pg_store.get_org_definition("org-1")
        assert result is not None
        assert result["org_id"] == "org-1"

    def test_get_missing_org_definition_returns_none(self, pg_store):
        assert pg_store.get_org_definition("nonexistent") is None

    def test_org_definition_upsert(self, pg_store):
        pg_store.store_org_definition("org-1", {"org_id": "org-1", "name": "V1"})
        pg_store.store_org_definition("org-1", {"org_id": "org-1", "name": "V2"})
        result = pg_store.get_org_definition("org-1")
        assert result["name"] == "V2"


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


class TestPostgreSQLHealthCheck:
    def test_health_check_returns_true(self, pg_store):
        assert pg_store.health_check() is True

    def test_health_check_false_on_closed_pool(self):
        store = PostgreSQLTrustStore(database_url=_DATABASE_URL)
        store._drop_all_tables()
        store.close()
        assert store.health_check() is False


# ---------------------------------------------------------------------------
# Context Manager
# ---------------------------------------------------------------------------


class TestPostgreSQLContextManager:
    def test_context_manager(self):
        with PostgreSQLTrustStore(database_url=_DATABASE_URL) as store:
            assert store.health_check() is True
            store._drop_all_tables()
        # After exit, health check should fail
        assert store.health_check() is False


# ---------------------------------------------------------------------------
# Thread Safety
# ---------------------------------------------------------------------------


class TestPostgreSQLThreadSafety:
    def test_concurrent_writes(self, pg_store):
        """Multiple threads can write envelopes concurrently without errors."""
        errors = []

        def write_envelope(store, i):
            try:
                store.store_envelope(
                    f"env-thread-{i}",
                    _make_envelope_data(f"env-thread-{i}", f"agent-{i}"),
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=write_envelope, args=(pg_store, i)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        all_envelopes = pg_store.list_envelopes()
        assert len(all_envelopes) == 10
