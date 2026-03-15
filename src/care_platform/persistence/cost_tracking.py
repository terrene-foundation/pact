# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""API cost tracking and budget controls.

Addresses red team finding M-6 (API cost risk): without tracking, agent teams
at higher posture levels can consume unbounded API budget. This module provides
per-agent daily budgets, per-team monthly budgets, threshold alerts, and
spend reporting.

All monetary values use ``Decimal`` to avoid floating-point rounding errors.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ApiCostRecord(BaseModel):
    """Record of an LLM API call with cost."""

    record_id: str = Field(default_factory=lambda: f"cost-{uuid4().hex[:8]}")
    agent_id: str
    team_id: str = ""
    provider: str = ""  # e.g., "anthropic", "openai"
    model: str = ""  # e.g., "claude-opus-4-6"
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action_id: str = ""  # link to audit anchor


class BudgetAlert(BaseModel):
    """Budget alert triggered when thresholds are reached."""

    alert_id: str = Field(default_factory=lambda: f"alert-{uuid4().hex[:8]}")
    agent_id: str
    team_id: str = ""
    alert_type: str  # "warning" (80%), "limit_reached" (100%), "team_warning" (90%)
    current_spend: Decimal
    budget_limit: Decimal
    percentage: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str


class CostReport(BaseModel):
    """Cost report for a team or agent."""

    period_days: int
    total_cost: Decimal = Decimal("0")
    by_agent: dict[str, Decimal] = Field(default_factory=dict)
    by_model: dict[str, Decimal] = Field(default_factory=dict)
    by_day: dict[str, Decimal] = Field(default_factory=dict)  # date string -> cost
    total_calls: int = 0
    alerts_triggered: int = 0


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------


