# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for posture history — append-only store and eligibility checking."""

from datetime import UTC, datetime, timedelta

import pytest

from care_platform.trust.store.posture_history import (
    EligibilityResult,
    PostureChangeRecord,
    PostureChangeTrigger,
    PostureEligibilityChecker,
    PostureHistoryError,
    PostureHistoryStore,
)
from care_platform.trust.reasoning import ReasoningTrace

# ---------------------------------------------------------------------------
# PostureChangeRecord model
# ---------------------------------------------------------------------------


class TestPostureChangeRecord:
    def test_record_has_auto_generated_id(self):
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="admin-1",
        )
        assert record.record_id.startswith("pc-")

    def test_record_stores_all_fields(self):
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="admin-1",
            reason="Performance met threshold",
            evidence_ref="shadow-report-42",
        )
        assert record.agent_id == "agent-1"
        assert record.from_posture == "supervised"
        assert record.to_posture == "shared_planning"
        assert record.direction == "upgrade"
        assert record.trigger == PostureChangeTrigger.REVIEW
        assert record.changed_by == "admin-1"
        assert record.reason == "Performance met threshold"
        assert record.evidence_ref == "shadow-report-42"

    def test_record_has_timestamp(self):
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="admin-1",
        )
        assert record.changed_at is not None

    def test_trigger_enum_values(self):
        assert PostureChangeTrigger.INCIDENT == "incident"
        assert PostureChangeTrigger.REVIEW == "review"
        assert PostureChangeTrigger.SCHEDULED == "scheduled"
        assert PostureChangeTrigger.CASCADE_REVOCATION == "cascade_revocation"


# ---------------------------------------------------------------------------
# PostureHistoryStore — append-only
# ---------------------------------------------------------------------------


class TestPostureHistoryStoreAppend:
    def test_record_change_appends(self):
        store = PostureHistoryStore()
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="admin-1",
        )
        store.record_change(record)
        history = store.get_history("agent-1")
        assert len(history) == 1

    def test_multiple_appends(self):
        store = PostureHistoryStore()
        for _i in range(3):
            record = PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
            )
            store.record_change(record)
        assert len(store.get_history("agent-1")) == 3

    def test_append_only_no_modification(self):
        """History records must never be modified after appending."""
        store = PostureHistoryStore()
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="admin-1",
            reason="Original reason",
        )
        store.record_change(record)
        # Retrieve and confirm original
        history = store.get_history("agent-1")
        assert history[0].reason == "Original reason"

    def test_empty_history_for_unknown_agent(self):
        store = PostureHistoryStore()
        assert store.get_history("unknown") == []

    def test_histories_isolated_per_agent(self):
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
            )
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-2",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
            )
        )
        assert len(store.get_history("agent-1")) == 1
        assert len(store.get_history("agent-2")) == 1


# ---------------------------------------------------------------------------
# PostureHistoryStore — current_posture
# ---------------------------------------------------------------------------


class TestPostureHistoryCurrentPosture:
    def test_current_posture_from_latest_record(self):
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
            )
        )
        assert store.current_posture("agent-1") == "shared_planning"

    def test_current_posture_reflects_latest(self):
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
            )
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="shared_planning",
                to_posture="supervised",
                direction="downgrade",
                trigger=PostureChangeTrigger.INCIDENT,
                changed_by="admin-1",
            )
        )
        assert store.current_posture("agent-1") == "supervised"

    def test_current_posture_raises_for_unknown_agent(self):
        """No silent defaults. Must raise for unknown agents."""
        store = PostureHistoryStore()
        with pytest.raises(KeyError):
            store.current_posture("unknown-agent")


# ---------------------------------------------------------------------------
# PostureHistoryStore — get_duration_at_posture
# ---------------------------------------------------------------------------


