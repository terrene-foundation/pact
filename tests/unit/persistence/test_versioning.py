# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for constraint envelope version tracking and diffing."""

import pytest

from pact_platform.trust.store.versioning import (
    VersionTracker,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope_data(
    max_spend: float = 0.0,
    allowed_actions: list[str] | None = None,
    internal_only: bool = True,
) -> dict:
    """Create an envelope data dict for testing."""
    return {
        "id": "env-1",
        "financial": {"max_spend_usd": max_spend},
        "operational": {"allowed_actions": allowed_actions or [], "blocked_actions": []},
        "temporal": {},
        "data_access": {},
        "communication": {"internal_only": internal_only},
    }


# ---------------------------------------------------------------------------
# EnvelopeVersion model tests
# ---------------------------------------------------------------------------


class TestEnvelopeVersion:
    def test_version_has_content_hash(self):
        tracker = VersionTracker()
        version = tracker.record_version(
            "env-1",
            _make_envelope_data(),
            created_by="admin-1",
        )
        assert version.content_hash
        assert len(version.content_hash) == 64  # SHA-256 hex digest

    def test_version_number_starts_at_one(self):
        tracker = VersionTracker()
        version = tracker.record_version(
            "env-1",
            _make_envelope_data(),
            created_by="admin-1",
        )
        assert version.version == 1

    def test_version_number_increments(self):
        tracker = VersionTracker()
        v1 = tracker.record_version(
            "env-1",
            _make_envelope_data(),
            created_by="admin-1",
        )
        v2 = tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=50.0),
            created_by="admin-1",
        )
        assert v1.version == 1
        assert v2.version == 2

    def test_version_stores_envelope_id(self):
        tracker = VersionTracker()
        version = tracker.record_version(
            "env-1",
            _make_envelope_data(),
            created_by="admin-1",
        )
        assert version.envelope_id == "env-1"

    def test_version_stores_created_by(self):
        tracker = VersionTracker()
        version = tracker.record_version(
            "env-1",
            _make_envelope_data(),
            created_by="admin-1",
        )
        assert version.created_by == "admin-1"

    def test_version_stores_reason(self):
        tracker = VersionTracker()
        version = tracker.record_version(
            "env-1",
            _make_envelope_data(),
            created_by="admin-1",
            reason="Initial setup",
        )
        assert version.reason == "Initial setup"


# ---------------------------------------------------------------------------
# Version chain integrity
# ---------------------------------------------------------------------------


class TestVersionChainIntegrity:
    def test_first_version_has_no_previous_hash(self):
        tracker = VersionTracker()
        v1 = tracker.record_version(
            "env-1",
            _make_envelope_data(),
            created_by="admin-1",
        )
        assert v1.previous_version_hash is None

    def test_second_version_chains_to_first(self):
        tracker = VersionTracker()
        v1 = tracker.record_version(
            "env-1",
            _make_envelope_data(),
            created_by="admin-1",
        )
        v2 = tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=50.0),
            created_by="admin-1",
        )
        assert v2.previous_version_hash == v1.content_hash

    def test_different_data_produces_different_hashes(self):
        tracker = VersionTracker()
        v1 = tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=0.0),
            created_by="admin-1",
        )
        v2 = tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=100.0),
            created_by="admin-1",
        )
        assert v1.content_hash != v2.content_hash


# ---------------------------------------------------------------------------
# History retrieval
# ---------------------------------------------------------------------------


