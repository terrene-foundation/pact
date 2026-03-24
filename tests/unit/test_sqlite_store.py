# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for SQLiteTrustStore — durable trust state persistence.

Tests verify that SQLiteTrustStore correctly implements the TrustStore protocol
and its extended methods (genesis, delegations, attestations).
"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

import pytest

from pact_platform.trust.store.sqlite_store import GenesisAlreadyExistsError, SQLiteTrustStore
from pact_platform.trust.store.store import TrustStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> SQLiteTrustStore:
    """Create an in-memory SQLite trust store."""
    return SQLiteTrustStore(":memory:")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """SQLiteTrustStore must satisfy the TrustStore protocol."""

    def test_is_trust_store_instance(self, store: SQLiteTrustStore):
        assert isinstance(store, TrustStore)


# ---------------------------------------------------------------------------
# Envelopes
# ---------------------------------------------------------------------------


class TestEnvelopes:
    """CRUD operations on constraint envelopes."""

    def test_store_and_get(self, store: SQLiteTrustStore):
        data = {"agent_id": "agent-1", "constraints": {"max_spend": 100}}
        store.store_envelope("env-1", data)
        result = store.get_envelope("env-1")
        assert result is not None
        assert result["agent_id"] == "agent-1"
        assert result["constraints"]["max_spend"] == 100

    def test_get_missing_returns_none(self, store: SQLiteTrustStore):
        assert store.get_envelope("nonexistent") is None

    def test_store_replaces_existing(self, store: SQLiteTrustStore):
        store.store_envelope("env-1", {"agent_id": "a", "v": 1})
        store.store_envelope("env-1", {"agent_id": "a", "v": 2})
        result = store.get_envelope("env-1")
        assert result is not None
        assert result["v"] == 2

    def test_list_all(self, store: SQLiteTrustStore):
        store.store_envelope("env-1", {"agent_id": "a"})
        store.store_envelope("env-2", {"agent_id": "b"})
        envelopes = store.list_envelopes()
        assert len(envelopes) == 2

    def test_list_by_agent(self, store: SQLiteTrustStore):
        store.store_envelope("env-1", {"agent_id": "a"})
        store.store_envelope("env-2", {"agent_id": "b"})
        store.store_envelope("env-3", {"agent_id": "a"})
        envelopes = store.list_envelopes(agent_id="a")
        assert len(envelopes) == 2
        assert all(e["agent_id"] == "a" for e in envelopes)


# ---------------------------------------------------------------------------
# Audit Anchors
# ---------------------------------------------------------------------------


