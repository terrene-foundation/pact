# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Integration tests for the full persistence stack (Milestone 3, Todo 307).

Tests the persistence layer end-to-end:
- Trust object round-trip through MemoryStore
- Audit chain integrity after store/retrieve
- Posture history append-only semantics
- Audit query interface correctness
- API cost tracking with budget enforcement
- Envelope versioning and diffing
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pact_platform.build.config.schema import VerificationLevel
from pact_platform.trust.audit.anchor import AuditChain
from pact_platform.trust.store.audit_query import AuditQuery, AuditReport
from pact_platform.trust.store.cost_tracking import ApiCostRecord, CostTracker
from pact_platform.trust.store.posture_history import (
    EligibilityResult,
    PostureChangeRecord,
    PostureChangeTrigger,
    PostureEligibilityChecker,
    PostureHistoryStore,
)
from pact_platform.trust.store.store import MemoryStore
from pact_platform.trust.store.versioning import VersionTracker

# ===========================================================================
# 1. Trust Object Round-Trip Through Store
# ===========================================================================


class TestTrustObjectRoundTrip:
    """Store trust chain -> retrieve -> verify integrity."""

    def test_store_and_retrieve_envelope(self):
        """Create envelope data, persist, retrieve, and verify identical."""
        store = MemoryStore()

        envelope_data = {
            "id": "env-test-1",
            "description": "Test envelope",
            "financial": {"max_spend_usd": 500.0},
            "operational": {"allowed_actions": ["read", "write"]},
            "agent_id": "agent-1",
        }

        store.store_envelope("env-test-1", envelope_data)
        retrieved = store.get_envelope("env-test-1")

        assert retrieved is not None
        assert retrieved == envelope_data
        assert retrieved["financial"]["max_spend_usd"] == 500.0
        assert retrieved["operational"]["allowed_actions"] == ["read", "write"]

    def test_store_and_retrieve_audit_anchor(self):
        """Create audit anchor, persist, retrieve, verify."""
        store = MemoryStore()

        anchor_data = {
            "anchor_id": "anc-1",
            "agent_id": "agent-1",
            "action": "read_metrics",
            "verification_level": "AUTO_APPROVED",
            "timestamp": datetime.now(UTC).isoformat(),
            "content_hash": "abc123",
        }

        store.store_audit_anchor("anc-1", anchor_data)
        retrieved = store.get_audit_anchor("anc-1")

        assert retrieved is not None
        assert retrieved == anchor_data

    def test_store_delegation_chain_3_hops(self):
        """Persist a 3-hop delegation chain and verify all records survive."""
        store = MemoryStore()

        chain_records = [
            {"id": "genesis-1", "type": "genesis", "authority": "terrene.foundation"},
            {"id": "del-1", "type": "delegation", "from": "genesis-1", "to": "team-lead"},
            {"id": "del-2", "type": "delegation", "from": "team-lead", "to": "specialist"},
        ]

        for i, record in enumerate(chain_records):
            store.store_envelope(f"chain-{i}", record)

        # Verify all 3 records retrieved
        for i, expected in enumerate(chain_records):
            retrieved = store.get_envelope(f"chain-{i}")
            assert retrieved is not None
            assert retrieved == expected

    def test_list_envelopes_by_agent(self):
        """Filter envelopes by agent_id."""
        store = MemoryStore()

        store.store_envelope("env-a1", {"id": "env-a1", "agent_id": "agent-1"})
        store.store_envelope("env-a2", {"id": "env-a2", "agent_id": "agent-1"})
        store.store_envelope("env-b1", {"id": "env-b1", "agent_id": "agent-2"})

        agent_1_envelopes = store.list_envelopes(agent_id="agent-1")
        assert len(agent_1_envelopes) == 2
        assert all(e["agent_id"] == "agent-1" for e in agent_1_envelopes)

    def test_store_empty_envelope_id_raises(self):
        """Storing with empty envelope_id raises ValueError."""
        store = MemoryStore()
        with pytest.raises(ValueError, match="must not be empty"):
            store.store_envelope("", {"data": "test"})


# ===========================================================================
# 2. Audit Chain Integrity After Persist/Reload
# ===========================================================================


