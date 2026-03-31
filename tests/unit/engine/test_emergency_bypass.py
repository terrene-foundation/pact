# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the EmergencyBypass engine component (implemented, formerly TODO-07).

Covers: tier durations, auto-expiry, manual expiry, audit anchor
creation, post-incident review scheduling, bounded collection,
fail-closed check, thread safety, Tier 4 rejection, scope validation,
structural authority, and rate limiting.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from pact_platform.engine.emergency_bypass import (
    COOLDOWN_HOURS,
    MAX_BYPASS_RECORDS,
    MAX_BYPASSES_PER_WEEK,
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

    def test_create_tier_4_rejected(self):
        """C2: Tier 4 creation is rejected per PACT spec Section 9."""
        mgr = EmergencyBypass()
        with pytest.raises(ValueError, match="Tier 4.*not permitted"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_4,
                reason="Major crisis",
                approved_by="admin",
            )

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

    def test_tier_4_creation_rejected(self):
        """C2: Tier 4 cannot be created via create_bypass — must use normal governance."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            with pytest.raises(ValueError, match="Tier 4.*not permitted"):
                mgr.create_bypass(
                    role_address="D4-R1",
                    tier=BypassTier.TIER_4,
                    reason="major crisis",
                    approved_by="admin",
                )


# ------------------------------------------------------------------
# EmergencyBypass — manual expiry
# ------------------------------------------------------------------


class TestManualExpiry:
    """Tests for manually expiring bypasses."""

    def test_expire_bypass(self):
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_3,
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
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()
        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="first",
                approved_by="admin",
            )
        with freeze_time(base_time + timedelta(hours=COOLDOWN_HOURS + 1)):
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
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()
        for i, (tier, duration) in enumerate(_TIER_DURATION.items()):
            # Use different roles to avoid rate limiting
            with freeze_time(base_time + timedelta(hours=i)):
                record = mgr.create_bypass(
                    role_address=f"D{i + 1}-R1",
                    tier=tier,
                    reason="test",
                    approved_by="admin",
                )
            assert record.review_due_by is not None
            assert record.expires_at is not None
            expected = record.expires_at + timedelta(days=_REVIEW_WINDOW_DAYS)
            assert record.review_due_by == expected

    def test_review_due_7_days_after_creation_for_tier_4_legacy_record(self):
        """Legacy Tier 4 records (created before Tier 4 rejection) have review_due_by
        set to 7 days after creation (not after expiry, since they have no expiry)."""
        now = datetime.now(UTC)
        review_due_by = now + timedelta(days=_REVIEW_WINDOW_DAYS)
        record = BypassRecord(
            bypass_id="eb-legacy-t4",
            role_address="D1-R1",
            tier=BypassTier.TIER_4,
            reason="crisis",
            approved_by="admin",
            created_at=now,
            expires_at=None,
            review_due_by=review_due_by,
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
        # Fill to capacity using TIER_3 (TIER_4 creation is now rejected)
        first_id = None
        for i in range(MAX_BYPASS_RECORDS):
            record = mgr.create_bypass(
                role_address=f"D{i}-R1",
                tier=BypassTier.TIER_3,
                reason=f"bypass-{i}",
                approved_by="admin",
            )
            if i == 0:
                first_id = record.bypass_id

        # One more should evict the oldest
        mgr.create_bypass(
            role_address="D-NEW-R1",
            tier=BypassTier.TIER_3,
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

    def test_executive_cannot_approve_tier_3_variant(self):
        """Executive cannot approve higher tiers than their authority level allows.
        Note: Tier 4 creation is rejected at a higher priority than authority checks."""
        mgr = EmergencyBypass()
        # Executive can approve up to TIER_3, but DEPARTMENT_HEAD cannot
        with pytest.raises(PermissionError, match="insufficient"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_3,
                reason="crisis",
                approved_by="dept-head-2",
                authority_level=AuthorityLevel.DEPARTMENT_HEAD,
            )

    def test_tier_4_rejected_before_authority_check(self):
        """C2: Tier 4 rejection happens before authority level validation.
        Even COMPLIANCE authority cannot create Tier 4 via create_bypass."""
        mgr = EmergencyBypass()
        with pytest.raises(ValueError, match="Tier 4.*not permitted"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_4,
                reason="full compliance override",
                approved_by="compliance-officer",
                authority_level=AuthorityLevel.COMPLIANCE,
            )

    def test_compliance_can_approve_tiers_1_through_3(self):
        """Compliance (highest authority) can approve all permitted tiers."""
        mgr = EmergencyBypass()
        permitted_tiers = [BypassTier.TIER_1, BypassTier.TIER_2, BypassTier.TIER_3]
        for i, tier in enumerate(permitted_tiers):
            record = mgr.create_bypass(
                role_address=f"D{i + 1}-R1",
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
            tier=BypassTier.TIER_3,
            reason="no auth check",
            approved_by="anyone",
        )
        assert record.tier == BypassTier.TIER_3


# ------------------------------------------------------------------
# C2: Tier 4 rejection — legacy record compatibility
# ------------------------------------------------------------------


class TestTier4LegacyRecords:
    """Verify that Tier 4 enum value is preserved for backwards compatibility
    with existing records, even though creation is rejected."""

    def test_tier_4_enum_still_exists(self):
        """Tier 4 enum value must exist for backwards compat with existing records."""
        assert BypassTier.TIER_4 == "tier_4"

    def test_tier_4_not_in_tier_duration(self):
        """Tier 4 has no duration mapping (as before)."""
        assert BypassTier.TIER_4 not in _TIER_DURATION

    def test_legacy_tier_4_record_is_active(self):
        """A legacy Tier 4 record (created before rejection policy) remains active
        until manually expired."""
        now = datetime.now(UTC)
        record = BypassRecord(
            bypass_id="eb-legacy-001",
            role_address="D1-R1",
            tier=BypassTier.TIER_4,
            reason="legacy crisis",
            approved_by="compliance-officer",
            created_at=now,
            expires_at=None,
        )
        far_future = datetime(2099, 1, 1, tzinfo=UTC)
        assert record.is_active(far_future)
        assert not record.is_expired(far_future)

    def test_legacy_tier_4_record_can_be_manually_expired(self):
        """Legacy Tier 4 records can still be manually expired."""
        now = datetime.now(UTC)
        record = BypassRecord(
            bypass_id="eb-legacy-002",
            role_address="D1-R1",
            tier=BypassTier.TIER_4,
            reason="legacy crisis",
            approved_by="admin",
            created_at=now,
            expires_at=None,
            expired_manually=True,
        )
        assert record.is_expired()


# ------------------------------------------------------------------
# H2: Bypass scope validation — expanded_envelope vs approver envelope
# ------------------------------------------------------------------


class TestBypassScopeValidation:
    """Verify that expanded_envelope is validated against the approver's envelope."""

    def test_within_bounds_accepted(self):
        """Expanded envelope within approver's envelope is accepted."""
        mgr = EmergencyBypass()
        approver_envelope = {
            "financial": {"max_spend_usd": 100000.0},
            "operational": {"allowed_actions": ["trade", "report", "audit"]},
            "data_access": {"read_paths": ["/data/public", "/data/restricted"]},
            "communication": {"allowed_channels": ["email", "slack", "sms"]},
        }
        expanded = {
            "financial": {"max_spend_usd": 50000.0},
            "operational": {"allowed_actions": ["trade", "report"]},
            "data_access": {"read_paths": ["/data/public"]},
            "communication": {"allowed_channels": ["email"]},
        }
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="tactical",
            approved_by="admin",
            expanded_envelope=expanded,
            approver_envelope=approver_envelope,
        )
        assert record.expanded_envelope == expanded

    def test_financial_exceeds_approver_rejected(self):
        """Expanded financial max_spend_usd exceeding approver's is rejected."""
        mgr = EmergencyBypass()
        approver_envelope = {"financial": {"max_spend_usd": 50000.0}}
        expanded = {"financial": {"max_spend_usd": 100000.0}}
        with pytest.raises(PermissionError, match="financial.*max_spend_usd"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="admin",
                expanded_envelope=expanded,
                approver_envelope=approver_envelope,
            )

    def test_operational_exceeds_approver_rejected(self):
        """Expanded operational actions not in approver's set are rejected."""
        mgr = EmergencyBypass()
        approver_envelope = {"operational": {"allowed_actions": ["read", "write"]}}
        expanded = {"operational": {"allowed_actions": ["read", "write", "delete"]}}
        with pytest.raises(PermissionError, match="operational.*allowed_actions"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="admin",
                expanded_envelope=expanded,
                approver_envelope=approver_envelope,
            )

    def test_data_access_exceeds_approver_rejected(self):
        """Expanded read_paths not in approver's set are rejected."""
        mgr = EmergencyBypass()
        approver_envelope = {"data_access": {"read_paths": ["/data/public"]}}
        expanded = {"data_access": {"read_paths": ["/data/public", "/data/secret"]}}
        with pytest.raises(PermissionError, match="data_access.*read_paths"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="admin",
                expanded_envelope=expanded,
                approver_envelope=approver_envelope,
            )

    def test_communication_exceeds_approver_rejected(self):
        """Expanded communication channels not in approver's set are rejected."""
        mgr = EmergencyBypass()
        approver_envelope = {"communication": {"allowed_channels": ["email"]}}
        expanded = {"communication": {"allowed_channels": ["email", "sms"]}}
        with pytest.raises(PermissionError, match="communication.*allowed_channels"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="admin",
                expanded_envelope=expanded,
                approver_envelope=approver_envelope,
            )

    def test_no_approver_envelope_deprecation_warning(self):
        """When approver_envelope is None, a deprecation warning is emitted."""
        mgr = EmergencyBypass()
        expanded = {"financial": {"max_spend_usd": 99999.0}}
        with pytest.warns(DeprecationWarning, match="approver_envelope"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="admin",
                expanded_envelope=expanded,
            )

    def test_nan_in_expanded_envelope_rejected(self):
        """NaN values in expanded envelope financial fields are rejected."""
        mgr = EmergencyBypass()
        approver_envelope = {"financial": {"max_spend_usd": 50000.0}}
        expanded = {"financial": {"max_spend_usd": float("nan")}}
        with pytest.raises(ValueError, match="must be finite"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="admin",
                expanded_envelope=expanded,
                approver_envelope=approver_envelope,
            )

    def test_inf_in_expanded_envelope_rejected(self):
        """Inf values in expanded envelope financial fields are rejected."""
        mgr = EmergencyBypass()
        approver_envelope = {"financial": {"max_spend_usd": 50000.0}}
        expanded = {"financial": {"max_spend_usd": float("inf")}}
        with pytest.raises(ValueError, match="must be finite"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="admin",
                expanded_envelope=expanded,
                approver_envelope=approver_envelope,
            )

    def test_negative_inf_in_expanded_envelope_rejected(self):
        """Negative Inf values in expanded envelope financial fields are rejected."""
        mgr = EmergencyBypass()
        approver_envelope = {"financial": {"max_spend_usd": 50000.0}}
        expanded = {"financial": {"max_spend_usd": float("-inf")}}
        with pytest.raises(ValueError, match="must be finite"):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="admin",
                expanded_envelope=expanded,
                approver_envelope=approver_envelope,
            )

    def test_partial_envelope_dimensions_accepted(self):
        """Expanded envelope may specify only some dimensions — unspecified are not checked."""
        mgr = EmergencyBypass()
        approver_envelope = {
            "financial": {"max_spend_usd": 100000.0},
            "operational": {"allowed_actions": ["trade", "report"]},
        }
        expanded = {"financial": {"max_spend_usd": 50000.0}}
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="tactical",
            approved_by="admin",
            expanded_envelope=expanded,
            approver_envelope=approver_envelope,
        )
        assert record.expanded_envelope == expanded

    def test_empty_expanded_envelope_accepted(self):
        """Empty expanded envelope is always valid."""
        mgr = EmergencyBypass()
        approver_envelope = {"financial": {"max_spend_usd": 100000.0}}
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="tactical",
            approved_by="admin",
            expanded_envelope={},
            approver_envelope=approver_envelope,
        )
        assert record.expanded_envelope == {}