class TestAuditAnchors:
    """Audit anchor storage — append-only semantics."""

    def test_store_and_get(self, store: SQLiteTrustStore):
        data = {
            "agent_id": "agent-1",
            "action": "read_file",
            "verification_level": "AUTO_APPROVED",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        store.store_audit_anchor("anchor-1", data)
        result = store.get_audit_anchor("anchor-1")
        assert result is not None
        assert result["action"] == "read_file"

    def test_get_missing_returns_none(self, store: SQLiteTrustStore):
        assert store.get_audit_anchor("nonexistent") is None

    def test_append_only_ignores_duplicate(self, store: SQLiteTrustStore):
        """INSERT OR IGNORE means second insert with same ID is silently ignored."""
        data1 = {"agent_id": "a", "action": "first", "timestamp": "2026-01-01T00:00:00+00:00"}
        data2 = {"agent_id": "a", "action": "second", "timestamp": "2026-01-01T00:00:00+00:00"}
        store.store_audit_anchor("anchor-1", data1)
        store.store_audit_anchor("anchor-1", data2)
        result = store.get_audit_anchor("anchor-1")
        assert result is not None
        assert result["action"] == "first"  # Second insert was ignored

    def test_query_by_agent(self, store: SQLiteTrustStore):
        store.store_audit_anchor(
            "a1", {"agent_id": "agent-1", "action": "x", "timestamp": "2026-01-01T00:00:00+00:00"}
        )
        store.store_audit_anchor(
            "a2", {"agent_id": "agent-2", "action": "y", "timestamp": "2026-01-01T00:00:00+00:00"}
        )
        results = store.query_anchors(agent_id="agent-1")
        assert len(results) == 1
        assert results[0]["agent_id"] == "agent-1"

    def test_query_by_verification_level(self, store: SQLiteTrustStore):
        store.store_audit_anchor(
            "a1",
            {
                "agent_id": "a",
                "verification_level": "BLOCKED",
                "timestamp": "2026-01-01T00:00:00+00:00",
            },
        )
        store.store_audit_anchor(
            "a2",
            {
                "agent_id": "a",
                "verification_level": "AUTO_APPROVED",
                "timestamp": "2026-01-01T00:00:00+00:00",
            },
        )
        results = store.query_anchors(verification_level="BLOCKED")
        assert len(results) == 1

    def test_query_with_time_range(self, store: SQLiteTrustStore):
        store.store_audit_anchor("a1", {"agent_id": "a", "timestamp": "2026-01-01T00:00:00+00:00"})
        store.store_audit_anchor("a2", {"agent_id": "a", "timestamp": "2026-06-01T00:00:00+00:00"})
        store.store_audit_anchor("a3", {"agent_id": "a", "timestamp": "2026-12-01T00:00:00+00:00"})
        results = store.query_anchors(
            since=datetime(2026, 3, 1, tzinfo=UTC),
            until=datetime(2026, 9, 1, tzinfo=UTC),
        )
        assert len(results) == 1
        assert results[0]["timestamp"] == "2026-06-01T00:00:00+00:00"

    def test_query_with_limit(self, store: SQLiteTrustStore):
        for i in range(10):
            store.store_audit_anchor(
                f"a{i}", {"agent_id": "a", "timestamp": f"2026-01-{i + 1:02d}T00:00:00+00:00"}
            )
        results = store.query_anchors(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Posture Changes
# ---------------------------------------------------------------------------


class TestPostureChanges:
    """Posture change storage — append-only per agent."""

    def test_store_and_get(self, store: SQLiteTrustStore):
        store.store_posture_change("agent-1", {"from": "supervised", "to": "shared_planning"})
        history = store.get_posture_history("agent-1")
        assert len(history) == 1
        assert history[0]["from"] == "supervised"

    def test_multiple_changes_ordered(self, store: SQLiteTrustStore):
        store.store_posture_change("agent-1", {"step": 1})
        store.store_posture_change("agent-1", {"step": 2})
        store.store_posture_change("agent-1", {"step": 3})
        history = store.get_posture_history("agent-1")
        assert len(history) == 3
        assert [h["step"] for h in history] == [1, 2, 3]

    def test_empty_history(self, store: SQLiteTrustStore):
        history = store.get_posture_history("nonexistent")
        assert history == []


# ---------------------------------------------------------------------------
# Revocations
# ---------------------------------------------------------------------------


class TestRevocations:
    """Revocation record storage."""

    def test_store_and_get_all(self, store: SQLiteTrustStore):
        store.store_revocation("rev-1", {"agent_id": "a", "reason": "compromised"})
        revocations = store.get_revocations()
        assert len(revocations) == 1
        assert revocations[0]["reason"] == "compromised"

    def test_filter_by_agent(self, store: SQLiteTrustStore):
        store.store_revocation("rev-1", {"agent_id": "a"})
        store.store_revocation("rev-2", {"agent_id": "b"})
        revocations = store.get_revocations(agent_id="a")
        assert len(revocations) == 1

    def test_replace_revocation(self, store: SQLiteTrustStore):
        store.store_revocation("rev-1", {"agent_id": "a", "v": 1})
        store.store_revocation("rev-1", {"agent_id": "a", "v": 2})
        revocations = store.get_revocations()
        assert len(revocations) == 1
        assert revocations[0]["v"] == 2


# ---------------------------------------------------------------------------
# Extended: Genesis Records
# ---------------------------------------------------------------------------


class TestGenesisRecords:
    """Genesis record storage (trust root)."""

    def test_store_and_get(self, store: SQLiteTrustStore):
        store.store_genesis("terrene.foundation", {"authority_name": "Terrene Foundation"})
        result = store.get_genesis("terrene.foundation")
        assert result is not None
        assert result["authority_name"] == "Terrene Foundation"

    def test_get_missing_returns_none(self, store: SQLiteTrustStore):
        assert store.get_genesis("nonexistent") is None

    def test_write_once_genesis_does_not_overwrite(self, store: SQLiteTrustStore):
        """RT5-14: Genesis records are write-once — second store raises error."""
        store.store_genesis("auth-1", {"v": 1})
        with pytest.raises(GenesisAlreadyExistsError):
            store.store_genesis("auth-1", {"v": 2})
        result = store.get_genesis("auth-1")
        assert result is not None
        assert result["v"] == 1  # Original record preserved (write-once)


# ---------------------------------------------------------------------------
# Extended: Delegations
# ---------------------------------------------------------------------------


class TestDelegations:
    """Delegation record storage."""

    def test_store_and_get(self, store: SQLiteTrustStore):
        data = {"delegator_id": "root", "delegatee_id": "agent-1", "scope": "read"}
        store.store_delegation("del-1", data)
        result = store.get_delegation("del-1")
        assert result is not None
        assert result["scope"] == "read"

    def test_get_missing_returns_none(self, store: SQLiteTrustStore):
        assert store.get_delegation("nonexistent") is None

    def test_get_delegations_for_agent(self, store: SQLiteTrustStore):
        store.store_delegation("d1", {"delegator_id": "root", "delegatee_id": "a"})
        store.store_delegation("d2", {"delegator_id": "a", "delegatee_id": "b"})
        store.store_delegation("d3", {"delegator_id": "root", "delegatee_id": "c"})
        # Agent "a" is both delegator and delegatee
        results = store.get_delegations_for("a")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Extended: Attestations
# ---------------------------------------------------------------------------


class TestAttestations:
    """Capability attestation storage."""

    def test_store_and_get(self, store: SQLiteTrustStore):
        data = {"agent_id": "agent-1", "capabilities": ["read", "write"]}
        store.store_attestation("att-1", data)
        result = store.get_attestation("att-1")
        assert result is not None
        assert result["capabilities"] == ["read", "write"]

    def test_get_missing_returns_none(self, store: SQLiteTrustStore):
        assert store.get_attestation("nonexistent") is None

    def test_get_attestations_for_agent(self, store: SQLiteTrustStore):
        store.store_attestation("att-1", {"agent_id": "a", "cap": "read"})
        store.store_attestation("att-2", {"agent_id": "a", "cap": "write"})
        store.store_attestation("att-3", {"agent_id": "b", "cap": "read"})
        results = store.get_attestations_for("a")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# RT4-H6: Thread-safe connection model
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """RT4-H6: Verify per-thread connection model with threading.local()."""

    def test_thread_safety_concurrent_writes(self, store: SQLiteTrustStore):
        """Multiple threads writing audit anchors concurrently must all succeed."""
        num_threads = 8
        anchors_per_thread = 10
        errors: list[Exception] = []

        def write_anchors(thread_id: int) -> None:
            try:
                for i in range(anchors_per_thread):
                    anchor_id = f"anchor-t{thread_id}-{i}"
                    store.store_audit_anchor(
                        anchor_id,
                        {
                            "agent_id": f"agent-{thread_id}",
                            "action": "concurrent_write",
                            "timestamp": "2026-01-01T00:00:00+00:00",
                        },
                    )
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_anchors, tid) for tid in range(num_threads)]
            for future in as_completed(futures):
                future.result()  # re-raises exceptions

        assert errors == [], f"Thread errors: {errors}"

        # Verify all anchors were stored
        total = num_threads * anchors_per_thread
        all_anchors = store.query_anchors(limit=total + 10)
        assert len(all_anchors) == total, f"Expected {total} anchors, got {len(all_anchors)}"

    def test_thread_safety_concurrent_reads_and_writes(self, store: SQLiteTrustStore):
        """Concurrent readers and writers must not crash or corrupt data."""
        # Pre-populate some data
        for i in range(5):
            store.store_envelope(f"env-{i}", {"agent_id": "a", "v": i})

        errors: list[Exception] = []

        def reader() -> None:
            try:
                for _ in range(20):
                    store.list_envelopes()
            except Exception as exc:
                errors.append(exc)

        def writer(tid: int) -> None:
            try:
                for i in range(10):
                    store.store_posture_change(
                        f"agent-{tid}",
                        {"step": i},
                    )
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            futures.extend(executor.submit(reader) for _ in range(3))
            futures.extend(executor.submit(writer, tid) for tid in range(3))
            for future in as_completed(futures):
                future.result()

        assert errors == [], f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# RT4-C1: Append-only immutability triggers