class TestAuditChainIntegrityAfterPersist:
    """Create audit anchors, persist to store, reload, verify integrity."""

    def test_audit_chain_persists_and_verifies(self):
        """Create 10 anchors, persist, reload, verify chain links."""
        store = MemoryStore()
        chain = AuditChain(chain_id="persist-chain")

        # Create 10 linked anchors
        for i in range(10):
            anchor = chain.append(
                agent_id=f"agent-{i % 3}",
                action=f"action_{i}",
                verification_level=VerificationLevel.AUTO_APPROVED,
                result=f"result_{i}",
            )
            # Persist each anchor
            store.store_audit_anchor(
                f"anchor-{i}",
                {
                    "anchor_id": f"anchor-{i}",
                    "sequence": anchor.sequence,
                    "agent_id": anchor.agent_id,
                    "action": anchor.action,
                    "verification_level": anchor.verification_level.value,
                    "content_hash": anchor.content_hash,
                    "previous_hash": anchor.previous_hash,
                    "timestamp": anchor.timestamp.isoformat(),
                },
            )

        # Verify the in-memory chain is intact
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"
        assert chain.length == 10

        # Verify all persisted anchors can be retrieved
        for i in range(10):
            retrieved = store.get_audit_anchor(f"anchor-{i}")
            assert retrieved is not None
            assert retrieved["sequence"] == i
            if i > 0:
                # Verify chain link via previous_hash
                prev = store.get_audit_anchor(f"anchor-{i - 1}")
                assert retrieved["previous_hash"] == prev["content_hash"]

    def test_tampered_anchor_hash_detected(self):
        """Deliberately corrupt one anchor hash -> integrity check detects it."""
        chain = AuditChain(chain_id="tamper-chain")

        for i in range(5):
            chain.append(
                agent_id="agent-1",
                action=f"action_{i}",
                verification_level=VerificationLevel.AUTO_APPROVED,
            )

        # Tamper with anchor 2's action (changes its actual content but not stored hash)
        chain.anchors[2].action = "TAMPERED_ACTION"

        is_valid, errors = chain.verify_chain_integrity()
        assert not is_valid
        assert len(errors) >= 1

    def test_gap_in_chain_detected(self):
        """A chain with a modified previous_hash creates a linkage gap."""
        chain = AuditChain(chain_id="gap-chain")

        for i in range(4):
            chain.append(
                agent_id="agent-1",
                action=f"action_{i}",
                verification_level=VerificationLevel.AUTO_APPROVED,
            )

        # Break the link between anchor 1 and anchor 2
        chain.anchors[2].previous_hash = "fake-hash-that-does-not-match"
        chain.anchors[2].seal()  # re-seal with broken linkage

        is_valid, errors = chain.verify_chain_integrity()
        assert not is_valid


# ===========================================================================
# 3. Posture History Accuracy
# ===========================================================================


class TestPostureHistoryAccuracy:
    """Posture history: append-only, ordered, current_posture correct."""

    def test_three_posture_changes_ordered(self):
        """Record 3 posture changes and verify they return in order."""
        history = PostureHistoryStore()

        changes = [
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="authority-1",
                reason="Earned trust",
            ),
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="shared_planning",
                to_posture="supervised",
                direction="downgrade",
                trigger=PostureChangeTrigger.INCIDENT,
                changed_by="authority-1",
                reason="Security incident",
            ),
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="authority-1",
                reason="Recovered trust",
            ),
        ]

        for change in changes:
            history.record_change(change)

        records = history.get_history("agent-1")
        assert len(records) == 3
        assert records[0].to_posture == "shared_planning"
        assert records[1].to_posture == "supervised"
        assert records[2].to_posture == "shared_planning"

    def test_current_posture_reflects_latest(self):
        """current_posture returns the to_posture of the latest record."""
        history = PostureHistoryStore()

        history.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="authority-1",
            )
        )

        assert history.current_posture("agent-1") == "shared_planning"

        history.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="shared_planning",
                to_posture="supervised",
                direction="downgrade",
                trigger=PostureChangeTrigger.INCIDENT,
                changed_by="authority-1",
            )
        )

        assert history.current_posture("agent-1") == "supervised"

    def test_unknown_agent_raises_key_error(self):
        """current_posture for unknown agent raises KeyError, not silent default."""
        history = PostureHistoryStore()
        with pytest.raises(KeyError, match="No posture history found"):
            history.current_posture("unknown-agent")

    def test_append_only_semantics(self):
        """Records can only be appended, never replaced or removed via the API."""
        history = PostureHistoryStore()

        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="authority-1",
        )
        history.record_change(record)

        # Appending another record does not remove the first
        record2 = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="shared_planning",
            to_posture="supervised",
            direction="downgrade",
            trigger=PostureChangeTrigger.INCIDENT,
            changed_by="authority-1",
        )
        history.record_change(record2)

        records = history.get_history("agent-1")
        assert len(records) == 2
        # Original record is still present and unchanged
        assert records[0].to_posture == "shared_planning"
        assert records[0].direction == "upgrade"