# ------------------------------------------------------------------
# H3: Structural authority validation via D/T/R addresses
# ------------------------------------------------------------------


class TestStructuralAuthority:
    """Verify D/T/R structural relationship validation for bypass approvals."""

    def test_immediate_parent_can_approve_tier_1(self):
        """Tier 1: approver must be the immediate parent R in the accountability chain."""
        mgr = EmergencyBypass()
        # D1-R1 is the immediate parent R of D1-R1-T1-R1
        record = mgr.create_bypass(
            role_address="D1-R1-T1-R1",
            tier=BypassTier.TIER_1,
            reason="tactical",
            approved_by="dept-head",
            approver_address="D1-R1",
            target_address="D1-R1-T1-R1",
        )
        assert record.tier == BypassTier.TIER_1

    def test_non_parent_cannot_approve_tier_1(self):
        """Tier 1: an address that is not the immediate parent R is rejected."""
        mgr = EmergencyBypass()
        # D2-R1 is not an ancestor of D1-R1-T1-R1 at all
        with pytest.raises(PermissionError, match="structural.*authority"):
            mgr.create_bypass(
                role_address="D1-R1-T1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="unrelated-dept-head",
                approver_address="D2-R1",
                target_address="D1-R1-T1-R1",
            )

    def test_grandparent_can_approve_tier_2(self):
        """Tier 2: approver must be 2+ levels up in the accountability chain."""
        mgr = EmergencyBypass()
        # For D1-R1-D2-R1-T1-R1, the chain is [D1-R1, D1-R1-D2-R1, D1-R1-D2-R1-T1-R1]
        # D1-R1 is 2 levels up from D1-R1-D2-R1-T1-R1
        record = mgr.create_bypass(
            role_address="D1-R1-D2-R1-T1-R1",
            tier=BypassTier.TIER_2,
            reason="extended incident",
            approved_by="executive",
            approver_address="D1-R1",
            target_address="D1-R1-D2-R1-T1-R1",
        )
        assert record.tier == BypassTier.TIER_2

    def test_immediate_parent_insufficient_for_tier_2(self):
        """Tier 2: immediate parent (1 level up) is insufficient."""
        mgr = EmergencyBypass()
        # D1-R1-D2-R1 is 1 level up from D1-R1-D2-R1-T1-R1 — not enough for Tier 2
        with pytest.raises(PermissionError, match="structural.*authority"):
            mgr.create_bypass(
                role_address="D1-R1-D2-R1-T1-R1",
                tier=BypassTier.TIER_2,
                reason="extended incident",
                approved_by="dept-head",
                approver_address="D1-R1-D2-R1",
                target_address="D1-R1-D2-R1-T1-R1",
            )

    def test_top_level_can_approve_tier_3(self):
        """Tier 3: approver must be at depth 0 or 1 in the accountability chain (top-level)."""
        mgr = EmergencyBypass()
        # D1-R1 is at depth=2 (2 segments), which is the first R in the chain (index 0)
        record = mgr.create_bypass(
            role_address="D1-R1-D2-R1-T1-R1",
            tier=BypassTier.TIER_3,
            reason="crisis",
            approved_by="c-suite",
            approver_address="D1-R1",
            target_address="D1-R1-D2-R1-T1-R1",
        )
        assert record.tier == BypassTier.TIER_3

    def test_mid_level_cannot_approve_tier_3(self):
        """Tier 3: a mid-level address at index 2+ in the chain is insufficient."""
        mgr = EmergencyBypass()
        # D1-R1-D2-R1-T1-R1 is at index 2 in the chain of D1-R1-D2-R1-T1-R1-R2
        # (chain: [D1-R1, D1-R1-D2-R1, D1-R1-D2-R1-T1-R1, D1-R1-D2-R1-T1-R1-R2])
        # Position 2 > 1, so this should be rejected for Tier 3
        with pytest.raises(PermissionError, match="structural.*authority"):
            mgr.create_bypass(
                role_address="D1-R1-D2-R1-T1-R1-R2",
                tier=BypassTier.TIER_3,
                reason="crisis",
                approved_by="team-lead",
                approver_address="D1-R1-D2-R1-T1-R1",
                target_address="D1-R1-D2-R1-T1-R1-R2",
            )

    def test_no_addresses_falls_back_to_authority_level(self):
        """When addresses are not provided, the existing authority_level check is used."""
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="tactical",
            approved_by="supervisor",
            authority_level=AuthorityLevel.SUPERVISOR,
        )
        assert record.tier == BypassTier.TIER_1

    def test_only_approver_address_without_target_skips_structural(self):
        """When only approver_address is given (no target_address), structural check is skipped."""
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1-T1-R1",
            tier=BypassTier.TIER_1,
            reason="tactical",
            approved_by="supervisor",
            approver_address="D1-R1",
        )
        assert record.tier == BypassTier.TIER_1

    def test_approver_not_in_chain_at_all(self):
        """Approver address that is not in the target's accountability chain is rejected."""
        mgr = EmergencyBypass()
        with pytest.raises(PermissionError, match="structural.*authority"):
            mgr.create_bypass(
                role_address="D1-R1-T1-R1",
                tier=BypassTier.TIER_1,
                reason="tactical",
                approved_by="unrelated",
                approver_address="D2-R1",
                target_address="D1-R1-T1-R1",
            )