# ---------------------------------------------------------------------------


class TestAppendOnlyTriggers:
    """RT4-C1: Verify that audit_anchors and posture_changes are truly immutable."""

    def test_audit_anchor_update_blocked(self, store: SQLiteTrustStore):
        """UPDATE on audit_anchors must be rejected by trigger."""
        store.store_audit_anchor(
            "anchor-immutable",
            {"agent_id": "a", "action": "test", "timestamp": "2026-01-01T00:00:00+00:00"},
        )
        conn = store._get_connection()
        with pytest.raises(sqlite3.IntegrityError, match="immutable.*UPDATE"):
            conn.execute(
                "UPDATE audit_anchors SET action = 'hacked' WHERE anchor_id = 'anchor-immutable'"
            )

    def test_audit_anchor_delete_blocked(self, store: SQLiteTrustStore):
        """DELETE on audit_anchors must be rejected by trigger."""
        store.store_audit_anchor(
            "anchor-nodelete",
            {"agent_id": "a", "action": "test", "timestamp": "2026-01-01T00:00:00+00:00"},
        )
        conn = store._get_connection()
        with pytest.raises(sqlite3.IntegrityError, match="immutable.*DELETE"):
            conn.execute("DELETE FROM audit_anchors WHERE anchor_id = 'anchor-nodelete'")

    def test_posture_change_update_blocked(self, store: SQLiteTrustStore):
        """UPDATE on posture_changes must be rejected by trigger."""
        store.store_posture_change("agent-1", {"from": "supervised", "to": "shared_planning"})
        conn = store._get_connection()
        with pytest.raises(sqlite3.IntegrityError, match="immutable.*UPDATE"):
            conn.execute("UPDATE posture_changes SET data = '{}' WHERE agent_id = 'agent-1'")

    def test_posture_change_delete_blocked(self, store: SQLiteTrustStore):
        """DELETE on posture_changes must be rejected by trigger."""
        store.store_posture_change("agent-1", {"step": 1})
        conn = store._get_connection()
        with pytest.raises(sqlite3.IntegrityError, match="immutable.*DELETE"):
            conn.execute("DELETE FROM posture_changes WHERE agent_id = 'agent-1'")