# ===========================================================================
# 4. Audit Query Interface Correctness
# ===========================================================================


class TestAuditQueryInterface:
    """Insert varied anchors, query by agent/time/level, verify correct subsets."""

    def _populate_store(self, store: MemoryStore) -> list[dict]:
        """Insert 50 audit anchors with varied agents, times, and levels."""
        anchors = []
        agents = ["agent-alpha", "agent-beta", "agent-gamma"]
        levels = ["AUTO_APPROVED", "FLAGGED", "HELD", "BLOCKED"]
        actions = ["read", "write", "delete", "draft", "send"]

        base_time = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

        for i in range(50):
            anchor = {
                "anchor_id": f"anc-{i}",
                "agent_id": agents[i % len(agents)],
                "action": actions[i % len(actions)],
                "verification_level": levels[i % len(levels)],
                "timestamp": (base_time + timedelta(hours=i)).isoformat(),
                "result": "success" if i % 3 != 0 else "denied",
            }
            store.store_audit_anchor(f"anc-{i}", anchor)
            anchors.append(anchor)

        return anchors

    def test_query_by_agent(self):
        """Query by agent returns only that agent's anchors."""
        store = MemoryStore()
        self._populate_store(store)
        query = AuditQuery(store=store)

        alpha_results = query.by_agent("agent-alpha")
        assert len(alpha_results) > 0
        assert all(a["agent_id"] == "agent-alpha" for a in alpha_results)

    def test_query_by_time_range(self):
        """Query by time range returns anchors within the window."""
        store = MemoryStore()
        self._populate_store(store)
        query = AuditQuery(store=store)

        start = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        end = datetime(2026, 3, 1, 22, 0, tzinfo=UTC)  # 10-hour window

        results = query.by_time_range(start, end, limit=100)
        assert len(results) > 0
        # All results should be within the window
        for r in results:
            ts = datetime.fromisoformat(r["timestamp"])
            assert start <= ts <= end

    def test_query_by_verification_level_held(self):
        """Query by HELD level returns only held actions."""
        store = MemoryStore()
        self._populate_store(store)
        query = AuditQuery(store=store)

        held = query.by_verification_level("HELD")
        assert len(held) > 0
        assert all(a["verification_level"] == "HELD" for a in held)

    def test_compound_query_agent_and_time(self):
        """Compound query: agent + time range returns intersection."""
        store = MemoryStore()
        self._populate_store(store)
        query = AuditQuery(store=store)

        start = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        end = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)

        results = query.filter(
            agent_id="agent-beta",
            since=start,
            until=end,
            limit=100,
        )

        for r in results:
            assert r["agent_id"] == "agent-beta"
            ts = datetime.fromisoformat(r["timestamp"])
            assert start <= ts <= end

    def test_aggregate_by_agent(self):
        """Aggregate action counts per agent are correct."""
        store = MemoryStore()
        self._populate_store(store)
        query = AuditQuery(store=store)

        counts = query.aggregate_by_agent()
        # 50 anchors spread across 3 agents: ~16-17 each
        total = sum(counts.values())
        assert total == 50
        assert "agent-alpha" in counts
        assert "agent-beta" in counts
        assert "agent-gamma" in counts

    def test_team_summary_report(self):
        """Team summary report returns correct totals."""
        store = MemoryStore()
        self._populate_store(store)
        query = AuditQuery(store=store)
        report = AuditReport(query)

        summary = report.team_summary(
            agent_ids=["agent-alpha", "agent-beta"],
            days=30,
        )

        assert "agent_counts" in summary
        assert "total_actions" in summary
        assert "held_count" in summary
        assert summary["total_actions"] > 0

    def test_compliance_check(self):
        """Compliance check returns held actions count."""
        store = MemoryStore()
        self._populate_store(store)
        query = AuditQuery(store=store)
        report = AuditReport(query)

        compliance = report.compliance_check(
            agent_ids=["agent-alpha", "agent-beta", "agent-gamma"],
        )

        assert "held_actions_count" in compliance
        assert "has_unresolved_held" in compliance
        assert isinstance(compliance["has_unresolved_held"], bool)