class TestPostureHistoryDuration:
    def test_duration_at_single_posture(self):
        store = PostureHistoryStore()
        t1 = datetime(2026, 1, 1, tzinfo=UTC)
        t2 = datetime(2026, 4, 1, tzinfo=UTC)
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="pseudo_agent",
                to_posture="supervised",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=t1,
            )
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=t2,
            )
        )
        duration = store.get_duration_at_posture("agent-1", "supervised")
        assert duration == t2 - t1

    def test_duration_accumulates_across_returns(self):
        """If agent goes supervised -> shared -> supervised, total supervised time accumulates."""
        store = PostureHistoryStore()
        t1 = datetime(2026, 1, 1, tzinfo=UTC)
        t2 = datetime(2026, 4, 1, tzinfo=UTC)
        t3 = datetime(2026, 7, 1, tzinfo=UTC)
        t4 = datetime(2026, 10, 1, tzinfo=UTC)
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="pseudo_agent",
                to_posture="supervised",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=t1,
            )
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=t2,
            )
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="shared_planning",
                to_posture="supervised",
                direction="downgrade",
                trigger=PostureChangeTrigger.INCIDENT,
                changed_by="admin-1",
                changed_at=t3,
            )
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=t4,
            )
        )
        duration = store.get_duration_at_posture("agent-1", "supervised")
        # First stint: t1->t2 = 90 days, second stint: t3->t4 = 92 days
        expected = (t2 - t1) + (t4 - t3)
        assert duration == expected

    def test_duration_zero_for_never_held_posture(self):
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="pseudo_agent",
                to_posture="supervised",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
            )
        )
        duration = store.get_duration_at_posture("agent-1", "delegated")
        assert duration == timedelta(0)

    def test_duration_raises_for_unknown_agent(self):
        store = PostureHistoryStore()
        with pytest.raises(KeyError):
            store.get_duration_at_posture("unknown", "supervised")


# ---------------------------------------------------------------------------
# PostureEligibilityChecker
# ---------------------------------------------------------------------------


class TestPostureEligibilityChecker:
    def _build_eligible_history(self) -> PostureHistoryStore:
        """Build a history where agent-1 has been supervised for 100 days."""
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="pseudo_agent",
                to_posture="supervised",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=datetime.now(UTC) - timedelta(days=100),
            )
        )
        return store

    def test_eligible_for_upgrade(self):
        store = self._build_eligible_history()
        checker = PostureEligibilityChecker(history=store)
        result, reason = checker.check(
            "agent-1",
            "shared_planning",
            shadow_pass_rate=0.95,
            total_operations=200,
        )
        assert result == EligibilityResult.ELIGIBLE

    def test_not_yet_insufficient_time(self):
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="pseudo_agent",
                to_posture="supervised",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=datetime.now(UTC) - timedelta(days=10),
            )
        )
        checker = PostureEligibilityChecker(history=store)
        result, reason = checker.check(
            "agent-1",
            "shared_planning",
            shadow_pass_rate=0.95,
            total_operations=200,
        )
        assert result == EligibilityResult.NOT_YET
        assert "days" in reason.lower() or "time" in reason.lower()

    def test_not_yet_insufficient_operations(self):
        store = self._build_eligible_history()
        checker = PostureEligibilityChecker(history=store)
        result, reason = checker.check(
            "agent-1",
            "shared_planning",
            shadow_pass_rate=0.95,
            total_operations=10,
        )
        assert result == EligibilityResult.NOT_YET
        assert "operation" in reason.lower()

    def test_not_yet_low_shadow_pass_rate(self):
        store = self._build_eligible_history()
        checker = PostureEligibilityChecker(history=store)
        result, reason = checker.check(
            "agent-1",
            "shared_planning",
            shadow_pass_rate=0.50,
            total_operations=200,
        )
        assert result == EligibilityResult.NOT_YET
        assert "shadow" in reason.lower()

    def test_blocked_for_recent_downgrade(self):
        """Agent recently downgraded should be BLOCKED from immediate upgrade."""
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="pseudo_agent",
                to_posture="supervised",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=datetime.now(UTC) - timedelta(days=200),
            )
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=datetime.now(UTC) - timedelta(days=100),
            )
        )
        # Recent downgrade
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="shared_planning",
                to_posture="supervised",
                direction="downgrade",
                trigger=PostureChangeTrigger.INCIDENT,
                changed_by="admin-1",
                changed_at=datetime.now(UTC) - timedelta(days=5),
            )
        )
        checker = PostureEligibilityChecker(history=store)
        result, reason = checker.check(
            "agent-1",
            "shared_planning",
            shadow_pass_rate=0.95,
            total_operations=200,
        )
        assert result == EligibilityResult.BLOCKED
        assert "downgrade" in reason.lower() or "incident" in reason.lower()

    def test_raises_for_unknown_agent(self):
        store = PostureHistoryStore()
        checker = PostureEligibilityChecker(history=store)
        with pytest.raises(KeyError):
            checker.check("unknown", "shared_planning")

    def test_eligibility_result_enum_values(self):
        assert EligibilityResult.ELIGIBLE == "eligible"
        assert EligibilityResult.NOT_YET == "not_yet"
        assert EligibilityResult.BLOCKED == "blocked"


