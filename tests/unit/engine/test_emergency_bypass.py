# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the EmergencyBypass engine component (implemented, formerly TODO-07).

Covers: tier durations, auto-expiry, manual expiry, audit anchor
creation, post-incident review scheduling, bounded collection,
fail-closed check, and thread safety.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from pact_platform.engine.emergency_bypass import (
    MAX_BYPASS_RECORDS,
    AuthorityLevel,
    BypassRecord,
    BypassTier,
    EmergencyBypass,
    _REVIEW_WINDOW_DAYS,
    _TIER_DURATION,
)


# ------------------------------------------------------------------
# BypassTier constants
# ------------------------------------------------------------------


class TestBypassTierDurations:
    """Verify each tier maps to the correct duration."""

    def test_tier_1_is_4_hours(self):
        assert _TIER_DURATION[BypassTier.TIER_1] == timedelta(hours=4)

    def test_tier_2_is_24_hours(self):
        assert _TIER_DURATION[BypassTier.TIER_2] == timedelta(hours=24)

    def test_tier_3_is_72_hours(self):
        assert _TIER_DURATION[BypassTier.TIER_3] == timedelta(hours=72)

    def test_tier_4_has_no_duration(self):
        assert BypassTier.TIER_4 not in _TIER_DURATION


# ------------------------------------------------------------------
# BypassRecord
# ------------------------------------------------------------------


class TestBypassRecord:
    """Tests for the frozen BypassRecord dataclass."""

    def test_frozen(self):
        record = BypassRecord(
            bypass_id="eb-test",
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="test",
            approved_by="admin",
        )
        with pytest.raises(AttributeError):
            record.reason = "changed"  # type: ignore[misc]

    def test_expanded_envelope_deep_copied(self):
        """M3: external mutation of the source dict must not affect the record."""
        source_envelope = {"financial": {"max_budget": 5000.0}}
        record = BypassRecord(
            bypass_id="eb-test",
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="test",
            approved_by="admin",
            expanded_envelope=source_envelope,
        )
        # Mutate the original dict
        source_envelope["financial"]["max_budget"] = 99999.0
        # Record should be unaffected
        assert record.expanded_envelope["financial"]["max_budget"] == 5000.0

    def test_is_expired_when_manually_expired(self):
        record = BypassRecord(
            bypass_id="eb-test",
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="test",
            approved_by="admin",
            expired_manually=True,
        )
        assert record.is_expired()

    def test_is_not_expired_within_window(self):
        now = datetime.now(UTC)
        record = BypassRecord(
            bypass_id="eb-test",
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="test",
            approved_by="admin",
            created_at=now,
            expires_at=now + timedelta(hours=4),
        )
        assert not record.is_expired(now + timedelta(hours=1))

    def test_is_expired_past_window(self):
        now = datetime.now(UTC)
        record = BypassRecord(
            bypass_id="eb-test",
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="test",
            approved_by="admin",
            created_at=now,
            expires_at=now + timedelta(hours=4),
        )
        assert record.is_expired(now + timedelta(hours=5))

    def test_tier_4_never_auto_expires(self):
        record = BypassRecord(
            bypass_id="eb-test",
            role_address="D1-R1",
            tier=BypassTier.TIER_4,
            reason="crisis",
            approved_by="admin",
            expires_at=None,
        )
        far_future = datetime(2099, 1, 1, tzinfo=UTC)
        assert not record.is_expired(far_future)

    def test_is_active_inverse(self):
        now = datetime.now(UTC)
        record = BypassRecord(
            bypass_id="eb-test",
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="test",
            approved_by="admin",
            created_at=now,
            expires_at=now + timedelta(hours=4),
        )
        assert record.is_active(now + timedelta(hours=1))
        assert not record.is_active(now + timedelta(hours=5))


# ------------------------------------------------------------------
# EmergencyBypass — creation
# ------------------------------------------------------------------


