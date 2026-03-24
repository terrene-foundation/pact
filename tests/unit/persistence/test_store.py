# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for TrustStore protocol, MemoryStore, and FilesystemStore."""

import json
from datetime import UTC, datetime

import pytest

from pact_platform.trust.store.store import (
    FilesystemStore,
    MemoryStore,
    TrustStore,
)

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


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestTrustStoreProtocol:
    """Verify that both MemoryStore and FilesystemStore satisfy the TrustStore protocol."""

    def test_memory_store_is_trust_store(self):
        store = MemoryStore()
        assert isinstance(store, TrustStore)

    def test_filesystem_store_is_trust_store(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        assert isinstance(store, TrustStore)


# ---------------------------------------------------------------------------
# MemoryStore tests
# ---------------------------------------------------------------------------


class TestMemoryStoreEnvelopes:
    def test_store_and_get_envelope(self):
        store = MemoryStore()
        data = _make_envelope_data("env-1")
        store.store_envelope("env-1", data)
        result = store.get_envelope("env-1")
        assert result is not None
        assert result["envelope_id"] == "env-1"

    def test_get_missing_envelope_returns_none(self):
        store = MemoryStore()
        assert store.get_envelope("nonexistent") is None

    def test_list_envelopes_all(self):
        store = MemoryStore()
        store.store_envelope("env-1", _make_envelope_data("env-1", "agent-1"))
        store.store_envelope("env-2", _make_envelope_data("env-2", "agent-2"))
        result = store.list_envelopes()
        assert len(result) == 2

    def test_list_envelopes_by_agent(self):
        store = MemoryStore()
        store.store_envelope("env-1", _make_envelope_data("env-1", "agent-1"))
        store.store_envelope("env-2", _make_envelope_data("env-2", "agent-2"))
        store.store_envelope("env-3", _make_envelope_data("env-3", "agent-1"))
        result = store.list_envelopes(agent_id="agent-1")
        assert len(result) == 2
        assert all(e["agent_id"] == "agent-1" for e in result)

    def test_store_envelope_overwrites_existing(self):
        store = MemoryStore()
        store.store_envelope("env-1", {"envelope_id": "env-1", "version": 1})
        store.store_envelope("env-1", {"envelope_id": "env-1", "version": 2})
        result = store.get_envelope("env-1")
        assert result["version"] == 2


class TestMemoryStoreAnchors:
    def test_store_and_get_anchor(self):
        store = MemoryStore()
        data = _make_anchor_data("anc-1")
        store.store_audit_anchor("anc-1", data)
        result = store.get_audit_anchor("anc-1")
        assert result is not None
        assert result["anchor_id"] == "anc-1"

    def test_get_missing_anchor_returns_none(self):
        store = MemoryStore()
        assert store.get_audit_anchor("nonexistent") is None

    def test_query_anchors_by_agent(self):
        store = MemoryStore()
        store.store_audit_anchor("anc-1", _make_anchor_data("anc-1", "agent-1"))
        store.store_audit_anchor("anc-2", _make_anchor_data("anc-2", "agent-2"))
        store.store_audit_anchor("anc-3", _make_anchor_data("anc-3", "agent-1"))
        results = store.query_anchors(agent_id="agent-1")
        assert len(results) == 2

    def test_query_anchors_by_action(self):
        store = MemoryStore()
        store.store_audit_anchor("anc-1", _make_anchor_data("anc-1", action="read"))
        store.store_audit_anchor("anc-2", _make_anchor_data("anc-2", action="write"))
        results = store.query_anchors(action="read")
        assert len(results) == 1
        assert results[0]["action"] == "read"

    def test_query_anchors_by_time_range(self):
        store = MemoryStore()
        t1 = datetime(2026, 1, 1, tzinfo=UTC)
        t2 = datetime(2026, 6, 1, tzinfo=UTC)
        t3 = datetime(2026, 12, 1, tzinfo=UTC)
        store.store_audit_anchor("anc-1", _make_anchor_data("anc-1", timestamp=t1))
        store.store_audit_anchor("anc-2", _make_anchor_data("anc-2", timestamp=t2))
        store.store_audit_anchor("anc-3", _make_anchor_data("anc-3", timestamp=t3))
        results = store.query_anchors(
            since=datetime(2026, 3, 1, tzinfo=UTC),
            until=datetime(2026, 9, 1, tzinfo=UTC),
        )
        assert len(results) == 1
        assert results[0]["anchor_id"] == "anc-2"

    def test_query_anchors_by_verification_level(self):
        store = MemoryStore()
        store.store_audit_anchor(
            "anc-1",
            _make_anchor_data("anc-1", verification_level="HELD"),
        )
        store.store_audit_anchor(
            "anc-2",
            _make_anchor_data("anc-2", verification_level="AUTO_APPROVED"),
        )
        results = store.query_anchors(verification_level="HELD")
        assert len(results) == 1

    def test_query_anchors_limit(self):
        store = MemoryStore()
        for i in range(10):
            store.store_audit_anchor(f"anc-{i}", _make_anchor_data(f"anc-{i}"))
        results = store.query_anchors(limit=3)
        assert len(results) == 3

    def test_query_anchors_combined_filters(self):
        store = MemoryStore()
        t = datetime(2026, 6, 1, tzinfo=UTC)
        store.store_audit_anchor(
            "anc-1",
            _make_anchor_data("anc-1", "agent-1", "read", "HELD", t),
        )
        store.store_audit_anchor(
            "anc-2",
            _make_anchor_data("anc-2", "agent-2", "read", "HELD", t),
        )
        store.store_audit_anchor(
            "anc-3",
            _make_anchor_data("anc-3", "agent-1", "write", "HELD", t),
        )
        results = store.query_anchors(agent_id="agent-1", action="read")
        assert len(results) == 1
        assert results[0]["anchor_id"] == "anc-1"


class TestMemoryStorePosture:
    def test_store_and_get_posture_change(self):
        store = MemoryStore()
        data = _make_posture_change_data("agent-1")
        store.store_posture_change("agent-1", data)
        results = store.get_posture_history("agent-1")
        assert len(results) == 1
        assert results[0]["agent_id"] == "agent-1"

    def test_multiple_posture_changes_append(self):
        store = MemoryStore()
        store.store_posture_change("agent-1", _make_posture_change_data("agent-1"))
        store.store_posture_change(
            "agent-1", _make_posture_change_data("agent-1", "shared_planning", "continuous_insight")
        )
        results = store.get_posture_history("agent-1")
        assert len(results) == 2

    def test_posture_history_empty_for_unknown_agent(self):
        store = MemoryStore()
        results = store.get_posture_history("unknown-agent")
        assert results == []

    def test_posture_history_isolated_per_agent(self):
        store = MemoryStore()
        store.store_posture_change("agent-1", _make_posture_change_data("agent-1"))
        store.store_posture_change("agent-2", _make_posture_change_data("agent-2"))
        assert len(store.get_posture_history("agent-1")) == 1
        assert len(store.get_posture_history("agent-2")) == 1


class TestMemoryStoreRevocations:
    def test_store_and_get_revocation(self):
        store = MemoryStore()
        data = _make_revocation_data("rev-1", "agent-1")
        store.store_revocation("rev-1", data)
        results = store.get_revocations()
        assert len(results) == 1

    def test_get_revocations_by_agent(self):
        store = MemoryStore()
        store.store_revocation("rev-1", _make_revocation_data("rev-1", "agent-1"))
        store.store_revocation("rev-2", _make_revocation_data("rev-2", "agent-2"))
        results = store.get_revocations(agent_id="agent-1")
        assert len(results) == 1
        assert results[0]["agent_id"] == "agent-1"

    def test_get_revocations_empty(self):
        store = MemoryStore()
        assert store.get_revocations() == []


# ---------------------------------------------------------------------------
# FilesystemStore tests
# ---------------------------------------------------------------------------


class TestFilesystemStoreInit:
    def test_creates_subdirectories(self, tmp_path):
        FilesystemStore(base_path=tmp_path)
        for subdir in ["envelopes", "anchors", "posture", "revocations"]:
            assert (tmp_path / subdir).is_dir()

    def test_accepts_string_path(self, tmp_path):
        FilesystemStore(base_path=str(tmp_path))
        assert (tmp_path / "envelopes").is_dir()


class TestFilesystemStoreEnvelopes:
    def test_store_and_get_envelope(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        data = _make_envelope_data("env-1")
        store.store_envelope("env-1", data)
        result = store.get_envelope("env-1")
        assert result is not None
        assert result["envelope_id"] == "env-1"

    def test_get_missing_envelope_returns_none(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        assert store.get_envelope("nonexistent") is None

    def test_list_envelopes_all(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        store.store_envelope("env-1", _make_envelope_data("env-1", "agent-1"))
        store.store_envelope("env-2", _make_envelope_data("env-2", "agent-2"))
        result = store.list_envelopes()
        assert len(result) == 2

    def test_list_envelopes_by_agent(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        store.store_envelope("env-1", _make_envelope_data("env-1", "agent-1"))
        store.store_envelope("env-2", _make_envelope_data("env-2", "agent-2"))
        result = store.list_envelopes(agent_id="agent-1")
        assert len(result) == 1

    def test_data_persists_as_json_file(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        data = _make_envelope_data("env-1")
        store.store_envelope("env-1", data)
        json_file = tmp_path / "envelopes" / "env-1.json"
        assert json_file.exists()
        content = json.loads(json_file.read_text())
        assert content["envelope_id"] == "env-1"

    def test_store_envelope_overwrites_existing(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        store.store_envelope("env-1", {"envelope_id": "env-1", "version": 1})
        store.store_envelope("env-1", {"envelope_id": "env-1", "version": 2})
        result = store.get_envelope("env-1")
        assert result["version"] == 2


class TestFilesystemStoreAnchors:
    def test_store_and_get_anchor(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        data = _make_anchor_data("anc-1")
        store.store_audit_anchor("anc-1", data)
        result = store.get_audit_anchor("anc-1")
        assert result is not None
        assert result["anchor_id"] == "anc-1"

    def test_get_missing_anchor_returns_none(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        assert store.get_audit_anchor("nonexistent") is None

    def test_query_anchors_by_agent(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        store.store_audit_anchor("anc-1", _make_anchor_data("anc-1", "agent-1"))
        store.store_audit_anchor("anc-2", _make_anchor_data("anc-2", "agent-2"))
        results = store.query_anchors(agent_id="agent-1")
        assert len(results) == 1

    def test_query_anchors_by_time_range(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        t1 = datetime(2026, 1, 1, tzinfo=UTC)
        t2 = datetime(2026, 6, 1, tzinfo=UTC)
        store.store_audit_anchor("anc-1", _make_anchor_data("anc-1", timestamp=t1))
        store.store_audit_anchor("anc-2", _make_anchor_data("anc-2", timestamp=t2))
        results = store.query_anchors(
            since=datetime(2026, 3, 1, tzinfo=UTC),
            until=datetime(2026, 9, 1, tzinfo=UTC),
        )
        assert len(results) == 1


class TestFilesystemStorePosture:
    def test_store_and_get_posture_change(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        data = _make_posture_change_data("agent-1")
        store.store_posture_change("agent-1", data)
        results = store.get_posture_history("agent-1")
        assert len(results) == 1

    def test_multiple_changes_append(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        store.store_posture_change("agent-1", _make_posture_change_data("agent-1"))
        store.store_posture_change("agent-1", _make_posture_change_data("agent-1"))
        results = store.get_posture_history("agent-1")
        assert len(results) == 2

    def test_posture_stored_as_json(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        store.store_posture_change("agent-1", _make_posture_change_data("agent-1"))
        json_file = tmp_path / "posture" / "agent-1.json"
        assert json_file.exists()


class TestFilesystemStoreRevocations:
    def test_store_and_get_revocations(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        data = _make_revocation_data("rev-1", "agent-1")
        store.store_revocation("rev-1", data)
        results = store.get_revocations()
        assert len(results) == 1

    def test_get_revocations_by_agent(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        store.store_revocation("rev-1", _make_revocation_data("rev-1", "agent-1"))
        store.store_revocation("rev-2", _make_revocation_data("rev-2", "agent-2"))
        results = store.get_revocations(agent_id="agent-1")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestStoreErrorHandling:
    def test_memory_store_envelope_id_required(self):
        store = MemoryStore()
        with pytest.raises((ValueError, TypeError)):
            store.store_envelope("", {})

    def test_memory_store_anchor_id_required(self):
        store = MemoryStore()
        with pytest.raises((ValueError, TypeError)):
            store.store_audit_anchor("", {})

    def test_memory_store_posture_agent_id_required(self):
        store = MemoryStore()
        with pytest.raises((ValueError, TypeError)):
            store.store_posture_change("", {})

    def test_memory_store_revocation_id_required(self):
        store = MemoryStore()
        with pytest.raises((ValueError, TypeError)):
            store.store_revocation("", {})

    def test_filesystem_store_envelope_id_required(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises((ValueError, TypeError)):
            store.store_envelope("", {})

    def test_filesystem_store_anchor_id_required(self, tmp_path):
        store = FilesystemStore(base_path=tmp_path)
        with pytest.raises((ValueError, TypeError)):
            store.store_audit_anchor("", {})