# ---------------------------------------------------------------------------
# Trigger taxonomy — expanded from 4 to 10 types
# ---------------------------------------------------------------------------


class TestTriggerTaxonomy:
    """Test the expanded trigger taxonomy (10 types total)."""

    def test_original_four_triggers_still_work(self):
        """Backward compatibility: existing 4 trigger types are unchanged."""
        assert PostureChangeTrigger.INCIDENT == "incident"
        assert PostureChangeTrigger.REVIEW == "review"
        assert PostureChangeTrigger.SCHEDULED == "scheduled"
        assert PostureChangeTrigger.CASCADE_REVOCATION == "cascade_revocation"

    def test_new_trigger_manual(self):
        assert PostureChangeTrigger.MANUAL == "manual"

    def test_new_trigger_trust_score(self):
        assert PostureChangeTrigger.TRUST_SCORE == "trust_score"

    def test_new_trigger_escalation(self):
        assert PostureChangeTrigger.ESCALATION == "escalation"

    def test_new_trigger_downgrade(self):
        assert PostureChangeTrigger.DOWNGRADE == "downgrade"

    def test_new_trigger_drift(self):
        assert PostureChangeTrigger.DRIFT == "drift"

    def test_new_trigger_approval(self):
        assert PostureChangeTrigger.APPROVAL == "approval"

    def test_total_trigger_count_is_ten(self):
        """Exactly 10 trigger types in the enum."""
        assert len(PostureChangeTrigger) == 10

    def test_all_triggers_usable_in_record(self):
        """Every trigger type can be used to create a PostureChangeRecord."""
        for trigger in PostureChangeTrigger:
            record = PostureChangeRecord(
                agent_id="agent-test",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=trigger,
                changed_by="admin-1",
            )
            assert record.trigger == trigger

    def test_original_triggers_in_existing_eligibility_flow(self):
        """Existing code using original triggers still works end-to-end."""
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="pseudo_agent",
                to_posture="supervised",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
                changed_at=datetime.now(UTC) - timedelta(days=100),
            )
        )
        checker = PostureEligibilityChecker(history=store)
        result, _reason = checker.check(
            "agent-1",
            "shared_planning",
            shadow_pass_rate=0.95,
            total_operations=200,
        )
        assert result == EligibilityResult.ELIGIBLE


# ---------------------------------------------------------------------------
# Reasoning trace storage per transition
# ---------------------------------------------------------------------------


class TestReasoningTraceStorage:
    """Test optional ReasoningTrace attachment to PostureChangeRecord."""

    def test_record_accepts_optional_reasoning_trace(self):
        """PostureChangeRecord can have a reasoning trace attached."""
        trace = ReasoningTrace(
            parent_record_type="posture_change",
            parent_record_id="pc-test",
            decision="Upgrade agent to shared_planning",
            rationale="Agent met all thresholds for 90 days",
            confidence=0.95,
        )
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="admin-1",
            reasoning_trace=trace,
        )
        assert record.reasoning_trace is not None
        assert record.reasoning_trace.decision == "Upgrade agent to shared_planning"
        assert record.reasoning_trace.confidence == 0.95

    def test_record_defaults_to_no_reasoning_trace(self):
        """Without explicit trace, reasoning_trace is None."""
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="admin-1",
        )
        assert record.reasoning_trace is None

    def test_reasoning_trace_retrievable_from_history(self):
        """Reasoning trace survives storage and retrieval in PostureHistoryStore."""
        store = PostureHistoryStore()
        trace = ReasoningTrace(
            parent_record_type="posture_change",
            parent_record_id="pc-trace-test",
            decision="Downgrade due to drift",
            rationale="Behavioral drift exceeded threshold",
            confidence=0.8,
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="shared_planning",
                to_posture="supervised",
                direction="downgrade",
                trigger=PostureChangeTrigger.DRIFT,
                changed_by="admin-1",
                reasoning_trace=trace,
            )
        )
        history = store.get_history("agent-1")
        assert len(history) == 1
        assert history[0].reasoning_trace is not None
        assert history[0].reasoning_trace.decision == "Downgrade due to drift"
        assert history[0].reasoning_trace.rationale == "Behavioral drift exceeded threshold"

    def test_evidence_ref_still_works_alongside_trace(self):
        """evidence_ref (backward compat) and reasoning_trace coexist."""
        trace = ReasoningTrace(
            parent_record_type="posture_change",
            parent_record_id="pc-both",
            decision="Upgrade approved",
            rationale="All criteria met",
        )
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.APPROVAL,
            changed_by="admin-1",
            evidence_ref="shadow-report-99",
            reasoning_trace=trace,
        )
        assert record.evidence_ref == "shadow-report-99"
        assert record.reasoning_trace is not None
        assert record.reasoning_trace.decision == "Upgrade approved"