class TestCreateBypass:
    """Tests for creating emergency bypasses."""

    def test_create_tier_1(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="Tactical response",
            approved_by="admin",
        )
        assert record.bypass_id.startswith("eb-")
        assert record.role_address == "D1-R1"
        assert record.tier == BypassTier.TIER_1
        assert record.reason == "Tactical response"
        assert record.approved_by == "admin"
        assert record.expires_at is not None
        expected_expiry = record.created_at + timedelta(hours=4)
        assert record.expires_at == expected_expiry

    def test_create_tier_2(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_2,
            reason="Extended incident",
            approved_by="admin",
        )
        expected_expiry = record.created_at + timedelta(hours=24)
        assert record.expires_at == expected_expiry

    def test_create_tier_3(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_3,
            reason="Crisis",
            approved_by="admin",
        )
        expected_expiry = record.created_at + timedelta(hours=72)
        assert record.expires_at == expected_expiry

    def test_create_tier_4_no_auto_expiry(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_4,
            reason="Major crisis",
            approved_by="admin",
        )
        assert record.expires_at is None

    def test_create_stores_expanded_envelope(self):
        mgr = EmergencyBypass()
        envelope = {"financial": {"max_spend_usd": 50000}}
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="Budget override",
            approved_by="admin",
            expanded_envelope=envelope,
        )
        assert record.expanded_envelope == envelope

    def test_create_rejects_empty_role_address(self):
        mgr = EmergencyBypass()
        with pytest.raises(ValueError, match="role_address must not be empty"):
            mgr.create_bypass(
                role_address="",
                tier=BypassTier.TIER_1,
                reason="test",
                approved_by="admin",
            )

    def test_create_rejects_empty_reason(self):
        mgr = EmergencyBypass()
        with pytest.raises(ValueError, match="reason must not be empty"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="",
                approved_by="admin",
            )

    def test_create_rejects_empty_approved_by(self):
        mgr = EmergencyBypass()
        with pytest.raises(ValueError, match="approved_by must not be empty"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="test",
                approved_by="",
            )


# ------------------------------------------------------------------
# EmergencyBypass — auto-expiry with freezegun
# ------------------------------------------------------------------


class TestAutoExpiry:
    """Tests for automatic bypass expiry using freezegun to control time."""

    def test_tier_1_active_then_expired(self):
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            record = mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="admin",
            )

        # 2 hours later: still active
        with freeze_time(base_time + timedelta(hours=2)):
            result = mgr.check_bypass("D1-R1")
            assert result is not None
            assert result.bypass_id == record.bypass_id

        # 5 hours later: expired
        with freeze_time(base_time + timedelta(hours=5)):
            result = mgr.check_bypass("D1-R1")
            assert result is None

    def test_tier_2_active_then_expired(self):
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D2-R1",
                tier=BypassTier.TIER_2,
                reason="extended",
                approved_by="admin",
            )

        # 20 hours: active
        with freeze_time(base_time + timedelta(hours=20)):
            assert mgr.check_bypass("D2-R1") is not None

        # 25 hours: expired
        with freeze_time(base_time + timedelta(hours=25)):
            assert mgr.check_bypass("D2-R1") is None

    def test_tier_3_active_then_expired(self):
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D3-R1",
                tier=BypassTier.TIER_3,
                reason="crisis",
                approved_by="admin",
            )

        # 48 hours: active
        with freeze_time(base_time + timedelta(hours=48)):
            assert mgr.check_bypass("D3-R1") is not None

        # 73 hours: expired
        with freeze_time(base_time + timedelta(hours=73)):
            assert mgr.check_bypass("D3-R1") is None

    def test_tier_4_never_auto_expires(self):
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D4-R1",
                tier=BypassTier.TIER_4,
                reason="major crisis",
                approved_by="admin",
            )

        # 1000 hours later: still active (no auto-expiry)
        with freeze_time(base_time + timedelta(hours=1000)):
            assert mgr.check_bypass("D4-R1") is not None


# ------------------------------------------------------------------
# EmergencyBypass — manual expiry
# ------------------------------------------------------------------


class TestManualExpiry:
    """Tests for manually expiring bypasses."""

    def test_expire_bypass(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_4,
            reason="crisis",
            approved_by="admin",
        )
        assert mgr.check_bypass("D1-R1") is not None

        expired = mgr.expire_bypass(record.bypass_id)
        assert expired is not None
        assert expired.expired_manually is True
        assert mgr.check_bypass("D1-R1") is None

    def test_expire_nonexistent_returns_none(self):
        mgr = EmergencyBypass()
        assert mgr.expire_bypass("eb-nonexistent") is None


# ------------------------------------------------------------------
# EmergencyBypass — check_bypass
# ------------------------------------------------------------------


