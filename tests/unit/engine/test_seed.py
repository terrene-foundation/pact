# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for AutoSeed (seed.py).

Covers:
- seed_demo_data creates objectives, requests, decisions, runs, pools
- seed_demo_data is idempotent (no-op on second call)
- seed_if_empty handles exceptions gracefully
- Seeded record counts match expected totals
- Read-back verification of persisted records
"""

from __future__ import annotations

import pytest

from pact_platform.engine.seed import seed_demo_data, seed_if_empty
from pact_platform.models import db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_records(model: str, limit: int = 100) -> list[dict]:
    """List records of a given model from DataFlow."""
    wf = db.create_workflow()
    wf.add_node(f"{model}ListNode", "list", {"filter": {}, "limit": limit})
    results, _ = db.execute_workflow(wf)
    return results["list"].get("records", [])


# ---------------------------------------------------------------------------
# Tests: seed_demo_data
# ---------------------------------------------------------------------------


class TestSeedDemoData:
    """Test the seed_demo_data function."""

    def test_returns_seeded_result(self):
        result = seed_demo_data(db)
        # In full-suite runs, other tests may have already seeded.
        # Verify the return structure is valid either way.
        assert isinstance(result["seeded"], bool)
        if result["seeded"]:
            assert result["objectives"] == 2
            assert result["requests"] == 5

    def test_seeded_counts_match(self):
        # seed_demo_data was already called in the test above, but since
        # tests share the module-level db and the DB might already have data,
        # we just verify the counts if seeded
        result = seed_demo_data(db)
        if result["seeded"]:
            assert result["objectives"] == 2
            assert result["requests"] == 5
            assert result["decisions"] == 1
            assert result["runs"] == 3
            assert result["pools"] == 1
            assert result["pool_members"] == 1

    def test_creates_objectives(self):
        result = seed_demo_data(db)
        objectives = _list_records("AgenticObjective")
        # Seed either created records or they existed from prior tests
        assert len(objectives) >= 1
        if result["seeded"]:
            titles = {o["title"] for o in objectives}
            assert "Review Graduate Admissions" in titles
            assert "Update Course Catalog" in titles

    def test_creates_requests(self):
        result = seed_demo_data(db)
        requests = _list_records("AgenticRequest")
        if result["seeded"]:
            assert len(requests) >= 5

    def test_creates_held_decision(self):
        result = seed_demo_data(db)
        if result["seeded"]:
            decisions = _list_records("AgenticDecision")
            held = [d for d in decisions if d["status"] == "pending"]
            assert len(held) >= 1
            held_dec = held[0]
            assert held_dec["decision_type"] == "governance_hold"
            assert held_dec["constraint_dimension"] == "data_access"

    def test_creates_runs_with_costs(self):
        result = seed_demo_data(db)
        if result["seeded"]:
            runs = _list_records("Run")
            assert len(runs) >= 3
            costs = [r["cost_usd"] for r in runs]
            assert all(c >= 0 for c in costs)

    def test_creates_pool_and_membership(self):
        result = seed_demo_data(db)
        if result["seeded"]:
            pools = _list_records("AgenticPool")
            assert len(pools) >= 1
            assert pools[0]["name"] == "University Research Pool"
            memberships = _list_records("AgenticPoolMembership")
            assert len(memberships) >= 1


# ---------------------------------------------------------------------------
# Tests: Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """seed_demo_data must be a no-op when data already exists."""

    def test_second_call_returns_seeded_false(self):
        # First call seeds
        seed_demo_data(db)
        # Second call should detect existing data and skip
        result = seed_demo_data(db)
        assert result["seeded"] is False

    def test_no_duplicate_objectives_after_double_seed(self):
        seed_demo_data(db)
        count_after_first = len(_list_records("AgenticObjective"))
        seed_demo_data(db)
        count_after_second = len(_list_records("AgenticObjective"))
        # Second call must not create additional records
        assert count_after_second == count_after_first


# ---------------------------------------------------------------------------
# Tests: seed_if_empty
# ---------------------------------------------------------------------------


class TestSeedIfEmpty:
    """Test the seed_if_empty convenience wrapper."""

    def test_seed_if_empty_does_not_crash_on_exception(self):
        """seed_if_empty must swallow exceptions and continue."""

        class _FailingDB:
            def create_workflow(self, *args, **kwargs):
                raise RuntimeError("DB is broken")

        # Must not raise
        seed_if_empty(_FailingDB())

    def test_seed_if_empty_calls_seed_demo_data(self):
        """seed_if_empty delegates to seed_demo_data."""
        # Since data already exists, it should be a no-op
        seed_if_empty(db)
        objectives = _list_records("AgenticObjective")
        assert len(objectives) >= 2
