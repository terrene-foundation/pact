# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""RT9-06: DelegationManager.validate_tightening() must use _is_time_window_tighter()
for temporal window comparison instead of lexicographic string comparison.

RT9-08: _is_time_window_tighter() has a vacuous `cs >= 0` check that should be simplified.

Tests:
1. Overnight parent window with tighter overnight child -- accepted
2. Overnight parent window with looser overnight child -- rejected
3. Overnight parent window with daytime child subset -- accepted
4. Normal daytime windows still work correctly after the fix
5. Child removes parent window -- rejected (existing behavior preserved)
6. _is_time_window_tighter() direct tests for overnight edge cases
"""

import pytest

from care_platform.config.schema import (
    ConstraintEnvelopeConfig,
    TemporalConstraintConfig,
)
from care_platform.constraint.envelope import _is_time_window_tighter
from care_platform.trust.delegation import DelegationManager
from care_platform.trust.eatp_bridge import EATPBridge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def bridge():
    b = EATPBridge()
    await b.initialize()
    return b


@pytest.fixture()
def delegation_manager(bridge):
    return DelegationManager(bridge=bridge)


# ---------------------------------------------------------------------------
# RT9-06: validate_tightening() overnight temporal window tests
# ---------------------------------------------------------------------------


class TestOvernightTemporalTightening:
    """validate_tightening() must correctly handle overnight time windows
    (where start > end, e.g., 22:00-06:00) by using _is_time_window_tighter()
    instead of lexicographic string comparison."""

    def test_overnight_parent_with_tighter_overnight_child_accepted(self, delegation_manager):
        """Parent 22:00-06:00, child 23:00-05:00 -- child is tighter, should be accepted."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="22:00",
                active_hours_end="06:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="23:00",
                active_hours_end="05:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True, f"Expected valid tightening but got violations: {violations}"
        assert len(violations) == 0

    def test_overnight_parent_with_looser_overnight_child_rejected(self, delegation_manager):
        """Parent 23:00-05:00, child 22:00-06:00 -- child is wider, should be rejected."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="23:00",
                active_hours_end="05:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="22:00",
                active_hours_end="06:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("temporal" in v.lower() for v in violations)

    def test_overnight_parent_with_daytime_child_subset_accepted(self, delegation_manager):
        """Parent 20:00-08:00, child 23:00-02:00 -- child is daytime subset within
        parent's overnight range, should be accepted.

        Note: child 23:00-02:00 is overnight too. But a non-overnight child that fits
        entirely within one segment of the parent's overnight window is also valid."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="20:00",
                active_hours_end="08:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="23:00",
                active_hours_end="02:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True, f"Expected valid tightening but got violations: {violations}"

    def test_daytime_parent_with_overnight_child_rejected(self, delegation_manager):
        """Parent 09:00-17:00, child 22:00-06:00 -- child wraps midnight but parent
        doesn't, so child is NOT tighter."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="22:00",
                active_hours_end="06:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("temporal" in v.lower() for v in violations)

    def test_normal_daytime_windows_still_work(self, delegation_manager):
        """Regression: normal daytime windows (no overnight) must still work correctly."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="20:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="18:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True
        assert len(violations) == 0

    def test_normal_daytime_child_starts_earlier_rejected(self, delegation_manager):
        """Regression: daytime child starting earlier than parent is still rejected."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="07:00",
                active_hours_end="17:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("temporal" in v.lower() for v in violations)

    def test_overnight_parent_daytime_child_within_evening_segment_accepted(
        self, delegation_manager
    ):
        """Parent 20:00-06:00, child 21:00-23:00 (daytime, within evening segment).
        Child is non-overnight but fits entirely within parent's evening segment [20:00, 24:00)."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="20:00",
                active_hours_end="06:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="21:00",
                active_hours_end="23:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True, f"Expected valid tightening but got violations: {violations}"

    def test_overnight_parent_daytime_child_within_morning_segment_accepted(
        self, delegation_manager
    ):
        """Parent 20:00-06:00, child 01:00-05:00 (daytime, within morning segment).
        Child is non-overnight but fits entirely within parent's morning segment [00:00, 06:00)."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="20:00",
                active_hours_end="06:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="01:00",
                active_hours_end="05:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True, f"Expected valid tightening but got violations: {violations}"


# ---------------------------------------------------------------------------
# RT9-08: _is_time_window_tighter() direct tests
# ---------------------------------------------------------------------------


class TestIsTimeWindowTighter:
    """Direct unit tests for _is_time_window_tighter() to verify overnight
    handling and the RT9-08 vacuous condition fix."""

    def test_normal_daytime_tighter(self):
        """Child 09:00-17:00 within parent 08:00-20:00."""
        assert _is_time_window_tighter("09:00", "17:00", "08:00", "20:00") is True

    def test_normal_daytime_not_tighter_start(self):
        """Child starts earlier than parent."""
        assert _is_time_window_tighter("07:00", "17:00", "08:00", "20:00") is False

    def test_normal_daytime_not_tighter_end(self):
        """Child ends later than parent."""
        assert _is_time_window_tighter("09:00", "21:00", "08:00", "20:00") is False

    def test_overnight_both_tighter(self):
        """Both overnight: child 23:00-05:00 within parent 22:00-06:00."""
        assert _is_time_window_tighter("23:00", "05:00", "22:00", "06:00") is True

    def test_overnight_both_not_tighter(self):
        """Both overnight: child 21:00-07:00 wider than parent 22:00-06:00."""
        assert _is_time_window_tighter("21:00", "07:00", "22:00", "06:00") is False

    def test_child_overnight_parent_daytime_rejected(self):
        """Child wraps midnight, parent doesn't -- never tighter."""
        assert _is_time_window_tighter("22:00", "06:00", "08:00", "20:00") is False

    def test_parent_overnight_child_daytime_evening_segment(self):
        """Parent 20:00-06:00, child 21:00-23:00 (within evening segment)."""
        assert _is_time_window_tighter("21:00", "23:00", "20:00", "06:00") is True

    def test_parent_overnight_child_daytime_morning_segment(self):
        """Parent 20:00-06:00, child 01:00-05:00 (within morning segment).

        RT9-08: Previously the condition was `(ce <= pe and cs >= 0)` where
        `cs >= 0` is always true. After fix, this should still work correctly
        with just `(ce <= pe)`."""
        assert _is_time_window_tighter("01:00", "05:00", "20:00", "06:00") is True

    def test_parent_overnight_child_daytime_spans_gap_rejected(self):
        """Parent 22:00-04:00, child 10:00-15:00 (in the gap, not covered)."""
        assert _is_time_window_tighter("10:00", "15:00", "22:00", "04:00") is False

    def test_equal_windows(self):
        """Equal windows should be considered tighter (subset includes equal)."""
        assert _is_time_window_tighter("09:00", "17:00", "09:00", "17:00") is True

    def test_equal_overnight_windows(self):
        """Equal overnight windows should be considered tighter."""
        assert _is_time_window_tighter("22:00", "06:00", "22:00", "06:00") is True