class TestCheckBypass:
    """Tests for looking up active bypasses."""

    def test_check_nonexistent_role(self):
        mgr = EmergencyBypass()
        assert mgr.check_bypass("D99-R99") is None

    def test_check_returns_most_recent_active(self):
        mgr = EmergencyBypass()
        mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="first",
            approved_by="admin",
        )
        second = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_2,
            reason="second",
            approved_by="admin",
        )
        result = mgr.check_bypass("D1-R1")
        assert result is not None
        assert result.bypass_id == second.bypass_id

    def test_expired_bypass_returns_none(self):
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="test",
                approved_by="admin",
            )

        with freeze_time(base_time + timedelta(hours=5)):
            assert mgr.check_bypass("D1-R1") is None


# ------------------------------------------------------------------
# EmergencyBypass — list_active_bypasses
# ------------------------------------------------------------------


class TestListActive:
    """Tests for listing active bypasses."""

    def test_list_empty(self):
        mgr = EmergencyBypass()
        assert mgr.list_active_bypasses() == []

    def test_list_filters_expired(self):
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="short",
                approved_by="admin",
            )
            mgr.create_bypass(
                role_address="D2-R1",
                tier=BypassTier.TIER_3,
                reason="long",
                approved_by="admin",
            )

        # 5 hours later: TIER_1 expired, TIER_3 active
        with freeze_time(base_time + timedelta(hours=5)):
            active = mgr.list_active_bypasses()
            assert len(active) == 1
            assert active[0].role_address == "D2-R1"


# ------------------------------------------------------------------
# EmergencyBypass — audit anchor
# ------------------------------------------------------------------


class TestAuditAnchor:
    """Tests for audit anchor creation on bypass creation."""

    def test_audit_callback_invoked(self):
        events: list[tuple[str, dict]] = []

        def audit_cb(event: str, details: dict) -> str:
            events.append((event, details))
            return f"anchor-{len(events)}"

        mgr = EmergencyBypass(audit_callback=audit_cb)
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_2,
            reason="incident",
            approved_by="admin",
        )

        assert len(events) == 1
        event_name, details = events[0]
        assert event_name == "emergency_bypass_created"
        assert details["bypass_id"] == record.bypass_id
        assert details["role_address"] == "D1-R1"
        assert details["tier"] == "tier_2"
        assert details["approved_by"] == "admin"
        assert record.audit_anchor_id == "anchor-1"

    def test_audit_callback_failure_blocks_creation(self):
        """C3 fix: audit failure must abort bypass creation (fail-closed)."""

        def bad_cb(event: str, details: dict) -> str:
            raise RuntimeError("Audit system down")

        mgr = EmergencyBypass(audit_callback=bad_cb)
        with pytest.raises(RuntimeError, match="audit anchor creation failed"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="test",
                approved_by="admin",
            )

    def test_no_callback_means_empty_anchor_id(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="test",
            approved_by="admin",
        )
        assert record.audit_anchor_id == ""


# ------------------------------------------------------------------
# EmergencyBypass — post-incident review scheduling
# ------------------------------------------------------------------


class TestReviewScheduling:
    """Tests for post-incident review due dates."""

    def test_review_due_7_days_after_expiry_for_tiers_1_2_3(self):
        mgr = EmergencyBypass()
        for tier, duration in _TIER_DURATION.items():
            record = mgr.create_bypass(
                role_address="D1-R1",
                tier=tier,
                reason="test",
                approved_by="admin",
            )
            assert record.review_due_by is not None
            expected = record.expires_at + timedelta(days=_REVIEW_WINDOW_DAYS)
            assert record.review_due_by == expected

    def test_review_due_7_days_after_creation_for_tier_4(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_4,
            reason="crisis",
            approved_by="admin",
        )
        assert record.review_due_by is not None
        expected = record.created_at + timedelta(days=_REVIEW_WINDOW_DAYS)
        assert record.review_due_by == expected

    def test_list_reviews_due(self):
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="test",
                approved_by="admin",
            )

        # Right after expiry (4h+1m), review is due
        with freeze_time(base_time + timedelta(hours=4, minutes=1)):
            reviews = mgr.list_reviews_due()
            assert len(reviews) == 1
            assert reviews[0].role_address == "D1-R1"

        # Past review window (4h + 8 days), review no longer listed
        with freeze_time(base_time + timedelta(hours=4, days=8)):
            reviews = mgr.list_reviews_due()
            assert len(reviews) == 0


# ------------------------------------------------------------------
# EmergencyBypass — bounded collection
# ------------------------------------------------------------------


