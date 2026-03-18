# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Red team tests for incomplete constraint dimension enforcement.

Covers RT-15, RT-16, RT-17, RT-24, RT-27, RT-28, RT-35 findings:
- Temporal: overnight windows, blackout periods, timezone conversion
- Data Access: read_paths/write_paths enforcement
- Communication: external_requires_approval enforcement
- Financial: soft-limit HELD result, cumulative budget tracking
"""

from datetime import UTC, datetime

from care_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    TemporalConstraintConfig,
)
from care_platform.trust.constraint.envelope import (
    ConstraintEnvelope,
    EvaluationResult,
)


def _make_envelope(**kwargs) -> ConstraintEnvelope:
    config = ConstraintEnvelopeConfig(id="rt-test-env", **kwargs)
    return ConstraintEnvelope(config=config)


# ===========================================================================
# RT-15 / RT-28 / RT-35: Temporal dimension enforcement
# ===========================================================================


class TestTemporalOvernightWindows:
    """RT-15 / RT-28: Overnight active hour windows (start > end)."""

    def test_overnight_window_allowed_after_start(self):
        """Agent with 22:00-06:00 window should be ALLOWED at 23:00."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="22:00",
                active_hours_end="06:00",
            ),
        )
        night_time = datetime(2026, 3, 11, 23, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=night_time)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED, (
            f"Expected ALLOWED at 23:00 within overnight 22:00-06:00 window, "
            f"got {temp_dim.result}: {temp_dim.reason}"
        )

    def test_overnight_window_allowed_before_end(self):
        """Agent with 22:00-06:00 window should be ALLOWED at 04:00."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="22:00",
                active_hours_end="06:00",
            ),
        )
        early_morning = datetime(2026, 3, 12, 4, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=early_morning)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED, (
            f"Expected ALLOWED at 04:00 within overnight 22:00-06:00 window, "
            f"got {temp_dim.result}: {temp_dim.reason}"
        )

    def test_overnight_window_allowed_at_exact_start(self):
        """Agent with 22:00-06:00 window should be ALLOWED at exactly 22:00."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="22:00",
                active_hours_end="06:00",
            ),
        )
        at_start = datetime(2026, 3, 11, 22, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=at_start)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED

    def test_overnight_window_allowed_at_exact_end(self):
        """Agent with 22:00-06:00 window should be ALLOWED at exactly 06:00."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="22:00",
                active_hours_end="06:00",
            ),
        )
        at_end = datetime(2026, 3, 12, 6, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=at_end)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED

    def test_overnight_window_denied_midday(self):
        """Agent with 22:00-06:00 window should be DENIED at 14:00."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="22:00",
                active_hours_end="06:00",
            ),
        )
        midday = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=midday)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED, (
            f"Expected DENIED at 14:00 outside overnight 22:00-06:00 window, got {temp_dim.result}"
        )

    def test_overnight_window_denied_just_after_end(self):
        """Agent with 22:00-06:00 window should be DENIED at 06:01."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="22:00",
                active_hours_end="06:00",
            ),
        )
        after_end = datetime(2026, 3, 12, 6, 1, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=after_end)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED


class TestTemporalBlackoutPeriods:
    """RT-15: Blackout periods should be evaluated and deny during blackout."""

    def test_blackout_period_full_date_match_denied(self):
        """Action on a blackout date (YYYY-MM-DD format) should be DENIED."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                blackout_periods=["2026-03-15"],
            ),
        )
        blackout_day = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=blackout_day)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED, (
            f"Expected DENIED on blackout date 2026-03-15, got {temp_dim.result}"
        )
        assert "blackout" in temp_dim.reason.lower()

    def test_blackout_period_month_day_match_denied(self):
        """Action on a blackout date (MM-DD format) should be DENIED any year."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                blackout_periods=["12-25"],
            ),
        )
        christmas = datetime(2026, 12, 25, 10, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=christmas)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED, (
            f"Expected DENIED on blackout date 12-25, got {temp_dim.result}"
        )

    def test_no_blackout_day_before(self):
        """Day before a blackout should be ALLOWED."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                blackout_periods=["2026-03-15"],
            ),
        )
        day_before = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=day_before)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED

    def test_multiple_blackout_periods(self):
        """Multiple blackout periods should all be enforced."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                blackout_periods=["2026-03-15", "2026-04-01", "01-01"],
            ),
        )
        # Check second blackout date
        april_fools = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=april_fools)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED

        # Check recurring date
        new_year = datetime(2027, 1, 1, 12, 0, tzinfo=UTC)
        result2 = env.evaluate_action("read", "agent-1", current_time=new_year)
        temp_dim2 = next(d for d in result2.dimensions if d.dimension == "temporal")
        assert temp_dim2.result == EvaluationResult.DENIED

    def test_blackout_combined_with_active_hours(self):
        """Blackout should deny even when within active hours."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
                blackout_periods=["2026-03-15"],
            ),
        )
        during_hours_blackout = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=during_hours_blackout)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED


