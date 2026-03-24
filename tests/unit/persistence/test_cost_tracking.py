# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for API cost tracking and budget controls (M-6 red team finding)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pact_platform.trust.store.cost_tracking import (
    ApiCostRecord,
    CostTracker,
)


def _make_record(
    agent_id: str = "agent-1",
    team_id: str = "team-ops",
    cost_usd: Decimal | str = "0.05",
    provider: str = "anthropic",
    model: str = "claude-opus-4-6",
    input_tokens: int = 1000,
    output_tokens: int = 500,
    timestamp: datetime | None = None,
) -> ApiCostRecord:
    """Helper to create an ApiCostRecord with sensible defaults."""
    cost = Decimal(cost_usd) if isinstance(cost_usd, str) else cost_usd
    return ApiCostRecord(
        agent_id=agent_id,
        team_id=team_id,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        **({"timestamp": timestamp} if timestamp is not None else {}),
    )


class TestApiCostRecord:
    """Test that API cost records are created and stored correctly."""

    def test_record_has_unique_id(self):
        r1 = _make_record()
        r2 = _make_record()
        assert r1.record_id.startswith("cost-")
        assert r2.record_id.startswith("cost-")
        assert r1.record_id != r2.record_id

    def test_record_fields_stored(self):
        r = _make_record(
            agent_id="agent-x",
            team_id="team-eng",
            cost_usd="0.12",
            provider="openai",
            model="gpt-4",
            input_tokens=2000,
            output_tokens=800,
        )
        assert r.agent_id == "agent-x"
        assert r.team_id == "team-eng"
        assert r.cost_usd == Decimal("0.12")
        assert r.provider == "openai"
        assert r.model == "gpt-4"
        assert r.input_tokens == 2000
        assert r.output_tokens == 800

    def test_record_has_timestamp(self):
        before = datetime.now(UTC)
        r = _make_record()
        after = datetime.now(UTC)
        assert before <= r.timestamp <= after

    def test_cost_uses_decimal_not_float(self):
        r = _make_record(cost_usd="0.10")
        assert isinstance(r.cost_usd, Decimal)
        assert r.cost_usd == Decimal("0.10")


class TestRecordStorage:
    """Test that CostTracker correctly stores recorded API calls."""

    def test_record_stored(self):
        tracker = CostTracker()
        record = _make_record()
        tracker.record(record)
        # Verify it is retrievable through daily spend
        assert tracker.daily_spend("agent-1") == Decimal("0.05")

    def test_multiple_records_stored(self):
        tracker = CostTracker()
        tracker.record(_make_record(cost_usd="0.10"))
        tracker.record(_make_record(cost_usd="0.20"))
        tracker.record(_make_record(cost_usd="0.30"))
        assert tracker.daily_spend("agent-1") == Decimal("0.60")


class TestDailySpend:
    """Test daily spend calculation for agents."""

    def test_daily_spend_today(self):
        tracker = CostTracker()
        tracker.record(_make_record(agent_id="agent-1", cost_usd="0.10"))
        tracker.record(_make_record(agent_id="agent-1", cost_usd="0.25"))
        assert tracker.daily_spend("agent-1") == Decimal("0.35")

    def test_daily_spend_excludes_other_agents(self):
        tracker = CostTracker()
        tracker.record(_make_record(agent_id="agent-1", cost_usd="0.10"))
        tracker.record(_make_record(agent_id="agent-2", cost_usd="0.50"))
        assert tracker.daily_spend("agent-1") == Decimal("0.10")
        assert tracker.daily_spend("agent-2") == Decimal("0.50")

    def test_daily_spend_excludes_other_dates(self):
        tracker = CostTracker()
        today = datetime.now(UTC)
        yesterday = today - timedelta(days=1)
        tracker.record(_make_record(cost_usd="0.10", timestamp=today))
        tracker.record(_make_record(cost_usd="0.90", timestamp=yesterday))
        assert tracker.daily_spend("agent-1") == Decimal("0.10")

    def test_daily_spend_specific_date(self):
        tracker = CostTracker()
        target_date = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
        tracker.record(_make_record(cost_usd="0.50", timestamp=target_date))
        tracker.record(_make_record(cost_usd="0.70", timestamp=target_date + timedelta(days=1)))
        assert tracker.daily_spend("agent-1", date=target_date) == Decimal("0.50")

    def test_daily_spend_no_records_returns_zero(self):
        tracker = CostTracker()
        assert tracker.daily_spend("agent-1") == Decimal("0")


