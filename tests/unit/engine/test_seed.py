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

from typing import Any

import pytest

from pact_platform.engine.seed import seed_demo_data, seed_if_empty


# ---------------------------------------------------------------------------
# Helpers — MockExpressSync
# ---------------------------------------------------------------------------


class MockExpressSync:
    """In-memory Express sync API that tracks all calls and stores records."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._store: dict[str, list[dict[str, Any]]] = {}

    def create(self, model: str, data: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"method": "create", "model": model, "data": data})
        self._store.setdefault(model, []).append(dict(data))
        return dict(data)

    def read(self, model: str, record_id: str) -> dict[str, Any] | None:
        self.calls.append({"method": "read", "model": model, "record_id": record_id})
        for rec in self._store.get(model, []):
            if rec.get("id") == record_id:
                return dict(rec)
        return None

    def update(self, model: str, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(
            {"method": "update", "model": model, "record_id": record_id, "fields": fields}
        )
        for rec in self._store.get(model, []):
            if rec.get("id") == record_id:
                rec.update(fields)
                return dict(rec)
        return fields

    def list(
        self, model: str, filter_dict: dict[str, Any], limit: int = 100
    ) -> list[dict[str, Any]]:
        self.calls.append({"method": "list", "model": model, "filter": filter_dict, "limit": limit})
        records = self._store.get(model, [])
        # Apply simple filter
        matched = []
        for rec in records:
            match = True
            for k, v in filter_dict.items():
                if rec.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(dict(rec))
        return matched[:limit]


class MockDB:
    """Mock DataFlow with express_sync attribute."""

    def __init__(self) -> None:
        self.express_sync = MockExpressSync()


# ---------------------------------------------------------------------------
# Tests: seed_demo_data
# ---------------------------------------------------------------------------


class TestSeedDemoData:
    """Test the seed_demo_data function."""

    def test_returns_seeded_result(self):
        mock_db = MockDB()
        result = seed_demo_data(mock_db)
        assert isinstance(result["seeded"], bool)
        assert result["seeded"] is True
        assert result["objectives"] == 2
        assert result["requests"] == 5

    def test_seeded_counts_match(self):
        mock_db = MockDB()
        result = seed_demo_data(mock_db)
        assert result["seeded"] is True
        assert result["objectives"] == 2
        assert result["requests"] == 5
        assert result["decisions"] == 1
        assert result["runs"] == 3
        assert result["pools"] == 1
        assert result["pool_members"] == 1

    def test_creates_objectives(self):
        mock_db = MockDB()
        seed_demo_data(mock_db)
        objectives = mock_db.express_sync.list("AgenticObjective", {})
        assert len(objectives) == 2
        titles = {o["title"] for o in objectives}
        assert "Review Graduate Admissions" in titles
        assert "Update Course Catalog" in titles

    def test_creates_requests(self):
        mock_db = MockDB()
        seed_demo_data(mock_db)
        requests = mock_db.express_sync.list("AgenticRequest", {})
        assert len(requests) == 5

    def test_creates_held_decision(self):
        mock_db = MockDB()
        seed_demo_data(mock_db)
        decisions = mock_db.express_sync.list("AgenticDecision", {})
        held = [d for d in decisions if d["status"] == "pending"]
        assert len(held) == 1
        held_dec = held[0]
        assert held_dec["decision_type"] == "governance_hold"
        assert held_dec["constraint_dimension"] == "data_access"

    def test_creates_runs_with_costs(self):
        mock_db = MockDB()
        seed_demo_data(mock_db)
        runs = mock_db.express_sync.list("Run", {})
        assert len(runs) == 3
        costs = [r["cost_usd"] for r in runs]
        assert all(c >= 0 for c in costs)

    def test_creates_pool_and_membership(self):
        mock_db = MockDB()
        seed_demo_data(mock_db)
        pools = mock_db.express_sync.list("AgenticPool", {})
        assert len(pools) == 1
        assert pools[0]["name"] == "University Research Pool"
        memberships = mock_db.express_sync.list("AgenticPoolMembership", {})
        assert len(memberships) == 1


# ---------------------------------------------------------------------------
# Tests: Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """seed_demo_data must be a no-op when data already exists."""

    def test_second_call_returns_seeded_false(self):
        mock_db = MockDB()
        # First call seeds
        seed_demo_data(mock_db)
        # Second call should detect existing data and skip
        result = seed_demo_data(mock_db)
        assert result["seeded"] is False

    def test_no_duplicate_objectives_after_double_seed(self):
        mock_db = MockDB()
        seed_demo_data(mock_db)
        count_after_first = len(mock_db.express_sync.list("AgenticObjective", {}))
        seed_demo_data(mock_db)
        count_after_second = len(mock_db.express_sync.list("AgenticObjective", {}))
        # Second call must not create additional records
        assert count_after_second == count_after_first


# ---------------------------------------------------------------------------
# Tests: seed_if_empty
# ---------------------------------------------------------------------------


class TestSeedIfEmpty:
    """Test the seed_if_empty convenience wrapper."""

    def test_seed_if_empty_does_not_crash_on_exception(self):
        """seed_if_empty must swallow exceptions and continue."""

        class _FailingExpressSync:
            def list(self, *args, **kwargs):
                raise RuntimeError("DB is broken")

        class _FailingDB:
            express_sync = _FailingExpressSync()

        # Must not raise
        seed_if_empty(_FailingDB())

    def test_seed_if_empty_calls_seed_demo_data(self):
        """seed_if_empty delegates to seed_demo_data."""
        mock_db = MockDB()
        seed_if_empty(mock_db)
        objectives = mock_db.express_sync.list("AgenticObjective", {})
        assert len(objectives) >= 2