class TestTemporalTimezone:
    """RT-15 / RT-35: Timezone conversion for temporal evaluation."""

    def test_timezone_converts_utc_to_configured_timezone(self):
        """When timezone is Asia/Singapore (+8), 01:00 UTC = 09:00 SGT (within 09:00-17:00)."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
                timezone="Asia/Singapore",
            ),
        )
        # 01:00 UTC = 09:00 Singapore Time
        utc_time = datetime(2026, 3, 11, 1, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=utc_time)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED, (
            f"Expected ALLOWED: 01:00 UTC = 09:00 SGT within 09:00-17:00 window, "
            f"got {temp_dim.result}: {temp_dim.reason}"
        )

    def test_timezone_denies_when_local_time_outside_window(self):
        """When timezone is Asia/Singapore (+8), 14:00 UTC = 22:00 SGT (outside 09:00-17:00)."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
                timezone="Asia/Singapore",
            ),
        )
        # 14:00 UTC = 22:00 Singapore Time
        utc_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=utc_time)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED, (
            f"Expected DENIED: 14:00 UTC = 22:00 SGT outside 09:00-17:00 window, "
            f"got {temp_dim.result}"
        )

    def test_timezone_utc_default_no_conversion(self):
        """With default timezone='UTC', no conversion occurs."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
                timezone="UTC",
            ),
        )
        utc_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=utc_time)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED

    def test_timezone_affects_blackout_evaluation(self):
        """Blackout periods should also use the configured timezone."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                timezone="Asia/Singapore",
                blackout_periods=["2026-03-15"],
            ),
        )
        # 16:00 UTC on Mar 14 = 00:00 SGT on Mar 15 -> blackout
        utc_time = datetime(2026, 3, 14, 16, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=utc_time)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED, (
            f"Expected DENIED: 16:00 UTC Mar 14 = 00:00 SGT Mar 15 (blackout), "
            f"got {temp_dim.result}"
        )


# ===========================================================================
# RT-16: Data Access path enforcement
# ===========================================================================