# ---------------------------------------------------------------------------
# RT4-C3: Referential integrity triggers
# ---------------------------------------------------------------------------


class TestReferentialIntegrity:
    """RT4-C3: Prevent deletion of genesis records referenced by delegations."""

    def test_cannot_delete_genesis_with_delegations(self, store: SQLiteTrustStore):
        """Deleting a genesis record that is referenced by a delegation must fail."""
        # Create genesis record for authority "root"
        store.store_genesis("root", {"authority_name": "Root Authority"})
        # Create a delegation referencing "root" as delegator
        store.store_delegation(
            "del-1",
            {"delegator_id": "root", "delegatee_id": "agent-1"},
        )
        conn = store._get_connection()
        with pytest.raises(
            sqlite3.IntegrityError,
            match="Cannot delete genesis.*delegations reference",
        ):
            conn.execute("DELETE FROM genesis_records WHERE authority_id = 'root'")

    def test_can_delete_genesis_without_delegations(self, store: SQLiteTrustStore):
        """Deleting a genesis record with no delegation references should succeed."""
        store.store_genesis("orphan", {"authority_name": "Orphan Authority"})
        conn = store._get_connection()
        # Should not raise
        conn.execute("DELETE FROM genesis_records WHERE authority_id = 'orphan'")
        conn.commit()
        assert store.get_genesis("orphan") is None


# ---------------------------------------------------------------------------
# RT4-M4: Write-once genesis records (additional tests)
# ---------------------------------------------------------------------------


class TestWriteOnceGenesis:
    """RT4-M4: Verify write-once semantics for genesis records."""

    def test_store_genesis_raises_on_duplicate(self, store: SQLiteTrustStore):
        """RT5-14: Calling store_genesis twice with same ID raises GenesisAlreadyExistsError."""
        store.store_genesis("auth-1", {"v": 1})
        # This must raise and must not overwrite
        with pytest.raises(GenesisAlreadyExistsError):
            store.store_genesis("auth-1", {"v": 999})
        result = store.get_genesis("auth-1")
        assert result is not None
        assert result["v"] == 1

    def test_different_authority_ids_are_independent(self, store: SQLiteTrustStore):
        """Write-once applies per authority_id, not globally."""
        store.store_genesis("auth-A", {"name": "A"})
        store.store_genesis("auth-B", {"name": "B"})
        assert store.get_genesis("auth-A")["name"] == "A"
        assert store.get_genesis("auth-B")["name"] == "B"


# ---------------------------------------------------------------------------
# RT4-L6: Envelope versioning
# ---------------------------------------------------------------------------


