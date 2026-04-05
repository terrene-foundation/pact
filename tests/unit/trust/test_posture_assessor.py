# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for D/T/R-based posture assessor validation.

Validates that the D/T/R-aware assessor validator correctly:
- Blocks direct supervisors from assessing their subordinates (COI)
- Allows compliance roles regardless of hierarchy position
- Allows ancestors 2+ governance levels up
- Allows peer supervisors from different branches
- Skips validation for downgrades
- Fails closed on unparseable addresses
"""

from __future__ import annotations

import pytest

from pact_platform.trust.posture_assessor import (
    create_dtr_assessor_validator,
    wire_assessor_validator,
)
from pact_platform.trust.store.posture_history import (
    PostureChangeRecord,
    PostureChangeTrigger,
    PostureHistoryError,
    PostureHistoryStore,
)


class _MockEngine:
    """Minimal mock engine for assessor testing.

    Unit tests (Tier 1) -- mocking is permitted per testing rules.
    This mock provides the minimum interface the validator needs.
    """

    def __init__(self) -> None:
        pass

    def get_org(self):  # noqa: ANN201
        return None


class TestDTRAssessorValidator:
    """Test the D/T/R assessor validator logic."""

    def test_self_upgrade_blocked_by_builtin(self) -> None:
        """Self-upgrade is blocked by the built-in check, not the DTR validator.

        The PostureHistoryStore has a built-in self-upgrade check that
        runs before the custom validator. This test verifies that the
        built-in check fires first with the correct error message.
        """
        store = PostureHistoryStore()
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)
        store.set_assessor_validator(validator)

        record = PostureChangeRecord(
            agent_id="D1-R1-T1-R1",
            from_posture="supervised",
            to_posture="guided",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="D1-R1-T1-R1",
        )
        with pytest.raises(PostureHistoryError, match="self-assessment"):
            store.record_change(record)

    def test_direct_supervisor_blocked(self) -> None:
        """Direct supervisor (immediate parent in accountability chain) blocked due to COI.

        D1-R1 is the direct supervisor of D1-R1-T1-R1 in the
        accountability chain [D1-R1, D1-R1-T1-R1]. Governance
        distance is 1 -- BLOCKED.
        """
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        with pytest.raises(PostureHistoryError, match="direct supervisor"):
            validator("D1-R1-T1-R1", "D1-R1", "upgrade")

    def test_ancestor_two_governance_levels_up_allowed(self) -> None:
        """Ancestor 2+ governance levels up is independent enough.

        For agent D1-R1-D2-R1-T1-R1, the accountability chain is
        [D1-R1, D1-R1-D2-R1, D1-R1-D2-R1-T1-R1].

        D1-R1 is 2 levels up from D1-R1-D2-R1-T1-R1 -- ALLOWED.
        """
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        # Should not raise -- 2 governance levels up
        validator("D1-R1-D2-R1-T1-R1", "D1-R1", "upgrade")

    def test_direct_supervisor_of_deep_agent_blocked(self) -> None:
        """Direct supervisor of a deep agent is still blocked.

        For agent D1-R1-D2-R1-T1-R1, the direct supervisor is
        D1-R1-D2-R1 (governance distance 1) -- BLOCKED.
        """
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        with pytest.raises(PostureHistoryError, match="direct supervisor"):
            validator("D1-R1-D2-R1-T1-R1", "D1-R1-D2-R1", "upgrade")

    def test_peer_allowed(self) -> None:
        """Peer supervisor (different branch, same depth) allowed.

        D2-R1 is not an ancestor of D1-R1-T1-R1 -- peer/unrelated.
        """
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        # Should not raise
        validator("D1-R1-T1-R1", "D2-R1", "upgrade")

    def test_unrelated_address_allowed(self) -> None:
        """Completely unrelated address is allowed (no ancestor relationship)."""
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        # D3-R2-T1-R1 has no relationship with D1-R1-T1-R1
        validator("D1-R1-T1-R1", "D3-R2-T1-R1", "upgrade")

    def test_compliance_role_allowed_even_if_direct_supervisor(self) -> None:
        """Registered compliance role always allowed, even if direct supervisor.

        D1-R1 would normally be blocked as direct supervisor of D1-R1-T1-R1,
        but compliance registration overrides the COI check.
        """
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(
            engine,
            compliance_roles={"D1-R1"},
        )

        # Should not raise -- compliance role overrides COI
        validator("D1-R1-T1-R1", "D1-R1", "upgrade")

    def test_compliance_role_not_in_set_still_checked(self) -> None:
        """A non-compliance role is still subject to COI checks."""
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(
            engine,
            compliance_roles={"D3-R1"},  # different role is compliance
        )

        # D1-R1 is NOT a compliance role, and IS the direct supervisor -> blocked
        with pytest.raises(PostureHistoryError, match="direct supervisor"):
            validator("D1-R1-T1-R1", "D1-R1", "upgrade")

    def test_downgrade_not_checked(self) -> None:
        """Downgrade direction skips independence check entirely.

        Downgrades are allowed by anyone (incident response, voluntary
        step-down). Even a direct supervisor can downgrade.
        """
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        # Direct supervisor can downgrade -- should not raise
        validator("D1-R1-T1-R1", "D1-R1", "downgrade")

    def test_invalid_address_fails_closed(self) -> None:
        """Unparseable addresses fail closed -- upgrade is blocked."""
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        with pytest.raises(PostureHistoryError, match="unable to parse"):
            validator("not-a-valid-address!!!", "also-bad!!!", "upgrade")

    def test_invalid_agent_address_fails_closed(self) -> None:
        """Invalid agent address with valid assessor still fails closed."""
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        with pytest.raises(PostureHistoryError, match="unable to parse"):
            validator("BOGUS", "D1-R1", "upgrade")

    def test_invalid_assessor_address_fails_closed(self) -> None:
        """Valid agent address with invalid assessor still fails closed."""
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        with pytest.raises(PostureHistoryError, match="unable to parse"):
            validator("D1-R1-T1-R1", "BOGUS", "upgrade")

    def test_no_compliance_roles_default(self) -> None:
        """When no compliance_roles are passed, the set defaults to empty."""
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)

        # Direct supervisor should still be blocked (no compliance override)
        with pytest.raises(PostureHistoryError, match="direct supervisor"):
            validator("D1-R1-T1-R1", "D1-R1", "upgrade")


class TestWireAssessorValidator:
    """Test the wire_assessor_validator convenience function."""

    def test_wire_sets_validator_on_store(self) -> None:
        """wire_assessor_validator sets the assessor validator on the store."""
        store = PostureHistoryStore()
        engine = _MockEngine()

        wire_assessor_validator(engine, store)

        # Verify by trying a direct-supervisor upgrade (should be blocked)
        record = PostureChangeRecord(
            agent_id="D1-R1-T1-R1",
            from_posture="supervised",
            to_posture="guided",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="D1-R1",  # direct supervisor
        )
        with pytest.raises(PostureHistoryError, match="direct supervisor"):
            store.record_change(record)

    def test_wire_with_compliance_roles(self) -> None:
        """wire_assessor_validator passes compliance roles through."""
        store = PostureHistoryStore()
        engine = _MockEngine()

        wire_assessor_validator(engine, store, compliance_roles={"D1-R1"})

        # D1-R1 is compliance -> should succeed even as direct supervisor
        record = PostureChangeRecord(
            agent_id="D1-R1-T1-R1",
            from_posture="supervised",
            to_posture="guided",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="D1-R1",  # compliance role
        )
        store.record_change(record)
        assert store.current_posture("D1-R1-T1-R1") == "guided"


class TestFullIntegration:
    """Full integration tests: DTR validator through PostureHistoryStore."""

    def test_allowed_upgrade_then_blocked_supervisor(self) -> None:
        """Full flow: allowed upgrade by distant ancestor, then blocked supervisor.

        1. D1-R1 (2 levels up from D1-R1-D2-R1-T1-R1) records initial upgrade -- ALLOWED
        2. D1-R1-D2-R1 (direct supervisor) tries to upgrade -- BLOCKED
        """
        store = PostureHistoryStore()
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)
        store.set_assessor_validator(validator)

        # Step 1: D1-R1 upgrades D1-R1-D2-R1-T1-R1 (2 levels up -- allowed)
        init_record = PostureChangeRecord(
            agent_id="D1-R1-D2-R1-T1-R1",
            from_posture="new",
            to_posture="supervised",
            direction="upgrade",
            trigger=PostureChangeTrigger.MANUAL,
            changed_by="D1-R1",
        )
        store.record_change(init_record)
        assert store.current_posture("D1-R1-D2-R1-T1-R1") == "supervised"

        # Step 2: D1-R1-D2-R1 (direct supervisor) tries to upgrade -- BLOCKED
        upgrade_record = PostureChangeRecord(
            agent_id="D1-R1-D2-R1-T1-R1",
            from_posture="supervised",
            to_posture="guided",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="D1-R1-D2-R1",
        )
        with pytest.raises(PostureHistoryError, match="direct supervisor"):
            store.record_change(upgrade_record)

        # Posture should remain "supervised" -- the blocked record was not stored
        assert store.current_posture("D1-R1-D2-R1-T1-R1") == "supervised"

    def test_peer_upgrade_succeeds(self) -> None:
        """Peer supervisor from different branch can upgrade."""
        store = PostureHistoryStore()
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)
        store.set_assessor_validator(validator)

        record = PostureChangeRecord(
            agent_id="D1-R1-T1-R1",
            from_posture="new",
            to_posture="supervised",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="D2-R1",  # peer -- different branch
        )
        store.record_change(record)
        assert store.current_posture("D1-R1-T1-R1") == "supervised"

    def test_downgrade_by_direct_supervisor_allowed(self) -> None:
        """Direct supervisor CAN downgrade (incident response)."""
        store = PostureHistoryStore()
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)
        store.set_assessor_validator(validator)

        # First, create initial posture via peer
        init_record = PostureChangeRecord(
            agent_id="D1-R1-T1-R1",
            from_posture="new",
            to_posture="guided",
            direction="upgrade",
            trigger=PostureChangeTrigger.MANUAL,
            changed_by="D2-R1",  # peer -- allowed
        )
        store.record_change(init_record)

        # Direct supervisor downgrades (incident response) -- allowed
        downgrade_record = PostureChangeRecord(
            agent_id="D1-R1-T1-R1",
            from_posture="guided",
            to_posture="supervised",
            direction="downgrade",
            trigger=PostureChangeTrigger.INCIDENT,
            changed_by="D1-R1",  # direct supervisor -- allowed for downgrade
        )
        store.record_change(downgrade_record)
        assert store.current_posture("D1-R1-T1-R1") == "supervised"

    def test_sequence_numbers_assigned_correctly(self) -> None:
        """Sequence numbers are assigned only to successful records."""
        store = PostureHistoryStore()
        engine = _MockEngine()
        validator = create_dtr_assessor_validator(engine)
        store.set_assessor_validator(validator)

        # Successful record gets sequence 1
        record1 = PostureChangeRecord(
            agent_id="D1-R1-T1-R1",
            from_posture="new",
            to_posture="supervised",
            direction="upgrade",
            trigger=PostureChangeTrigger.MANUAL,
            changed_by="D2-R1",
        )
        store.record_change(record1)

        # Blocked record does NOT consume a sequence number
        blocked_record = PostureChangeRecord(
            agent_id="D1-R1-T1-R1",
            from_posture="supervised",
            to_posture="guided",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="D1-R1",  # direct supervisor -- blocked
        )
        with pytest.raises(PostureHistoryError):
            store.record_change(blocked_record)

        # Next successful record gets sequence 2 (not 3)
        record2 = PostureChangeRecord(
            agent_id="D1-R1-T1-R1",
            from_posture="supervised",
            to_posture="guided",
            direction="upgrade",
            trigger=PostureChangeTrigger.REVIEW,
            changed_by="D2-R1",  # peer -- allowed
        )
        store.record_change(record2)

        history = store.get_history("D1-R1-T1-R1")
        assert len(history) == 2
        assert history[0].sequence_number == 1
        assert history[1].sequence_number == 2
