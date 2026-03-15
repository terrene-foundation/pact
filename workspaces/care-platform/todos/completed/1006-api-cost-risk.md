# 1006: API Cost Risk Modeling (M-6)

**Milestone**: 10 — Red Team Findings
**Priority**: Medium
**Estimated effort**: Small

## Description

Red team finding M-6: API cost risk is not in the risk register. Running multiple agent teams daily could cost hundreds/thousands per month in LLM API costs.

## Tasks

- [ ] Estimate API costs per team:
  - DM team: ~20 drafts/day × avg tokens → cost/day
  - Analytics: batch reports → cost/day
  - Standards team: spec drafting, cross-reference → cost/day
  - Governance team: compliance monitoring → cost/day
  - Total estimated monthly cost across 4 teams
- [ ] Define cost control mechanisms:
  - Per-team API budget (financial constraint dimension)
  - Per-agent rate limits (temporal constraint dimension)
  - Model selection by task complexity (expensive for complex, cheap for routine)
  - Local model fallback for low-stakes tasks
- [ ] Implement cost tracking (integrate into constraint envelope financial dimension):
  - Track API cost per agent per day
  - Track cost per action type
  - Alert when approaching budget limits
- [ ] Define cost optimization strategies:
  - Caching frequent queries
  - Batch processing where possible
  - Template-based generation (cheaper than open-ended)
  - Progressive model selection (start with haiku/mini, escalate to opus/gpt-4 only when needed)
- [ ] Add to risk register with mitigations

## Acceptance Criteria

- Cost estimates for 4-team operation
- Cost control mechanisms designed
- Cost tracking integrated into financial constraint dimension
- Optimization strategies documented
- Risk register updated
