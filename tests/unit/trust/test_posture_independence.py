# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for posture change independence validation (PACT spec Section 12.9.4).

Covers:
- Self-upgrade blocked (changed_by == agent_id for upgrade direction)
- Self-downgrade allowed (operators can downgrade themselves)
- Upgrade by independent assessor succeeds
- Custom validator called on upgrade, not on downgrade
- Validator error propagates as PostureHistoryError
- Default validator function (validate_posture_independence)
- Backwards compatibility (no validator set = old behavior)
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pact_platform.trust.store.posture_history import (
    PostureChangeRecord,
    PostureChangeTrigger,
    PostureHistoryError,
    PostureHistoryStore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_upgrade_record(
    agent_id: str = "agent-001",
    changed_by: str = "assessor-002",
    from_posture: str = "supervised",
    to_posture: str = "shared_planning",
) -> PostureChangeRecord:
    """Build an upgrade posture change record."""
    return PostureChangeRecord(
        agent_id=agent_id,
        from_posture=from_posture,
        to_posture=to_posture,
        direction="upgrade",
        trigger=PostureChangeTrigger.REVIEW,
        changed_by=changed_by,
        changed_at=datetime.now(UTC),
        reason="Meets upgrade criteria",
    )


def _make_downgrade_record(
    agent_id: str = "agent-001",
    changed_by: str = "agent-001",
    from_posture: str = "shared_planning",
    to_posture: str = "supervised",
) -> PostureChangeRecord:
    """Build a downgrade posture change record."""
    return PostureChangeRecord(
        agent_id=agent_id,
        from_posture=from_posture,
        to_posture=to_posture,
        direction="downgrade",
        trigger=PostureChangeTrigger.INCIDENT,
        changed_by=changed_by,
        changed_at=datetime.now(UTC),
        reason="Incident detected",
    )


# ---------------------------------------------------------------------------
# Test: Self-upgrade blocked
# ---------------------------------------------------------------------------


class TestSelfUpgradeBlocked:
    """PACT spec 12.9.4: An agent cannot upgrade its own posture."""

    def test_self_upgrade_raises_error(self) -> None:
        """changed_by == agent_id on upgrade MUST raise PostureHistoryError."""
        store = PostureHistoryStore()
        record = _make_upgrade_record(agent_id="agent-001", changed_by="agent-001")

        with pytest.raises(PostureHistoryError, match="self-assessment"):
            store.record_change(record)

    def test_self_upgrade_not_stored(self) -> None:
        """A rejected self-upgrade MUST NOT be stored in history."""
        store = PostureHistoryStore()
        record = _make_upgrade_record(agent_id="agent-001", changed_by="agent-001")

        with pytest.raises(PostureHistoryError):
            store.record_change(record)

        # History must be empty - the invalid record was not persisted
        assert store.get_history("agent-001") == []

    def test_self_upgrade_case_sensitivity(self) -> None:
        """Self-upgrade check must be exact string match (case-sensitive)."""
        store = PostureHistoryStore()
        # Different case is a different identity
        record = _make_upgrade_record(agent_id="agent-001", changed_by="Agent-001")

        # Should succeed -- they are different strings
        store.record_change(record)
        history = store.get_history("agent-001")
        assert len(history) == 1


# ---------------------------------------------------------------------------
# Test: Self-downgrade allowed
# ---------------------------------------------------------------------------


class TestSelfDowngradeAllowed:
    """Operators can downgrade their own posture (incident response, voluntary)."""

    def test_self_downgrade_succeeds(self) -> None:
        """changed_by == agent_id on downgrade is permitted."""
        store = PostureHistoryStore()
        record = _make_downgrade_record(agent_id="agent-001", changed_by="agent-001")

        store.record_change(record)
        history = store.get_history("agent-001")
        assert len(history) == 1
        assert history[0].direction == "downgrade"

    def test_self_incident_downgrade_succeeds(self) -> None:
        """Self-downgrade via incident trigger is allowed."""
        store = PostureHistoryStore()
        record = PostureChangeRecord(
            agent_id="agent-001",
            from_posture="shared_planning",
            to_posture="supervised",
            direction="downgrade",
            trigger=PostureChangeTrigger.INCIDENT,
            changed_by="agent-001",
            changed_at=datetime.now(UTC),
            reason="Self-detected anomaly",
        )
        store.record_change(record)
        assert store.current_posture("agent-001") == "supervised"


# ---------------------------------------------------------------------------
# Test: Independent upgrade succeeds
# ---------------------------------------------------------------------------


class TestIndependentUpgradeSucceeds:
    """Upgrade by a different assessor is valid."""

    def test_upgrade_by_different_agent(self) -> None:
        """changed_by != agent_id on upgrade succeeds normally."""
        store = PostureHistoryStore()
        record = _make_upgrade_record(agent_id="agent-001", changed_by="assessor-002")

        store.record_change(record)
        history = store.get_history("agent-001")
        assert len(history) == 1
        assert history[0].to_posture == "shared_planning"

    def test_upgrade_by_compliance_role(self) -> None:
        """Upgrade by a compliance role succeeds."""
        store = PostureHistoryStore()
        record = _make_upgrade_record(
            agent_id="agent-001",
            changed_by="compliance-officer-01",
        )
        store.record_change(record)
        assert store.current_posture("agent-001") == "shared_planning"

    def test_upgrade_preserves_sequence_number(self) -> None:
        """Independent upgrade gets a proper sequence number."""
        store = PostureHistoryStore()
        record = _make_upgrade_record(agent_id="agent-001", changed_by="assessor-002")

        store.record_change(record)
        history = store.get_history("agent-001")
        assert history[0].sequence_number == 1


# ---------------------------------------------------------------------------
# Test: Custom validator
# ---------------------------------------------------------------------------


class TestCustomAssessorValidator:
    """Custom validator is called on upgrades, not on downgrades."""

    def test_validator_called_on_upgrade(self) -> None:
        """When set, the assessor validator is invoked for upgrade records."""
        call_log: list[tuple[str, str, str]] = []

        def tracking_validator(agent_id: str, changed_by: str, direction: str) -> None:
            call_log.append((agent_id, changed_by, direction))

        store = PostureHistoryStore()
        store.set_assessor_validator(tracking_validator)

        record = _make_upgrade_record(agent_id="agent-001", changed_by="assessor-002")
        store.record_change(record)

        assert len(call_log) == 1
        assert call_log[0] == ("agent-001", "assessor-002", "upgrade")

    def test_validator_not_called_on_downgrade(self) -> None:
        """Validator is NOT invoked for downgrade records."""
        call_log: list[tuple[str, str, str]] = []

        def tracking_validator(agent_id: str, changed_by: str, direction: str) -> None:
            call_log.append((agent_id, changed_by, direction))

        store = PostureHistoryStore()
        store.set_assessor_validator(tracking_validator)

        record = _make_downgrade_record(agent_id="agent-001", changed_by="supervisor-001")
        store.record_change(record)

        assert len(call_log) == 0

    def test_validator_error_raises_posture_history_error(self) -> None:
        """Validator that raises propagates as PostureHistoryError."""

        def blocking_validator(agent_id: str, changed_by: str, direction: str) -> None:
            raise PostureHistoryError(
                f"Assessor '{changed_by}' is agent's direct supervisor "
                f"-- conflict of interest for upgrade of '{agent_id}'"
            )

        store = PostureHistoryStore()
        store.set_assessor_validator(blocking_validator)

        record = _make_upgrade_record(agent_id="agent-001", changed_by="supervisor-001")

        with pytest.raises(PostureHistoryError, match="conflict of interest"):
            store.record_change(record)

    def test_validator_generic_exception_wrapped(self) -> None:
        """Non-PostureHistoryError from validator is wrapped in PostureHistoryError."""

        def buggy_validator(agent_id: str, changed_by: str, direction: str) -> None:
            raise ValueError("unexpected validation error")

        store = PostureHistoryStore()
        store.set_assessor_validator(buggy_validator)

        record = _make_upgrade_record(agent_id="agent-001", changed_by="assessor-002")

        with pytest.raises(PostureHistoryError, match="Assessor validation failed"):
            store.record_change(record)

    def test_validator_error_does_not_store_record(self) -> None:
        """When validator raises, the record must NOT be persisted."""

        def blocking_validator(agent_id: str, changed_by: str, direction: str) -> None:
            raise PostureHistoryError("blocked by validator")

        store = PostureHistoryStore()
        store.set_assessor_validator(blocking_validator)

        record = _make_upgrade_record(agent_id="agent-001", changed_by="supervisor-001")

        with pytest.raises(PostureHistoryError):
            store.record_change(record)

        assert store.get_history("agent-001") == []


# ---------------------------------------------------------------------------
# Test: Default validator function
# ---------------------------------------------------------------------------


class TestDefaultValidatePostureIndependence:
    """Tests for the standalone validate_posture_independence function."""

    def test_self_assessment_blocked(self) -> None:
        """changed_by == agent_id raises PostureHistoryError."""
        from pact_platform.trust.store.posture_history import (
            validate_posture_independence,
        )

        with pytest.raises(PostureHistoryError, match="self-assessment"):
            validate_posture_independence("agent-001", "agent-001", "upgrade")

    def test_independent_assessor_passes(self) -> None:
        """changed_by != agent_id does not raise."""
        from pact_platform.trust.store.posture_history import (
            validate_posture_independence,
        )

        # Should not raise
        validate_posture_independence("agent-001", "assessor-002", "upgrade")

    def test_downgrade_self_allowed(self) -> None:
        """Downgrades by self are allowed in the default validator."""
        from pact_platform.trust.store.posture_history import (
            validate_posture_independence,
        )

        # Should not raise even though changed_by == agent_id
        validate_posture_independence("agent-001", "agent-001", "downgrade")


# ---------------------------------------------------------------------------
# Test: Backwards compatibility
# ---------------------------------------------------------------------------


class TestBackwardsCompatibility:
    """No validator set = old behavior (only self-upgrade check applies)."""

    def test_no_validator_upgrade_by_other_succeeds(self) -> None:
        """Without a validator set, upgrades by non-self assessors succeed."""
        store = PostureHistoryStore()
        record = _make_upgrade_record(agent_id="agent-001", changed_by="assessor-002")

        store.record_change(record)
        assert len(store.get_history("agent-001")) == 1

    def test_no_validator_self_upgrade_still_blocked(self) -> None:
        """The built-in self-upgrade check applies even without a custom validator."""
        store = PostureHistoryStore()
        record = _make_upgrade_record(agent_id="agent-001", changed_by="agent-001")

        with pytest.raises(PostureHistoryError, match="self-assessment"):
            store.record_change(record)

    def test_no_validator_downgrade_by_self_allowed(self) -> None:
        """Self-downgrades are allowed without a validator."""
        store = PostureHistoryStore()
        record = _make_downgrade_record(agent_id="agent-001", changed_by="agent-001")

        store.record_change(record)
        assert len(store.get_history("agent-001")) == 1

    def test_append_only_invariant_preserved(self) -> None:
        """The append-only _records guard still works with new validation."""
        store = PostureHistoryStore()
        with pytest.raises(PostureHistoryError, match="Direct reassignment"):
            store._records = {}  # type: ignore[misc]

    def test_sequence_number_incremented_correctly(self) -> None:
        """Sequence numbers are monotonic across mixed upgrade/downgrade ops."""
        store = PostureHistoryStore()

        r1 = _make_upgrade_record(agent_id="agent-001", changed_by="assessor-002")
        store.record_change(r1)

        r2 = _make_downgrade_record(agent_id="agent-001", changed_by="agent-001")
        store.record_change(r2)

        r3 = _make_upgrade_record(
            agent_id="agent-001",
            changed_by="assessor-003",
            from_posture="supervised",
            to_posture="shared_planning",
        )
        store.record_change(r3)

        history = store.get_history("agent-001")
        assert [r.sequence_number for r in history] == [1, 2, 3]