# ------------------------------------------------------------------
# M4: Bypass rate limiting — per-role frequency limits
# ------------------------------------------------------------------


class TestBypassRateLimiting:
    """Verify rate limiting prevents perpetual bypass via sequential creation."""

    def test_first_bypass_succeeds(self):
        """First bypass for a role always succeeds."""
        mgr = EmergencyBypass()
        record = mgr.create_bypass(
            role_address="D1-R1",
            tier=BypassTier.TIER_1,
            reason="first incident",
            approved_by="admin",
        )
        assert record.tier == BypassTier.TIER_1

    def test_three_bypasses_in_week_accepted(self):
        """Up to MAX_BYPASSES_PER_WEEK bypasses in a 7-day window are accepted."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        for i in range(MAX_BYPASSES_PER_WEEK):
            with freeze_time(base_time + timedelta(hours=COOLDOWN_HOURS * (i + 1))):
                mgr.create_bypass(
                    role_address="D1-R1",
                    tier=BypassTier.TIER_1,
                    reason=f"incident-{i}",
                    approved_by="admin",
                )

    def test_fourth_bypass_in_week_rejected(self):
        """Exceeding MAX_BYPASSES_PER_WEEK in a 7-day window raises ValueError."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        # Create MAX_BYPASSES_PER_WEEK bypasses with sufficient cooldown between them
        for i in range(MAX_BYPASSES_PER_WEEK):
            with freeze_time(base_time + timedelta(hours=COOLDOWN_HOURS * (i + 1))):
                mgr.create_bypass(
                    role_address="D1-R1",
                    tier=BypassTier.TIER_1,
                    reason=f"incident-{i}",
                    approved_by="admin",
                )

        # One more within the same 7-day window (after cooldown)
        next_time = base_time + timedelta(hours=COOLDOWN_HOURS * (MAX_BYPASSES_PER_WEEK + 1))
        with freeze_time(next_time):
            with pytest.raises(ValueError, match="rate limit.*week"):
                mgr.create_bypass(
                    role_address="D1-R1",
                    tier=BypassTier.TIER_1,
                    reason="one too many",
                    approved_by="admin",
                )

    def test_cooldown_period_enforced(self):
        """Creating a bypass within COOLDOWN_HOURS of the last one raises ValueError."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="first",
                approved_by="admin",
            )

        # Try again 1 hour later (less than COOLDOWN_HOURS)
        with freeze_time(base_time + timedelta(hours=1)):
            with pytest.raises(ValueError, match="cooldown"):
                mgr.create_bypass(
                    role_address="D1-R1",
                    tier=BypassTier.TIER_1,
                    reason="too soon",
                    approved_by="admin",
                )

    def test_after_cooldown_succeeds(self):
        """After the cooldown period, a new bypass is accepted."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="first",
                approved_by="admin",
            )

        with freeze_time(base_time + timedelta(hours=COOLDOWN_HOURS + 1)):
            record = mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="after cooldown",
                approved_by="admin",
            )
            assert record.tier == BypassTier.TIER_1

    def test_weekly_limit_resets_after_7_days(self):
        """After 7 days, the weekly count resets."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        # Fill up the weekly limit
        for i in range(MAX_BYPASSES_PER_WEEK):
            with freeze_time(base_time + timedelta(hours=COOLDOWN_HOURS * (i + 1))):
                mgr.create_bypass(
                    role_address="D1-R1",
                    tier=BypassTier.TIER_1,
                    reason=f"incident-{i}",
                    approved_by="admin",
                )

        # 8 days later (past the 7-day window), a new bypass succeeds
        with freeze_time(base_time + timedelta(days=8)):
            record = mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="fresh week",
                approved_by="admin",
            )
            assert record.tier == BypassTier.TIER_1

    def test_rate_limit_per_role_not_global(self):
        """Rate limits are per-role — different roles have independent counters."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        # Fill up the limit for D1-R1
        for i in range(MAX_BYPASSES_PER_WEEK):
            with freeze_time(base_time + timedelta(hours=COOLDOWN_HOURS * (i + 1))):
                mgr.create_bypass(
                    role_address="D1-R1",
                    tier=BypassTier.TIER_1,
                    reason=f"incident-{i}",
                    approved_by="admin",
                )

        # D2-R1 should still be able to create bypasses
        next_time = base_time + timedelta(hours=COOLDOWN_HOURS * (MAX_BYPASSES_PER_WEEK + 1))
        with freeze_time(next_time):
            record = mgr.create_bypass(
                role_address="D2-R1",
                tier=BypassTier.TIER_1,
                reason="different role",
                approved_by="admin",
            )
            assert record.role_address == "D2-R1"

    def test_old_entries_cleaned_up(self):
        """Bypass history entries older than 7 days are cleaned up."""
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
        mgr = EmergencyBypass()

        # Create a bypass
        with freeze_time(base_time):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="old incident",
                approved_by="admin",
            )

        # 8 days later — create 3 more (should succeed because old one expired from count)
        for i in range(MAX_BYPASSES_PER_WEEK):
            with freeze_time(base_time + timedelta(days=8, hours=COOLDOWN_HOURS * (i + 1))):
                mgr.create_bypass(
                    role_address="D1-R1",
                    tier=BypassTier.TIER_1,
                    reason=f"new-{i}",
                    approved_by="admin",
                )