class TestDataAccessPathEnforcement:
    """RT-16: read_paths and write_paths should be enforced."""

    def test_read_path_allowed_when_under_read_path(self):
        """Reading from an allowed read path should be ALLOWED."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                read_paths=["reports/", "metrics/"],
            ),
        )
        result = env.evaluate_action(
            "read",
            "agent-1",
            data_paths=["reports/q1.csv"],
            access_type="read",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.ALLOWED

    def test_read_path_denied_when_outside_read_paths(self):
        """Reading from a path not under any read_path should be DENIED."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                read_paths=["reports/", "metrics/"],
            ),
        )
        result = env.evaluate_action(
            "read",
            "agent-1",
            data_paths=["secrets/credentials.json"],
            access_type="read",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.DENIED, (
            f"Expected DENIED for reading secrets/ with read_paths=['reports/', 'metrics/'], "
            f"got {data_dim.result}"
        )

    def test_write_path_allowed_when_under_write_path(self):
        """Writing to an allowed write path should be ALLOWED."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                write_paths=["drafts/", "output/"],
            ),
        )
        result = env.evaluate_action(
            "write",
            "agent-1",
            data_paths=["drafts/report.md"],
            access_type="write",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.ALLOWED

    def test_write_path_denied_when_outside_write_paths(self):
        """Writing to a path not under any write_path should be DENIED."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                write_paths=["drafts/"],
            ),
        )
        result = env.evaluate_action(
            "write",
            "agent-1",
            data_paths=["config/settings.yaml"],
            access_type="write",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.DENIED, (
            f"Expected DENIED for writing config/ with write_paths=['drafts/'], "
            f"got {data_dim.result}"
        )

    def test_multiple_data_paths_all_must_be_under_allowed(self):
        """All data_paths must be under an allowed path; one outside = DENIED."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                read_paths=["reports/", "metrics/"],
            ),
        )
        result = env.evaluate_action(
            "read",
            "agent-1",
            data_paths=["reports/q1.csv", "secrets/key.pem"],
            access_type="read",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.DENIED

    def test_empty_read_paths_no_restriction(self):
        """When read_paths is empty, no path restriction is applied."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                read_paths=[],
            ),
        )
        result = env.evaluate_action(
            "read",
            "agent-1",
            data_paths=["anything/anywhere.txt"],
            access_type="read",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.ALLOWED

    def test_blocked_data_types_still_enforced_with_paths(self):
        """blocked_data_types check should remain as an additional layer."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                read_paths=["data/"],
                blocked_data_types=["pii"],
            ),
        )
        result = env.evaluate_action(
            "read",
            "agent-1",
            data_paths=["data/users_pii.csv"],
            access_type="read",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.DENIED
        assert "pii" in data_dim.reason.lower()

    def test_read_access_type_not_checked_against_write_paths(self):
        """Read access should not be checked against write_paths."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                read_paths=["reports/"],
                write_paths=["drafts/"],
            ),
        )
        # Reading from reports/ should be allowed even though drafts/ is write-only
        result = env.evaluate_action(
            "read",
            "agent-1",
            data_paths=["reports/q1.csv"],
            access_type="read",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.ALLOWED

    def test_access_type_passed_through_evaluate_action(self):
        """access_type kwarg should flow through evaluate_action to _evaluate_data_access."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                write_paths=["output/"],
            ),
        )
        # Write to disallowed path
        result = env.evaluate_action(
            "write",
            "agent-1",
            data_paths=["secrets/token.txt"],
            access_type="write",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.DENIED

    def test_glob_pattern_matching_write_paths(self):
        """Write paths can use glob-like patterns with fnmatch."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                write_paths=["output/*.csv", "drafts/"],
            ),
        )
        result = env.evaluate_action(
            "write",
            "agent-1",
            data_paths=["output/report.csv"],
            access_type="write",
        )
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.ALLOWED


# ===========================================================================
# RT-17: Communication external_requires_approval enforcement
# ===========================================================================


class TestCommunicationExternalApproval:
    """RT-17: external_requires_approval should produce NEAR_BOUNDARY for external comms."""

    def test_external_requires_approval_returns_near_boundary(self):
        """External communication with external_requires_approval=True returns NEAR_BOUNDARY."""
        env = _make_envelope(
            communication=CommunicationConstraintConfig(
                internal_only=False,
                external_requires_approval=True,
            ),
        )
        result = env.evaluate_action("send_email", "agent-1", is_external=True)
        comm_dim = next(d for d in result.dimensions if d.dimension == "communication")
        assert comm_dim.result == EvaluationResult.NEAR_BOUNDARY, (
            f"Expected NEAR_BOUNDARY for external comm with approval required, "
            f"got {comm_dim.result}"
        )
        assert "approval" in comm_dim.reason.lower()

    def test_internal_communication_not_affected_by_approval_flag(self):
        """Internal communication (is_external=False) should not trigger approval check."""
        env = _make_envelope(
            communication=CommunicationConstraintConfig(
                internal_only=False,
                external_requires_approval=True,
            ),
        )
        result = env.evaluate_action("send_msg", "agent-1", is_external=False)
        comm_dim = next(d for d in result.dimensions if d.dimension == "communication")
        assert comm_dim.result == EvaluationResult.ALLOWED

    def test_external_no_approval_required_allowed(self):
        """External communication with external_requires_approval=False is ALLOWED."""
        env = _make_envelope(
            communication=CommunicationConstraintConfig(
                internal_only=False,
                external_requires_approval=False,
            ),
        )
        result = env.evaluate_action("send_email", "agent-1", is_external=True)
        comm_dim = next(d for d in result.dimensions if d.dimension == "communication")
        assert comm_dim.result == EvaluationResult.ALLOWED

    def test_internal_only_takes_precedence_over_approval(self):
        """When internal_only=True, that DENIED result takes precedence."""
        env = _make_envelope(
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )
        result = env.evaluate_action("send_email", "agent-1", is_external=True)
        comm_dim = next(d for d in result.dimensions if d.dimension == "communication")
        # internal_only should deny before we even check external_requires_approval
        assert comm_dim.result == EvaluationResult.DENIED

    def test_external_approval_surfaces_in_overall_result(self):
        """NEAR_BOUNDARY from communication should surface in overall_result."""
        env = _make_envelope(
            communication=CommunicationConstraintConfig(
                internal_only=False,
                external_requires_approval=True,
            ),
        )
        result = env.evaluate_action("send_email", "agent-1", is_external=True)
        assert result.overall_result == EvaluationResult.NEAR_BOUNDARY


# ===========================================================================
# RT-24: Soft-limit HELD result from financial dimension
# ===========================================================================


class TestFinancialSoftLimit:
    """RT-24: requires_approval_above_usd should produce NEAR_BOUNDARY."""

    def test_spend_above_approval_threshold_near_boundary(self):
        """Spend exceeding requires_approval_above_usd but under max returns NEAR_BOUNDARY."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                requires_approval_above_usd=200.0,
            ),
        )
        result = env.evaluate_action("purchase", "agent-1", spend_amount=250.0)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.NEAR_BOUNDARY, (
            f"Expected NEAR_BOUNDARY for $250 spend exceeding $200 approval threshold, "
            f"got {fin_dim.result}: {fin_dim.reason}"
        )
        assert "approval" in fin_dim.reason.lower()

    def test_spend_below_approval_threshold_allowed(self):
        """Spend under requires_approval_above_usd is ALLOWED (if under max too)."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                requires_approval_above_usd=200.0,
            ),
        )
        result = env.evaluate_action("purchase", "agent-1", spend_amount=150.0)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.ALLOWED

    def test_spend_exactly_at_approval_threshold_allowed(self):
        """Spend exactly at requires_approval_above_usd is NOT over the threshold (not >)."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                requires_approval_above_usd=200.0,
            ),
        )
        result = env.evaluate_action("purchase", "agent-1", spend_amount=200.0)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        # Exactly at threshold: not exceeding (not strictly greater than)
        assert fin_dim.result == EvaluationResult.ALLOWED

    def test_spend_over_max_still_denied_even_with_approval_threshold(self):
        """Spend over max_spend_usd is DENIED regardless of approval threshold."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                requires_approval_above_usd=200.0,
            ),
        )
        result = env.evaluate_action("purchase", "agent-1", spend_amount=600.0)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.DENIED

    def test_no_approval_threshold_does_not_trigger(self):
        """When requires_approval_above_usd is None, no soft-limit check occurs."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                requires_approval_above_usd=None,
            ),
        )
        result = env.evaluate_action("purchase", "agent-1", spend_amount=250.0)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.ALLOWED


# ===========================================================================
# RT-27: Cumulative budget tracking in financial envelope
# ===========================================================================


class TestCumulativeBudgetTracking:
    """RT-27: api_cost_budget_usd with cumulative_spend kwarg."""

    def test_cumulative_spend_exceeding_budget_denied(self):
        """When cumulative_spend + spend_amount > api_cost_budget_usd, DENIED."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                api_cost_budget_usd=100.0,
            ),
        )
        result = env.evaluate_action(
            "llm_call",
            "agent-1",
            spend_amount=10.0,
            cumulative_spend=95.0,
        )
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.DENIED, (
            f"Expected DENIED: cumulative $95 + $10 = $105 > budget $100, "
            f"got {fin_dim.result}: {fin_dim.reason}"
        )
        assert "cumulative" in fin_dim.reason.lower() or "budget" in fin_dim.reason.lower()

    def test_cumulative_spend_within_budget_allowed(self):
        """When cumulative_spend + spend_amount <= api_cost_budget_usd, allowed."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                api_cost_budget_usd=100.0,
            ),
        )
        result = env.evaluate_action(
            "llm_call",
            "agent-1",
            spend_amount=10.0,
            cumulative_spend=50.0,
        )
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.ALLOWED

    def test_cumulative_spend_exactly_at_budget_allowed(self):
        """When cumulative_spend + spend_amount == api_cost_budget_usd, allowed (not >)."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                api_cost_budget_usd=100.0,
            ),
        )
        result = env.evaluate_action(
            "llm_call",
            "agent-1",
            spend_amount=10.0,
            cumulative_spend=90.0,
        )
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.ALLOWED

    def test_cumulative_budget_checked_before_per_action_max(self):
        """Cumulative budget check should fire before per-action max_spend check."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                api_cost_budget_usd=100.0,
            ),
        )
        # spend_amount=5 is well under max_spend_usd=500, but cumulative exceeds budget
        result = env.evaluate_action(
            "llm_call",
            "agent-1",
            spend_amount=5.0,
            cumulative_spend=98.0,
        )
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.DENIED
        assert "cumulative" in fin_dim.reason.lower() or "budget" in fin_dim.reason.lower()

    def test_no_api_cost_budget_ignores_cumulative(self):
        """When api_cost_budget_usd is None, cumulative_spend is ignored."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                api_cost_budget_usd=None,
            ),
        )
        result = env.evaluate_action(
            "llm_call",
            "agent-1",
            spend_amount=10.0,
            cumulative_spend=9999.0,
        )
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.ALLOWED

    def test_zero_cumulative_spend_default(self):
        """Default cumulative_spend=0.0 should not affect evaluation."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                api_cost_budget_usd=100.0,
            ),
        )
        # No cumulative_spend passed -> default 0.0
        result = env.evaluate_action("llm_call", "agent-1", spend_amount=10.0)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.ALLOWED


# ===========================================================================
# Backward compatibility: existing behavior must not break
# ===========================================================================


class TestBackwardCompatibility:
    """Ensure existing callers without new kwargs are not broken."""

    def test_evaluate_action_without_new_kwargs(self):
        """Calling evaluate_action without access_type or cumulative_spend works."""
        env = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        result = env.evaluate_action("read", "agent-1", spend_amount=10.0)
        assert result.is_allowed

    def test_data_access_without_access_type_still_checks_blocked(self):
        """Without access_type, blocked_data_types check still works."""
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii"],
            ),
        )
        result = env.evaluate_action("read", "agent-1", data_paths=["users/pii/data"])
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.DENIED

    def test_existing_temporal_normal_window_still_works(self):
        """Normal (non-overnight) active hour windows should still work as before."""
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        # Within window
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=work_time)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED

        # Outside window
        late_time = datetime(2026, 3, 11, 22, 0, tzinfo=UTC)
        result2 = env.evaluate_action("read", "agent-1", current_time=late_time)
        temp_dim2 = next(d for d in result2.dimensions if d.dimension == "temporal")
        assert temp_dim2.result == EvaluationResult.DENIED
