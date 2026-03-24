# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for audit query interface and audit reports."""

from datetime import UTC, datetime, timedelta

import pytest

from pact_platform.trust.store.audit_query import AuditQuery, AuditReport
from pact_platform.trust.store.store import MemoryStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_anchor(
    anchor_id: str = "anc-1",
    agent_id: str = "agent-1",
    action: str = "read_metrics",
    verification_level: str = "AUTO_APPROVED",
    timestamp: datetime | None = None,
    result: str = "success",
) -> dict:
    return {
        "anchor_id": anchor_id,
        "agent_id": agent_id,
        "action": action,
        "verification_level": verification_level,
        "timestamp": (timestamp or datetime.now(UTC)).isoformat(),
        "result": result,
    }


def _populate_store(store: MemoryStore) -> None:
    """Load the store with a diverse set of anchors for query testing.

    Uses offsets that avoid boundary conditions so that test assertions
    remain deterministic regardless of ``datetime.now()`` drift.
    """
    now = datetime.now(UTC)
    store.store_audit_anchor(
        "anc-1",
        _make_anchor(
            "anc-1",
            "agent-1",
            "read_metrics",
            "AUTO_APPROVED",
            now - timedelta(days=5),
        ),
    )
    store.store_audit_anchor(
        "anc-2",
        _make_anchor(
            "anc-2",
            "agent-1",
            "write_report",
            "FLAGGED",
            now - timedelta(days=3),
        ),
    )
    store.store_audit_anchor(
        "anc-3",
        _make_anchor(
            "anc-3",
            "agent-2",
            "draft_email",
            "HELD",
            now - timedelta(days=2),
        ),
    )
    store.store_audit_anchor(
        "anc-4",
        _make_anchor(
            "anc-4",
            "agent-2",
            "send_email",
            "HELD",
            now - timedelta(hours=12),
        ),
    )
    store.store_audit_anchor(
        "anc-5",
        _make_anchor(
            "anc-5",
            "agent-3",
            "read_metrics",
            "AUTO_APPROVED",
            now,
        ),
    )


# ---------------------------------------------------------------------------
# AuditQuery.by_agent
# ---------------------------------------------------------------------------