# ---------------------------------------------------------------------------
# Strict append-only enforcement — sequence numbers + mutation protection
# ---------------------------------------------------------------------------


class TestAppendOnlyEnforcement:
    """Test strict append-only enforcement with sequence numbers and mutation protection."""

    def test_sequence_numbers_assigned_on_record(self):
        """Each record gets a monotonically increasing sequence number."""
        store = PostureHistoryStore()
        for i in range(5):
            store.record_change(
                PostureChangeRecord(
                    agent_id="agent-1",
                    from_posture="supervised",
                    to_posture="shared_planning",
                    direction="upgrade",
                    trigger=PostureChangeTrigger.REVIEW,
                    changed_by="admin-1",
                )
            )
        history = store.get_history("agent-1")
        for i, record in enumerate(history):
            assert record.sequence_number == i + 1

    def test_sequence_numbers_monotonically_increasing(self):
        """Sequence numbers are strictly increasing across agents."""
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
            )
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-2",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
            )
        )
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="shared_planning",
                to_posture="supervised",
                direction="downgrade",
                trigger=PostureChangeTrigger.INCIDENT,
                changed_by="admin-1",
            )
        )
        # Global sequence: 1, 2, 3 across all agents
        h1 = store.get_history("agent-1")
        h2 = store.get_history("agent-2")
        assert h1[0].sequence_number == 1
        assert h2[0].sequence_number == 2
        assert h1[1].sequence_number == 3

    def test_sequence_number_defaults_to_none_before_storage(self):
        """Before being stored, sequence_number is None."""
        record = PostureChangeRecord(
            agent_id="agent-1",
            from_posture="supervised",
            to_posture="shared_planning",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="admin-1",
        )
        assert record.sequence_number is None

    def test_direct_records_mutation_raises_error(self):
        """Direct assignment to _records after init raises PostureHistoryError."""
        store = PostureHistoryStore()
        store.record_change(
            PostureChangeRecord(
                agent_id="agent-1",
                from_posture="supervised",
                to_posture="shared_planning",
                direction="upgrade",
                trigger=PostureChangeTrigger.REVIEW,
                changed_by="admin-1",
            )
        )
        with pytest.raises(PostureHistoryError, match="_records"):
            store._records = {}

    def test_direct_records_mutation_raises_after_multiple_appends(self):
        """Mutation protection works regardless of how many records exist."""
        store = PostureHistoryStore()
        for _ in range(3):
            store.record_change(
                PostureChangeRecord(
                    agent_id="agent-1",
                    from_posture="supervised",
                    to_posture="shared_planning",
                    direction="upgrade",
                    trigger=PostureChangeTrigger.REVIEW,
                    changed_by="admin-1",
                )
            )
        with pytest.raises(PostureHistoryError):
            store._records = {"agent-1": []}

    def test_posture_history_error_is_exception(self):
        """PostureHistoryError is a proper exception class."""
        assert issubclass(PostureHistoryError, Exception)
        error = PostureHistoryError("test message")
        assert str(error) == "test message"
