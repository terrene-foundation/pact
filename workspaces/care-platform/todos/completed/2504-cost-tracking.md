# Todo 2504: Cost Tracking Integration with Real API Data

**Milestone**: M25 — LLM Backend Integration
**Priority**: High
**Effort**: Small
**Source**: Phase 3 requirement
**Dependencies**: 2501, 2502

## What

Extract real token counts from LLM API responses in both `AnthropicBackend` and `OpenAIBackend` and feed them into the existing cost tracking module (completed in M3-306). Calculate USD costs based on current model pricing tables (stored in configuration, not hardcoded). Update the cumulative spend counter in the constraint middleware after each LLM call. Financial constraints must be evaluated against actual spend, not estimated spend. If a call would cause spend to exceed the budget, it must be held or blocked according to the verification gradient before the API call is made.

## Where

- `src/care_platform/execution/backends/anthropic.py`
- `src/care_platform/execution/backends/openai.py`
- `src/care_platform/constraint/middleware.py`

## Evidence

- [ ] After each Anthropic API call, real prompt and completion token counts are recorded in the cost module
- [ ] After each OpenAI API call, real prompt and completion token counts are recorded in the cost module
- [ ] USD cost is calculated from token counts and the configured model pricing table
- [ ] Cumulative spend in the constraint middleware reflects actual LLM costs after each call
- [ ] A request that would exceed the configured financial constraint is HELD or BLOCKED before the API call is issued
- [ ] Unit tests cover cost calculation for both backends with known token counts
- [ ] Integration tests confirm cumulative spend increments correctly across multiple calls