class TestAuditQueryByAgent:
    def test_returns_all_anchors_for_agent(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        results = query.by_agent("agent-1")
        assert len(results) == 2
        assert all(r["agent_id"] == "agent-1" for r in results)

    def test_returns_empty_for_unknown_agent(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        results = query.by_agent("unknown-agent")
        assert results == []

    def test_respects_limit(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        results = query.by_agent("agent-2", limit=1)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# AuditQuery.by_time_range
# ---------------------------------------------------------------------------


class TestAuditQueryByTimeRange:
    def test_returns_anchors_in_range(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        now = datetime.now(UTC)
        results = query.by_time_range(
            start=now - timedelta(days=4),
            end=now - timedelta(days=1),
        )
        # Should include anc-2 (3 days ago), anc-3 (2 days ago), anc-4 (1 day ago)
        assert len(results) >= 2

    def test_returns_empty_for_out_of_range(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        results = query.by_time_range(
            start=datetime(2020, 1, 1, tzinfo=UTC),
            end=datetime(2020, 12, 31, tzinfo=UTC),
        )
        assert results == []


# ---------------------------------------------------------------------------
# AuditQuery.by_verification_level
# ---------------------------------------------------------------------------


class TestAuditQueryByVerificationLevel:
    def test_returns_held_anchors(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        results = query.by_verification_level("HELD")
        assert len(results) == 2
        assert all(r["verification_level"] == "HELD" for r in results)

    def test_returns_auto_approved_anchors(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        results = query.by_verification_level("AUTO_APPROVED")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# AuditQuery.filter (combined)
# ---------------------------------------------------------------------------


class TestAuditQueryFilter:
    def test_filter_by_agent_and_action(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        results = query.filter(agent_id="agent-1", action="read_metrics")
        assert len(results) == 1
        assert results[0]["anchor_id"] == "anc-1"

    def test_filter_by_verification_level_and_limit(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        results = query.filter(verification_level="HELD", limit=1)
        assert len(results) == 1

    def test_filter_with_no_criteria_returns_all(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        results = query.filter()
        assert len(results) == 5

    def test_filter_by_time_range(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        now = datetime.now(UTC)
        results = query.filter(since=now - timedelta(days=2), until=now)
        # Should include anc-3 (2 days), anc-4 (1 day), anc-5 (now)
        assert len(results) >= 2


# ---------------------------------------------------------------------------
# AuditQuery.aggregate_by_agent
# ---------------------------------------------------------------------------


class TestAuditQueryAggregate:
    def test_aggregate_counts_per_agent(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        agg = query.aggregate_by_agent()
        assert agg["agent-1"] == 2
        assert agg["agent-2"] == 2
        assert agg["agent-3"] == 1

    def test_aggregate_with_since_filter(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        now = datetime.now(UTC)
        agg = query.aggregate_by_agent(since=now - timedelta(days=1))
        # Only anc-4 (1 day) and anc-5 (now) should be counted
        assert agg.get("agent-1", 0) == 0
        assert agg.get("agent-2", 0) >= 1
        assert agg.get("agent-3", 0) == 1

    def test_aggregate_empty_store(self):
        store = MemoryStore()
        query = AuditQuery(store=store)
        agg = query.aggregate_by_agent()
        assert agg == {}


# ---------------------------------------------------------------------------
# AuditQuery.held_actions
# ---------------------------------------------------------------------------


class TestAuditQueryHeldActions:
    def test_returns_all_held_actions(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        held = query.held_actions()
        assert len(held) == 2
        assert all(h["verification_level"] == "HELD" for h in held)

    def test_held_actions_empty_when_none(self):
        store = MemoryStore()
        store.store_audit_anchor(
            "anc-1",
            _make_anchor(
                "anc-1",
                verification_level="AUTO_APPROVED",
            ),
        )
        query = AuditQuery(store=store)
        held = query.held_actions()
        assert held == []


# ---------------------------------------------------------------------------
# AuditReport
# ---------------------------------------------------------------------------


class TestAuditReport:
    def test_team_summary_contains_agent_counts(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        report = AuditReport(query=query)
        summary = report.team_summary(["agent-1", "agent-2"], days=7)
        assert "agent_counts" in summary
        assert summary["agent_counts"]["agent-1"] >= 1
        assert summary["agent_counts"]["agent-2"] >= 1

    def test_team_summary_contains_total_actions(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        report = AuditReport(query=query)
        summary = report.team_summary(["agent-1", "agent-2"], days=7)
        assert "total_actions" in summary
        assert summary["total_actions"] >= 2

    def test_team_summary_contains_held_count(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        report = AuditReport(query=query)
        summary = report.team_summary(["agent-2"], days=7)
        assert "held_count" in summary

    def test_compliance_check_structure(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        report = AuditReport(query=query)
        check = report.compliance_check(["agent-1", "agent-2"])
        assert "agents_checked" in check
        assert "held_actions_count" in check
        assert "has_unresolved_held" in check

    def test_compliance_check_detects_held_actions(self):
        store = MemoryStore()
        _populate_store(store)
        query = AuditQuery(store=store)
        report = AuditReport(query=query)
        check = report.compliance_check(["agent-2"])
        assert check["held_actions_count"] >= 1
        assert check["has_unresolved_held"] is True

    def test_compliance_check_clean_for_auto_approved_agents(self):
        store = MemoryStore()
        store.store_audit_anchor(
            "anc-1",
            _make_anchor(
                "anc-1",
                "agent-clean",
                "read",
                "AUTO_APPROVED",
            ),
        )
        query = AuditQuery(store=store)
        report = AuditReport(query=query)
        check = report.compliance_check(["agent-clean"])
        assert check["held_actions_count"] == 0
        assert check["has_unresolved_held"] is False


# ---------------------------------------------------------------------------
# AuditQuery requires a store
# ---------------------------------------------------------------------------


class TestAuditQueryRequiresStore:
    def test_raises_without_store(self):
        """AuditQuery must NOT silently default to a MemoryStore.
        Explicit is better than implicit."""
        with pytest.raises(TypeError):
            AuditQuery()