class TestBoundedCollection:
    """Tests for bounded collection enforcement."""

    def test_evicts_oldest_when_full(self):
        mgr = EmergencyBypass()
        # Fill to capacity
        first_id = None
        for i in range(MAX_BYPASS_RECORDS):
            record = mgr.create_bypass(
                role_address=f"D{i}-R1",
                tier=BypassTier.TIER_4,
                reason=f"bypass-{i}",
                approved_by="admin",
            )
            if i == 0:
                first_id = record.bypass_id

        # One more should evict the oldest
        mgr.create_bypass(
            role_address="D-NEW-R1",
            tier=BypassTier.TIER_4,
            reason="new-bypass",
            approved_by="admin",
        )

        # The first one should have been evicted
        with mgr._lock:
            assert first_id not in mgr._bypasses
            assert len(mgr._bypasses) == MAX_BYPASS_RECORDS


# ------------------------------------------------------------------
# EmergencyBypass — fail-closed
# ------------------------------------------------------------------


class TestFailClosed:
    """Tests for fail-closed behavior on check_bypass errors."""

    def test_check_bypass_returns_none_on_internal_error(self):
        mgr = EmergencyBypass()
        # Corrupt internal state to force an error
        mgr._bypasses = None  # type: ignore[assignment]
        result = mgr.check_bypass("D1-R1")
        assert result is None


# ------------------------------------------------------------------
# H5: Authority level validation
# ------------------------------------------------------------------


class TestAuthorityLevelValidation:
    """Verify that tier-based authorization checks enforce PACT Section 9."""

    def test_supervisor_can_approve_tier_1(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="incident",
            approved_by="supervisor-1",
            authority_level=AuthorityLevel.SUPERVISOR,
        )
        assert record.tier == BypassTier.TIER_1

    def test_supervisor_cannot_approve_tier_2(self):
        mgr = EmergencyBypass()
        with pytest.raises(PermissionError, match="insufficient"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_2,
                reason="incident",
                approved_by="supervisor-1",
                authority_level=AuthorityLevel.SUPERVISOR,
            )

    def test_department_head_can_approve_tier_2(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_2,
            reason="extended incident",
            approved_by="dept-head-1",
            authority_level=AuthorityLevel.DEPARTMENT_HEAD,
        )
        assert record.tier == BypassTier.TIER_2

    def test_department_head_can_approve_tier_1(self):
        """Higher authority can approve lower tiers."""
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="minor incident",
            approved_by="dept-head-1",
            authority_level=AuthorityLevel.DEPARTMENT_HEAD,
        )
        assert record.tier == BypassTier.TIER_1

    def test_department_head_cannot_approve_tier_3(self):
        mgr = EmergencyBypass()
        with pytest.raises(PermissionError, match="insufficient"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_3,
                reason="crisis",
                approved_by="dept-head-1",
                authority_level=AuthorityLevel.DEPARTMENT_HEAD,
            )

    def test_executive_can_approve_tier_3(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_3,
            reason="crisis management",
            approved_by="executive-1",
            authority_level=AuthorityLevel.EXECUTIVE,
        )
        assert record.tier == BypassTier.TIER_3

    def test_executive_cannot_approve_tier_4(self):
        mgr = EmergencyBypass()
        with pytest.raises(PermissionError, match="insufficient"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_4,
                reason="full override",
                approved_by="executive-1",
                authority_level=AuthorityLevel.EXECUTIVE,
            )

    def test_compliance_can_approve_tier_4(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_4,
            reason="full compliance override",
            approved_by="compliance-officer",
            authority_level=AuthorityLevel.COMPLIANCE,
        )
        assert record.tier == BypassTier.TIER_4

    def test_compliance_can_approve_any_tier(self):
        """Compliance (highest authority) can approve all tiers."""
        mgr = EmergencyBypass()
        for tier in BypassTier:
            record = mgr.create_bypass(
                role_address="D1-R1",
                tier=tier,
                reason=f"testing {tier.value}",
                approved_by="compliance-officer",
                authority_level=AuthorityLevel.COMPLIANCE,
            )
            assert record.tier == tier

    def test_no_authority_level_is_backwards_compatible(self):
        """When authority_level is None, no authorization check is performed."""
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_4,
            reason="no auth check",
            approved_by="anyone",
        )
        assert record.tier == BypassTier.TIER_4