class TestMonthlySpend:
    """Test monthly team spend calculation."""

    def test_monthly_spend_current_month(self):
        tracker = CostTracker()
        tracker.record(_make_record(agent_id="a1", team_id="team-ops", cost_usd="1.00"))
        tracker.record(_make_record(agent_id="a2", team_id="team-ops", cost_usd="2.00"))
        assert tracker.monthly_spend("team-ops") == Decimal("3.00")

    def test_monthly_spend_excludes_other_teams(self):
        tracker = CostTracker()
        tracker.record(_make_record(agent_id="a1", team_id="team-ops", cost_usd="1.00"))
        tracker.record(_make_record(agent_id="a2", team_id="team-eng", cost_usd="5.00"))
        assert tracker.monthly_spend("team-ops") == Decimal("1.00")

    def test_monthly_spend_excludes_other_months(self):
        tracker = CostTracker()
        now = datetime.now(UTC)
        last_month = (
            now.replace(month=now.month - 1)
            if now.month > 1
            else now.replace(year=now.year - 1, month=12)
        )
        tracker.record(_make_record(team_id="team-ops", cost_usd="1.00", timestamp=now))
        tracker.record(_make_record(team_id="team-ops", cost_usd="9.00", timestamp=last_month))
        assert tracker.monthly_spend("team-ops") == Decimal("1.00")

    def test_monthly_spend_specific_month(self):
        tracker = CostTracker()
        feb = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
        mar = datetime(2026, 3, 5, 12, 0, tzinfo=UTC)
        tracker.record(_make_record(team_id="team-ops", cost_usd="2.00", timestamp=feb))
        tracker.record(_make_record(team_id="team-ops", cost_usd="3.00", timestamp=mar))
        assert tracker.monthly_spend("team-ops", month=feb) == Decimal("2.00")

    def test_monthly_spend_no_records_returns_zero(self):
        tracker = CostTracker()
        assert tracker.monthly_spend("team-ops") == Decimal("0")


class TestBudgetEnforcement:
    """Test that budget limits block spending when exhausted."""

    def test_can_spend_when_under_budget(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("10.00"))
        allowed, reason = tracker.can_spend("agent-1", Decimal("1.00"))
        assert allowed is True

    def test_can_spend_blocked_when_budget_exhausted(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("1.00"))
        tracker.record(_make_record(agent_id="agent-1", cost_usd="0.90"))
        allowed, reason = tracker.can_spend("agent-1", Decimal("0.20"))
        assert allowed is False
        assert "exceed" in reason.lower() or "budget" in reason.lower()

    def test_can_spend_blocked_at_exact_limit(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("1.00"))
        tracker.record(_make_record(agent_id="agent-1", cost_usd="1.00"))
        allowed, reason = tracker.can_spend("agent-1", Decimal("0.01"))
        assert allowed is False

    def test_can_spend_without_budget_set(self):
        """No budget set means no enforcement -- spending is allowed."""
        tracker = CostTracker()
        allowed, reason = tracker.can_spend("agent-1", Decimal("100.00"))
        assert allowed is True

    def test_team_budget_blocks_when_exhausted(self):
        tracker = CostTracker()
        tracker.set_team_monthly_budget("team-ops", Decimal("5.00"))
        tracker.record(_make_record(agent_id="a1", team_id="team-ops", cost_usd="5.00"))
        # Record returns alerts when budget is hit
        alerts = tracker.record(_make_record(agent_id="a2", team_id="team-ops", cost_usd="0.01"))
        # Team budget should have been hit
        team_alerts = [a for a in alerts if a.alert_type == "limit_reached"]
        assert len(team_alerts) >= 1