class TestEnvelopeVersioning:
    """RT4-L6: Envelope version column auto-increments on replace."""

    def test_initial_version_is_one(self, store: SQLiteTrustStore):
        """A newly created envelope starts at version 1."""
        store.store_envelope("env-v", {"agent_id": "a"})
        version = store.get_envelope_version("env-v")
        assert version == 1

    def test_version_increments_on_update(self, store: SQLiteTrustStore):
        """Replacing an envelope increments the version each time."""
        store.store_envelope("env-v", {"agent_id": "a", "v": 1})
        assert store.get_envelope_version("env-v") == 1

        store.store_envelope("env-v", {"agent_id": "a", "v": 2})
        assert store.get_envelope_version("env-v") == 2

        store.store_envelope("env-v", {"agent_id": "a", "v": 3})
        assert store.get_envelope_version("env-v") == 3

    def test_version_none_for_missing_envelope(self, store: SQLiteTrustStore):
        """get_envelope_version returns None for non-existent envelopes."""
        assert store.get_envelope_version("nonexistent") is None

    def test_different_envelopes_have_independent_versions(self, store: SQLiteTrustStore):
        """Version counters are independent per envelope_id."""
        store.store_envelope("env-A", {"agent_id": "a"})
        store.store_envelope("env-B", {"agent_id": "b"})
        store.store_envelope("env-A", {"agent_id": "a", "updated": True})

        assert store.get_envelope_version("env-A") == 2
        assert store.get_envelope_version("env-B") == 1


# ---------------------------------------------------------------------------
# RT4-H12: Extended TrustStore protocol conformance
# ---------------------------------------------------------------------------


class TestExtendedProtocolConformance:
    """RT4-H12: Verify that MemoryStore and FilesystemStore satisfy the extended protocol."""

    def test_memory_store_has_genesis_methods(self):
        from pact_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        store.store_genesis("auth-1", {"name": "test"})
        assert store.get_genesis("auth-1") == {"name": "test"}
        assert store.get_genesis("missing") is None

    def test_memory_store_has_delegation_methods(self):
        from pact_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        store.store_delegation("del-1", {"delegator_id": "root", "delegatee_id": "a"})
        assert store.get_delegation("del-1") is not None
        assert store.get_delegation("missing") is None
        results = store.get_delegations_for("a")
        assert len(results) == 1

    def test_memory_store_has_attestation_methods(self):
        from pact_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        store.store_attestation("att-1", {"agent_id": "a", "cap": "read"})
        assert store.get_attestation("att-1") is not None
        assert store.get_attestation("missing") is None
        results = store.get_attestations_for("a")
        assert len(results) == 1

    def test_memory_store_satisfies_protocol(self):
        from pact_platform.trust.store.store import MemoryStore

        store = MemoryStore()
        assert isinstance(store, TrustStore)

    def test_filesystem_store_has_genesis_methods(self, tmp_path):
        from pact_platform.trust.store.store import FilesystemStore

        store = FilesystemStore(tmp_path)
        store.store_genesis("auth-1", {"name": "test"})
        assert store.get_genesis("auth-1") == {"name": "test"}
        assert store.get_genesis("missing") is None

    def test_filesystem_store_has_delegation_methods(self, tmp_path):
        from pact_platform.trust.store.store import FilesystemStore

        store = FilesystemStore(tmp_path)
        store.store_delegation("del-1", {"delegator_id": "root", "delegatee_id": "a"})
        assert store.get_delegation("del-1") is not None
        assert store.get_delegation("missing") is None
        results = store.get_delegations_for("a")
        assert len(results) == 1

    def test_filesystem_store_has_attestation_methods(self, tmp_path):
        from pact_platform.trust.store.store import FilesystemStore

        store = FilesystemStore(tmp_path)
        store.store_attestation("att-1", {"agent_id": "a", "cap": "read"})
        assert store.get_attestation("att-1") is not None
        assert store.get_attestation("missing") is None
        results = store.get_attestations_for("a")
        assert len(results) == 1

    def test_filesystem_store_satisfies_protocol(self, tmp_path):
        from pact_platform.trust.store.store import FilesystemStore

        store = FilesystemStore(tmp_path)
        assert isinstance(store, TrustStore)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """Context manager and close()."""

    def test_context_manager(self):
        with SQLiteTrustStore(":memory:") as store:
            store.store_envelope("env-1", {"agent_id": "a"})
            assert store.get_envelope("env-1") is not None

    def test_close(self):
        store = SQLiteTrustStore(":memory:")
        store.store_envelope("env-1", {"agent_id": "a"})
        store.close()
        # After close, operations should raise
        with pytest.raises(Exception):
            store.get_envelope("env-1")