class TestVersionHistory:
    def test_get_history_returns_all_versions(self):
        tracker = VersionTracker()
        tracker.record_version("env-1", _make_envelope_data(), "admin-1")
        tracker.record_version("env-1", _make_envelope_data(max_spend=50.0), "admin-1")
        tracker.record_version("env-1", _make_envelope_data(max_spend=100.0), "admin-1")
        history = tracker.get_history("env-1")
        assert len(history) == 3

    def test_get_history_ordered_by_version(self):
        tracker = VersionTracker()
        tracker.record_version("env-1", _make_envelope_data(), "admin-1")
        tracker.record_version("env-1", _make_envelope_data(max_spend=50.0), "admin-1")
        history = tracker.get_history("env-1")
        assert history[0].version < history[1].version

    def test_get_history_empty_for_unknown_envelope(self):
        tracker = VersionTracker()
        history = tracker.get_history("nonexistent")
        assert history == []

    def test_get_current_returns_latest(self):
        tracker = VersionTracker()
        tracker.record_version("env-1", _make_envelope_data(), "admin-1")
        tracker.record_version("env-1", _make_envelope_data(max_spend=50.0), "admin-1")
        current = tracker.get_current("env-1")
        assert current is not None
        assert current.version == 2

    def test_get_current_returns_none_for_unknown(self):
        tracker = VersionTracker()
        assert tracker.get_current("nonexistent") is None

    def test_get_specific_version(self):
        tracker = VersionTracker()
        tracker.record_version("env-1", _make_envelope_data(), "admin-1")
        tracker.record_version("env-1", _make_envelope_data(max_spend=50.0), "admin-1")
        v1 = tracker.get_version("env-1", 1)
        assert v1 is not None
        assert v1.version == 1

    def test_get_specific_version_returns_none_for_bad_version(self):
        tracker = VersionTracker()
        tracker.record_version("env-1", _make_envelope_data(), "admin-1")
        assert tracker.get_version("env-1", 99) is None

    def test_histories_isolated_per_envelope(self):
        tracker = VersionTracker()
        tracker.record_version("env-1", _make_envelope_data(), "admin-1")
        tracker.record_version("env-2", _make_envelope_data(), "admin-1")
        assert len(tracker.get_history("env-1")) == 1
        assert len(tracker.get_history("env-2")) == 1


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------


class TestVersionDiff:
    def test_diff_detects_financial_change(self):
        tracker = VersionTracker()
        tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=0.0),
            "admin-1",
        )
        tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=50.0),
            "admin-1",
        )
        diffs = tracker.compute_diff("env-1", 1, 2)
        assert len(diffs) >= 1
        financial_diffs = [d for d in diffs if d.dimension == "financial"]
        assert len(financial_diffs) == 1
        assert financial_diffs[0].field == "max_spend_usd"
        assert financial_diffs[0].old_value == "0.0"
        assert financial_diffs[0].new_value == "50.0"

    def test_diff_detects_communication_change(self):
        tracker = VersionTracker()
        tracker.record_version(
            "env-1",
            _make_envelope_data(internal_only=True),
            "admin-1",
        )
        tracker.record_version(
            "env-1",
            _make_envelope_data(internal_only=False),
            "admin-1",
        )
        diffs = tracker.compute_diff("env-1", 1, 2)
        comm_diffs = [d for d in diffs if d.dimension == "communication"]
        assert len(comm_diffs) == 1
        assert comm_diffs[0].field == "internal_only"

    def test_diff_returns_empty_when_identical(self):
        tracker = VersionTracker()
        tracker.record_version(
            "env-1",
            _make_envelope_data(),
            "admin-1",
        )
        tracker.record_version(
            "env-1",
            _make_envelope_data(),
            "admin-1",
        )
        diffs = tracker.compute_diff("env-1", 1, 2)
        assert diffs == []

    def test_diff_has_human_readable_description(self):
        tracker = VersionTracker()
        tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=0.0),
            "admin-1",
        )
        tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=50.0),
            "admin-1",
        )
        diffs = tracker.compute_diff("env-1", 1, 2)
        assert len(diffs) >= 1
        assert diffs[0].description  # non-empty

    def test_diff_raises_for_unknown_envelope(self):
        tracker = VersionTracker()
        with pytest.raises(KeyError):
            tracker.compute_diff("nonexistent", 1, 2)

    def test_diff_raises_for_invalid_version(self):
        tracker = VersionTracker()
        tracker.record_version("env-1", _make_envelope_data(), "admin-1")
        with pytest.raises(KeyError):
            tracker.compute_diff("env-1", 1, 99)

    def test_diff_multiple_changes(self):
        tracker = VersionTracker()
        tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=0.0, internal_only=True),
            "admin-1",
        )
        tracker.record_version(
            "env-1",
            _make_envelope_data(max_spend=100.0, internal_only=False),
            "admin-1",
        )
        diffs = tracker.compute_diff("env-1", 1, 2)
        dimensions_changed = {d.dimension for d in diffs}
        assert "financial" in dimensions_changed
        assert "communication" in dimensions_changed
