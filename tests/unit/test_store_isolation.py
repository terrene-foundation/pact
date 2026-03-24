# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for store isolation — management/data plane separation.

M17-1704: Logical plane isolation with separate store interfaces.
- Data plane cannot write management tables (genesis, delegations, envelopes, attestations).
- Management plane cannot bypass data plane constraints.
- Each plane has a restricted interface.
"""

from __future__ import annotations

import pytest

from pact_platform.trust.store.sqlite_store import SQLiteTrustStore
from pact_platform.trust.store_isolation import (
    DataPlaneStore,
    ManagementPlaneStore,
    PlaneViolationError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_store() -> SQLiteTrustStore:
    """Provide a shared in-memory SQLite store."""
    return SQLiteTrustStore(":memory:")


@pytest.fixture
def management_store(base_store: SQLiteTrustStore) -> ManagementPlaneStore:
    """Management plane store wrapping the base store."""
    return ManagementPlaneStore(base_store)


@pytest.fixture
def data_store(base_store: SQLiteTrustStore) -> DataPlaneStore:
    """Data plane store wrapping the base store."""
    return DataPlaneStore(base_store)


# ---------------------------------------------------------------------------
# ManagementPlaneStore
# ---------------------------------------------------------------------------


class TestManagementPlaneStore:
    """ManagementPlaneStore provides access to trust management operations."""

    def test_can_store_genesis(self, management_store: ManagementPlaneStore):
        management_store.store_genesis("authority-1", {"authority_id": "authority-1"})
        result = management_store.get_genesis("authority-1")
        assert result is not None
        assert result["authority_id"] == "authority-1"

    def test_can_store_delegation(self, management_store: ManagementPlaneStore):
        data = {
            "delegation_id": "d1",
            "delegator_id": "root",
            "delegatee_id": "agent-1",
        }
        management_store.store_delegation("d1", data)
        result = management_store.get_delegation("d1")
        assert result is not None

    def test_can_store_envelope(self, management_store: ManagementPlaneStore):
        data = {"agent_id": "agent-1", "constraints": {"max_spend": 100}}
        management_store.store_envelope("env-1", data)
        result = management_store.get_envelope("env-1")
        assert result is not None

    def test_can_store_attestation(self, management_store: ManagementPlaneStore):
        data = {"agent_id": "agent-1", "capabilities": ["read", "write"]}
        management_store.store_attestation("att-1", data)
        result = management_store.get_attestation("att-1")
        assert result is not None

    def test_can_store_revocation(self, management_store: ManagementPlaneStore):
        data = {"agent_id": "agent-1", "reason": "policy violation"}
        management_store.store_revocation("rev-1", data)
        result = management_store.get_revocations("agent-1")
        assert len(result) >= 1

    def test_cannot_write_audit_anchors(self, management_store: ManagementPlaneStore):
        """Management plane should not write audit anchors — that is the data plane's job."""
        with pytest.raises(PlaneViolationError, match="management plane"):
            management_store.store_audit_anchor("anchor-1", {"agent_id": "a1", "action": "test"})

    def test_cannot_write_posture_changes(self, management_store: ManagementPlaneStore):
        """Posture changes are operational data, not management data."""
        with pytest.raises(PlaneViolationError, match="management plane"):
            management_store.store_posture_change("agent-1", {"new_posture": "supervised"})

    def test_can_read_audit_anchors(
        self, management_store: ManagementPlaneStore, base_store: SQLiteTrustStore
    ):
        """Management plane can read audit anchors for oversight."""
        base_store.store_audit_anchor(
            "anchor-1",
            {"agent_id": "a1", "action": "test", "verification_level": "AUTO_APPROVED"},
        )
        result = management_store.get_audit_anchor("anchor-1")
        assert result is not None


# ---------------------------------------------------------------------------
# DataPlaneStore
# ---------------------------------------------------------------------------


