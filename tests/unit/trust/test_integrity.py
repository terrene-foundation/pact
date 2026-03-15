# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for TrustChainIntegrity — hash-chain verification for trust records.

M17-1701: Trust chain records need hash chaining for tamper detection.
- Each delegation record includes a `previous_record_hash` linking to the prior record.
- TrustChainIntegrity verifier validates the full chain.
- Tampering with any record breaks the chain.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from care_platform.trust.integrity import (
    TrustChainIntegrity,
    TrustRecordHash,
    IntegrityCheckResult,
    IntegrityViolation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_genesis_data(authority_id: str = "terrene.foundation") -> dict:
    """Create a minimal genesis record data dict."""
    return {
        "record_type": "genesis",
        "authority_id": authority_id,
        "agent_id": f"authority:{authority_id}",
        "policy_reference": "https://terrene.foundation/governance",
    }


def _make_delegation_data(
    delegation_id: str,
    delegator_id: str,
    delegatee_id: str,
) -> dict:
    """Create a minimal delegation record data dict."""
    return {
        "record_type": "delegation",
        "delegation_id": delegation_id,
        "delegator_id": delegator_id,
        "delegatee_id": delegatee_id,
    }


# ---------------------------------------------------------------------------
# TrustRecordHash
# ---------------------------------------------------------------------------


class TestTrustRecordHash:
    """TrustRecordHash computes deterministic hashes for trust records."""

    def test_hash_genesis_record_is_deterministic(self):
        data = _make_genesis_data()
        h1 = TrustRecordHash.compute(data)
        h2 = TrustRecordHash.compute(data)
        assert h1 == h2

    def test_hash_is_sha256_hex(self):
        data = _make_genesis_data()
        h = TrustRecordHash.compute(data)
        # SHA-256 hex digest is 64 chars
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_data_produces_different_hash(self):
        h1 = TrustRecordHash.compute(_make_genesis_data("authority-a"))
        h2 = TrustRecordHash.compute(_make_genesis_data("authority-b"))
        assert h1 != h2

    def test_compute_with_previous_hash(self):
        data = _make_delegation_data("d1", "root", "agent-1")
        prev = "abc123"
        h = TrustRecordHash.compute(data, previous_hash=prev)
        assert len(h) == 64

    def test_previous_hash_affects_result(self):
        data = _make_delegation_data("d1", "root", "agent-1")
        h_no_prev = TrustRecordHash.compute(data)
        h_with_prev = TrustRecordHash.compute(data, previous_hash="abc123")
        assert h_no_prev != h_with_prev


# ---------------------------------------------------------------------------
# TrustChainIntegrity — building chains
# ---------------------------------------------------------------------------


class TestTrustChainIntegrityBuild:
    """TrustChainIntegrity can build and maintain hash chains."""

    def test_append_genesis_returns_hash(self):
        chain = TrustChainIntegrity()
        genesis = _make_genesis_data()
        record_hash = chain.append_record(genesis)
        assert isinstance(record_hash, str)
        assert len(record_hash) == 64

    def test_append_delegation_links_to_previous(self):
        chain = TrustChainIntegrity()
        genesis = _make_genesis_data()
        genesis_hash = chain.append_record(genesis)

        delegation = _make_delegation_data("d1", "root", "agent-1")
        delegation_hash = chain.append_record(delegation)

        # Different records produce different hashes
        assert delegation_hash != genesis_hash

    def test_chain_length_increments(self):
        chain = TrustChainIntegrity()
        assert chain.length == 0

        chain.append_record(_make_genesis_data())
        assert chain.length == 1

        chain.append_record(_make_delegation_data("d1", "root", "a1"))
        assert chain.length == 2

    def test_get_record_hash_by_index(self):
        chain = TrustChainIntegrity()
        h0 = chain.append_record(_make_genesis_data())
        h1 = chain.append_record(_make_delegation_data("d1", "root", "a1"))

        assert chain.get_hash(0) == h0
        assert chain.get_hash(1) == h1

    def test_get_hash_invalid_index_raises(self):
        chain = TrustChainIntegrity()
        with pytest.raises(IndexError, match="out of range"):
            chain.get_hash(0)

    def test_head_hash_returns_latest(self):
        chain = TrustChainIntegrity()
        chain.append_record(_make_genesis_data())
        h1 = chain.append_record(_make_delegation_data("d1", "root", "a1"))

        assert chain.head_hash == h1

    def test_head_hash_empty_chain_raises(self):
        chain = TrustChainIntegrity()
        with pytest.raises(ValueError, match="empty"):
            _ = chain.head_hash


# ---------------------------------------------------------------------------
# TrustChainIntegrity — verification
# ---------------------------------------------------------------------------


class TestTrustChainIntegrityVerify:
    """TrustChainIntegrity can verify chain integrity."""

    def test_valid_chain_passes_verification(self):
        chain = TrustChainIntegrity()
        chain.append_record(_make_genesis_data())
        chain.append_record(_make_delegation_data("d1", "root", "a1"))
        chain.append_record(_make_delegation_data("d2", "a1", "a2"))

        result = chain.verify()
        assert result.is_valid is True
        assert len(result.violations) == 0

    def test_empty_chain_is_valid(self):
        chain = TrustChainIntegrity()
        result = chain.verify()
        assert result.is_valid is True

    def test_single_record_chain_is_valid(self):
        chain = TrustChainIntegrity()
        chain.append_record(_make_genesis_data())
        result = chain.verify()
        assert result.is_valid is True

    def test_tampered_record_detected(self):
        """Tampering with a stored record's data should be caught by verification."""
        chain = TrustChainIntegrity()
        chain.append_record(_make_genesis_data())
        chain.append_record(_make_delegation_data("d1", "root", "a1"))
        chain.append_record(_make_delegation_data("d2", "a1", "a2"))

        # Tamper with the middle record's data
        chain._records[1].data["delegatee_id"] = "tampered-agent"

        result = chain.verify()
        assert result.is_valid is False
        assert len(result.violations) >= 1
        # The violation should reference the tampered index
        assert any(v.record_index == 1 for v in result.violations)

    def test_tampered_genesis_detected(self):
        """Tampering with the genesis record should be caught."""
        chain = TrustChainIntegrity()
        chain.append_record(_make_genesis_data())
        chain.append_record(_make_delegation_data("d1", "root", "a1"))

        # Tamper with genesis data
        chain._records[0].data["authority_id"] = "evil-authority"

        result = chain.verify()
        assert result.is_valid is False
        assert any(v.record_index == 0 for v in result.violations)

    def test_deleted_record_detected(self):
        """Removing a record from the middle of the chain should be caught."""
        chain = TrustChainIntegrity()
        chain.append_record(_make_genesis_data())
        chain.append_record(_make_delegation_data("d1", "root", "a1"))
        chain.append_record(_make_delegation_data("d2", "a1", "a2"))

        # Remove the middle record
        del chain._records[1]

        result = chain.verify()
        assert result.is_valid is False


# ---------------------------------------------------------------------------
# IntegrityCheckResult model
# ---------------------------------------------------------------------------


class TestIntegrityCheckResult:
    """IntegrityCheckResult provides clear status information."""

    def test_valid_result(self):
        result = IntegrityCheckResult(
            is_valid=True,
            violations=[],
            records_checked=3,
        )
        assert result.is_valid is True
        assert result.records_checked == 3

    def test_invalid_result_with_violation(self):
        violation = IntegrityViolation(
            record_index=1,
            expected_hash="abc",
            actual_hash="def",
            description="Record hash mismatch at index 1",
        )
        result = IntegrityCheckResult(
            is_valid=False,
            violations=[violation],
            records_checked=3,
        )
        assert result.is_valid is False
        assert len(result.violations) == 1
        assert result.violations[0].record_index == 1


# ---------------------------------------------------------------------------
# SQLiteTrustStore integration with hash chain
# ---------------------------------------------------------------------------


class TestSQLiteStoreHashChain:
    """SQLiteTrustStore can store and verify delegation record hashes."""

    def test_store_delegation_with_hash(self):
        from care_platform.persistence.sqlite_store import SQLiteTrustStore

        store = SQLiteTrustStore(":memory:")
        data = {
            "delegation_id": "d1",
            "delegator_id": "root",
            "delegatee_id": "agent-1",
            "record_hash": "abc123",
            "previous_record_hash": None,
        }
        store.store_delegation("d1", data)
        result = store.get_delegation("d1")
        assert result is not None
        assert result["record_hash"] == "abc123"
        assert result["previous_record_hash"] is None

    def test_store_delegation_chain_with_hashes(self):
        from care_platform.persistence.sqlite_store import SQLiteTrustStore

        store = SQLiteTrustStore(":memory:")

        # Genesis delegation
        d1 = {
            "delegation_id": "d1",
            "delegator_id": "root",
            "delegatee_id": "a1",
            "record_hash": "hash_d1",
            "previous_record_hash": None,
        }
        store.store_delegation("d1", d1)

        # Chained delegation
        d2 = {
            "delegation_id": "d2",
            "delegator_id": "a1",
            "delegatee_id": "a2",
            "record_hash": "hash_d2",
            "previous_record_hash": "hash_d1",
        }
        store.store_delegation("d2", d2)

        result = store.get_delegation("d2")
        assert result is not None
        assert result["previous_record_hash"] == "hash_d1"

    def test_verify_delegation_chain_integrity(self):
        """Build a real chain with computed hashes and verify through the store."""
        from care_platform.persistence.sqlite_store import SQLiteTrustStore

        store = SQLiteTrustStore(":memory:")
        integrity = TrustChainIntegrity()

        # Build chain
        genesis_data = _make_genesis_data()
        genesis_hash = integrity.append_record(genesis_data)

        d1_data = _make_delegation_data("d1", "root", "agent-1")
        d1_hash = integrity.append_record(d1_data)

        # Store in SQLite with hashes
        store.store_delegation(
            "d1",
            {**d1_data, "record_hash": d1_hash, "previous_record_hash": genesis_hash},
        )

        # Retrieve and verify hash matches
        stored = store.get_delegation("d1")
        assert stored is not None
        assert stored["record_hash"] == d1_hash
        assert stored["previous_record_hash"] == genesis_hash

        # Full chain verification
        result = integrity.verify()
        assert result.is_valid is True
