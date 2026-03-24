# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for genesis record write-once enforcement (M22-2206 / RT5-14).

Validates that:
- SQLiteTrustStore.store_genesis() raises an error when a genesis record
  already exists for the given authority_id (not silently ignored)
- First write succeeds normally
- Application-level enforcement is explicit (raises GenesisAlreadyExistsError)
- Original genesis data is never overwritten
"""

from __future__ import annotations

import pytest

from pact_platform.trust.store.sqlite_store import (
    GenesisAlreadyExistsError,
    SQLiteTrustStore,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store():
    """Fresh in-memory SQLiteTrustStore for each test."""
    return SQLiteTrustStore()


@pytest.fixture()
def genesis_data():
    """Sample genesis record data."""
    return {
        "authority_id": "test.foundation",
        "authority_name": "Test Foundation",
        "policy_reference": "https://test.foundation/policy",
    }


@pytest.fixture()
def different_genesis_data():
    """Different genesis data for the same authority."""
    return {
        "authority_id": "test.foundation",
        "authority_name": "Altered Foundation",
        "policy_reference": "https://altered.foundation/policy",
    }


# ---------------------------------------------------------------------------
# Tests: First write succeeds
# ---------------------------------------------------------------------------


class TestGenesisFirstWrite:
    """First genesis write for a new authority succeeds."""

    def test_first_write_stores_record(self, store, genesis_data):
        """First store_genesis() for an authority should succeed."""
        store.store_genesis("test.foundation", genesis_data)
        result = store.get_genesis("test.foundation")
        assert result is not None
        assert result["authority_name"] == "Test Foundation"

    def test_first_write_returns_none(self, store, genesis_data):
        """First store_genesis() should return None (no return value)."""
        result = store.store_genesis("test.foundation", genesis_data)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Second write raises error
# ---------------------------------------------------------------------------


class TestGenesisWriteOnceEnforcement:
    """Second write for same authority raises GenesisAlreadyExistsError."""

    def test_second_write_raises_error(self, store, genesis_data, different_genesis_data):
        """Attempting to overwrite an existing genesis record raises an error."""
        store.store_genesis("test.foundation", genesis_data)

        with pytest.raises(GenesisAlreadyExistsError) as exc_info:
            store.store_genesis("test.foundation", different_genesis_data)

        assert "test.foundation" in str(exc_info.value)

    def test_original_data_preserved(self, store, genesis_data, different_genesis_data):
        """After a failed overwrite attempt, original data is preserved."""
        store.store_genesis("test.foundation", genesis_data)

        with pytest.raises(GenesisAlreadyExistsError):
            store.store_genesis("test.foundation", different_genesis_data)

        result = store.get_genesis("test.foundation")
        assert result is not None
        assert result["authority_name"] == "Test Foundation"
        assert result["authority_name"] != "Altered Foundation"

    def test_different_authority_still_works(self, store, genesis_data):
        """Different authority_id can still write genesis records."""
        store.store_genesis("test.foundation", genesis_data)

        other_data = {
            "authority_id": "other.foundation",
            "authority_name": "Other Foundation",
        }
        store.store_genesis("other.foundation", other_data)

        # Both should exist
        assert store.get_genesis("test.foundation") is not None
        assert store.get_genesis("other.foundation") is not None


# ---------------------------------------------------------------------------
# Tests: GenesisAlreadyExistsError
# ---------------------------------------------------------------------------


class TestGenesisAlreadyExistsError:
    """GenesisAlreadyExistsError is a proper exception type."""

    def test_error_is_value_error_subclass(self):
        """GenesisAlreadyExistsError should be catchable as ValueError."""
        assert issubclass(GenesisAlreadyExistsError, ValueError)

    def test_error_includes_authority_id(self):
        """Error message includes the authority_id."""
        err = GenesisAlreadyExistsError("test.foundation")
        assert "test.foundation" in str(err)
