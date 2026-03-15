# Red Team Finding 1006: API Cost Risk

**Finding ID**: M-6
**Severity**: Medium
**Status**: RESOLVED -- cost tracking fully implemented
**Date**: 2026-03-12

---

## Finding

Running multiple agent teams daily could consume unbounded LLM API budget. Without cost tracking and budget controls, API costs could reach hundreds or thousands of dollars per month -- potentially threatening Foundation sustainability, especially in the pre-incorporation phase.

## Risk/Impact

**Medium**. Uncontrolled API costs are a financial risk that could:

- Exhaust Foundation operating budget on LLM API calls
- Force sudden service reduction if costs spike unexpectedly
- Undermine the "sustainable solo founder" operating model
- Create perverse incentives to reduce governance (fewer verification calls = lower cost)

## Analysis

### Estimated API Costs Per Team

| Team         | Daily Activity                                             | Estimated Daily Cost | Monthly Cost         |
| ------------ | ---------------------------------------------------------- | -------------------- | -------------------- |
| DM/Media     | ~20 content drafts, 5 analytics reports, 10 scheduling ops | $5-15                | $150-450             |
| Standards    | ~5 spec drafts, 10 cross-reference checks                  | $3-8                 | $90-240              |
| Governance   | ~3 compliance checks, 2 report generations                 | $2-5                 | $60-150              |
| Partnerships | ~5 research queries, 3 draft emails                        | $3-8                 | $90-240              |
| **Total**    |                                                            | **$13-36/day**       | **$390-1,080/month** |

These estimates assume a mix of models (cheaper models for routine tasks, more capable models for complex generation). Actual costs depend heavily on model selection strategy.

### Implemented Mitigations

#### Cost Tracking Module

**Location**: `care_platform/persistence/cost_tracking.py`
**Tests**: `tests/unit/persistence/test_cost_tracking.py`

The `CostTracker` provides comprehensive API cost management:

**Per-Agent Daily Budgets**:

- Each agent has a configurable daily budget in USD
- Pre-flight `can_spend()` check before every API call -- blocks calls that would exceed the daily budget
- Warning alert at 80% of daily budget
- Hard block at 100% of daily budget

**Per-Team Monthly Budgets**:

- Each team has a configurable monthly budget in USD
- Warning alert at 90% of monthly budget
- Hard block at 100% of monthly budget

**Budget Alerts** (`BudgetAlert` model):

- Alert type: `warning` (80% agent daily), `team_warning` (90% team monthly), `limit_reached` (100%)
- Includes current spend, budget limit, percentage, and human-readable message
- Alerts are returned from the `record()` method so callers can act immediately

**Spend Reporting** (`CostReport` model):

- Aggregated by agent, by model, and by day
- Configurable reporting window (default 30 days)
- Tracks total calls and alerts triggered
- Enables trend analysis and budget forecasting

**Cost Records** (`ApiCostRecord` model):

- Per-call tracking: agent, team, provider, model, input/output tokens, cost in USD
- Links to audit anchors via `action_id` for full traceability
- Uses `Decimal` for monetary values (no floating-point rounding errors)

### Cost Optimization Strategies

The following strategies reduce API costs without compromising governance:

1. **Progressive model selection**: Use cheaper models (Haiku, GPT-4o-mini) for routine tasks (formatting, scheduling, simple queries). Escalate to capable models (Opus, GPT-4) only for complex generation (novel content, strategic analysis). The agent definition can specify model tiers per action type.

2. **Caching**: Frequent queries with stable answers (e.g., "what are the Foundation's core entities?") can be cached. The knowledge base serves as a warm cache for institutional knowledge.

3. **Batch processing**: Analytics reports, compliance checks, and similar periodic tasks can be batched rather than executed individually. One larger API call is often cheaper than many small ones.

4. **Template-based generation**: For routine content (weekly reports, standard social media posts), template-based generation with variable substitution is cheaper than open-ended generation.

5. **Local model fallback**: For low-stakes, high-volume tasks (formatting, simple classification), local models (Llama, Mistral) eliminate API costs entirely. The multi-backend architecture (Gap 4) enables this naturally.

### Integration with Constraint Dimensions

Cost tracking maps directly to EATP constraint dimensions:

| EATP Dimension  | Cost Control                                    |
| --------------- | ----------------------------------------------- |
| **Financial**   | Per-agent daily budget, per-team monthly budget |
| **Temporal**    | Rate limits per agent (prevent burst spending)  |
| **Operational** | Model selection by task complexity              |

This means cost controls are not bolted on -- they are part of the constraint envelope that governs every agent action.

## Conclusion

The API cost risk is fully mitigated through the implemented cost tracking module. Per-agent daily budgets and per-team monthly budgets provide hard controls. Budget alerts at 80% (agent) and 90% (team) provide early warning. Pre-flight `can_spend()` checks prevent budget overruns before they happen. The cost tracking integrates with the EATP constraint model, making cost governance a native part of the trust framework rather than an afterthought.
