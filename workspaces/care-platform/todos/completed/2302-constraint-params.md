# Todo 2302: Missing Constraint Model Parameters

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: High
**Effort**: Medium
**Source**: RT5-17, RT5-20, RT5-28
**Dependencies**: 2301 (financial Optional pattern should be in place first)

## What

Add spec-defined parameters that are currently absent from the constraint models and wire them into the evaluation pipeline:

**Financial dimension** (RT5-17):

- `daily_limit: Optional[float]` — cumulative spend cap per calendar day
- `monthly_limit: Optional[float]` — cumulative spend cap per calendar month
- `vendor_limits: Optional[dict[str, float]]` — per-vendor spending caps keyed by vendor identifier

**Communication dimension** (RT5-20):

- `recipient_limits: Optional[dict[str, int]]` — maximum messages per recipient per time window
- `escalation_triggers: Optional[list[str]]` — keyword or pattern list that forces HELD for human review

**Temporal dimension** (RT5-28):

- `max_duration: Optional[float]` — maximum seconds an action may run before being considered timed out
- `deadline_behavior: Optional[str]` — what happens when deadline is exceeded: `"block"`, `"flag"`, or `"hold"`

All new parameters must follow the `Optional[T] = None` pattern established in 2301. The verification gradient engine must evaluate each new parameter when it is set; `None` means unconstrained for that dimension.

## Where

- `src/care_platform/config/schema.py` — constraint model field declarations for all three dimensions
- `src/care_platform/constraint/envelope.py` — evaluation logic for daily/monthly spend accumulators, vendor checks, recipient limits, escalation trigger matching, duration enforcement

## Evidence

- [ ] All seven new fields present in the constraint schema with correct types and `Optional` defaults
- [ ] Financial: `daily_limit` and `monthly_limit` evaluated against cumulative spend tracking
- [ ] Financial: `vendor_limits` enforced when a vendor identifier is provided on the action
- [ ] Communication: `recipient_limits` enforced per recipient within the configured time window
- [ ] Communication: `escalation_triggers` cause HELD result when any pattern matches action content
- [ ] Temporal: `max_duration` used in duration checks; `deadline_behavior` routes the outcome correctly
- [ ] Gradient engine produces correct BLOCKED/HELD/FLAGGED/AUTO_APPROVED for each new parameter
- [ ] Unit tests cover each new parameter in isolation and in combination
- [ ] Existing constraint tests continue to pass