# ===========================================================================
# 5. API Cost Tracking with Budget Enforcement
# ===========================================================================


class TestCostTrackingBudgetEnforcement:
    """Track costs -> check budget alerts -> verify reports."""

    def test_warning_at_80_percent(self):
        """Recording 90% of daily budget triggers a warning alert."""
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("100"))

        # Record $90 in spending (90% of $100)
        record = ApiCostRecord(
            agent_id="agent-1",
            team_id="team-dm",
            provider="anthropic",
            model="claude-opus-4-6",
            cost_usd=Decimal("90"),
        )
        alerts = tracker.record(record)

        # Should trigger warning (>= 80%)
        assert len(alerts) >= 1
        warning_alerts = [a for a in alerts if a.alert_type == "warning"]
        assert len(warning_alerts) == 1
        assert warning_alerts[0].percentage >= 80.0

    def test_budget_exceeded_triggers_limit_reached(self):
        """Recording cost that exceeds budget triggers limit_reached alert."""
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("100"))

        # Record $100 (exactly at limit)
        record = ApiCostRecord(
            agent_id="agent-1",
            cost_usd=Decimal("100"),
        )
        alerts = tracker.record(record)

        limit_alerts = [a for a in alerts if a.alert_type == "limit_reached"]
        assert len(limit_alerts) == 1

    def test_can_spend_blocks_overspend(self):
        """Pre-flight check blocks call that would exceed budget."""
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("100"))

        # Record $80 in spending
        tracker.record(ApiCostRecord(agent_id="agent-1", cost_usd=Decimal("80")))

        # Try to spend $30 more (would total $110)
        allowed, reason = tracker.can_spend("agent-1", Decimal("30"))
        assert not allowed
        assert "exceed" in reason.lower()

    def test_can_spend_allows_within_budget(self):
        """Pre-flight check allows call within budget."""
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("100"))

        tracker.record(ApiCostRecord(agent_id="agent-1", cost_usd=Decimal("50")))

        allowed, reason = tracker.can_spend("agent-1", Decimal("30"))
        assert allowed

    def test_spend_report_correct_totals(self):
        """Spend report returns correct totals by agent and model."""
        tracker = CostTracker()

        records = [
            ApiCostRecord(agent_id="agent-1", model="claude-opus-4-6", cost_usd=Decimal("10")),
            ApiCostRecord(agent_id="agent-1", model="claude-opus-4-6", cost_usd=Decimal("20")),
            ApiCostRecord(agent_id="agent-2", model="gpt-4", cost_usd=Decimal("15")),
        ]
        for r in records:
            tracker.record(r)

        report = tracker.spend_report(days=30)

        assert report.total_cost == Decimal("45")
        assert report.by_agent["agent-1"] == Decimal("30")
        assert report.by_agent["agent-2"] == Decimal("15")
        assert report.by_model["claude-opus-4-6"] == Decimal("30")
        assert report.by_model["gpt-4"] == Decimal("15")
        assert report.total_calls == 3

    def test_team_monthly_budget_alert(self):
        """Team monthly budget triggers team_warning at 90%."""
        tracker = CostTracker()
        tracker.set_team_monthly_budget("team-dm", Decimal("1000"))

        # Record $950 for the team (95%)
        record = ApiCostRecord(
            agent_id="agent-1",
            team_id="team-dm",
            cost_usd=Decimal("950"),
        )
        alerts = tracker.record(record)

        team_alerts = [a for a in alerts if a.alert_type == "team_warning"]
        assert len(team_alerts) == 1

    def test_negative_budget_raises(self):
        """Setting a negative budget raises ValueError."""
        tracker = CostTracker()
        with pytest.raises(ValueError, match="non-negative"):
            tracker.set_daily_budget("agent-1", Decimal("-10"))


# ===========================================================================
# 6. Envelope Versioning and Diffing
# ===========================================================================