class TestBudgetAlerts:
    """Test that alerts fire at correct thresholds."""

    def test_alert_at_80_percent_threshold(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("10.00"))
        # Record enough to cross 80% ($8.00+)
        alerts = tracker.record(_make_record(agent_id="agent-1", cost_usd="8.50"))
        warning_alerts = [a for a in alerts if a.alert_type == "warning"]
        assert len(warning_alerts) == 1
        assert warning_alerts[0].percentage >= 80.0

    def test_alert_at_100_percent_limit(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("10.00"))
        alerts = tracker.record(_make_record(agent_id="agent-1", cost_usd="10.00"))
        limit_alerts = [a for a in alerts if a.alert_type == "limit_reached"]
        assert len(limit_alerts) == 1

    def test_no_alert_under_threshold(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("10.00"))
        alerts = tracker.record(_make_record(agent_id="agent-1", cost_usd="2.00"))
        assert len(alerts) == 0

    def test_team_alert_at_90_percent(self):
        tracker = CostTracker()
        tracker.set_team_monthly_budget("team-ops", Decimal("100.00"))
        alerts = tracker.record(_make_record(agent_id="a1", team_id="team-ops", cost_usd="91.00"))
        team_alerts = [a for a in alerts if a.alert_type == "team_warning"]
        assert len(team_alerts) == 1
        assert team_alerts[0].percentage >= 90.0

    def test_alert_contains_budget_info(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("10.00"))
        alerts = tracker.record(_make_record(agent_id="agent-1", cost_usd="9.00"))
        assert len(alerts) >= 1
        alert = alerts[0]
        assert alert.agent_id == "agent-1"
        assert alert.budget_limit == Decimal("10.00")
        assert alert.current_spend == Decimal("9.00")
        assert alert.message  # message must not be empty

    def test_recent_alerts_property(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("1.00"))
        tracker.record(_make_record(agent_id="agent-1", cost_usd="0.90"))
        assert len(tracker.recent_alerts) >= 1


class TestCanSpend:
    """Test pre-flight spending checks."""

    def test_returns_false_when_budget_exhausted(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("5.00"))
        tracker.record(_make_record(agent_id="agent-1", cost_usd="5.00"))
        allowed, reason = tracker.can_spend("agent-1", Decimal("0.01"))
        assert allowed is False
        assert reason  # reason must not be empty

    def test_returns_true_when_budget_available(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("10.00"))
        tracker.record(_make_record(agent_id="agent-1", cost_usd="3.00"))
        allowed, reason = tracker.can_spend("agent-1", Decimal("2.00"))
        assert allowed is True

    def test_considers_estimated_cost_in_check(self):
        """Should check current_spend + estimated_cost <= budget."""
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("10.00"))
        tracker.record(_make_record(agent_id="agent-1", cost_usd="9.00"))
        # $9 spent + $2 estimated = $11 > $10 budget
        allowed, _ = tracker.can_spend("agent-1", Decimal("2.00"))
        assert allowed is False
        # $9 spent + $0.50 estimated = $9.50 <= $10 budget
        allowed, _ = tracker.can_spend("agent-1", Decimal("0.50"))
        assert allowed is True


