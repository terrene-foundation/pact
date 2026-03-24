# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for trust store backup and restore (Task 2604).

Validates that:
- backup_store exports all trust data to a JSON file
- restore_store imports trust data from a JSON file
- Append-only semantics are preserved (full audit trail in backup)
- Data integrity is validated on restore
- Round-trip: backup -> new store -> restore -> data matches
- Error handling: corrupt file, missing file, invalid data
"""

import json
from datetime import UTC, datetime

import pytest

from pact_platform.trust.store.backup import (
    BackupError,
    RestoreError,
    backup_store,
    restore_store,
)
from pact_platform.trust.store.sqlite_store import SQLiteTrustStore
from pact_platform.trust.store.store import MemoryStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _populate_store(store) -> dict:
    """Populate a store with test data across all entity types.

    Returns a dict describing what was stored so tests can verify round-trips.
    """
    # Envelopes
    store.store_envelope(
        "env-1",
        {
            "envelope_id": "env-1",
            "agent_id": "agent-1",
            "financial": {"max_spend_usd": 100.0},
        },
    )
    store.store_envelope(
        "env-2",
        {
            "envelope_id": "env-2",
            "agent_id": "agent-2",
            "financial": {"max_spend_usd": 200.0},
        },
    )

    # Audit anchors
    store.store_audit_anchor(
        "anc-1",
        {
            "anchor_id": "anc-1",
            "agent_id": "agent-1",
            "action": "read_metrics",
            "verification_level": "AUTO_APPROVED",
            "timestamp": datetime(2026, 6, 1, tzinfo=UTC).isoformat(),
        },
    )
    store.store_audit_anchor(
        "anc-2",
        {
            "anchor_id": "anc-2",
            "agent_id": "agent-2",
            "action": "write_report",
            "verification_level": "HELD",
            "timestamp": datetime(2026, 6, 15, tzinfo=UTC).isoformat(),
        },
    )

    # Posture changes
    store.store_posture_change(
        "agent-1",
        {
            "agent_id": "agent-1",
            "from_posture": "supervised",
            "to_posture": "shared_planning",
            "direction": "upgrade",
        },
    )
    store.store_posture_change(
        "agent-1",
        {
            "agent_id": "agent-1",
            "from_posture": "shared_planning",
            "to_posture": "continuous_insight",
            "direction": "upgrade",
        },
    )

    # Revocations
    store.store_revocation(
        "rev-1",
        {
            "revocation_id": "rev-1",
            "agent_id": "agent-1",
            "reason": "Policy violation",
        },
    )

    # Genesis records
    store.store_genesis(
        "auth-1",
        {
            "authority_id": "auth-1",
            "trust_root": True,
        },
    )

    # Delegation records
    store.store_delegation(
        "del-1",
        {
            "delegation_id": "del-1",
            "delegator_id": "agent-1",
            "delegatee_id": "agent-2",
            "scope": "read_only",
        },
    )

    # Attestations
    store.store_attestation(
        "att-1",
        {
            "attestation_id": "att-1",
            "agent_id": "agent-1",
            "capabilities": ["read", "write"],
        },
    )

    # Org definitions
    store.store_org_definition(
        "org-1",
        {
            "org_id": "org-1",
            "name": "Test Org",
        },
    )

    return {
        "envelopes": 2,
        "anchors": 2,
        "posture_agents": ["agent-1"],
        "posture_count_agent1": 2,
        "revocations": 1,
        "genesis": 1,
        "delegations": 1,
        "attestations": 1,
        "org_definitions": 1,
    }


@pytest.fixture
def populated_memory_store():
    store = MemoryStore()
    counts = _populate_store(store)
    return store, counts


@pytest.fixture
def populated_sqlite_store():
    store = SQLiteTrustStore()
    counts = _populate_store(store)
    yield store, counts
    store.close()


# ---------------------------------------------------------------------------
# backup_store
# ---------------------------------------------------------------------------


class TestBackupStore:
    """backup_store exports all trust data to a JSON file."""

    def test_backup_creates_file(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)
        assert output_path.exists()

    def test_backup_file_is_valid_json(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)
        data = json.loads(output_path.read_text())
        assert isinstance(data, dict)

    def test_backup_contains_all_entity_types(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)
        data = json.loads(output_path.read_text())
        assert "envelopes" in data
        assert "audit_anchors" in data
        assert "posture_changes" in data
        assert "revocations" in data
        assert "genesis_records" in data
        assert "delegations" in data
        assert "attestations" in data
        assert "org_definitions" in data

    def test_backup_contains_metadata(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)
        data = json.loads(output_path.read_text())
        assert "metadata" in data
        assert "created_at" in data["metadata"]
        assert "version" in data["metadata"]

    def test_backup_envelope_count(self, populated_memory_store, tmp_path):
        store, counts = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)
        data = json.loads(output_path.read_text())
        assert len(data["envelopes"]) == counts["envelopes"]

    def test_backup_anchor_count(self, populated_memory_store, tmp_path):
        store, counts = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)
        data = json.loads(output_path.read_text())
        assert len(data["audit_anchors"]) == counts["anchors"]

    def test_backup_posture_changes_preserved(self, populated_memory_store, tmp_path):
        store, counts = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)
        data = json.loads(output_path.read_text())
        # posture_changes is a dict keyed by agent_id
        assert "agent-1" in data["posture_changes"]
        assert len(data["posture_changes"]["agent-1"]) == counts["posture_count_agent1"]

    def test_backup_from_sqlite_store(self, populated_sqlite_store, tmp_path):
        store, counts = populated_sqlite_store
        output_path = tmp_path / "backup_sqlite.json"
        backup_store(store, output_path)
        data = json.loads(output_path.read_text())
        assert len(data["envelopes"]) == counts["envelopes"]
        assert len(data["audit_anchors"]) == counts["anchors"]


# ---------------------------------------------------------------------------
# restore_store
# ---------------------------------------------------------------------------


class TestRestoreStore:
    """restore_store imports trust data from a JSON file."""

    def test_restore_creates_envelopes(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)
        assert target.get_envelope("env-1") is not None
        assert target.get_envelope("env-2") is not None

    def test_restore_creates_anchors(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)
        assert target.get_audit_anchor("anc-1") is not None
        assert target.get_audit_anchor("anc-2") is not None

    def test_restore_creates_posture_changes(self, populated_memory_store, tmp_path):
        store, counts = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)
        history = target.get_posture_history("agent-1")
        assert len(history) == counts["posture_count_agent1"]

    def test_restore_creates_revocations(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)
        revocations = target.get_revocations()
        assert len(revocations) == 1

    def test_restore_creates_genesis(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)
        genesis = target.get_genesis("auth-1")
        assert genesis is not None
        assert genesis["authority_id"] == "auth-1"

    def test_restore_creates_delegations(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)
        delegation = target.get_delegation("del-1")
        assert delegation is not None

    def test_restore_creates_attestations(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)
        attestation = target.get_attestation("att-1")
        assert attestation is not None

    def test_restore_creates_org_definitions(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "backup.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)
        org = target.get_org_definition("org-1")
        assert org is not None
        assert org["name"] == "Test Org"


# ---------------------------------------------------------------------------
# Round-trip integrity
# ---------------------------------------------------------------------------


class TestBackupRestoreRoundTrip:
    """Data survives a backup -> restore round-trip."""

    def test_envelope_data_preserved(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "roundtrip.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)

        original = store.get_envelope("env-1")
        restored = target.get_envelope("env-1")
        assert original == restored

    def test_anchor_data_preserved(self, populated_memory_store, tmp_path):
        store, _ = populated_memory_store
        output_path = tmp_path / "roundtrip.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)

        original = store.get_audit_anchor("anc-1")
        restored = target.get_audit_anchor("anc-1")
        assert original == restored

    def test_sqlite_to_memory_roundtrip(self, populated_sqlite_store, tmp_path):
        """Backup from SQLite, restore to MemoryStore — data matches."""
        store, counts = populated_sqlite_store
        output_path = tmp_path / "sqlite_roundtrip.json"
        backup_store(store, output_path)

        target = MemoryStore()
        restore_store(target, output_path)

        assert len(target.list_envelopes()) == counts["envelopes"]
        assert target.get_genesis("auth-1") is not None
        assert target.get_delegation("del-1") is not None

    def test_memory_to_sqlite_roundtrip(self, populated_memory_store, tmp_path):
        """Backup from MemoryStore, restore to SQLite — data matches."""
        store, counts = populated_memory_store
        output_path = tmp_path / "memory_roundtrip.json"
        backup_store(store, output_path)

        target = SQLiteTrustStore()
        restore_store(target, output_path)

        assert len(target.list_envelopes()) == counts["envelopes"]
        assert target.get_genesis("auth-1") is not None
        assert target.get_audit_anchor("anc-1") is not None
        target.close()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestBackupRestoreErrors:
    """Error handling for backup and restore operations."""

    def test_restore_missing_file_raises(self):
        target = MemoryStore()
        with pytest.raises((RestoreError, FileNotFoundError)):
            restore_store(target, "/nonexistent/path/backup.json")

    def test_restore_corrupt_json_raises(self, tmp_path):
        corrupt_path = tmp_path / "corrupt.json"
        corrupt_path.write_text("this is not valid json {{{")
        target = MemoryStore()
        with pytest.raises((RestoreError, json.JSONDecodeError)):
            restore_store(target, corrupt_path)

    def test_restore_invalid_structure_raises(self, tmp_path):
        """JSON is valid but not a backup structure."""
        invalid_path = tmp_path / "invalid.json"
        invalid_path.write_text(json.dumps({"random_key": "value"}))
        target = MemoryStore()
        with pytest.raises(RestoreError, match="[Ii]nvalid|[Mm]issing|structure"):
            restore_store(target, invalid_path)

    def test_backup_to_unwritable_path_raises(self, populated_memory_store):
        store, _ = populated_memory_store
        with pytest.raises((BackupError, OSError, PermissionError)):
            backup_store(store, "/nonexistent_directory/backup.json")

    def test_restore_validates_metadata(self, tmp_path):
        """Backup with missing metadata should raise RestoreError."""
        bad_backup_path = tmp_path / "no_metadata.json"
        bad_backup_path.write_text(
            json.dumps(
                {
                    "envelopes": [],
                    "audit_anchors": [],
                    "posture_changes": {},
                    "revocations": [],
                    "genesis_records": [],
                    "delegations": [],
                    "attestations": [],
                    "org_definitions": [],
                    # No "metadata" key
                }
            )
        )
        target = MemoryStore()
        with pytest.raises(RestoreError, match="[Mm]etadata"):
            restore_store(target, bad_backup_path)
