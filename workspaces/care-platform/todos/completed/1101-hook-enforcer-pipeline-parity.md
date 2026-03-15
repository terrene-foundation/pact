# 1101: HookEnforcer Pipeline Parity — Expiry Check + Kwargs Forwarding

**Priority**: Critical
**Effort**: Small
**Source**: RT3 R3-01, R3-10
**Dependencies**: None

## Problem

The HookEnforcer produces real ALLOW/BLOCK/HOLD verdicts that COC hooks act on, but has two gaps versus the middleware:

1. **Missing envelope expiry check**: The middleware checks `self.envelope.is_expired` and blocks immediately. The HookEnforcer skips this check, meaning an expired envelope still evaluates constraints and may return ALLOW.

2. **kwargs not forwarded to envelope evaluation**: `enforce()` accepts `**kwargs` but discards them. The `evaluate_action` call only passes `action` and `agent_id`, omitting `spend_amount`, `cumulative_spend`, `current_action_count`, `is_external`, and `data_paths`. All constraint checks use default values (zero spend, zero action count, etc.).

## Attack Scenario

A COC hook asks the HookEnforcer if an agent can spend $50,000. The HookEnforcer doesn't forward the spend amount, evaluates with $0, and returns ALLOW. The middleware would have returned BLOCKED.

## Implementation

### File: `care_platform/execution/hook_enforcer.py`

1. Add envelope expiry check in `enforce()` after the PSEUDO_AGENT check and before the fail-safe check:
   ```python
   # RT3-01: Check envelope expiry (pipeline parity with middleware)
   if self._envelope.is_expired:
       return HookVerdict(
           verdict="BLOCK",
           reason="Constraint envelope has expired",
           verification_level=VerificationLevel.BLOCKED,
       )
   ```

2. Forward kwargs to `evaluate_action`:
   ```python
   # RT3-10: Forward kwargs to envelope evaluation (spend_amount, etc.)
   envelope_evaluation = self._envelope.evaluate_action(
       action=action, agent_id=agent_id, **kwargs
   )
   ```

3. Update `**kwargs` docstring from "reserved for future use" to "Forwarded to ConstraintEnvelope.evaluate_action".

## Acceptance Criteria

- [ ] HookEnforcer returns BLOCK when envelope is expired
- [ ] HookEnforcer forwards spend_amount, current_action_count, etc. to envelope evaluation
- [ ] Tests verify both behaviors
- [ ] All existing tests still pass