class TestSpendReport:
    """Test spend report generation with aggregations."""

    def test_report_aggregates_by_agent(self):
        tracker = CostTracker()
        tracker.record(_make_record(agent_id="a1", cost_usd="1.00"))
        tracker.record(_make_record(agent_id="a1", cost_usd="2.00"))
        tracker.record(_make_record(agent_id="a2", cost_usd="3.00"))
        report = tracker.spend_report(days=30)
        assert report.by_agent["a1"] == Decimal("3.00")
        assert report.by_agent["a2"] == Decimal("3.00")
        assert report.total_cost == Decimal("6.00")

    def test_report_aggregates_by_model(self):
        tracker = CostTracker()
        tracker.record(_make_record(model="claude-opus-4-6", cost_usd="2.00"))
        tracker.record(_make_record(model="claude-opus-4-6", cost_usd="1.00"))
        tracker.record(_make_record(model="gpt-4", cost_usd="0.50"))
        report = tracker.spend_report(days=30)
        assert report.by_model["claude-opus-4-6"] == Decimal("3.00")
        assert report.by_model["gpt-4"] == Decimal("0.50")

    def test_report_total_calls(self):
        tracker = CostTracker()
        tracker.record(_make_record(cost_usd="0.10"))
        tracker.record(_make_record(cost_usd="0.20"))
        tracker.record(_make_record(cost_usd="0.30"))
        report = tracker.spend_report(days=30)
        assert report.total_calls == 3

    def test_report_respects_days_filter(self):
        tracker = CostTracker()
        now = datetime.now(UTC)
        old = now - timedelta(days=45)
        tracker.record(_make_record(cost_usd="1.00", timestamp=now))
        tracker.record(_make_record(cost_usd="5.00", timestamp=old))
        report = tracker.spend_report(days=30)
        assert report.total_cost == Decimal("1.00")
        assert report.total_calls == 1

    def test_report_by_agent_id_filter(self):
        tracker = CostTracker()
        tracker.record(_make_record(agent_id="a1", cost_usd="1.00"))
        tracker.record(_make_record(agent_id="a2", cost_usd="2.00"))
        report = tracker.spend_report(agent_id="a1", days=30)
        assert report.total_cost == Decimal("1.00")
        assert "a1" in report.by_agent
        assert "a2" not in report.by_agent

    def test_report_by_team_id_filter(self):
        tracker = CostTracker()
        tracker.record(_make_record(agent_id="a1", team_id="team-ops", cost_usd="1.00"))
        tracker.record(_make_record(agent_id="a2", team_id="team-eng", cost_usd="2.00"))
        report = tracker.spend_report(team_id="team-ops", days=30)
        assert report.total_cost == Decimal("1.00")

    def test_report_includes_alerts_count(self):
        tracker = CostTracker()
        tracker.set_daily_budget("agent-1", Decimal("1.00"))
        # This will trigger alerts
        tracker.record(_make_record(agent_id="agent-1", cost_usd="0.90"))
        report = tracker.spend_report(days=30)
        assert report.alerts_triggered >= 1

    def test_report_aggregates_by_day(self):
        tracker = CostTracker()
        day1 = datetime(2026, 3, 10, 10, 0, tzinfo=UTC)
        day2 = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)
        tracker.record(_make_record(cost_usd="1.00", timestamp=day1))
        tracker.record(_make_record(cost_usd="2.00", timestamp=day1))
        tracker.record(_make_record(cost_usd="3.00", timestamp=day2))
        report = tracker.spend_report(days=30)
        assert report.by_day["2026-03-10"] == Decimal("3.00")
        assert report.by_day["2026-03-11"] == Decimal("3.00")


class TestMultiAgentTracking:
    """Test that multiple agents are tracked independently."""

    def test_agents_tracked_independently(self):
        tracker = CostTracker()
        tracker.set_daily_budget("a1", Decimal("5.00"))
        tracker.set_daily_budget("a2", Decimal("10.00"))
        tracker.record(_make_record(agent_id="a1", cost_usd="4.00"))
        tracker.record(_make_record(agent_id="a2", cost_usd="3.00"))
        assert tracker.daily_spend("a1") == Decimal("4.00")
        assert tracker.daily_spend("a2") == Decimal("3.00")
        # a1 near budget, a2 is not
        allowed_a1, _ = tracker.can_spend("a1", Decimal("2.00"))
        allowed_a2, _ = tracker.can_spend("a2", Decimal("2.00"))
        assert allowed_a1 is False
        assert allowed_a2 is True

    def test_team_budget_across_agents(self):
        tracker = CostTracker()
        tracker.set_team_monthly_budget("team-ops", Decimal("10.00"))
        tracker.record(_make_record(agent_id="a1", team_id="team-ops", cost_usd="4.00"))
        tracker.record(_make_record(agent_id="a2", team_id="team-ops", cost_usd="3.00"))
        tracker.record(_make_record(agent_id="a3", team_id="team-ops", cost_usd="2.00"))
        assert tracker.monthly_spend("team-ops") == Decimal("9.00")

    def test_different_teams_independent(self):
        tracker = CostTracker()
        tracker.set_team_monthly_budget("team-ops", Decimal("10.00"))
        tracker.set_team_monthly_budget("team-eng", Decimal("20.00"))
        tracker.record(_make_record(agent_id="a1", team_id="team-ops", cost_usd="9.50"))
        tracker.record(_make_record(agent_id="a2", team_id="team-eng", cost_usd="5.00"))
        assert tracker.monthly_spend("team-ops") == Decimal("9.50")
        assert tracker.monthly_spend("team-eng") == Decimal("5.00")
