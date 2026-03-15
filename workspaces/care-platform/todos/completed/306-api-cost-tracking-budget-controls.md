# 306: API Cost Tracking and Budget Controls (M-6 Mitigation)

**Milestone**: 3 — Persistence Layer
**Priority**: Medium
**Estimated effort**: Small
**Depends on**: 301, 401
**Completed**: 2026-03-12
**Verified by**: CostTracker + ApiCostRecord + BudgetAlert + CostReport in `care_platform/persistence/cost_tracking.py`; 41 unit tests pass in `tests/unit/persistence/test_cost_tracking.py`

## Description

Implement per-agent LLM API call cost tracking, configurable budget thresholds, and alert mechanisms. This directly addresses red team finding M-6 (API cost risk). Without tracking, an agent team at higher posture levels can consume unbounded API budget. With tracking, every LLM call is recorded, budgets are configurable per agent and per team, and the human operator is alerted before overspend occurs.

## Tasks

- [ ] Implement `ApiCostRecord` model:
  - agent_id, team_id, provider, model, input_tokens, output_tokens, cost_usd, timestamp
  - action_id: link back to the audit anchor for the action that caused this call
- [ ] Implement `CostTracker`:
  - `CostTracker.record(agent_id, call_details)` — record each LLM API call
  - `CostTracker.daily_spend(agent_id) -> Decimal` — total cost for today
  - `CostTracker.monthly_spend(team_id) -> Decimal` — total team cost for current month
  - `CostTracker.spend_report(team_id, days=30) -> CostReport` — full spending breakdown
- [ ] Implement budget configuration in constraint envelope:
  - `FinancialConstraints.daily_api_budget_usd`: per-agent daily limit (default $0 = no LLM access)
  - `FinancialConstraints.monthly_api_budget_usd`: per-team monthly limit
  - `FinancialConstraints.alert_threshold_pct`: alert when X% of budget consumed (default 80%)
- [ ] Implement budget enforcement:
  - Before each LLM call: check `CostTracker.daily_spend(agent_id)` against daily budget
  - If spend >= budget: block the LLM call, log to audit, queue for human decision
  - If spend >= alert_threshold: flag action (FLAGGED gradient level), continue but notify
- [ ] Implement alert mechanism:
  - Alert when daily budget 80% consumed: log to audit + add to session briefing
  - Alert when daily budget 100% consumed: HELD action, require human to approve additional spend
  - Alert when monthly team budget 90% consumed: notify operator via session briefing
- [ ] Implement CLI commands:
  - `care-platform cost report --team dm --days 30` — cost report
  - `care-platform cost set-budget --agent content-creator --daily 2.00` — set budget
- [ ] Write integration tests:
  - Cost recorded correctly for a simulated LLM call
  - Budget enforcement blocks call when limit reached
  - Alert triggers correctly at threshold percentage

## Acceptance Criteria

- Every LLM API call recorded with cost breakdown
- Budget enforcement blocks or flags when limits reached
- Alerts generated before hard limits hit
- CLI report shows per-agent and per-team spend
- Integration tests passing

## Dependencies

- 301: DataFlow schema (api_cost_records table)
- 401: Kaizen agent bridge (intercept LLM calls for recording)
- 103: Constraint envelope model (financial constraints field)

## References

- Red team finding M-6: API cost risk — `01-analysis/01-research/05-red-team-analysis.md`
- Financial constraint dimension: CARE specification, constraint dimensions