class TestDataPlaneStore:
    """DataPlaneStore provides access to operational data operations."""

    def test_can_store_audit_anchors(self, data_store: DataPlaneStore):
        data_store.store_audit_anchor(
            "anchor-1",
            {"agent_id": "a1", "action": "test", "verification_level": "AUTO_APPROVED"},
        )
        result = data_store.get_audit_anchor("anchor-1")
        assert result is not None

    def test_can_store_posture_changes(self, data_store: DataPlaneStore):
        data_store.store_posture_change("agent-1", {"new_posture": "supervised"})
        result = data_store.get_posture_history("agent-1")
        assert len(result) >= 1

    def test_can_query_anchors(self, data_store: DataPlaneStore):
        data_store.store_audit_anchor(
            "anchor-1",
            {
                "agent_id": "a1",
                "action": "test",
                "verification_level": "AUTO_APPROVED",
                "timestamp": "2026-01-01T00:00:00+00:00",
            },
        )
        results = data_store.query_anchors(agent_id="a1")
        assert len(results) >= 1

    def test_cannot_write_genesis(self, data_store: DataPlaneStore):
        """Data plane must not create trust roots."""
        with pytest.raises(PlaneViolationError, match="data plane"):
            data_store.store_genesis("authority-1", {"authority_id": "authority-1"})

    def test_cannot_write_delegations(self, data_store: DataPlaneStore):
        """Data plane must not create delegation records."""
        with pytest.raises(PlaneViolationError, match="data plane"):
            data_store.store_delegation("d1", {"delegator_id": "root"})

    def test_cannot_write_envelopes(self, data_store: DataPlaneStore):
        """Data plane must not create constraint envelopes."""
        with pytest.raises(PlaneViolationError, match="data plane"):
            data_store.store_envelope("env-1", {"agent_id": "a1"})

    def test_cannot_write_attestations(self, data_store: DataPlaneStore):
        """Data plane must not create capability attestations."""
        with pytest.raises(PlaneViolationError, match="data plane"):
            data_store.store_attestation("att-1", {"agent_id": "a1"})

    def test_cannot_write_revocations(self, data_store: DataPlaneStore):
        """Data plane must not revoke trust — that is a management action."""
        with pytest.raises(PlaneViolationError, match="data plane"):
            data_store.store_revocation("rev-1", {"agent_id": "a1"})

    def test_can_read_envelopes(self, data_store: DataPlaneStore, base_store: SQLiteTrustStore):
        """Data plane can read envelopes for constraint evaluation."""
        base_store.store_envelope("env-1", {"agent_id": "a1", "constraints": {}})
        result = data_store.get_envelope("env-1")
        assert result is not None

    def test_can_read_delegations(self, data_store: DataPlaneStore, base_store: SQLiteTrustStore):
        """Data plane can read delegation records for chain walking."""
        base_store.store_delegation(
            "d1",
            {
                "delegation_id": "d1",
                "delegator_id": "root",
                "delegatee_id": "a1",
            },
        )
        result = data_store.get_delegation("d1")
        assert result is not None

    def test_can_read_genesis(self, data_store: DataPlaneStore, base_store: SQLiteTrustStore):
        """Data plane can read genesis records for chain verification."""
        base_store.store_genesis("authority-1", {"authority_id": "authority-1"})
        result = data_store.get_genesis("authority-1")
        assert result is not None


# ---------------------------------------------------------------------------
# Cross-plane isolation enforcement
# ---------------------------------------------------------------------------


class TestCrossPlaneIsolation:
    """Data written through one plane is visible through the other (same underlying store)."""

    def test_management_writes_visible_to_data_reads(
        self,
        management_store: ManagementPlaneStore,
        data_store: DataPlaneStore,
    ):
        """Data written by management plane is readable by data plane."""
        management_store.store_envelope("env-1", {"agent_id": "a1", "constraints": {}})
        result = data_store.get_envelope("env-1")
        assert result is not None

    def test_data_writes_visible_to_management_reads(
        self,
        management_store: ManagementPlaneStore,
        data_store: DataPlaneStore,
    ):
        """Audit anchors written by data plane are readable by management plane."""
        data_store.store_audit_anchor(
            "anchor-1",
            {"agent_id": "a1", "action": "test", "verification_level": "AUTO_APPROVED"},
        )
        result = management_store.get_audit_anchor("anchor-1")
        assert result is not None

    def test_health_check_available_on_both_planes(
        self,
        management_store: ManagementPlaneStore,
        data_store: DataPlaneStore,
    ):
        assert management_store.health_check() is True
        assert data_store.health_check() is True


# ---------------------------------------------------------------------------
# PlaneViolationError
# ---------------------------------------------------------------------------


class TestPlaneViolationError:
    """PlaneViolationError provides clear error information."""

    def test_error_message_includes_plane_name(self):
        error = PlaneViolationError("data plane", "store_genesis")
        assert "data plane" in str(error)
        assert "store_genesis" in str(error)

    def test_is_exception_subclass(self):
        error = PlaneViolationError("data plane", "store_genesis")
        assert isinstance(error, Exception)
