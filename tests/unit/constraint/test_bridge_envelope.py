# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for bridge constraint envelope intersection, information sharing modes,
and bridge tightening validation (M32 — Constraint Intersection).
"""

from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)
from pact_platform.build.workspace.bridge import BridgePermission
from pact_platform.trust.constraint.bridge_envelope import (
    BridgeSharingPolicy,
    FieldSharingRule,
    SharingMode,
    compute_bridge_envelope,
    validate_bridge_tightening,
)


def _make_envelope(id: str = "test", **kwargs) -> ConstraintEnvelopeConfig:
    return ConstraintEnvelopeConfig(id=id, **kwargs)


def _make_permissions(**kwargs) -> BridgePermission:
    return BridgePermission(**kwargs)


# ---------------------------------------------------------------------------
# Financial Intersection Tests (3201)
# ---------------------------------------------------------------------------


class TestFinancialIntersection:
    """Financial dimension: min of both budgets."""

    def test_min_of_both_budgets(self):
        source = _make_envelope(
            id="src",
            financial=FinancialConstraintConfig(max_spend_usd=500.0),
        )
        target = _make_envelope(
            id="tgt",
            financial=FinancialConstraintConfig(max_spend_usd=200.0),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.financial is not None
        assert result.financial.max_spend_usd == 200.0

    def test_source_none_financial_produces_none(self):
        source = _make_envelope(id="src", financial=None)
        target = _make_envelope(
            id="tgt",
            financial=FinancialConstraintConfig(max_spend_usd=200.0),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.financial is None

    def test_target_none_financial_produces_none(self):
        source = _make_envelope(
            id="src",
            financial=FinancialConstraintConfig(max_spend_usd=500.0),
        )
        target = _make_envelope(id="tgt", financial=None)
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.financial is None

    def test_both_none_financial_produces_none(self):
        source = _make_envelope(id="src", financial=None)
        target = _make_envelope(id="tgt", financial=None)
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.financial is None

    def test_approval_threshold_min_of_both(self):
        source = _make_envelope(
            id="src",
            financial=FinancialConstraintConfig(
                max_spend_usd=1000.0, requires_approval_above_usd=100.0
            ),
        )
        target = _make_envelope(
            id="tgt",
            financial=FinancialConstraintConfig(
                max_spend_usd=1000.0, requires_approval_above_usd=50.0
            ),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.financial is not None
        assert result.financial.requires_approval_above_usd == 50.0

    def test_approval_threshold_one_none(self):
        source = _make_envelope(
            id="src",
            financial=FinancialConstraintConfig(
                max_spend_usd=1000.0, requires_approval_above_usd=100.0
            ),
        )
        target = _make_envelope(
            id="tgt",
            financial=FinancialConstraintConfig(max_spend_usd=1000.0),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.financial is not None
        assert result.financial.requires_approval_above_usd == 100.0

    def test_api_cost_budget_min(self):
        source = _make_envelope(
            id="src",
            financial=FinancialConstraintConfig(max_spend_usd=1000.0, api_cost_budget_usd=500.0),
        )
        target = _make_envelope(
            id="tgt",
            financial=FinancialConstraintConfig(max_spend_usd=1000.0, api_cost_budget_usd=300.0),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.financial is not None
        assert result.financial.api_cost_budget_usd == 300.0


# ---------------------------------------------------------------------------
# Operational Intersection Tests (3201)
# ---------------------------------------------------------------------------


class TestOperationalIntersection:
    """Operational dimension: allowed = intersection, blocked = union, rate = min."""

    def test_allowed_actions_intersection(self):
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(allowed_actions=["read", "write", "deploy"]),
        )
        target = _make_envelope(
            id="tgt",
            operational=OperationalConstraintConfig(allowed_actions=["read", "write", "review"]),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert sorted(result.operational.allowed_actions) == ["read", "write"]

    def test_allowed_actions_no_common(self):
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(allowed_actions=["deploy"]),
        )
        target = _make_envelope(
            id="tgt",
            operational=OperationalConstraintConfig(allowed_actions=["review"]),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.operational.allowed_actions == []

    def test_allowed_actions_one_empty(self):
        """RT12-003: When one side has an empty allowed list, result is empty (most restrictive)."""
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(allowed_actions=["read", "write"]),
        )
        target = _make_envelope(
            id="tgt",
            operational=OperationalConstraintConfig(allowed_actions=[]),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.operational.allowed_actions == []

    def test_blocked_actions_union(self):
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(blocked_actions=["delete"]),
        )
        target = _make_envelope(
            id="tgt",
            operational=OperationalConstraintConfig(blocked_actions=["deploy"]),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert sorted(result.operational.blocked_actions) == ["delete", "deploy"]

    def test_rate_limit_min(self):
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        target = _make_envelope(
            id="tgt",
            operational=OperationalConstraintConfig(max_actions_per_day=50),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.operational.max_actions_per_day == 50

    def test_rate_limit_one_none(self):
        """When only one side has a rate limit, use that one (None = infinity)."""
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        target = _make_envelope(
            id="tgt",
            operational=OperationalConstraintConfig(),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.operational.max_actions_per_day == 100

    def test_rate_limit_both_none(self):
        source = _make_envelope(id="src")
        target = _make_envelope(id="tgt")
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.operational.max_actions_per_day is None

    def test_hourly_rate_limit_min(self):
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(max_actions_per_hour=20),
        )
        target = _make_envelope(
            id="tgt",
            operational=OperationalConstraintConfig(max_actions_per_hour=10),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.operational.max_actions_per_hour == 10

    def test_reasoning_required_union(self):
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(reasoning_required=True),
        )
        target = _make_envelope(
            id="tgt",
            operational=OperationalConstraintConfig(reasoning_required=False),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.operational.reasoning_required is True


# ---------------------------------------------------------------------------
# Temporal Intersection Tests (3201)
# ---------------------------------------------------------------------------


class TestTemporalIntersection:
    """Temporal dimension: overlapping active hours window."""

    def test_overlapping_windows(self):
        source = _make_envelope(
            id="src",
            temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="18:00"),
        )
        target = _make_envelope(
            id="tgt",
            temporal=TemporalConstraintConfig(active_hours_start="10:00", active_hours_end="16:00"),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.temporal.active_hours_start == "10:00"
        assert result.temporal.active_hours_end == "16:00"

    def test_non_overlapping_windows(self):
        """Non-overlapping windows produce a sentinel (start == end)."""
        source = _make_envelope(
            id="src",
            temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="12:00"),
        )
        target = _make_envelope(
            id="tgt",
            temporal=TemporalConstraintConfig(active_hours_start="14:00", active_hours_end="18:00"),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        # Sentinel: start == end means no valid window
        assert result.temporal.active_hours_start == result.temporal.active_hours_end

    def test_one_unrestricted(self):
        """When one side has no temporal restriction, the other determines the window."""
        source = _make_envelope(
            id="src",
            temporal=TemporalConstraintConfig(active_hours_start="09:00", active_hours_end="17:00"),
        )
        target = _make_envelope(
            id="tgt",
            temporal=TemporalConstraintConfig(),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.temporal.active_hours_start == "09:00"
        assert result.temporal.active_hours_end == "17:00"

    def test_both_unrestricted(self):
        source = _make_envelope(id="src")
        target = _make_envelope(id="tgt")
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.temporal.active_hours_start is None
        assert result.temporal.active_hours_end is None

    def test_overnight_window_overlap(self):
        """Overnight windows (e.g., 22:00-06:00) should be handled correctly."""
        source = _make_envelope(
            id="src",
            temporal=TemporalConstraintConfig(active_hours_start="20:00", active_hours_end="08:00"),
        )
        target = _make_envelope(
            id="tgt",
            temporal=TemporalConstraintConfig(active_hours_start="22:00", active_hours_end="06:00"),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        # Both overnight: latest start (22:00), earliest end (06:00)
        assert result.temporal.active_hours_start == "22:00"
        assert result.temporal.active_hours_end == "06:00"

    def test_blackout_periods_union(self):
        source = _make_envelope(
            id="src",
            temporal=TemporalConstraintConfig(blackout_periods=["2026-01-01"]),
        )
        target = _make_envelope(
            id="tgt",
            temporal=TemporalConstraintConfig(blackout_periods=["2026-12-25"]),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert sorted(result.temporal.blackout_periods) == ["2026-01-01", "2026-12-25"]

    def test_blackout_periods_dedup(self):
        source = _make_envelope(
            id="src",
            temporal=TemporalConstraintConfig(blackout_periods=["2026-01-01", "2026-12-25"]),
        )
        target = _make_envelope(
            id="tgt",
            temporal=TemporalConstraintConfig(blackout_periods=["2026-01-01"]),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert sorted(result.temporal.blackout_periods) == ["2026-01-01", "2026-12-25"]


# ---------------------------------------------------------------------------
# Data Access Intersection Tests (3201)
# ---------------------------------------------------------------------------


class TestDataAccessIntersection:
    """Data Access dimension: path intersection with bridge permissions."""

    def test_read_paths_intersection(self):
        source = _make_envelope(
            id="src",
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/src/*", "ws/shared/*", "ws/docs/*"]
            ),
        )
        target = _make_envelope(
            id="tgt",
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/shared/*", "ws/docs/*", "ws/tgt/*"]
            ),
        )
        perms = _make_permissions(read_paths=["ws/shared/*", "ws/docs/*"])
        result = compute_bridge_envelope(source, perms, target)
        assert sorted(result.data_access.read_paths) == ["ws/docs/*", "ws/shared/*"]

    def test_read_paths_no_shared_patterns(self):
        source = _make_envelope(
            id="src",
            data_access=DataAccessConstraintConfig(read_paths=["ws/src/*"]),
        )
        target = _make_envelope(
            id="tgt",
            data_access=DataAccessConstraintConfig(read_paths=["ws/tgt/*"]),
        )
        perms = _make_permissions(read_paths=["ws/other/*"])
        result = compute_bridge_envelope(source, perms, target)
        assert result.data_access.read_paths == []

    def test_write_paths_intersection(self):
        source = _make_envelope(
            id="src",
            data_access=DataAccessConstraintConfig(write_paths=["ws/shared/*", "ws/src/*"]),
        )
        target = _make_envelope(
            id="tgt",
            data_access=DataAccessConstraintConfig(write_paths=["ws/shared/*", "ws/tgt/*"]),
        )
        perms = _make_permissions(write_paths=["ws/shared/*"])
        result = compute_bridge_envelope(source, perms, target)
        assert result.data_access.write_paths == ["ws/shared/*"]

    def test_blocked_data_types_union(self):
        source = _make_envelope(
            id="src",
            data_access=DataAccessConstraintConfig(blocked_data_types=["pii"]),
        )
        target = _make_envelope(
            id="tgt",
            data_access=DataAccessConstraintConfig(blocked_data_types=["financial_records"]),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert sorted(result.data_access.blocked_data_types) == [
            "financial_records",
            "pii",
        ]

    def test_empty_bridge_paths_with_envelope_paths(self):
        """RT12-002: Empty bridge paths means no access — result is empty."""
        source = _make_envelope(
            id="src",
            data_access=DataAccessConstraintConfig(read_paths=["ws/src/*"]),
        )
        target = _make_envelope(
            id="tgt",
            data_access=DataAccessConstraintConfig(read_paths=["ws/src/*"]),
        )
        perms = _make_permissions(read_paths=[])
        result = compute_bridge_envelope(source, perms, target)
        # RT12-002: Empty bridge paths = no access (most restrictive)
        assert result.data_access.read_paths == []

    def test_all_empty_paths(self):
        source = _make_envelope(id="src")
        target = _make_envelope(id="tgt")
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.data_access.read_paths == []
        assert result.data_access.write_paths == []


# ---------------------------------------------------------------------------
# Communication Intersection Tests (3201)
# ---------------------------------------------------------------------------


class TestCommunicationIntersection:
    """Communication dimension: most restrictive wins."""

    def test_internal_only_both_false(self):
        source = _make_envelope(
            id="src",
            communication=CommunicationConstraintConfig(internal_only=False),
        )
        target = _make_envelope(
            id="tgt",
            communication=CommunicationConstraintConfig(internal_only=False),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.communication.internal_only is False

    def test_internal_only_one_true(self):
        source = _make_envelope(
            id="src",
            communication=CommunicationConstraintConfig(internal_only=True),
        )
        target = _make_envelope(
            id="tgt",
            communication=CommunicationConstraintConfig(internal_only=False),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.communication.internal_only is True

    def test_external_requires_approval_one_true(self):
        source = _make_envelope(
            id="src",
            communication=CommunicationConstraintConfig(external_requires_approval=False),
        )
        target = _make_envelope(
            id="tgt",
            communication=CommunicationConstraintConfig(external_requires_approval=True),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.communication.external_requires_approval is True

    def test_allowed_channels_intersection(self):
        source = _make_envelope(
            id="src",
            communication=CommunicationConstraintConfig(
                allowed_channels=["slack", "email", "teams"]
            ),
        )
        target = _make_envelope(
            id="tgt",
            communication=CommunicationConstraintConfig(allowed_channels=["slack", "email"]),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert sorted(result.communication.allowed_channels) == ["email", "slack"]

    def test_allowed_channels_one_empty(self):
        """RT12-003: Empty allowed_channels means no channels — result is empty."""
        source = _make_envelope(
            id="src",
            communication=CommunicationConstraintConfig(allowed_channels=["slack", "email"]),
        )
        target = _make_envelope(
            id="tgt",
            communication=CommunicationConstraintConfig(allowed_channels=[]),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.communication.allowed_channels == []

    def test_reasoning_required_union(self):
        source = _make_envelope(
            id="src",
            communication=CommunicationConstraintConfig(reasoning_required=True),
        )
        target = _make_envelope(
            id="tgt",
            communication=CommunicationConstraintConfig(reasoning_required=False),
        )
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.communication.reasoning_required is True


# ---------------------------------------------------------------------------
# Full Five-Dimension Integration Test (3201)
# ---------------------------------------------------------------------------


class TestFullIntersection:
    """Test envelope intersection across all five CARE dimensions simultaneously."""

    def test_realistic_five_dimension_intersection(self):
        source = _make_envelope(
            id="dm-team",
            financial=FinancialConstraintConfig(
                max_spend_usd=1000.0,
                requires_approval_above_usd=200.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write", "publish"],
                blocked_actions=["delete"],
                max_actions_per_day=500,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="20:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/dm/*", "ws/shared/*"],
                write_paths=["ws/dm/*"],
                blocked_data_types=["pii"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=False,
                external_requires_approval=True,
                allowed_channels=["slack", "email"],
            ),
        )

        target = _make_envelope(
            id="standards-team",
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                requires_approval_above_usd=100.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "review", "publish"],
                blocked_actions=["deploy"],
                max_actions_per_day=200,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/standards/*", "ws/shared/*"],
                write_paths=["ws/standards/*"],
                blocked_data_types=["financial_records"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
                allowed_channels=["slack"],
            ),
        )

        perms = _make_permissions(
            read_paths=["ws/shared/*"],
            write_paths=[],
            message_types=["review_request", "review_response"],
        )

        result = compute_bridge_envelope(source, perms, target)

        # Financial: min(1000, 500) = 500, approval threshold min(200, 100) = 100
        assert result.financial is not None
        assert result.financial.max_spend_usd == 500.0
        assert result.financial.requires_approval_above_usd == 100.0

        # Operational: intersection(read/write/publish, read/review/publish) = read/publish
        # blocked: union(delete, deploy)
        assert sorted(result.operational.allowed_actions) == ["publish", "read"]
        assert sorted(result.operational.blocked_actions) == ["delete", "deploy"]
        assert result.operational.max_actions_per_day == 200

        # Temporal: overlap(08:00-20:00, 09:00-17:00) = 09:00-17:00
        assert result.temporal.active_hours_start == "09:00"
        assert result.temporal.active_hours_end == "17:00"

        # Data Access: read_paths intersection with bridge = ws/shared/*
        assert result.data_access.read_paths == ["ws/shared/*"]
        assert result.data_access.write_paths == []
        assert sorted(result.data_access.blocked_data_types) == [
            "financial_records",
            "pii",
        ]

        # Communication: internal_only=True (target has True), channels=slack
        assert result.communication.internal_only is True
        assert result.communication.external_requires_approval is True
        assert result.communication.allowed_channels == ["slack"]


# ---------------------------------------------------------------------------
# Information Sharing Mode Tests (3202)
# ---------------------------------------------------------------------------


class TestSharingModes:
    """Test BridgeSharingPolicy and field-level sharing control."""

    def test_exact_match(self):
        policy = BridgeSharingPolicy(
            rules=[
                FieldSharingRule(
                    field_pattern="budget.annual",
                    mode=SharingMode.NEVER_SHARE,
                ),
            ]
        )
        assert policy.check_field("budget.annual") == SharingMode.NEVER_SHARE

    def test_glob_match(self):
        policy = BridgeSharingPolicy(
            rules=[
                FieldSharingRule(
                    field_pattern="budget.*",
                    mode=SharingMode.NEVER_SHARE,
                ),
            ]
        )
        assert policy.check_field("budget.annual") == SharingMode.NEVER_SHARE
        assert policy.check_field("budget.quarterly") == SharingMode.NEVER_SHARE

    def test_star_public_glob(self):
        policy = BridgeSharingPolicy(
            rules=[
                FieldSharingRule(
                    field_pattern="*.public",
                    mode=SharingMode.AUTO_SHARE,
                ),
            ]
        )
        assert policy.check_field("content.public") == SharingMode.AUTO_SHARE

    def test_default_mode(self):
        policy = BridgeSharingPolicy(
            rules=[
                FieldSharingRule(
                    field_pattern="budget.*",
                    mode=SharingMode.NEVER_SHARE,
                ),
            ]
        )
        assert policy.check_field("unmatched.path") == SharingMode.REQUEST_SHARE

    def test_custom_default_mode(self):
        policy = BridgeSharingPolicy(
            rules=[],
            default_mode=SharingMode.AUTO_SHARE,
        )
        assert policy.check_field("anything") == SharingMode.AUTO_SHARE

    def test_first_match_wins(self):
        """Rules are tried in order — the first matching rule wins."""
        policy = BridgeSharingPolicy(
            rules=[
                FieldSharingRule(
                    field_pattern="budget.annual",
                    mode=SharingMode.AUTO_SHARE,
                ),
                FieldSharingRule(
                    field_pattern="budget.*",
                    mode=SharingMode.NEVER_SHARE,
                ),
            ]
        )
        # Exact match first
        assert policy.check_field("budget.annual") == SharingMode.AUTO_SHARE
        # Glob match second
        assert policy.check_field("budget.quarterly") == SharingMode.NEVER_SHARE

    def test_never_share_excludes_from_bridge_envelope(self):
        """NEVER_SHARE fields should be excluded from bridge envelope data access paths."""
        source = _make_envelope(
            id="src",
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/shared/public/*", "ws/shared/secret/*"]
            ),
        )
        target = _make_envelope(
            id="tgt",
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/shared/public/*", "ws/shared/secret/*"]
            ),
        )
        perms = _make_permissions(read_paths=["ws/shared/public/*", "ws/shared/secret/*"])
        policy = BridgeSharingPolicy(
            rules=[
                FieldSharingRule(
                    field_pattern="ws/shared/secret/*",
                    mode=SharingMode.NEVER_SHARE,
                ),
            ],
            default_mode=SharingMode.AUTO_SHARE,
        )

        result = compute_bridge_envelope(source, perms, target, sharing_policy=policy)
        assert result.data_access.read_paths == ["ws/shared/public/*"]

    def test_auto_share_passes_through(self):
        """AUTO_SHARE fields should remain in the bridge envelope."""
        policy = BridgeSharingPolicy(
            rules=[
                FieldSharingRule(
                    field_pattern="ws/shared/*",
                    mode=SharingMode.AUTO_SHARE,
                ),
            ]
        )
        source = _make_envelope(
            id="src",
            data_access=DataAccessConstraintConfig(read_paths=["ws/shared/*"]),
        )
        target = _make_envelope(
            id="tgt",
            data_access=DataAccessConstraintConfig(read_paths=["ws/shared/*"]),
        )
        perms = _make_permissions(read_paths=["ws/shared/*"])
        result = compute_bridge_envelope(source, perms, target, sharing_policy=policy)
        assert result.data_access.read_paths == ["ws/shared/*"]

    def test_request_share_passes_through(self):
        """REQUEST_SHARE fields remain in the bridge envelope (approval enforced at runtime)."""
        policy = BridgeSharingPolicy(
            rules=[
                FieldSharingRule(
                    field_pattern="ws/shared/*",
                    mode=SharingMode.REQUEST_SHARE,
                ),
            ]
        )
        source = _make_envelope(
            id="src",
            data_access=DataAccessConstraintConfig(read_paths=["ws/shared/*"]),
        )
        target = _make_envelope(
            id="tgt",
            data_access=DataAccessConstraintConfig(read_paths=["ws/shared/*"]),
        )
        perms = _make_permissions(read_paths=["ws/shared/*"])
        result = compute_bridge_envelope(source, perms, target, sharing_policy=policy)
        assert result.data_access.read_paths == ["ws/shared/*"]

    def test_sharing_mode_enum_values(self):
        assert SharingMode.AUTO_SHARE.value == "auto_share"
        assert SharingMode.REQUEST_SHARE.value == "request_share"
        assert SharingMode.NEVER_SHARE.value == "never_share"


# ---------------------------------------------------------------------------
# Bridge Tightening Validation Tests (3203)
# ---------------------------------------------------------------------------


class TestBridgeTighteningValidation:
    """Verify that bridge envelope is no wider than either team's envelope."""

    def _make_valid_bridge(
        self,
    ) -> tuple[
        ConstraintEnvelopeConfig,
        ConstraintEnvelopeConfig,
        ConstraintEnvelopeConfig,
    ]:
        """Create a valid bridge envelope that is tighter than both teams."""
        source = _make_envelope(
            id="src",
            financial=FinancialConstraintConfig(max_spend_usd=500.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
                blocked_actions=["delete"],
                max_actions_per_day=100,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="18:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/src/*", "ws/shared/*"],
                write_paths=["ws/shared/*"],
                blocked_data_types=["pii"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )
        target = _make_envelope(
            id="tgt",
            financial=FinancialConstraintConfig(max_spend_usd=300.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "review"],
                blocked_actions=["deploy"],
                max_actions_per_day=200,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/tgt/*", "ws/shared/*"],
                write_paths=["ws/shared/*"],
                blocked_data_types=["credentials"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )
        # Bridge envelope: the intersection (tighter than both)
        bridge = _make_envelope(
            id="bridge",
            financial=FinancialConstraintConfig(max_spend_usd=200.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read"],
                blocked_actions=["delete", "deploy"],
                max_actions_per_day=50,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="10:00",
                active_hours_end="16:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/shared/*"],
                write_paths=["ws/shared/*"],
                blocked_data_types=["pii", "credentials"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )
        return bridge, source, target

    def test_valid_tightening_passes(self):
        bridge, source, target = self._make_valid_bridge()
        is_valid, violations = validate_bridge_tightening(bridge, source, target)
        assert is_valid is True
        assert violations == []

    def test_financial_violation_exceeds_source(self):
        bridge, source, target = self._make_valid_bridge()
        # Make bridge budget exceed source
        loose_bridge = _make_envelope(
            id="bridge",
            financial=FinancialConstraintConfig(max_spend_usd=600.0),
            operational=bridge.operational,
            temporal=bridge.temporal,
            data_access=bridge.data_access,
            communication=bridge.communication,
        )
        is_valid, violations = validate_bridge_tightening(loose_bridge, source, target)
        assert is_valid is False
        assert any("Financial" in v and "source" in v for v in violations)

    def test_financial_violation_bridge_has_financial_but_parent_has_none(self):
        source = _make_envelope(id="src", financial=None)
        target = _make_envelope(
            id="tgt",
            financial=FinancialConstraintConfig(max_spend_usd=500.0),
        )
        bridge = _make_envelope(
            id="bridge",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        is_valid, violations = validate_bridge_tightening(bridge, source, target)
        assert is_valid is False
        assert any("Financial" in v and "source" in v for v in violations)

    def test_operational_violation_extra_allowed_action(self):
        bridge, source, target = self._make_valid_bridge()
        # Add action not in source
        loose_bridge = _make_envelope(
            id="bridge",
            financial=bridge.financial,
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "deploy"],
                blocked_actions=["delete", "deploy"],
                max_actions_per_day=50,
            ),
            temporal=bridge.temporal,
            data_access=bridge.data_access,
            communication=bridge.communication,
        )
        is_valid, violations = validate_bridge_tightening(loose_bridge, source, target)
        assert is_valid is False
        assert any("Operational" in v and "actions" in v.lower() for v in violations)

    def test_operational_violation_missing_blocked_action(self):
        bridge, source, target = self._make_valid_bridge()
        # Remove a blocked action
        loose_bridge = _make_envelope(
            id="bridge",
            financial=bridge.financial,
            operational=OperationalConstraintConfig(
                allowed_actions=["read"],
                blocked_actions=["delete"],  # missing "deploy" from target
                max_actions_per_day=50,
            ),
            temporal=bridge.temporal,
            data_access=bridge.data_access,
            communication=bridge.communication,
        )
        is_valid, violations = validate_bridge_tightening(loose_bridge, source, target)
        assert is_valid is False
        assert any("blocked" in v.lower() for v in violations)

    def test_temporal_violation_wider_window(self):
        bridge, source, target = self._make_valid_bridge()
        # Bridge window wider than target (09:00-17:00)
        loose_bridge = _make_envelope(
            id="bridge",
            financial=bridge.financial,
            operational=bridge.operational,
            temporal=TemporalConstraintConfig(
                active_hours_start="07:00",
                active_hours_end="19:00",
            ),
            data_access=bridge.data_access,
            communication=bridge.communication,
        )
        is_valid, violations = validate_bridge_tightening(loose_bridge, source, target)
        assert is_valid is False
        assert any("Temporal" in v for v in violations)

    def test_data_access_violation_extra_read_path(self):
        bridge, source, target = self._make_valid_bridge()
        # Add read path not in source
        loose_bridge = _make_envelope(
            id="bridge",
            financial=bridge.financial,
            operational=bridge.operational,
            temporal=bridge.temporal,
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/shared/*", "ws/secret/*"],
                write_paths=["ws/shared/*"],
                blocked_data_types=["pii", "credentials"],
            ),
            communication=bridge.communication,
        )
        is_valid, violations = validate_bridge_tightening(loose_bridge, source, target)
        assert is_valid is False
        assert any("Data Access" in v and "read" in v.lower() for v in violations)

    def test_data_access_violation_missing_blocked_type(self):
        bridge, source, target = self._make_valid_bridge()
        # Remove a blocked data type
        loose_bridge = _make_envelope(
            id="bridge",
            financial=bridge.financial,
            operational=bridge.operational,
            temporal=bridge.temporal,
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/shared/*"],
                write_paths=["ws/shared/*"],
                blocked_data_types=["pii"],  # missing "credentials" from target
            ),
            communication=bridge.communication,
        )
        is_valid, violations = validate_bridge_tightening(loose_bridge, source, target)
        assert is_valid is False
        assert any("blocked data types" in v.lower() for v in violations)

    def test_communication_violation_internal_only(self):
        bridge, source, target = self._make_valid_bridge()
        loose_bridge = _make_envelope(
            id="bridge",
            financial=bridge.financial,
            operational=bridge.operational,
            temporal=bridge.temporal,
            data_access=bridge.data_access,
            communication=CommunicationConstraintConfig(
                internal_only=False,  # source and target both have True
                external_requires_approval=True,
            ),
        )
        is_valid, violations = validate_bridge_tightening(loose_bridge, source, target)
        assert is_valid is False
        assert any("internal_only" in v for v in violations)

    def test_communication_violation_external_approval(self):
        bridge, source, target = self._make_valid_bridge()
        loose_bridge = _make_envelope(
            id="bridge",
            financial=bridge.financial,
            operational=bridge.operational,
            temporal=bridge.temporal,
            data_access=bridge.data_access,
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=False,  # both parents have True
            ),
        )
        is_valid, violations = validate_bridge_tightening(loose_bridge, source, target)
        assert is_valid is False
        assert any("external approval" in v.lower() for v in violations)

    def test_multiple_violations_returned(self):
        """All violations should be detected, not just the first one."""
        source = _make_envelope(
            id="src",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read"],
                blocked_actions=["delete"],
            ),
            communication=CommunicationConstraintConfig(internal_only=True),
        )
        target = _make_envelope(
            id="tgt",
            financial=FinancialConstraintConfig(max_spend_usd=200.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read"],
                blocked_actions=["deploy"],
            ),
            communication=CommunicationConstraintConfig(internal_only=True),
        )
        # Bridge violates multiple dimensions
        loose_bridge = _make_envelope(
            id="bridge",
            financial=FinancialConstraintConfig(max_spend_usd=500.0),  # > source
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],  # "write" not in either
                blocked_actions=[],  # missing both "delete" and "deploy"
            ),
            communication=CommunicationConstraintConfig(internal_only=False),  # both are True
        )
        is_valid, violations = validate_bridge_tightening(loose_bridge, source, target)
        assert is_valid is False
        # Should have financial + operational (actions + blocked) + communication violations
        assert len(violations) >= 4

    def test_rate_limit_violation(self):
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(max_actions_per_day=50),
        )
        target = _make_envelope(
            id="tgt",
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        bridge = _make_envelope(
            id="bridge",
            operational=OperationalConstraintConfig(max_actions_per_day=75),
        )
        is_valid, violations = validate_bridge_tightening(bridge, source, target)
        assert is_valid is False
        assert any("rate limit" in v.lower() or "daily" in v.lower() for v in violations)

    def test_rate_limit_removed_violation(self):
        source = _make_envelope(
            id="src",
            operational=OperationalConstraintConfig(max_actions_per_day=50),
        )
        target = _make_envelope(id="tgt")
        bridge = _make_envelope(
            id="bridge",
            operational=OperationalConstraintConfig(),  # No rate limit
        )
        is_valid, violations = validate_bridge_tightening(bridge, source, target)
        assert is_valid is False
        assert any("rate limit" in v.lower() for v in violations)


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for envelope intersection."""

    def test_bridge_envelope_id_format(self):
        source = _make_envelope(id="src")
        target = _make_envelope(id="tgt")
        result = compute_bridge_envelope(source, _make_permissions(), target)
        assert result.id == "bridge-src-tgt"

    def test_identical_envelopes_produce_same(self):
        envelope = _make_envelope(
            id="same",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read"],
                blocked_actions=["delete"],
            ),
        )
        result = compute_bridge_envelope(envelope, _make_permissions(), envelope)
        assert result.financial is not None
        assert result.financial.max_spend_usd == 100.0
        assert result.operational.allowed_actions == ["read"]
        assert result.operational.blocked_actions == ["delete"]

    def test_empty_sharing_policy_uses_default(self):
        policy = BridgeSharingPolicy()
        assert policy.check_field("any.path") == SharingMode.REQUEST_SHARE

    def test_sharing_policy_with_justification(self):
        rule = FieldSharingRule(
            field_pattern="secret.*",
            mode=SharingMode.NEVER_SHARE,
            justification="Contains sensitive data",
        )
        assert rule.justification == "Contains sensitive data"

    def test_computed_envelope_passes_tightening(self):
        """A properly computed bridge envelope should always pass tightening validation."""
        source = _make_envelope(
            id="src",
            financial=FinancialConstraintConfig(max_spend_usd=500.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
                blocked_actions=["delete"],
                max_actions_per_day=100,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="18:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/shared/*"],
                write_paths=["ws/shared/*"],
                blocked_data_types=["pii"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
                allowed_channels=["slack", "email"],
            ),
        )
        target = _make_envelope(
            id="tgt",
            financial=FinancialConstraintConfig(max_spend_usd=300.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "review"],
                blocked_actions=["deploy"],
                max_actions_per_day=200,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["ws/shared/*"],
                write_paths=["ws/shared/*"],
                blocked_data_types=["credentials"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
                allowed_channels=["slack"],
            ),
        )
        perms = _make_permissions(
            read_paths=["ws/shared/*"],
            write_paths=["ws/shared/*"],
        )

        bridge_env = compute_bridge_envelope(source, perms, target)
        is_valid, violations = validate_bridge_tightening(bridge_env, source, target)
        assert is_valid is True, f"Computed bridge envelope should be valid, got: {violations}"