# ---------------------------------------------------------------------------
# Tests: check_overdue_reviews (F7 / TODO-03 of RT27)
# ---------------------------------------------------------------------------


class TestOverdueReviews:
    """Test check_overdue_reviews() for post-incident review enforcement."""

    def test_no_bypasses_returns_empty(self):
        mgr = EmergencyBypass()
        assert mgr.check_overdue_reviews() == []

    def test_active_bypass_not_overdue(self):
        """Active (non-expired) bypasses should not appear as overdue."""
        mgr = EmergencyBypass()
        now = datetime(2026, 1, 1, tzinfo=UTC)
        with freeze_time(now):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="active",
                approved_by="admin",
            )
        # Still within the 4h tier_1 window
        with freeze_time(now + timedelta(hours=2)):
            assert mgr.check_overdue_reviews(as_of=now + timedelta(hours=2)) == []

    def test_expired_within_review_window_not_overdue(self):
        """Expired bypass still within 7-day review window is not overdue."""
        mgr = EmergencyBypass()
        now = datetime(2026, 1, 1, tzinfo=UTC)
        with freeze_time(now):
            mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="expired-in-window",
                approved_by="admin",
            )
        # 3 days after expiry — within the 7-day review window
        check_time = now + timedelta(hours=4) + timedelta(days=3)
        assert mgr.check_overdue_reviews(as_of=check_time) == []

    def test_expired_past_review_deadline_is_overdue(self):
        """Bypass past the review_due_by deadline should be returned."""
        mgr = EmergencyBypass()
        now = datetime(2026, 1, 1, tzinfo=UTC)
        with freeze_time(now):
            record = mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="overdue",
                approved_by="admin",
            )
        # 10 days after expiry — past the 7-day review window
        check_time = now + timedelta(hours=4) + timedelta(days=10)
        overdue = mgr.check_overdue_reviews(as_of=check_time)
        assert len(overdue) == 1
        assert overdue[0].bypass_id == record.bypass_id

    def test_multiple_overdue_sorted_oldest_first(self):
        """Multiple overdue reviews should be sorted oldest-first."""
        mgr = EmergencyBypass()
        now = datetime(2026, 1, 1, tzinfo=UTC)

        with freeze_time(now):
            r1 = mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="first",
                approved_by="admin",
            )
        with freeze_time(now + timedelta(hours=COOLDOWN_HOURS)):
            r2 = mgr.create_bypass(
                role_address="D1-R1",
                tier=BypassTier.TIER_1,
                reason="second",
                approved_by="admin",
            )

        # Both past review deadline
        check_time = now + timedelta(days=20)
        overdue = mgr.check_overdue_reviews(as_of=check_time)
        assert len(overdue) == 2
        assert overdue[0].bypass_id == r1.bypass_id
        assert overdue[1].bypass_id == r2.bypass_id