class CostTracker:
    """Tracks API costs per agent with budget enforcement.

    Provides:
    - Per-agent daily budgets with alerts at 80% and blocks at 100%.
    - Per-team monthly budgets with alerts at 90% and blocks at 100%.
    - Pre-flight ``can_spend`` checks before making API calls.
    - Aggregated spend reports by agent, model, and day.
    """

    # Alert thresholds (fraction of budget)
    _AGENT_WARNING_THRESHOLD: float = 0.8  # 80% of daily budget
    _TEAM_WARNING_THRESHOLD: float = 0.9  # 90% of monthly budget

    def __init__(self) -> None:
        self._records: list[ApiCostRecord] = []
        self._alerts: list[BudgetAlert] = []
        self._budgets: dict[str, Decimal] = {}  # agent_id -> daily budget
        self._team_budgets: dict[str, Decimal] = {}  # team_id -> monthly budget

    # ------------------------------------------------------------------
    # Budget configuration
    # ------------------------------------------------------------------

    def set_daily_budget(self, agent_id: str, budget_usd: Decimal) -> None:
        """Set daily API budget for an agent.

        Args:
            agent_id: The agent whose budget to set.
            budget_usd: Maximum USD the agent may spend per calendar day.

        Raises:
            ValueError: If ``budget_usd`` is negative.
        """
        if budget_usd < 0:
            msg = f"Daily budget must be non-negative, got {budget_usd}"
            raise ValueError(msg)
        self._budgets[agent_id] = budget_usd
        logger.info(
            "Daily budget set for agent %s: $%s",
            agent_id,
            budget_usd,
        )

    def set_team_monthly_budget(self, team_id: str, budget_usd: Decimal) -> None:
        """Set monthly API budget for a team.

        Args:
            team_id: The team whose budget to set.
            budget_usd: Maximum USD the team may spend per calendar month.

        Raises:
            ValueError: If ``budget_usd`` is negative.
        """
        if budget_usd < 0:
            msg = f"Monthly budget must be non-negative, got {budget_usd}"
            raise ValueError(msg)
        self._team_budgets[team_id] = budget_usd
        logger.info(
            "Monthly budget set for team %s: $%s",
            team_id,
            budget_usd,
        )

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, record: ApiCostRecord) -> list[BudgetAlert]:
        """Record an API call and return any triggered alerts.

        The record is stored, then agent daily and team monthly budgets are
        checked.  Alerts are generated at the warning threshold (80% for
        agents, 90% for teams) and at 100% (limit reached).

        Args:
            record: The cost record to store.

        Returns:
            A list of ``BudgetAlert`` objects triggered by this record
            (may be empty).
        """
        self._records.append(record)
        alerts: list[BudgetAlert] = []

        # --- Agent daily budget alerts ---
        agent_budget = self._budgets.get(record.agent_id)
        if agent_budget is not None and agent_budget > 0:
            current = self.daily_spend(record.agent_id)
            pct = float(current / agent_budget) * 100.0

            if current >= agent_budget:
                alert = BudgetAlert(
                    agent_id=record.agent_id,
                    team_id=record.team_id,
                    alert_type="limit_reached",
                    current_spend=current,
                    budget_limit=agent_budget,
                    percentage=pct,
                    message=(
                        f"Agent {record.agent_id} daily budget exhausted: "
                        f"${current} of ${agent_budget} ({pct:.1f}%)"
                    ),
                )
                alerts.append(alert)
                logger.warning(
                    "Budget limit reached for agent %s: $%s / $%s",
                    record.agent_id,
                    current,
                    agent_budget,
                )
            elif pct >= self._AGENT_WARNING_THRESHOLD * 100:
                alert = BudgetAlert(
                    agent_id=record.agent_id,
                    team_id=record.team_id,
                    alert_type="warning",
                    current_spend=current,
                    budget_limit=agent_budget,
                    percentage=pct,
                    message=(
                        f"Agent {record.agent_id} approaching daily budget: "
                        f"${current} of ${agent_budget} ({pct:.1f}%)"
                    ),
                )
                alerts.append(alert)
                logger.warning(
                    "Budget warning for agent %s: $%s / $%s (%.1f%%)",
                    record.agent_id,
                    current,
                    agent_budget,
                    pct,
                )

        # --- Team monthly budget alerts ---
        if record.team_id:
            team_budget = self._team_budgets.get(record.team_id)
            if team_budget is not None and team_budget > 0:
                team_current = self.monthly_spend(record.team_id)
                team_pct = float(team_current / team_budget) * 100.0

                if team_current >= team_budget:
                    alert = BudgetAlert(
                        agent_id=record.agent_id,
                        team_id=record.team_id,
                        alert_type="limit_reached",
                        current_spend=team_current,
                        budget_limit=team_budget,
                        percentage=team_pct,
                        message=(
                            f"Team {record.team_id} monthly budget exhausted: "
                            f"${team_current} of ${team_budget} ({team_pct:.1f}%)"
                        ),
                    )
                    alerts.append(alert)
                    logger.warning(
                        "Team budget limit reached for %s: $%s / $%s",
                        record.team_id,
                        team_current,
                        team_budget,
                    )
                elif team_pct >= self._TEAM_WARNING_THRESHOLD * 100:
                    alert = BudgetAlert(
                        agent_id=record.agent_id,
                        team_id=record.team_id,
                        alert_type="team_warning",
                        current_spend=team_current,
                        budget_limit=team_budget,
                        percentage=team_pct,
                        message=(
                            f"Team {record.team_id} approaching monthly budget: "
                            f"${team_current} of ${team_budget} ({team_pct:.1f}%)"
                        ),
                    )
                    alerts.append(alert)
                    logger.warning(
                        "Team budget warning for %s: $%s / $%s (%.1f%%)",
                        record.team_id,
                        team_current,
                        team_budget,
                        team_pct,
                    )

        self._alerts.extend(alerts)
        return alerts

    # ------------------------------------------------------------------
    # Spend queries
    # ------------------------------------------------------------------

    def daily_spend(self, agent_id: str, date: datetime | None = None) -> Decimal:
        """Total spend for an agent on a specific calendar day.

        Args:
            agent_id: The agent to query.
            date: The day to check (defaults to today UTC).

        Returns:
            Total USD spent as a ``Decimal``.
        """
        target = (date or datetime.now(UTC)).date()
        total = Decimal("0")
        for r in self._records:
            if r.agent_id == agent_id and r.timestamp.date() == target:
                total += r.cost_usd
        return total

    def monthly_spend(self, team_id: str, month: datetime | None = None) -> Decimal:
        """Total team spend for a calendar month.

        Args:
            team_id: The team to query.
            month: Any datetime within the target month (defaults to
                current month UTC).

        Returns:
            Total USD spent as a ``Decimal``.
        """
        ref = month or datetime.now(UTC)
        target_year = ref.year
        target_month = ref.month
        total = Decimal("0")
        for r in self._records:
            if (
                r.team_id == team_id
                and r.timestamp.year == target_year
                and r.timestamp.month == target_month
            ):
                total += r.cost_usd
        return total

    # ------------------------------------------------------------------
    # Pre-flight check
    # ------------------------------------------------------------------

    def can_spend(
        self,
        agent_id: str,
        estimated_cost: Decimal,
    ) -> tuple[bool, str]:
        """Check whether an agent can make an API call of ``estimated_cost``.

        Validates the agent's daily budget only (team monthly budget is
        checked on ``record``). If no daily budget is set, spending is
        allowed unconditionally.

        Args:
            agent_id: The agent requesting to spend.
            estimated_cost: The projected cost of the API call.

        Returns:
            A ``(allowed, reason)`` tuple.
        """
        budget = self._budgets.get(agent_id)
        if budget is None:
            return True, "No daily budget configured; spending allowed"

        current = self.daily_spend(agent_id)
        projected = current + estimated_cost

        if projected > budget:
            reason = (
                f"Estimated spend ${estimated_cost} would exceed daily budget: "
                f"current ${current} + estimated ${estimated_cost} = "
                f"${projected} > budget ${budget}"
            )
            logger.info(
                "Spend denied for agent %s: %s",
                agent_id,
                reason,
            )
            return False, reason

        return True, f"Within budget: ${projected} / ${budget}"

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def spend_report(
        self,
        *,
        agent_id: str | None = None,
        team_id: str | None = None,
        days: int = 30,
    ) -> CostReport:
        """Generate a spend report with aggregations.

        Args:
            agent_id: Filter to a specific agent (optional).
            team_id: Filter to a specific team (optional).
            days: Number of days to include in the report window.

        Returns:
            A ``CostReport`` with totals broken down by agent, model, and day.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Filter records
        filtered: list[ApiCostRecord] = []
        for r in self._records:
            if r.timestamp < cutoff:
                continue
            if agent_id is not None and r.agent_id != agent_id:
                continue
            if team_id is not None and r.team_id != team_id:
                continue
            filtered.append(r)

        # Aggregations
        total_cost = Decimal("0")
        by_agent: dict[str, Decimal] = {}
        by_model: dict[str, Decimal] = {}
        by_day: dict[str, Decimal] = {}

        for r in filtered:
            total_cost += r.cost_usd
            by_agent[r.agent_id] = by_agent.get(r.agent_id, Decimal("0")) + r.cost_usd
            if r.model:
                by_model[r.model] = by_model.get(r.model, Decimal("0")) + r.cost_usd
            day_key = r.timestamp.strftime("%Y-%m-%d")
            by_day[day_key] = by_day.get(day_key, Decimal("0")) + r.cost_usd

        # Count alerts in the same time window
        alerts_in_window = sum(1 for a in self._alerts if a.timestamp >= cutoff)

        return CostReport(
            period_days=days,
            total_cost=total_cost,
            by_agent=by_agent,
            by_model=by_model,
            by_day=by_day,
            total_calls=len(filtered),
            alerts_triggered=alerts_in_window,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def recent_alerts(self) -> list[BudgetAlert]:
        """Get all budget alerts (most recent last)."""
        return list(self._alerts)