class TestEnvelopeVersioning:
    """Version an envelope -> retrieve history -> verify diffs."""

    def test_version_recording_and_history(self):
        """Record 3 versions and verify history is complete."""
        vt = VersionTracker()

        v1 = vt.record_version(
            "env-1",
            {"financial": {"max_spend_usd": 500}},
            created_by="admin",
            reason="Initial",
        )
        v2 = vt.record_version(
            "env-1",
            {"financial": {"max_spend_usd": 300}},
            created_by="admin",
            reason="Tightened budget",
        )
        v3 = vt.record_version(
            "env-1",
            {"financial": {"max_spend_usd": 300}, "operational": {"max_actions_per_day": 50}},
            created_by="admin",
            reason="Added rate limit",
        )

        history = vt.get_history("env-1")
        assert len(history) == 3
        assert history[0].version == 1
        assert history[1].version == 2
        assert history[2].version == 3

    def test_version_hash_chaining(self):
        """Each version's previous_version_hash chains to the prior version."""
        vt = VersionTracker()

        v1 = vt.record_version("env-1", {"data": "v1"}, created_by="admin")
        v2 = vt.record_version("env-1", {"data": "v2"}, created_by="admin")
        v3 = vt.record_version("env-1", {"data": "v3"}, created_by="admin")

        assert v1.previous_version_hash is None  # first version
        assert v2.previous_version_hash == v1.content_hash
        assert v3.previous_version_hash == v2.content_hash

    def test_diff_between_versions(self):
        """Diff between two versions returns correct field-level changes."""
        vt = VersionTracker()

        vt.record_version(
            "env-1",
            {"financial": {"max_spend_usd": 500, "api_cost_budget_usd": 100}},
            created_by="admin",
        )
        vt.record_version(
            "env-1",
            {"financial": {"max_spend_usd": 300, "api_cost_budget_usd": 100}},
            created_by="admin",
        )

        diffs = vt.compute_diff("env-1", 1, 2)
        assert len(diffs) == 1
        assert diffs[0].dimension == "financial"
        assert diffs[0].field == "max_spend_usd"
        assert diffs[0].old_value == "500"
        assert diffs[0].new_value == "300"

    def test_get_current_version(self):
        """get_current returns the latest version."""
        vt = VersionTracker()

        vt.record_version("env-1", {"v": 1}, created_by="admin")
        vt.record_version("env-1", {"v": 2}, created_by="admin")

        current = vt.get_current("env-1")
        assert current is not None
        assert current.version == 2

    def test_diff_nonexistent_envelope_raises(self):
        """Diffing a nonexistent envelope raises KeyError."""
        vt = VersionTracker()
        with pytest.raises(KeyError, match="No versions found"):
            vt.compute_diff("nonexistent", 1, 2)

    def test_diff_nonexistent_version_raises(self):
        """Diffing with a nonexistent version number raises KeyError."""
        vt = VersionTracker()
        vt.record_version("env-1", {"v": 1}, created_by="admin")

        with pytest.raises(KeyError, match="Version 5 not found"):
            vt.compute_diff("env-1", 1, 5)


# ===========================================================================
# 7. Posture Eligibility Checking
# ===========================================================================


class TestPostureEligibilityChecking:
    """Verify eligibility checker uses posture history correctly."""

    def test_eligible_after_sufficient_time_and_operations(self):
        """Agent with enough time and operations at current posture is eligible."""
        history = PostureHistoryStore()

        # Record initial posture change (long ago)
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="pseudo_agent",
            to_posture="supervised",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="authority-1",
            changed_at=datetime.now(UTC) - timedelta(days=100),
        )
        history.record_change(record)

        checker = PostureEligibilityChecker(history)
        result, reason = checker.check(
            agent_id="agent-1",
            target_posture="shared_planning",
            shadow_pass_rate=0.95,
            total_operations=150,
        )

        assert result == EligibilityResult.ELIGIBLE

    def test_not_yet_insufficient_operations(self):
        """Agent with insufficient operations is not yet eligible."""
        history = PostureHistoryStore()

        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="pseudo_agent",
            to_posture="supervised",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="authority-1",
            changed_at=datetime.now(UTC) - timedelta(days=100),
        )
        history.record_change(record)

        checker = PostureEligibilityChecker(history)
        result, reason = checker.check(
            agent_id="agent-1",
            target_posture="shared_planning",
            shadow_pass_rate=0.95,
            total_operations=10,  # Not enough
        )

        assert result == EligibilityResult.NOT_YET
